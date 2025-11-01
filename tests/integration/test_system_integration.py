"""
System Integration Tests - End-to-End Verification

These tests verify the ENTIRE system works as documented:
1. API server is running and healthy
2. Worker is running and processing jobs
3. PostgreSQL is accessible
4. Label Studio is configured and accessible
5. Batch jobs can be submitted and completed
6. Results are saved correctly
7. Label Studio integration works (if enabled)
8. Models are loaded correctly
9. GPU is available and working

Run with: pytest tests/integration/test_system_integration.py -v -s

Requirements:
- API server running (port 4080)
- Worker running
- PostgreSQL running (port 4332)
- Label Studio running (port 4115) - optional
"""

import os
import json
import time
import pytest
import requests
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Test configuration
API_BASE = "http://localhost:4080"
LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://localhost:4115")
LABEL_STUDIO_TOKEN = os.getenv("LABEL_STUDIO_TOKEN", "")

# Load .env file to get database URL
from dotenv import load_dotenv
load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://vllm_user:vllm_password@localhost:4332/vllm_batch")


class TestSystemHealth:
    """Verify all system components are running and healthy."""
    
    def test_api_server_running(self):
        """Test API server is running on port 4080."""
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        print(f"✅ API Server: {data['status']} (v{data['version']})")
    
    def test_api_server_correct_port(self):
        """Verify API server is on port 4080, not 8000."""
        # Should work on 4080
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200
        
        # Should NOT work on 8000 (old port)
        try:
            requests.get("http://localhost:8000/health", timeout=2)
            pytest.fail("API server is running on old port 8000! Should be 4080")
        except requests.exceptions.ConnectionError:
            print("✅ API server NOT on old port 8000 (correct)")
    
    def test_postgresql_accessible(self):
        """Test PostgreSQL is accessible and has correct schema."""
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # Test connection
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
            
            # Check required tables exist
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]

            required_tables = ['batch_jobs', 'files', 'model_registry', 'worker_heartbeat',
                             'datasets', 'benchmarks', 'annotations']
            for table in required_tables:
                assert table in tables, f"Missing table: {table}"

            print(f"✅ PostgreSQL: Connected, {len(tables)} tables found")
    
    def test_worker_heartbeat(self):
        """Test worker is running and sending heartbeats."""
        engine = create_engine(DB_URL)

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT worker_pid, last_seen, status
                FROM worker_heartbeat
                ORDER BY last_seen DESC
                LIMIT 1
            """))
            row = result.fetchone()

            if row is None:
                pytest.fail("No worker heartbeat found! Is worker running?")

            worker_pid, last_seen, status = row

            # Check heartbeat is recent (within last 60 seconds)
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            # Make last_seen timezone-aware if it isn't
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
            heartbeat_age = (now - last_seen).total_seconds()

            assert heartbeat_age < 60, f"Worker heartbeat is {heartbeat_age}s old (should be <60s)"
            assert status in ["idle", "processing", "loading_model"], f"Worker status is '{status}'"

            print(f"✅ Worker: PID {worker_pid} ({status}, heartbeat {heartbeat_age:.1f}s ago)")
    
    def test_label_studio_accessible(self):
        """Test Label Studio is accessible (if configured)."""
        if not LABEL_STUDIO_TOKEN:
            pytest.skip("LABEL_STUDIO_TOKEN not configured")
        
        # Test health endpoint
        response = requests.get(f"{LABEL_STUDIO_URL}/health/", timeout=5)
        assert response.status_code == 200
        assert response.json()["status"] == "UP"
        
        # Test API with token
        headers = {"Authorization": f"Token {LABEL_STUDIO_TOKEN}"}
        response = requests.get(f"{LABEL_STUDIO_URL}/api/projects", headers=headers, timeout=5)
        
        if response.status_code == 401:
            pytest.fail("Label Studio token is invalid or expired!")
        
        assert response.status_code == 200
        projects = response.json()
        
        print(f"✅ Label Studio: Accessible, {len(projects)} projects")
    
    def test_label_studio_correct_port(self):
        """Verify Label Studio is on port 4115, not 4015."""
        if not LABEL_STUDIO_TOKEN:
            pytest.skip("LABEL_STUDIO_TOKEN not configured")
        
        # Should work on 4115
        response = requests.get(f"{LABEL_STUDIO_URL}/health/", timeout=5)
        assert response.status_code == 200
        
        # Should NOT work on 4015 (old port)
        try:
            requests.get("http://localhost:4015/health/", timeout=2)
            pytest.fail("Label Studio is running on old port 4015! Should be 4115")
        except requests.exceptions.ConnectionError:
            print("✅ Label Studio NOT on old port 4015 (correct)")
    
    def test_gpu_available(self):
        """Test GPU is available and has memory."""
        response = requests.get(f"{API_BASE}/health", timeout=5)
        data = response.json()
        
        # Check GPU info in health response
        if "gpu_memory_used_gb" in data and "gpu_memory_total_gb" in data:
            used = data["gpu_memory_used_gb"]
            total = data["gpu_memory_total_gb"]
            
            assert total > 0, "GPU total memory is 0!"
            assert used >= 0, "GPU used memory is negative!"
            assert used <= total, f"GPU used ({used}) > total ({total})"
            
            utilization = (used / total) * 100
            print(f"✅ GPU: {used:.1f} GB / {total:.1f} GB ({utilization:.1f}%)")
        else:
            print("⚠️  GPU info not in health response")


class TestModelRegistry:
    """Verify model registry is populated and correct."""
    
    def test_models_exist(self):
        """Test model registry has models."""
        response = requests.get(f"{API_BASE}/v1/models", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        models = data["data"]
        
        assert len(models) > 0, "No models in registry!"
        
        print(f"✅ Model Registry: {len(models)} models")
        for model in models:
            print(f"   - {model['id']}")
    
    def test_models_are_correct(self):
        """Test models match what we expect (not old/wrong models)."""
        response = requests.get(f"{API_BASE}/v1/models", timeout=5)
        models = response.json()["data"]
        
        model_ids = [m["id"] for m in models]
        
        # Check for expected models
        expected_models = [
            "google/gemma-3-4b-it",
            "meta-llama/Llama-3.2-3B-Instruct",
            "Qwen/Qwen3-4B-Instruct-2507"
        ]
        
        found_expected = [m for m in expected_models if m in model_ids]
        
        if not found_expected:
            print(f"⚠️  None of the expected models found: {expected_models}")
            print(f"   Found: {model_ids}")
        else:
            print(f"✅ Found {len(found_expected)} expected models")
        
        # Check for wrong/old models that shouldn't be there
        wrong_models = [
            "meta-llama/Llama-3.1-8B-Instruct",  # Old model from examples
        ]
        
        found_wrong = [m for m in wrong_models if m in model_ids]
        
        if found_wrong:
            pytest.fail(f"Found wrong/old models in registry: {found_wrong}")


class TestBatchProcessing:
    """Test end-to-end batch processing."""
    
    @pytest.fixture
    def test_batch_file(self, tmp_path):
        """Create a minimal test batch file (3 requests)."""
        batch_file = tmp_path / "test_batch.jsonl"
        
        requests_data = []
        for i in range(3):
            requests_data.append({
                "custom_id": f"test-req-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "google/gemma-3-4b-it",
                    "messages": [
                        {"role": "user", "content": f"Say 'Test {i}' and nothing else."}
                    ],
                    "max_tokens": 10
                }
            })
        
        with open(batch_file, "w") as f:
            for req in requests_data:
                f.write(json.dumps(req) + "\n")
        
        return batch_file
    
    def test_submit_batch_job(self, test_batch_file):
        """Test submitting a batch job."""
        # Upload file
        with open(test_batch_file, "rb") as f:
            response = requests.post(
                f"{API_BASE}/v1/files",
                files={"file": ("test.jsonl", f, "application/jsonl")},
                data={"purpose": "batch"}
            )
        
        assert response.status_code == 200
        file_data = response.json()
        file_id = file_data["id"]
        
        print(f"✅ Uploaded file: {file_id}")
        
        # Create batch
        response = requests.post(
            f"{API_BASE}/v1/batches",
            json={
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h"
            }
        )
        
        assert response.status_code == 200
        batch_data = response.json()
        batch_id = batch_data["id"]
        
        assert batch_data["status"] in ["validating", "in_progress", "completed"]
        
        print(f"✅ Created batch: {batch_id} (status: {batch_data['status']})")
        
        return batch_id
    
    def test_batch_job_completes(self, test_batch_file):
        """Test batch job completes successfully (may take a few minutes)."""
        # Submit batch
        batch_id = self.test_submit_batch_job(test_batch_file)
        
        # Poll for completion (max 5 minutes)
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = requests.get(f"{API_BASE}/v1/batches/{batch_id}")
            assert response.status_code == 200
            
            batch_data = response.json()
            status = batch_data["status"]
            
            print(f"   Status: {status} ({batch_data.get('request_counts', {}).get('completed', 0)}/3 completed)")
            
            if status == "completed":
                print(f"✅ Batch completed in {time.time() - start_time:.1f}s")
                
                # Verify output file exists
                assert "output_file_id" in batch_data
                output_file_id = batch_data["output_file_id"]
                
                # Download results
                response = requests.get(f"{API_BASE}/v1/files/{output_file_id}/content")
                assert response.status_code == 200
                
                results = response.text.strip().split("\n")
                assert len(results) == 3, f"Expected 3 results, got {len(results)}"
                
                print(f"✅ Results file has {len(results)} responses")
                return
            
            elif status == "failed":
                pytest.fail(f"Batch job failed: {batch_data.get('errors')}")
            
            time.sleep(10)
        
        pytest.fail(f"Batch job did not complete within {max_wait}s")


class TestLabelStudioIntegration:
    """Test Label Studio integration (if enabled)."""
    
    def test_auto_import_configuration(self):
        """Test auto-import is configured correctly."""
        auto_import = os.getenv("AUTO_IMPORT_TO_CURATION", "false").lower() == "true"
        curation_url = os.getenv("CURATION_API_URL", "")
        
        if auto_import:
            # If auto-import is enabled, curation URL should be Label Studio
            assert curation_url == LABEL_STUDIO_URL, \
                f"AUTO_IMPORT_TO_CURATION=true but CURATION_API_URL={curation_url} (should be {LABEL_STUDIO_URL})"
            
            print(f"✅ Auto-import enabled, pointing to Label Studio")
        else:
            print(f"⚠️  Auto-import disabled")
    
    def test_label_studio_project_exists(self):
        """Test Label Studio project exists."""
        if not LABEL_STUDIO_TOKEN:
            pytest.skip("LABEL_STUDIO_TOKEN not configured")
        
        project_id = os.getenv("LABEL_STUDIO_PROJECT_ID", "1")
        
        headers = {"Authorization": f"Token {LABEL_STUDIO_TOKEN}"}
        response = requests.get(
            f"{LABEL_STUDIO_URL}/api/projects/{project_id}",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 404:
            pytest.fail(f"Label Studio project {project_id} does not exist!")
        
        assert response.status_code == 200
        project = response.json()
        
        print(f"✅ Label Studio project {project_id}: '{project.get('title', 'Untitled')}'")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 SYSTEM INTEGRATION TESTS")
    print("=" * 80)
    print()
    print("These tests verify the ENTIRE system is configured correctly:")
    print("- API server (port 4080)")
    print("- Worker (heartbeat)")
    print("- PostgreSQL (schema)")
    print("- Label Studio (port 4115, token)")
    print("- Model registry")
    print("- Batch processing")
    print("- GPU availability")
    print()
    
    # Run tests
    pytest.main([__file__, "-v", "-s"])

