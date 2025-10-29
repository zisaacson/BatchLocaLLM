"""
Tests for OllamaBackend

Run with: pytest tests/test_ollama_backend.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models import ChatCompletionBody, ChatMessage
from src.ollama_backend import OllamaBackend


@pytest.fixture
def backend():
    """Create OllamaBackend instance"""
    return OllamaBackend(base_url="http://localhost:11434")


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    with patch("httpx.AsyncClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


class TestOllamaBackendInit:
    """Test OllamaBackend initialization"""

    def test_init_default_url(self):
        """Test initialization with default URL"""
        backend = OllamaBackend()
        assert backend.base_url == "http://localhost:11434"
        assert backend.current_model is None

    def test_init_custom_url(self):
        """Test initialization with custom URL"""
        backend = OllamaBackend(base_url="http://custom:8080")
        assert backend.base_url == "http://custom:8080"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base_url"""
        backend = OllamaBackend(base_url="http://localhost:11434/")
        assert backend.base_url == "http://localhost:11434"


class TestListModels:
    """Test list_models method"""

    @pytest.mark.asyncio
    async def test_list_models_success(self, backend):
        """Test successful model listing"""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:12b"},
                {"name": "gemma3:4b"},
                {"name": "llama3.2:3b"},
            ]
        }
        backend.client.get = AsyncMock(return_value=mock_response)

        # List models
        models = await backend.list_models()

        # Verify
        assert len(models) == 3
        assert "gemma3:12b" in models
        assert "gemma3:4b" in models
        assert "llama3.2:3b" in models
        backend.client.get.assert_called_once_with("http://localhost:11434/api/tags")

    @pytest.mark.asyncio
    async def test_list_models_empty(self, backend):
        """Test listing models when none exist"""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        backend.client.get = AsyncMock(return_value=mock_response)

        # List models
        models = await backend.list_models()

        # Verify
        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_error(self, backend):
        """Test error handling when listing models fails"""
        # Mock error
        backend.client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        # List models
        models = await backend.list_models()

        # Verify - should return empty list on error
        assert models == []


class TestLoadModel:
    """Test load_model method"""

    @pytest.mark.asyncio
    async def test_load_model_success(self, backend):
        """Test successful model loading"""
        # Mock list_models to return available models
        backend.list_models = AsyncMock(return_value=["gemma3:12b", "gemma3:4b"])

        # Load model
        await backend.load_model("gemma3:12b")

        # Verify
        assert backend.current_model == "gemma3:12b"

    @pytest.mark.asyncio
    async def test_load_model_not_found(self, backend):
        """Test loading a model that doesn't exist"""
        # Mock list_models to return available models
        backend.list_models = AsyncMock(return_value=["gemma3:12b"])

        # Try to load non-existent model
        with pytest.raises(ValueError, match="Model gemma3:4b not found"):
            await backend.load_model("gemma3:4b")

        # Verify current_model is not set
        assert backend.current_model is None


class TestChatCompletion:
    """Test chat_completion method"""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, backend):
        """Test successful chat completion"""
        # Set current model
        backend.current_model = "gemma3:12b"

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "gemma3:12b",
            "created_at": "2025-10-27T12:00:00Z",
            "message": {
                "role": "assistant",
                "content": "This is a test response"
            },
            "done": True,
            "total_duration": 1000000000,  # 1 second in nanoseconds
            "prompt_eval_count": 50,
            "eval_count": 20
        }
        backend.client.post = AsyncMock(return_value=mock_response)

        # Create request
        request = ChatCompletionBody(
            model="gemma3:12b",
            messages=[
                ChatMessage(role="user", content="Hello")
            ]
        )

        # Make request
        response = await backend.generate_chat_completion(request)

        # Verify response
        assert response.model == "gemma3:12b"
        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert response.choices[0].message.content == "This is a test response"
        assert response.usage.prompt_tokens == 50
        assert response.usage.completion_tokens == 20
        assert response.usage.total_tokens == 70

    @pytest.mark.asyncio
    async def test_chat_completion_with_system_message(self, backend):
        """Test chat completion with system message"""
        backend.current_model = "gemma3:12b"

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "gemma3:12b",
            "created_at": "2025-10-27T12:00:00Z",
            "message": {
                "role": "assistant",
                "content": "Response with system context"
            },
            "done": True,
            "total_duration": 1000000000,
            "prompt_eval_count": 100,
            "eval_count": 30
        }
        backend.client.post = AsyncMock(return_value=mock_response)

        # Create request with system message
        request = ChatCompletionBody(
            model="gemma3:12b",
            messages=[
                ChatMessage(role="system", content="You are a helpful assistant"),
                ChatMessage(role="user", content="Hello")
            ]
        )

        # Make request
        response = await backend.generate_chat_completion(request)

        # Verify
        assert response.choices[0].message.content == "Response with system context"
        assert response.usage.prompt_tokens == 100

    @pytest.mark.asyncio
    async def test_chat_completion_error(self, backend):
        """Test error handling in chat completion"""
        backend.current_model = "gemma3:12b"

        # Mock error
        backend.client.post = AsyncMock(side_effect=httpx.HTTPError("API error"))

        # Create request
        request = ChatCompletionBody(
            model="gemma3:12b",
            messages=[ChatMessage(role="user", content="Hello")]
        )

        # Verify error is raised
        with pytest.raises(httpx.HTTPError):
            await backend.generate_chat_completion(request)

    @pytest.mark.asyncio
    async def test_chat_completion_with_temperature(self, backend):
        """Test chat completion with temperature parameter"""
        backend.current_model = "gemma3:12b"

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "gemma3:12b",
            "created_at": "2025-10-27T12:00:00Z",
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "total_duration": 1000000000,
            "prompt_eval_count": 50,
            "eval_count": 20
        }
        backend.client.post = AsyncMock(return_value=mock_response)

        # Create request with temperature
        request = ChatCompletionBody(
            model="gemma3:12b",
            messages=[ChatMessage(role="user", content="Hello")],
            temperature=0.7
        )

        # Make request
        await backend.generate_chat_completion(request)

        # Verify temperature was passed to Ollama
        call_args = backend.client.post.call_args
        request_data = call_args[1]["json"]
        assert request_data["options"]["temperature"] == 0.7

