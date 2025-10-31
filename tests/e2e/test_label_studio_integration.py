"""End-to-end test for Label Studio integration.

This test verifies the complete data flow:
1. Submit batch job with candidate data
2. Wait for vLLM processing
3. Verify auto-import to Label Studio
4. Test gold-star functionality
5. Export training dataset

Requires:
- Batch API server running on localhost:4080
- Curation API server running on localhost:8001
- Label Studio running on localhost:8080
"""

import json
import time
from pathlib import Path

import pytest
import requests

# Test configuration
BATCH_API_URL = "http://localhost:4080"
CURATION_API_URL = "http://localhost:8001"
TIMEOUT = 300  # 5 minutes max wait for batch completion


@pytest.mark.e2e
@pytest.mark.slow
class TestLabelStudioIntegration:
    """End-to-end tests for batch → Label Studio integration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Verify all services are running."""
        # Check batch API
        try:
            response = requests.get(f"{BATCH_API_URL}/health", timeout=5)
            assert response.status_code == 200, "Batch API not healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("Batch API not running on localhost:4080")

        # Check curation API
        try:
            response = requests.get(f"{CURATION_API_URL}/health", timeout=5)
            assert response.status_code == 200, "Curation API not healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("Curation API not running on localhost:8001")

    def test_batch_to_label_studio_flow(self, tmp_path: Path):
        """Test complete flow: batch job → vLLM → Label Studio."""

        # Step 1: Create candidate evaluation batch input
        input_file = tmp_path / "candidates.jsonl"

        # Sample candidate data (realistic format)
        candidates = [
            {
                "custom_id": "candidate-001",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "google/gemma-3-4b-it",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert technical recruiter evaluating software engineering candidates."
                        },
                        {
                            "role": "user",
                            "content": json.dumps({
                                "name": "Alice Johnson",
                                "current_role": "Senior Software Engineer at Google",
                                "location": "San Francisco, CA",
                                "education": [
                                    {"school": "MIT", "degree": "BS Computer Science", "year": 2015}
                                ],
                                "work_history": [
                                    {"company": "Google", "title": "Senior SWE", "years": "2018-2024"},
                                    {"company": "Facebook", "title": "SWE", "years": "2015-2018"}
                                ]
                            })
                        }
                    ],
                    "max_tokens": 500
                }
            },
            {
                "custom_id": "candidate-002",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "google/gemma-3-4b-it",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert technical recruiter evaluating software engineering candidates."
                        },
                        {
                            "role": "user",
                            "content": json.dumps({
                                "name": "Bob Smith",
                                "current_role": "Junior Developer at Startup",
                                "location": "Austin, TX",
                                "education": [
                                    {"school": "State University", "degree": "BS IT", "year": 2020}
                                ],
                                "work_history": [
                                    {"company": "Startup Inc", "title": "Junior Dev", "years": "2020-2024"}
                                ]
                            })
                        }
                    ],
                    "max_tokens": 500
                }
            }
        ]

        with open(input_file, 'w') as f:
            for candidate in candidates:
                f.write(json.dumps(candidate) + '\n')

        # Step 2: Upload file to batch API
        with open(input_file, 'rb') as f:
            files = {'file': ('candidates.jsonl', f, 'application/jsonl')}
            data = {'purpose': 'batch'}
            response = requests.post(
                f"{BATCH_API_URL}/v1/files",
                files=files,
                data=data,
                timeout=30
            )

        assert response.status_code == 200, f"File upload failed: {response.text}"
        file_id = response.json()['id']

        # Step 3: Create batch job with metadata
        batch_request = {
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
            "metadata": {
                "conquest_type": "candidate_evaluation",
                "source": "e2e_test"
            }
        }

        response = requests.post(
            f"{BATCH_API_URL}/v1/batches",
            json=batch_request,
            timeout=30
        )

        assert response.status_code == 200, f"Batch creation failed: {response.text}"
        batch_id = response.json()['id']

        # Step 4: Wait for batch completion
        start_time = time.time()
        final_status = None

        while time.time() - start_time < TIMEOUT:
            response = requests.get(
                f"{BATCH_API_URL}/v1/batches/{batch_id}",
                timeout=30
            )
            assert response.status_code == 200

            batch_status = response.json()
            status = batch_status['status']

            if status == 'completed':
                final_status = batch_status
                break
            elif status == 'failed':
                pytest.fail(f"Batch failed: {batch_status.get('errors')}")
            elif status == 'cancelled':
                pytest.fail("Batch was cancelled")

            time.sleep(2)

        assert final_status is not None, f"Batch did not complete within {TIMEOUT}s"
        assert final_status['request_counts']['completed'] == 2

        # Step 5: Verify tasks were auto-imported to Label Studio
        # Wait a bit for auto-import to complete
        time.sleep(3)

        response = requests.get(
            f"{CURATION_API_URL}/api/tasks",
            params={
                "conquest_type": "candidate_evaluation",
                "page": 1,
                "page_size": 100
            },
            timeout=30
        )

        assert response.status_code == 200, f"Failed to get tasks: {response.text}"
        tasks_data = response.json()

        # Should have at least our 2 candidates
        assert len(tasks_data['tasks']) >= 2, f"Expected at least 2 tasks, got {len(tasks_data['tasks'])}"

        # Verify task structure
        our_tasks = [t for t in tasks_data['tasks'] if t.get('data', {}).get('batch_id') == batch_id]
        assert len(our_tasks) == 2, f"Expected 2 tasks from our batch, got {len(our_tasks)}"

        # Verify candidate data is present
        task_names = [t['data'].get('candidate_name', '') for t in our_tasks]
        assert 'Alice Johnson' in task_names or 'Bob Smith' in task_names, \
            f"Candidate names not found in tasks: {task_names}"

        # Step 6: Test gold-star functionality
        task_id = our_tasks[0]['id']

        # Mark as gold-star
        response = requests.post(
            f"{CURATION_API_URL}/api/tasks/{task_id}/gold-star",
            json={"is_gold_star": True},
            timeout=30
        )

        assert response.status_code == 200, f"Failed to mark gold-star: {response.text}"
        gold_star_data = response.json()
        assert gold_star_data['gold_star'] is True
        assert gold_star_data['task_id'] == task_id

        # Verify gold-star was set
        response = requests.get(
            f"{CURATION_API_URL}/api/tasks/{task_id}",
            timeout=30
        )
        assert response.status_code == 200
        task = response.json()
        assert task.get('meta', {}).get('gold_star') is True

        # Step 7: Test bulk gold-star
        task_ids = [t['id'] for t in our_tasks]
        response = requests.post(
            f"{CURATION_API_URL}/api/tasks/bulk-gold-star",
            json={"task_ids": task_ids, "is_gold_star": True},
            timeout=30
        )

        assert response.status_code == 200
        bulk_result = response.json()
        assert bulk_result['updated_count'] == 2

        # Step 8: Export gold-star dataset
        response = requests.post(
            f"{CURATION_API_URL}/api/export",
            json={
                "conquest_type": "candidate_evaluation",
                "format": "icl",
                "min_agreement": 0.0,  # Include manual gold-stars
                "min_annotations": 0
            },
            timeout=30
        )

        assert response.status_code == 200
        export_data = response.json()

        # Should have our gold-star tasks
        assert export_data['count'] >= 2, f"Expected at least 2 gold-star tasks, got {export_data['count']}"
        assert len(export_data['examples']) >= 2

    def test_large_batch_scenario(self, tmp_path: Path):
        """Test handling of larger batch (simulating 170K scenario with smaller sample)."""

        # Create 100 candidate requests (scaled down from 170K for testing)
        input_file = tmp_path / "large_batch.jsonl"

        with open(input_file, 'w') as f:
            for i in range(100):
                candidate = {
                    "custom_id": f"candidate-{i:04d}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "google/gemma-3-4b-it",
                        "messages": [
                            {"role": "system", "content": "Evaluate this candidate."},
                            {"role": "user", "content": f"Candidate {i}: Software Engineer"}
                        ],
                        "max_tokens": 100
                    }
                }
                f.write(json.dumps(candidate) + '\n')

        # Upload and create batch
        with open(input_file, 'rb') as f:
            response = requests.post(
                f"{BATCH_API_URL}/v1/files",
                files={'file': ('large_batch.jsonl', f, 'application/jsonl')},
                data={'purpose': 'batch'},
                timeout=30
            )

        assert response.status_code == 200
        file_id = response.json()['id']

        response = requests.post(
            f"{BATCH_API_URL}/v1/batches",
            json={
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {"conquest_type": "candidate_evaluation"}
            },
            timeout=30
        )

        assert response.status_code == 200
        batch_id = response.json()['id']

        # Note: We don't wait for completion in this test (would take too long)
        # Just verify the batch was created successfully
        assert batch_id.startswith('batch_')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

