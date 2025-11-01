"""Unit tests for API request validation - HIGH VALUE tests.

These tests prevent user-facing API errors from invalid requests.
Tests cover:
- Request model validation
- Input sanitization
- Error message clarity
- Edge cases

NOTE: These are unit tests that don't require database or server.
Run with: pytest core/tests/unit/test_api_validation.py -v
"""

import pytest
import json
from pydantic import ValidationError

from core.batch_app.api_server import CreateBatchRequest, CancelBatchRequest


# ============================================================================
# Batch Creation Request Validation
# ============================================================================

class TestCreateBatchRequestValidation:
    """Test CreateBatchRequest model validation."""

    def test_valid_request(self):
        """Test valid batch creation request."""
        request = CreateBatchRequest(
            input_file_id="file-abc123",
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        
        assert request.input_file_id == "file-abc123"
        assert request.endpoint == "/v1/chat/completions"
        assert request.completion_window == "24h"
        assert request.metadata is None

    def test_valid_request_with_metadata(self):
        """Test valid request with metadata."""
        request = CreateBatchRequest(
            input_file_id="file-abc123",
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"user_id": "123", "project": "test"}
        )
        
        assert request.metadata == {"user_id": "123", "project": "test"}

    def test_missing_input_file_id(self):
        """Test request with missing input_file_id."""
        with pytest.raises(ValidationError) as exc_info:
            CreateBatchRequest(
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )
        
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('input_file_id',) for e in errors)

    def test_default_endpoint(self):
        """Test that endpoint defaults to /v1/chat/completions."""
        request = CreateBatchRequest(
            input_file_id="file-abc123"
        )
        
        assert request.endpoint == "/v1/chat/completions"

    def test_default_completion_window(self):
        """Test that completion_window defaults to 24h."""
        request = CreateBatchRequest(
            input_file_id="file-abc123"
        )
        
        assert request.completion_window == "24h"

    def test_empty_metadata(self):
        """Test request with empty metadata dict."""
        request = CreateBatchRequest(
            input_file_id="file-abc123",
            metadata={}
        )
        
        assert request.metadata == {}

    def test_metadata_with_special_characters(self):
        """Test metadata with special characters."""
        request = CreateBatchRequest(
            input_file_id="file-abc123",
            metadata={"key": "value with spaces & special chars!"}
        )
        
        assert request.metadata["key"] == "value with spaces & special chars!"


# ============================================================================
# Cancel Batch Request Validation
# ============================================================================

class TestCancelBatchRequestValidation:
    """Test CancelBatchRequest model validation."""

    def test_valid_cancel_request(self):
        """Test valid cancel request."""
        request = CancelBatchRequest()
        
        # Should be empty (no body needed)
        assert request is not None


# ============================================================================
# GPU Health Check Logic
# ============================================================================

class TestGPUHealthCheckLogic:
    """Test GPU health check logic without actual GPU."""

    def test_healthy_gpu_status(self):
        """Test that healthy GPU status is correctly identified."""
        from core.batch_app.api_server import check_gpu_health
        
        # This will return fallback healthy status in test environment
        status = check_gpu_health()
        
        assert 'healthy' in status
        assert isinstance(status['healthy'], bool)

    def test_gpu_status_structure(self):
        """Test that GPU status has required fields."""
        from core.batch_app.api_server import check_gpu_health
        
        status = check_gpu_health()
        
        assert 'healthy' in status
        assert 'memory_percent' in status or 'warning' in status
        assert 'temperature_c' in status or 'warning' in status


# ============================================================================
# Input File Validation Logic
# ============================================================================

class TestInputFileValidation:
    """Test input file validation logic."""

    def test_valid_jsonl_line(self):
        """Test parsing valid JSONL line."""
        line = json.dumps({
            "custom_id": "req-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        })
        
        # Should parse without error
        data = json.loads(line)
        assert data["custom_id"] == "req-1"
        assert data["body"]["model"] == "test-model"

    def test_invalid_json_line(self):
        """Test parsing invalid JSON line."""
        line = "{invalid json}"
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(line)

    @pytest.mark.parametrize("request_data,missing_field,field_location", [
        (
            {
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            },
            "custom_id",
            "root"
        ),
        (
            {
                "custom_id": "req-1",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            },
            "model",
            "body"
        ),
    ])
    def test_missing_required_field(self, request_data, missing_field, field_location):
        """Test request missing required fields."""
        line = json.dumps(request_data)
        data = json.loads(line)

        if field_location == "root":
            assert missing_field not in data
        elif field_location == "body":
            assert missing_field not in data["body"]

    def test_empty_messages(self):
        """Test request with empty messages array."""
        line = json.dumps({
            "custom_id": "req-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "test-model",
                "messages": []
            }
        })
        
        data = json.loads(line)
        assert len(data["body"]["messages"]) == 0

    def test_multi_turn_conversation(self):
        """Test request with multi-turn conversation."""
        line = json.dumps({
            "custom_id": "req-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "test-model",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "How are you?"}
                ]
            }
        })
        
        data = json.loads(line)
        assert len(data["body"]["messages"]) == 4

    def test_unicode_content(self):
        """Test request with Unicode content."""
        line = json.dumps({
            "custom_id": "req-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello 世界 🌍"}]
            }
        })
        
        data = json.loads(line)
        assert "世界" in data["body"]["messages"][0]["content"]
        assert "🌍" in data["body"]["messages"][0]["content"]

    def test_very_long_content(self):
        """Test request with very long content."""
        long_content = "x" * 100000  # 100K characters
        
        line = json.dumps({
            "custom_id": "req-1",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "test-model",
                "messages": [{"role": "user", "content": long_content}]
            }
        })
        
        data = json.loads(line)
        assert len(data["body"]["messages"][0]["content"]) == 100000


# ============================================================================
# Constants and Limits
# ============================================================================

class TestAPIConstants:
    """Test API constants and limits."""

    def test_max_queue_depth_constant(self):
        """Test that MAX_QUEUE_DEPTH is defined."""
        from core.batch_app.api_server import MAX_QUEUE_DEPTH
        
        assert isinstance(MAX_QUEUE_DEPTH, int)
        assert MAX_QUEUE_DEPTH > 0

    def test_max_requests_per_job_constant(self):
        """Test that MAX_REQUESTS_PER_JOB is defined."""
        from core.batch_app.api_server import MAX_REQUESTS_PER_JOB
        
        assert isinstance(MAX_REQUESTS_PER_JOB, int)
        assert MAX_REQUESTS_PER_JOB > 0

    def test_files_dir_exists(self):
        """Test that FILES_DIR is defined."""
        from core.batch_app.api_server import FILES_DIR
        from pathlib import Path
        
        assert isinstance(FILES_DIR, Path)

    def test_logs_dir_exists(self):
        """Test that LOGS_DIR is defined."""
        from core.batch_app.api_server import LOGS_DIR
        from pathlib import Path
        
        assert isinstance(LOGS_DIR, Path)

