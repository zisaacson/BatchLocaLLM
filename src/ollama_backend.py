"""
Ollama Backend Adapter for vLLM Batch Server

This module provides an adapter that wraps Ollama's API to work with our
existing batch processing infrastructure. It implements the same interface
as the vLLM ModelManager but uses Ollama under the hood.
"""

import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime

from src.config import settings
from src.models import ChatCompletionBody, ChatCompletionResponse, ChatCompletionChoice, ChatMessage, Usage

logger = logging.getLogger(__name__)


class OllamaBackend:
    """
    Ollama backend adapter that provides the same interface as vLLM ModelManager.
    
    This allows us to use Ollama for inference while maintaining compatibility
    with our existing batch processing infrastructure.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama backend.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for long generations
        self.current_model: Optional[str] = None
        logger.info(f"Initialized Ollama backend with base_url={self.base_url}")
    
    async def health_check(self) -> bool:
        """
        Check if Ollama server is healthy and responsive.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """
        List all available models in Ollama.
        
        Returns:
            List of model names
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            logger.info(f"Found {len(models)} Ollama models: {models}")
            return models
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
    
    async def load_model(self, model_name: str) -> None:
        """
        Load a model in Ollama (ensures it's pulled and ready).
        
        Args:
            model_name: Name of the model to load (e.g., "gemma3:12b")
        """
        logger.info(f"Loading Ollama model: {model_name}")
        
        # Check if model exists
        models = await self.list_models()
        if model_name not in models:
            logger.warning(f"Model {model_name} not found in Ollama. Available models: {models}")
            raise ValueError(f"Model {model_name} not found. Please run: ollama pull {model_name}")
        
        # Ollama loads models on-demand, so we just verify it exists
        self.current_model = model_name
        logger.info(f"Model {model_name} ready for inference")
    
    async def generate_chat_completion(
        self,
        request: ChatCompletionBody
    ) -> ChatCompletionResponse:
        """
        Generate a chat completion using Ollama.
        
        Args:
            request: OpenAI-compatible chat completion request
            
        Returns:
            OpenAI-compatible chat completion response
        """
        start_time = datetime.utcnow()
        
        # Convert OpenAI format to Ollama format
        ollama_request = {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ],
            "stream": False,
            "options": {}
        }
        
        # Map OpenAI parameters to Ollama options
        if request.temperature is not None:
            ollama_request["options"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            ollama_request["options"]["num_predict"] = request.max_tokens
        if request.top_p is not None:
            ollama_request["options"]["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            ollama_request["options"]["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            ollama_request["options"]["presence_penalty"] = request.presence_penalty
        if request.stop:
            ollama_request["options"]["stop"] = request.stop
        
        logger.debug(f"Sending request to Ollama: {ollama_request}")
        
        try:
            # Call Ollama API
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=ollama_request
            )
            response.raise_for_status()
            ollama_response = response.json()
            
            # Extract response
            assistant_message = ollama_response.get("message", {})
            content = assistant_message.get("content", "")
            
            # Calculate tokens (Ollama provides these in the response)
            prompt_tokens = ollama_response.get("prompt_eval_count", 0)
            completion_tokens = ollama_response.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens
            
            # Build OpenAI-compatible response
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            logger.info(
                f"Ollama completion: model={request.model}, "
                f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, "
                f"duration_ms={duration_ms:.2f}"
            )
            
            return ChatCompletionResponse(
                id=f"chatcmpl-{datetime.utcnow().timestamp()}",
                object="chat.completion",
                created=int(start_time.timestamp()),
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content=content
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens
                )
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    async def generate_chat_completion_stream(
        self,
        request: ChatCompletionBody
    ) -> AsyncIterator[str]:
        """
        Generate a streaming chat completion using Ollama.
        
        Args:
            request: OpenAI-compatible chat completion request
            
        Yields:
            Server-sent events in OpenAI format
        """
        # Convert OpenAI format to Ollama format
        ollama_request = {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ],
            "stream": True,
            "options": {}
        }
        
        # Map parameters
        if request.temperature is not None:
            ollama_request["options"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            ollama_request["options"]["num_predict"] = request.max_tokens
        if request.top_p is not None:
            ollama_request["options"]["top_p"] = request.top_p
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=ollama_request
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    try:
                        import json
                        chunk = json.loads(line)
                        
                        # Extract delta content
                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        done = chunk.get("done", False)
                        
                        if content:
                            # Convert to OpenAI SSE format
                            sse_data = {
                                "id": f"chatcmpl-{datetime.utcnow().timestamp()}",
                                "object": "chat.completion.chunk",
                                "created": int(datetime.utcnow().timestamp()),
                                "model": request.model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": content},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(sse_data)}\n\n"
                        
                        if done:
                            # Send final chunk
                            final_data = {
                                "id": f"chatcmpl-{datetime.utcnow().timestamp()}",
                                "object": "chat.completion.chunk",
                                "created": int(datetime.utcnow().timestamp()),
                                "model": request.model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": "stop"
                                }]
                            }
                            yield f"data: {json.dumps(final_data)}\n\n"
                            yield "data: [DONE]\n\n"
                            break
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse Ollama stream chunk: {line}")
                        continue
                        
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("Ollama backend closed")

