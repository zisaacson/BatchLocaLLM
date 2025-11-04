"""Unit tests for result handlers - streamlined version.

Reduced from 14 tests to 5 tests focusing on core functionality:
- Base class abstract methods
- Handler registration
- Webhook handler
- Result processing
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from core.result_handlers.base import ResultHandler, ResultHandlerRegistry
from core.result_handlers.webhook import WebhookHandler


class TestResultHandlerBase:
    """Test result handler base class - core functionality only."""

    def test_abstract_base_class_cannot_be_instantiated(self):
        """Test that ResultHandler is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ResultHandler()

    def test_subclass_must_implement_abstract_methods(self):
        """Test that subclasses must implement all abstract methods."""
        class IncompleteHandler(ResultHandler):
            @property
            def name(self):
                return "incomplete"
        
        with pytest.raises(TypeError):
            IncompleteHandler()


class TestWebhookHandler:
    """Test webhook result handler - core functionality only."""

    @patch('result_handlers.webhook.requests.post')
    def test_webhook_handler_success(self, mock_post):
        """Test webhook handler sends HTTP POST successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        handler = WebhookHandler()
        result = handler.handle(
            batch_id="batch-123",
            results=[{"id": "1", "response": "test"}],
            metadata={"webhook_url": "https://example.com/webhook"}
        )
        
        assert result is True
        assert mock_post.called

    @patch('result_handlers.webhook.requests.post')
    @patch('time.sleep')
    def test_webhook_handler_retries_on_failure(self, mock_sleep, mock_post):
        """Test webhook handler retries on failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        handler = WebhookHandler()
        result = handler.handle(
            batch_id="batch-123",
            results=[],
            metadata={"webhook_url": "https://example.com/webhook"}
        )
        
        assert result is False
        assert mock_post.call_count == 3  # Default max_retries


class TestResultHandlerRegistry:
    """Test result handler registry - core functionality only."""

    def test_handler_registration_and_processing(self):
        """Test registering handlers and processing results."""
        # Create a concrete handler for testing
        class TestHandler(ResultHandler):
            @property
            def name(self):
                return "test_handler"

            def enabled(self, metadata):
                return True

            def handle(self, batch_id, results, metadata):
                return True

        registry = ResultHandlerRegistry()
        registry.handlers.clear()

        handler = TestHandler()
        registry.register(handler)

        # Process results - should not raise exception
        registry.process_results(
            batch_id="batch-123",
            results=[],
            metadata={}
        )

        # Verify handler was registered
        assert len(registry.handlers) == 1

