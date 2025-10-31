"""End-to-end test for complete batch processing workflow.

This test verifies the entire user journey:
1. Upload input file
2. Create batch job
3. Wait for processing
4. Download results
5. Verify output format

Requires: API server running on localhost:4080
"""

import json
import time
from pathlib import Path

import pytest
import requests

# Test configuration
API_BASE_URL = "http://localhost:4080"
TIMEOUT = 300  # 5 minutes max wait for batch completion


@pytest.mark.e2e
@pytest.mark.slow
class TestBatchWorkflow:
    """End-to-end tests for batch processing workflow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Verify API server is running."""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            assert response.status_code == 200, "API server not healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running on localhost:4080")

    def test_complete_batch_workflow(self, tmp_path: Path):
        """Test complete batch processing workflow from upload to results."""

        # Step 1: Create input file
        input_file = tmp_path / "batch_input.jsonl"
        requests_data = [
            {
                "custom_id": "request-1",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "google/gemma-3-4b-it",
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"}
                    ],
                    "max_tokens": 50
                }
            },
            {
                "custom_id": "request-2",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "google/gemma-3-4b-it",
                    "messages": [
                        {"role": "user", "content": "What is the capital of France?"}
                    ],
                    "max_tokens": 50
                }
            }
        ]

        with open(input_file, 'w') as f:
            for req in requests_data:
                f.write(json.dumps(req) + '\n')

        # Step 2: Upload file
        with open(input_file, 'rb') as f:
            files = {'file': ('batch_input.jsonl', f, 'application/jsonl')}
            data = {'purpose': 'batch'}
            response = requests.post(
                f"{API_BASE_URL}/v1/files",
                files=files,
                data=data,
                timeout=30
            )

        assert response.status_code == 200, f"File upload failed: {response.text}"
        file_data = response.json()
        file_id = file_data['id']
        assert file_id.startswith('file-'), f"Invalid file ID: {file_id}"

        # Step 3: Create batch job
        batch_request = {
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        }

        response = requests.post(
            f"{API_BASE_URL}/v1/batches",
            json=batch_request,
            timeout=30
        )

        assert response.status_code == 200, f"Batch creation failed: {response.text}"
        batch_data = response.json()
        batch_id = batch_data['id']
        assert batch_id.startswith('batch_'), f"Invalid batch ID: {batch_id}"
        assert batch_data['status'] in ['validating', 'in_progress', 'completed']

        # Step 4: Wait for batch completion
        start_time = time.time()
        final_status = None

        while time.time() - start_time < TIMEOUT:
            response = requests.get(
                f"{API_BASE_URL}/v1/batches/{batch_id}",
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

            # Wait before polling again
            time.sleep(2)

        assert final_status is not None, f"Batch did not complete within {TIMEOUT}s"
        assert final_status['request_counts']['completed'] == 2
        assert final_status['request_counts']['failed'] == 0

        # Step 5: Download results
        output_file_id = final_status['output_file_id']
        assert output_file_id is not None, "No output file ID"

        response = requests.get(
            f"{API_BASE_URL}/v1/files/{output_file_id}/content",
            timeout=30
        )
        assert response.status_code == 200

        # Step 6: Verify results
        results = []
        for line in response.text.strip().split('\n'):
            if line:
                results.append(json.loads(line))

        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        # Verify result structure
        for result in results:
            assert 'id' in result
            assert 'custom_id' in result
            assert 'response' in result
            assert result['error'] is None

            response_body = result['response']['body']
            assert response_body['object'] == 'chat.completion'
            assert 'choices' in response_body
            assert len(response_body['choices']) > 0
            assert 'message' in response_body['choices'][0]
            assert 'content' in response_body['choices'][0]['message']

        # Verify custom IDs match
        custom_ids = {r['custom_id'] for r in results}
        assert custom_ids == {'request-1', 'request-2'}

    def test_batch_with_invalid_model(self, tmp_path: Path):
        """Test batch job with invalid model name."""

        # Create input file with invalid model
        input_file = tmp_path / "invalid_model.jsonl"
        request_data = {
            "custom_id": "request-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "invalid-model-name",
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10
            }
        }

        with open(input_file, 'w') as f:
            f.write(json.dumps(request_data) + '\n')

        # Upload file
        with open(input_file, 'rb') as f:
            files = {'file': ('invalid_model.jsonl', f, 'application/jsonl')}
            data = {'purpose': 'batch'}
            response = requests.post(
                f"{API_BASE_URL}/v1/files",
                files=files,
                data=data,
                timeout=30
            )

        assert response.status_code == 200
        file_id = response.json()['id']

        # Create batch job
        batch_request = {
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        }

        response = requests.post(
            f"{API_BASE_URL}/v1/batches",
            json=batch_request,
            timeout=30
        )

        # Should still create the batch (validation happens during processing)
        assert response.status_code == 200
        batch_id = response.json()['id']

        # Wait for batch to process (with retries)
        max_retries = 10
        for _ in range(max_retries):
            time.sleep(2)
            response = requests.get(
                f"{API_BASE_URL}/v1/batches/{batch_id}",
                timeout=30
            )
            assert response.status_code == 200
            batch_status = response.json()
            if batch_status['status'] in ['failed', 'completed']:
                break

        # Batch should either fail or have failed requests
        assert batch_status['status'] in ['failed', 'completed']

        if batch_status['status'] == 'completed':
            # Check for failed requests
            assert batch_status['request_counts']['failed'] > 0

    def test_list_batches(self):
        """Test listing batch jobs."""
        response = requests.get(
            f"{API_BASE_URL}/v1/batches",
            params={'limit': 10},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        assert 'object' in data
        assert data['object'] == 'list'
        assert 'data' in data
        assert isinstance(data['data'], list)

        # Verify batch structure
        for batch in data['data']:
            assert 'id' in batch
            assert 'status' in batch
            assert 'created_at' in batch

    def test_list_files(self):
        """Test listing uploaded files."""
        response = requests.get(
            f"{API_BASE_URL}/v1/files",
            params={'limit': 10},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        assert 'object' in data
        assert data['object'] == 'list'
        assert 'data' in data
        assert isinstance(data['data'], list)

        # Verify file structure
        for file in data['data']:
            assert 'id' in file
            assert 'purpose' in file
            assert 'filename' in file
            assert 'bytes' in file

    def test_models_endpoint(self):
        """Test /v1/models endpoint returns correct format."""
        response = requests.get(
            f"{API_BASE_URL}/v1/models",
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        # Verify OpenAI-compatible format
        assert 'object' in data, "Missing 'object' field"
        assert data['object'] == 'list', f"Expected object='list', got {data['object']}"
        assert 'data' in data, "Missing 'data' field"
        assert isinstance(data['data'], list), "'data' should be a list"

        # Verify model structure
        for model in data['data']:
            assert 'id' in model
            assert 'object' in model
            assert model['object'] == 'model'
            assert 'created' in model
            assert 'owned_by' in model

