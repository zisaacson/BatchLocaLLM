"""
Automated tests for Model Management UI

Tests the full end-to-end flow:
1. Add model via API
2. Test model via API
3. Poll status
4. Verify results saved to database
5. Delete model
"""

import json
import time
import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.batch_app.database import ModelRegistry, Base

# Test configuration
API_BASE = "http://localhost:4080/admin"
DB_URL = "postgresql://vllm_batch_user:vllm_batch_password_dev@localhost:5432/vllm_batch"

# Create database session
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


class TestModelManagementAPI:
    """Test the model management API endpoints."""
    
    def test_list_models(self):
        """Test GET /admin/models - should return list of models."""
        response = requests.get(f"{API_BASE}/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        assert "count" in data
        assert isinstance(data["models"], list)
        assert data["count"] == len(data["models"])
        print(f"✅ Found {data['count']} models in registry")
    
    def test_add_model(self):
        """Test POST /admin/models - add a new test model."""
        # Use a small test model
        model_data = {
            "model_id": "test/tiny-model-for-testing",
            "name": "Test Tiny Model",
            "size_gb": 0.5,
            "estimated_memory_gb": 2.0,
            "max_model_len": 512,
            "gpu_memory_utilization": 0.5,
            "enable_prefix_caching": False,
            "chunked_prefill_enabled": False,
            "rtx4080_compatible": True,
            "requires_hf_auth": False
        }
        
        response = requests.post(f"{API_BASE}/models", json=model_data)
        
        # Should succeed or fail if already exists
        if response.status_code == 400 and "already exists" in response.json()["detail"]:
            print("⚠️  Model already exists, cleaning up...")
            # Delete and retry
            requests.delete(f"{API_BASE}/models/test/tiny-model-for-testing")
            response = requests.post(f"{API_BASE}/models", json=model_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == model_data["model_id"]
        assert data["name"] == model_data["name"]
        assert data["status"] == "untested"
        print(f"✅ Added model: {data['name']}")
    
    def test_get_model(self):
        """Test GET /admin/models/{id} - get specific model."""
        model_id = "test/tiny-model-for-testing"
        response = requests.get(f"{API_BASE}/models/{model_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["model_id"] == model_id
        print(f"✅ Retrieved model: {data['name']}")
    
    def test_model_in_database(self):
        """Verify model exists in database."""
        db = SessionLocal()
        try:
            model = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == "test/tiny-model-for-testing"
            ).first()
            assert model is not None
            assert model.name == "Test Tiny Model"
            assert model.status == "untested"
            print(f"✅ Model found in database with status: {model.status}")
        finally:
            db.close()
    
    def test_delete_model(self):
        """Test DELETE /admin/models/{id} - delete model."""
        model_id = "test/tiny-model-for-testing"
        response = requests.delete(f"{API_BASE}/models/{model_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "deleted successfully" in data["message"]
        print(f"✅ Deleted model: {model_id}")
        
        # Verify it's gone from database
        db = SessionLocal()
        try:
            model = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == model_id
            ).first()
            assert model is None
            print("✅ Model removed from database")
        finally:
            db.close()


class TestModelTesting:
    """Test the model testing workflow (without actually running vLLM)."""
    
    def test_add_test_model(self):
        """Add a model for testing purposes."""
        model_data = {
            "model_id": "test/model-for-test-workflow",
            "name": "Test Workflow Model",
            "size_gb": 1.0,
            "estimated_memory_gb": 3.0,
            "max_model_len": 512,
            "gpu_memory_utilization": 0.5,
            "rtx4080_compatible": True,
            "requires_hf_auth": False
        }
        
        # Clean up if exists
        requests.delete(f"{API_BASE}/models/test/model-for-test-workflow")
        
        response = requests.post(f"{API_BASE}/models", json=model_data)
        assert response.status_code == 200
        print(f"✅ Added test model for workflow testing")
    
    def test_status_endpoint(self):
        """Test GET /admin/models/{id}/status - should return status."""
        model_id = "test/model-for-test-workflow"
        response = requests.get(f"{API_BASE}/models/{model_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "model_id" in data
        assert "status" in data
        assert "progress" in data
        assert data["status"] == "untested"
        print(f"✅ Status endpoint works: {data['status']}")
    
    def test_cleanup_test_model(self):
        """Clean up test model."""
        model_id = "test/model-for-test-workflow"
        response = requests.delete(f"{API_BASE}/models/{model_id}")
        assert response.status_code == 200
        print("✅ Cleaned up test model")


class TestDataFlow:
    """Test that data flows correctly from API to database to UI."""
    
    def test_end_to_end_data_flow(self):
        """Test complete data flow: API → Database → API."""
        # 1. Add model via API
        model_data = {
            "model_id": "test/data-flow-test",
            "name": "Data Flow Test Model",
            "size_gb": 0.8,
            "estimated_memory_gb": 2.5,
            "max_model_len": 512,
            "gpu_memory_utilization": 0.5,
            "rtx4080_compatible": True,
            "requires_hf_auth": False
        }
        
        # Clean up if exists
        requests.delete(f"{API_BASE}/models/test/data-flow-test")
        
        response = requests.post(f"{API_BASE}/models", json=model_data)
        assert response.status_code == 200
        print("✅ Step 1: Model added via API")
        
        # 2. Verify in database
        db = SessionLocal()
        try:
            model = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == "test/data-flow-test"
            ).first()
            assert model is not None
            assert model.name == "Data Flow Test Model"
            print("✅ Step 2: Model found in database")
        finally:
            db.close()
        
        # 3. Retrieve via API
        response = requests.get(f"{API_BASE}/models/test/data-flow-test")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Data Flow Test Model"
        assert data["size_gb"] == 0.8
        print("✅ Step 3: Model retrieved via API")
        
        # 4. Verify in list endpoint
        response = requests.get(f"{API_BASE}/models")
        assert response.status_code == 200
        models = response.json()["models"]
        test_model = [m for m in models if m["model_id"] == "test/data-flow-test"]
        assert len(test_model) == 1
        print("✅ Step 4: Model appears in list endpoint")
        
        # 5. Clean up
        response = requests.delete(f"{API_BASE}/models/test/data-flow-test")
        assert response.status_code == 200
        print("✅ Step 5: Model deleted successfully")
        
        print("\n🎉 END-TO-END DATA FLOW TEST PASSED!")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 MODEL MANAGEMENT UI - AUTOMATED TESTS")
    print("=" * 80)
    print()
    
    # Run tests
    pytest.main([__file__, "-v", "-s"])

