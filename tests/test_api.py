"""
Tests for API endpoints

Run with: pytest tests/test_api.py
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import BatchJob, BatchStatus, FileObject, RequestCounts


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def mock_storage():
    """Mock storage manager"""
    with patch("src.main.storage") as mock:
        yield mock


@pytest.fixture
def mock_batch_processor():
    """Mock batch processor"""
    with patch("src.main.batch_processor") as mock:
        mock.llm = MagicMock()  # Simulate loaded model
        mock.processing_jobs = set()
        yield mock


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_check(self, client, mock_batch_processor):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "model_loaded" in data

    def test_readiness_check(self, client, mock_batch_processor):
        """Test /readiness endpoint"""
        response = client.get("/readiness")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_liveness_check(self, client):
        """Test /liveness endpoint"""
        response = client.get("/liveness")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


class TestFileEndpoints:
    """Test file upload/download endpoints"""

    def test_upload_file(self, client, mock_storage):
        """Test file upload"""
        # Mock storage.save_file
        mock_storage.save_file = AsyncMock(
            return_value=FileObject(
                id="file-123",
                filename="test.jsonl",
                bytes=100,
                created_at=1234567890,
                purpose="batch",
            )
        )

        # Upload file
        files = {"file": ("test.jsonl", b"test content", "application/jsonl")}
        data = {"purpose": "batch"}
        response = client.post("/v1/files", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == "file-123"
        assert result["filename"] == "test.jsonl"
        assert result["purpose"] == "batch"

    def test_upload_file_invalid_purpose(self, client):
        """Test file upload with invalid purpose"""
        files = {"file": ("test.jsonl", b"test content", "application/jsonl")}
        data = {"purpose": "invalid"}
        response = client.post("/v1/files", files=files, data=data)

        assert response.status_code == 400
        assert "Invalid purpose" in response.json()["error"]["message"]

    def test_get_file_content(self, client, mock_storage):
        """Test file content download"""
        # Mock storage.read_file
        mock_storage.read_file = AsyncMock(return_value=b"test content")

        response = client.get("/v1/files/file-123/content")

        assert response.status_code == 200
        assert response.text == "test content"

    def test_get_file_content_not_found(self, client, mock_storage):
        """Test file content download for non-existent file"""
        # Mock storage.read_file
        mock_storage.read_file = AsyncMock(return_value=None)

        response = client.get("/v1/files/file-999/content")

        assert response.status_code == 404


class TestBatchEndpoints:
    """Test batch job endpoints"""

    def test_create_batch(self, client, mock_storage, mock_batch_processor):
        """Test batch creation"""
        # Mock storage methods
        mock_storage.get_file = AsyncMock(
            return_value=FileObject(
                id="file-123",
                filename="input.jsonl",
                bytes=100,
                created_at=1234567890,
                purpose="batch",
            )
        )

        mock_storage.create_batch_job = AsyncMock(
            return_value=BatchJob(
                id="batch-123",
                status=BatchStatus.VALIDATING,
                input_file_id="file-123",
                created_at=1234567890,
                request_counts=RequestCounts(),
            )
        )

        # Create batch
        request_data = {
            "input_file_id": "file-123",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        }
        response = client.post("/v1/batches", json=request_data)

        assert response.status_code == 201
        result = response.json()
        assert result["status"] == "validating"
        assert result["input_file_id"] == "file-123"

    def test_create_batch_file_not_found(self, client, mock_storage):
        """Test batch creation with non-existent file"""
        # Mock storage.get_file to return None
        mock_storage.get_file = AsyncMock(return_value=None)

        request_data = {
            "input_file_id": "file-999",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        }
        response = client.post("/v1/batches", json=request_data)

        assert response.status_code == 404

    def test_get_batch(self, client, mock_storage):
        """Test get batch status"""
        # Mock storage.get_batch_job
        mock_storage.get_batch_job = AsyncMock(
            return_value=BatchJob(
                id="batch-123",
                status=BatchStatus.COMPLETED,
                input_file_id="file-123",
                output_file_id="file-456",
                created_at=1234567890,
                completed_at=1234567900,
                request_counts=RequestCounts(total=10, completed=10, failed=0),
            )
        )

        response = client.get("/v1/batches/batch-123")

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == "batch-123"
        assert result["status"] == "completed"
        assert result["request_counts"]["total"] == 10

    def test_get_batch_not_found(self, client, mock_storage):
        """Test get batch for non-existent batch"""
        # Mock storage.get_batch_job to return None
        mock_storage.get_batch_job = AsyncMock(return_value=None)

        response = client.get("/v1/batches/batch-999")

        assert response.status_code == 404

    def test_cancel_batch(self, client, mock_storage):
        """Test batch cancellation"""
        # Mock storage methods
        batch_job = BatchJob(
            id="batch-123",
            status=BatchStatus.IN_PROGRESS,
            input_file_id="file-123",
            created_at=1234567890,
            request_counts=RequestCounts(),
        )

        mock_storage.get_batch_job = AsyncMock(return_value=batch_job)
        mock_storage.update_batch_job = AsyncMock(return_value=batch_job)

        response = client.post("/v1/batches/batch-123/cancel")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "cancelled"

    def test_cancel_completed_batch(self, client, mock_storage):
        """Test cancelling an already completed batch"""
        # Mock storage.get_batch_job
        mock_storage.get_batch_job = AsyncMock(
            return_value=BatchJob(
                id="batch-123",
                status=BatchStatus.COMPLETED,
                input_file_id="file-123",
                created_at=1234567890,
                completed_at=1234567900,
                request_counts=RequestCounts(),
            )
        )

        response = client.post("/v1/batches/batch-123/cancel")

        assert response.status_code == 400


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root(self, client):
        """Test / endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "vLLM Batch Server"
        assert "version" in data
        assert "endpoints" in data

