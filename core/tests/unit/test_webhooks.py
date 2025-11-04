"""Unit tests for webhook notifications."""

import pytest
from unittest.mock import Mock, patch
from core.batch_app.webhooks import send_webhook
from core.batch_app.database import BatchJob


class TestWebhookNotifications:
    """Test webhook notification functionality."""

    @patch('core.batch_app.webhooks.requests.post')
    def test_send_webhook_success(self, mock_post):
        """Test successful webhook notification."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Create a mock batch job
        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "completed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.created_at = 1234567890
        batch_job.completed_at = 1234567900
        batch_job.total_requests = 100
        batch_job.completed_requests = 100
        batch_job.failed_requests = 0
        batch_job.metadata_json = None  # No metadata
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db)

        # Verify webhook was sent
        assert result is True
        mock_post.assert_called_once()

    @patch('core.batch_app.webhooks.requests.post')
    def test_send_webhook_no_url(self, mock_post):
        """Test webhook when no URL is configured."""
        # Create a mock batch job without webhook URL
        batch_job = Mock(spec=BatchJob)
        batch_job.webhook_url = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db)

        # Verify webhook was not sent but returned success
        assert result is True
        mock_post.assert_not_called()

    @patch('core.batch_app.webhooks.requests.post')
    def test_send_webhook_failure(self, mock_post):
        """Test webhook notification failure."""
        # Mock the HTTP response to return error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Create a mock batch job
        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "failed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.created_at = 1234567890
        batch_job.completed_at = 1234567900
        batch_job.total_requests = 100
        batch_job.completed_requests = 90
        batch_job.failed_requests = 10
        batch_job.metadata_json = None
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db)

        # Verify webhook failed
        assert result is False

    @patch('core.batch_app.webhooks.requests.post')
    def test_send_webhook_exception(self, mock_post):
        """Test webhook notification with exception."""
        # Mock the HTTP client to raise RequestException (which is caught by the code)
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        # Create a mock batch job
        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "completed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.created_at = 1234567890
        batch_job.completed_at = 1234567900
        batch_job.total_requests = 100
        batch_job.completed_requests = 100
        batch_job.failed_requests = 0
        batch_job.metadata_json = None
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db)

        # Verify webhook failed
        assert result is False

    @patch('core.batch_app.webhooks.requests.post')
    @patch('core.batch_app.webhooks.time.sleep')  # Mock sleep to speed up test
    def test_send_webhook_retry_logic(self, mock_sleep, mock_post):
        """Test webhook retry logic with exponential backoff."""
        # Mock the HTTP response to fail first 2 times, then succeed
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Internal Server Error"
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.text = "OK"
        mock_post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]

        # Create a mock batch job
        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "completed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.created_at = 1234567890
        batch_job.completed_at = 1234567900
        batch_job.total_requests = 100
        batch_job.completed_requests = 100
        batch_job.failed_requests = 0
        batch_job.metadata_json = None
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db, max_retries=3)

        # Verify webhook succeeded after retries
        assert result is True
        # Should have been called 3 times (2 failures + 1 success)
        assert mock_post.call_count == 3
        # Sleep should have been called 2 times (after first 2 failures)
        assert mock_sleep.call_count == 2

    @patch('core.batch_app.webhooks.requests.post')
    def test_send_webhook_with_metadata(self, mock_post):
        """Test webhook with metadata in batch job."""
        import json

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create a mock batch job with metadata
        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "completed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.created_at = 1234567890
        batch_job.completed_at = 1234567900
        batch_job.total_requests = 100
        batch_job.completed_requests = 100
        batch_job.failed_requests = 0
        batch_job.metadata_json = json.dumps({"user_id": "123", "project": "test"})
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        # Mock database session
        mock_db = Mock()

        # Send webhook
        result = send_webhook(batch_job, mock_db)

        # Verify webhook was sent
        assert result is True
        # Verify metadata was included in payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert 'metadata' in payload
        assert payload['metadata']['user_id'] == "123"
        assert payload['metadata']['project'] == "test"

    @patch('core.batch_app.webhooks.requests.post')
    @patch('core.batch_app.webhooks.time.sleep')
    def test_send_webhook_timeout(self, mock_sleep, mock_post):
        """Test webhook timeout handling."""
        import requests
        import time

        # Mock timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")

        batch_job = Mock(spec=BatchJob)
        batch_job.batch_id = "batch-test123"
        batch_job.status = "completed"
        batch_job.webhook_url = "https://example.com/webhook"
        batch_job.metadata_json = None
        batch_job.webhook_attempts = 0
        batch_job.webhook_last_attempt = None
        batch_job.webhook_status = None
        batch_job.webhook_error = None
        batch_job.created_at = int(time.time())
        batch_job.completed_at = int(time.time())
        batch_job.total_requests = 100
        batch_job.completed_requests = 100
        batch_job.failed_requests = 0
        batch_job.webhook_max_retries = 3
        batch_job.webhook_timeout = 10
        batch_job.webhook_secret = None

        mock_db = Mock()
        result = send_webhook(batch_job, mock_db)

        # Should return False after all retries fail
        assert result is False
        # Should have set error message
        assert "Timeout" in batch_job.webhook_error

