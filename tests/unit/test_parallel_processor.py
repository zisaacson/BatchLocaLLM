"""
Tests for ParallelBatchProcessor

Run with: pytest tests/test_parallel_processor.py -v
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import (
    BatchRequestLine,
    ChatCompletionBody,
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig


@pytest.fixture
def mock_backend():
    """Create mock OllamaBackend"""
    backend = MagicMock()
    backend.current_model = "gemma3:12b"
    return backend


@pytest.fixture
def processor(mock_backend):
    """Create ParallelBatchProcessor instance"""
    config = WorkerConfig(num_workers=2, retry_attempts=2)
    return ParallelBatchProcessor(backend=mock_backend, config=config)


@pytest.fixture
def sample_requests():
    """Create sample batch requests"""
    return [
        BatchRequestLine(
            custom_id=f"req-{i}",
            method="POST",
            url="/v1/chat/completions",
            body=ChatCompletionBody(
                model="gemma3:12b",
                messages=[ChatMessage(role="user", content=f"Test message {i}")]
            )
        )
        for i in range(10)
    ]


class TestWorkerConfig:
    """Test WorkerConfig dataclass"""

    def test_default_config(self):
        """Test default configuration"""
        config = WorkerConfig()
        assert config.num_workers == 8  # Updated to match actual default
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0

    def test_custom_config(self):
        """Test custom configuration"""
        config = WorkerConfig(num_workers=4, retry_attempts=5, retry_delay=2.0)
        assert config.num_workers == 4
        assert config.retry_attempts == 5
        assert config.retry_delay == 2.0


class TestParallelProcessorInit:
    """Test ParallelBatchProcessor initialization"""

    def test_init_with_default_config(self, mock_backend):
        """Test initialization with default config"""
        processor = ParallelBatchProcessor(backend=mock_backend)
        assert processor.backend == mock_backend
        assert processor.config.num_workers == 8  # Updated to match actual default
        assert processor.config.retry_attempts == 3

    def test_init_with_custom_config(self, mock_backend):
        """Test initialization with custom config"""
        config = WorkerConfig(num_workers=8, retry_attempts=5)
        processor = ParallelBatchProcessor(backend=mock_backend, config=config)
        assert processor.config.num_workers == 8
        assert processor.config.retry_attempts == 5


class TestProcessBatch:
    """Test process_batch method"""

    @pytest.mark.asyncio
    async def test_process_batch_success(self, processor, mock_backend, sample_requests):
        """Test successful batch processing"""
        # Mock successful responses
        mock_response = ChatCompletionResponse(
            id="chatcmpl-123",
            model="gemma3:12b",
            created=int(time.time()),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Response"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        # Fix: Use correct method name
        mock_backend.generate_chat_completion = AsyncMock(return_value=mock_response)

        # Process batch
        results = await processor.process_batch(sample_requests)

        # Verify
        assert len(results) == 10
        assert all(r.response is not None for r in results)
        assert all(r.error is None for r in results)

    @pytest.mark.asyncio
    async def test_process_batch_empty(self, processor):
        """Test processing empty batch"""
        results = await processor.process_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_process_batch_preserves_order(self, processor, mock_backend, sample_requests):
        """Test that batch processing preserves request order"""
        # Mock responses
        mock_response = ChatCompletionResponse(
            id="chatcmpl-123",
            model="gemma3:12b",
            created=int(time.time()),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Response"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        # Fix: Use correct method name
        mock_backend.generate_chat_completion = AsyncMock(return_value=mock_response)

        # Process batch
        results = await processor.process_batch(sample_requests)

        # Verify order is preserved
        for i, result in enumerate(results):
            assert result.custom_id == f"req-{i}"

