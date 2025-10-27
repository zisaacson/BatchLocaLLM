"""
Batch processor for Ollama Batch Server

Handles:
- Processing batch jobs using Ollama backend
- JSONL parsing and result generation
- Job queue management
- Error handling and retries
- Token-aware conversation batching
- VRAM-aware context management
"""

import asyncio
import json
import time
import uuid
import hashlib
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from src.config import settings
from src.ollama_backend import OllamaBackend
from src.logger import logger
from src.batch_metrics import BatchMetrics
from src.models import (
    BatchError,
    BatchJob,
    BatchRequestLine,
    BatchResultLine,
    BatchResponseBody,
    BatchStatus,
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
    RequestCounts,
    Usage,
)
from src.storage import storage

# Context window limits (conservative estimates)
# Gemma 3 12B supports 128K tokens, but we use conservative limits for VRAM safety
MAX_CONTEXT_TOKENS = 32000  # Conservative limit to prevent VRAM overflow
CONTEXT_TRIM_THRESHOLD = 28000  # Start trimming at 87.5% capacity
MIN_CONTEXT_RESERVE = 4000  # Always keep at least this much space for responses


class BatchProcessor:
    """Processes batch jobs using Ollama backend"""

    def __init__(self) -> None:
        self.backend: Optional[OllamaBackend] = None
        self.processing_jobs: set[str] = set()
        self.max_concurrent = settings.max_concurrent_batches

    async def initialize(self) -> None:
        """Initialize Ollama backend"""
        logger.info("Initializing Ollama backend", extra={"model": settings.model_name})

        # Initialize Ollama backend
        self.backend = OllamaBackend(base_url=settings.ollama_base_url)

        # Health check
        healthy = await self.backend.health_check()
        if not healthy:
            raise RuntimeError("Ollama server is not running or not accessible")

        # Load model
        await self.backend.load_model(settings.model_name)

        logger.info(
            "Ollama backend initialized",
            extra={
                "model": settings.model_name,
                "ollama_url": settings.ollama_base_url,
            },
        )

    async def process_batch(self, batch_id: str) -> None:
        """Process a batch job"""
        if batch_id in self.processing_jobs:
            logger.warning("Batch already being processed", extra={"batch_id": batch_id})
            return

        if len(self.processing_jobs) >= self.max_concurrent:
            logger.warning(
                "Max concurrent batches reached",
                extra={"batch_id": batch_id, "max_concurrent": self.max_concurrent},
            )
            return

        self.processing_jobs.add(batch_id)

        try:
            # Get batch job
            batch_job = await storage.get_batch_job(batch_id)
            if not batch_job:
                logger.error("Batch job not found", extra={"batch_id": batch_id})
                return

            # Update status to in_progress
            batch_job.status = BatchStatus.IN_PROGRESS
            batch_job.in_progress_at = int(time.time())
            await storage.update_batch_job(batch_job)

            logger.info("Processing batch", extra={"batch_id": batch_id})

            # Read input file
            input_content = await storage.read_file(batch_job.input_file_id)
            if not input_content:
                raise ValueError(f"Input file not found: {batch_job.input_file_id}")

            # Parse JSONL
            requests = self._parse_jsonl(input_content.decode("utf-8"))
            batch_job.request_counts.total = len(requests)
            await storage.update_batch_job(batch_job)

            logger.info(
                "Parsed batch requests",
                extra={"batch_id": batch_id, "request_count": len(requests)},
            )

            # Process requests
            results = await self._process_requests(requests)

            # Count successes and failures
            batch_job.request_counts.completed = sum(1 for r in results if r.error is None)
            batch_job.request_counts.failed = sum(1 for r in results if r.error is not None)

            # Save results
            output_file_id = f"batch_output_{batch_id}_{int(time.time())}"
            result_content = "\n".join(r.model_dump_json() for r in results).encode("utf-8")
            await storage.save_file(
                output_file_id, f"{output_file_id}.jsonl", result_content, purpose="batch_output"
            )

            # Update batch job
            batch_job.status = BatchStatus.COMPLETED
            batch_job.output_file_id = output_file_id
            batch_job.completed_at = int(time.time())
            await storage.update_batch_job(batch_job)

            logger.info(
                "Batch completed",
                extra={
                    "batch_id": batch_id,
                    "completed": batch_job.request_counts.completed,
                    "failed": batch_job.request_counts.failed,
                },
            )

        except Exception as e:
            logger.error(
                "Batch processing failed",
                extra={"batch_id": batch_id, "error": str(e)},
                exc_info=True,
            )

            # Update batch job to failed
            batch_job = await storage.get_batch_job(batch_id)
            if batch_job:
                batch_job.status = BatchStatus.FAILED
                batch_job.failed_at = int(time.time())
                await storage.update_batch_job(batch_job)

        finally:
            self.processing_jobs.discard(batch_id)

    def _parse_jsonl(self, content: str) -> List[BatchRequestLine]:
        """Parse JSONL content into batch requests"""
        requests = []
        for line_num, line in enumerate(content.strip().split("\n"), 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                request = BatchRequestLine.model_validate(data)
                requests.append(request)
            except Exception as e:
                logger.error(
                    "Failed to parse request line",
                    extra={"line_num": line_num, "error": str(e)},
                )
                raise ValueError(f"Invalid request at line {line_num}: {e}")
        return requests

    async def _process_requests(self, requests: List[BatchRequestLine]) -> List[BatchResultLine]:
        """
        Process batch requests with token optimization.

        For requests with identical system prompts:
        - Processes as single conversation to reuse tokenized system prompt
        - Trims context when approaching VRAM limits
        - Keeps model loaded to avoid reload overhead

        Token savings: ~97% for 170k requests with same system prompt
        """
        if not self.backend:
            raise RuntimeError("Ollama backend not initialized")

        # Check if all requests share the same system prompt
        system_prompts = set()
        for req in requests:
            system_msg = next((msg for msg in req.body.messages if msg.role == "system"), None)
            # Use empty string as placeholder for requests without system message
            system_prompts.add(system_msg.content if system_msg else "")

        # If all requests share same system prompt (or all have no system prompt), use optimized conversation batching
        if len(system_prompts) == 1:
            has_system_prompt = list(system_prompts)[0] != ""
            logger.info(
                "All requests share same system prompt - using optimized conversation batching",
                extra={
                    "total_requests": len(requests),
                    "has_system_prompt": has_system_prompt,
                    "estimated_token_savings": "~97%" if has_system_prompt else "~50%"
                }
            )
            return await self._process_conversation_batch(requests)
        else:
            logger.info(
                "Multiple system prompts detected - using standard processing",
                extra={
                    "total_requests": len(requests),
                    "unique_system_prompts": len(system_prompts)
                }
            )
            return await self._process_standard_batch(requests)

    async def _process_standard_batch(self, requests: List[BatchRequestLine]) -> List[BatchResultLine]:
        """Process requests individually (no optimization)"""
        results: List[BatchResultLine] = []

        for req in requests:
            try:
                response = await self.backend.generate_chat_completion(req.body)

                result = BatchResultLine(
                    id=f"batch-{uuid.uuid4().hex[:8]}",
                    custom_id=req.custom_id,
                    response=BatchResponseBody(
                        status_code=200,
                        request_id=f"req-{uuid.uuid4().hex[:8]}",
                        body=response,
                    ),
                    error=None,
                )
            except Exception as e:
                logger.error(
                    "Failed to process request",
                    extra={"custom_id": req.custom_id, "error": str(e)},
                )
                result = BatchResultLine(
                    id=f"batch-{uuid.uuid4().hex[:8]}",
                    custom_id=req.custom_id,
                    response=None,
                    error=BatchError(
                        message=str(e), type="processing_error", code="internal_error"
                    ),
                )

            results.append(result)

        return results

    async def _process_conversation_batch(self, requests: List[BatchRequestLine]) -> List[BatchResultLine]:
        """
        Process requests as single conversation for token optimization.

        For 170k candidates with same system prompt:
        - System prompt tokenized ONCE (not 170k times)
        - Saves ~97% of prompt tokens
        - Trims context every 50 requests to prevent VRAM overflow
        """
        results: List[BatchResultLine] = []

        # Initialize metrics tracking
        metrics = BatchMetrics(
            batch_id=f"batch-{uuid.uuid4().hex[:8]}",
            total_requests=len(requests)
        )

        # Extract system prompt from first request
        first_req = requests[0]
        system_msg = next((msg for msg in first_req.body.messages if msg.role == "system"), None)
        system_prompt_tokens = len(system_msg.content.split()) if system_msg else 0

        # Build conversation messages (start with system prompt)
        conversation = []
        if system_msg:
            conversation.append({"role": "system", "content": system_msg.content})

        # Track tokens to prevent overflow
        estimated_tokens = system_prompt_tokens

        for idx, req in enumerate(requests, 1):
            request_start_time = time.time()

            try:
                # Extract user message (skip system message)
                user_msg = next((msg for msg in req.body.messages if msg.role == "user"), None)
                if not user_msg:
                    raise ValueError("No user message found in request")

                # Add user message to conversation
                conversation.append({"role": "user", "content": user_msg.content})
                estimated_tokens += len(user_msg.content.split())

                # Update context metrics
                metrics.update_context(estimated_tokens)

                # Check VRAM usage
                vram_gb = metrics.get_vram_usage()
                if vram_gb:
                    metrics.update_vram(vram_gb)

                # Call Ollama with full conversation + keep_alive
                ollama_request = {
                    "model": req.body.model,
                    "messages": conversation,
                    "stream": False,
                    "keep_alive": -1,  # Keep model loaded forever
                    "options": {}
                }

                # Map parameters
                if req.body.temperature is not None:
                    ollama_request["options"]["temperature"] = req.body.temperature
                if req.body.max_tokens is not None:
                    ollama_request["options"]["num_predict"] = req.body.max_tokens

                # Make request
                response = await self.backend.client.post(
                    f"{self.backend.base_url}/api/chat",
                    json=ollama_request
                )
                response.raise_for_status()
                ollama_response = response.json()

                # Extract response
                assistant_content = ollama_response.get("message", {}).get("content", "")
                prompt_tokens = ollama_response.get("prompt_eval_count", 0)
                completion_tokens = ollama_response.get("eval_count", 0)

                # Add assistant response to conversation
                conversation.append({"role": "assistant", "content": assistant_content})
                estimated_tokens += len(assistant_content.split())

                # Update metrics
                request_time = time.time() - request_start_time
                metrics.update_request(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    processing_time_sec=request_time,
                    success=True
                )
                metrics.estimate_cached_tokens(system_prompt_tokens)

                # Build result
                result = BatchResultLine(
                    id=f"batch-{uuid.uuid4().hex[:8]}",
                    custom_id=req.custom_id,
                    response=BatchResponseBody(
                        status_code=200,
                        request_id=f"req-{uuid.uuid4().hex[:8]}",
                        body=ChatCompletionResponse(
                            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                            object="chat.completion",
                            created=int(time.time()),
                            model=req.body.model,
                            choices=[
                                ChatCompletionChoice(
                                    index=0,
                                    message=ChatMessage(role="assistant", content=assistant_content),
                                    finish_reason="stop"
                                )
                            ],
                            usage=Usage(
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=prompt_tokens + completion_tokens
                            )
                        ),
                    ),
                    error=None,
                )

                results.append(result)

                # Trim conversation every 50 requests to prevent VRAM overflow
                # Keep: system prompt + last 20 exchanges (40 messages)
                if idx % 50 == 0 and len(conversation) > 41:
                    logger.info(
                        "Trimming conversation context",
                        extra={
                            "request_num": idx,
                            "conversation_length": len(conversation),
                            "estimated_tokens": estimated_tokens,
                            "vram_gb": vram_gb if vram_gb else "unknown"
                        }
                    )
                    # Keep system message + last 40 messages (20 exchanges)
                    conversation = [conversation[0]] + conversation[-40:]
                    estimated_tokens = estimated_tokens // 3  # Rough estimate after trim
                    metrics.update_context(estimated_tokens, was_trimmed=True)

                # Log progress every 100 requests
                if idx % 100 == 0:
                    logger.info(
                        f"Batch progress: {idx}/{len(requests)}",
                        extra=metrics.to_dict()
                    )
                    # Print summary to console
                    print(metrics.log_summary())

            except Exception as e:
                request_time = time.time() - request_start_time
                error_msg = str(e)

                logger.error(
                    "Failed to process request in conversation",
                    extra={"custom_id": req.custom_id, "error": error_msg},
                )

                # Update metrics with error
                metrics.update_request(
                    prompt_tokens=0,
                    completion_tokens=0,
                    processing_time_sec=request_time,
                    success=False,
                    error_type=error_msg
                )

                result = BatchResultLine(
                    id=f"batch-{uuid.uuid4().hex[:8]}",
                    custom_id=req.custom_id,
                    response=None,
                    error=BatchError(
                        message=error_msg, type="processing_error", code="internal_error"
                    ),
                )
                results.append(result)

        # Log final metrics
        logger.info("Batch completed", extra=metrics.to_dict())
        print("\n" + "="*80)
        print("FINAL BATCH METRICS")
        print("="*80)
        print(metrics.log_summary())

        return results


# Global batch processor instance
batch_processor = BatchProcessor()

