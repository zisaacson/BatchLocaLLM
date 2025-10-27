"""
Batch processor for Ollama Batch Server

Handles:
- Processing batch jobs using Ollama backend
- JSONL parsing and result generation
- Job queue management
- Error handling and retries
"""

import asyncio
import json
import time
import uuid
from typing import List, Optional

from src.config import settings
from src.ollama_backend import OllamaBackend
from src.logger import logger
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
        """Process batch requests using Ollama backend"""
        if not self.backend:
            raise RuntimeError("Ollama backend not initialized")

        results: List[BatchResultLine] = []

        # Process requests sequentially (Ollama doesn't support batching)
        for req in requests:
            try:
                # Call Ollama backend
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

    def _messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """Convert chat messages to a prompt string"""
        # Simple implementation - in production, use model's chat template
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)


# Global batch processor instance
batch_processor = BatchProcessor()

