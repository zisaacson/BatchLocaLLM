"""
Batch processor for vLLM Batch Server

Handles:
- Processing batch jobs using vLLM engine
- JSONL parsing and result generation
- Job queue management
- Error handling and retries
"""

import asyncio
import json
import time
import uuid
from typing import List, Optional

from vllm import LLM, SamplingParams

from src.config import settings
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
    """Processes batch jobs using vLLM engine"""

    def __init__(self) -> None:
        self.llm: Optional[LLM] = None
        self.processing_jobs: set[str] = set()
        self.max_concurrent = settings.max_concurrent_batches

    async def initialize(self) -> None:
        """Initialize vLLM engine"""
        logger.info("Initializing vLLM engine", extra={"model": settings.model_name})

        # Build vLLM engine arguments
        engine_args = {
            "model": settings.model_name,
            "revision": settings.model_revision,
            "tensor_parallel_size": settings.tensor_parallel_size,
            "gpu_memory_utilization": settings.gpu_memory_utilization,
            "max_model_len": settings.max_model_len,
            "dtype": settings.dtype,
            "trust_remote_code": settings.trust_remote_code,
            "max_num_seqs": settings.max_num_seqs,
            "block_size": settings.block_size,
            "swap_space": settings.swap_space_gb,
            "disable_log_stats": settings.disable_log_stats,
            "disable_log_requests": settings.disable_log_requests,
        }

        # Add optional parameters
        if settings.quantization:
            engine_args["quantization"] = settings.quantization

        if settings.enable_prefix_caching:
            engine_args["enable_prefix_caching"] = True

        if settings.enable_chunked_prefill:
            engine_args["enable_chunked_prefill"] = True

        if settings.hf_token:
            engine_args["download_dir"] = None  # Use HF cache
            # Set HF token in environment
            import os

            os.environ["HF_TOKEN"] = settings.hf_token

        # Initialize LLM in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        self.llm = await loop.run_in_executor(None, lambda: LLM(**engine_args))

        logger.info(
            "vLLM engine initialized",
            extra={
                "model": settings.model_name,
                "max_model_len": settings.max_model_len,
                "tensor_parallel_size": settings.tensor_parallel_size,
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
        """Process batch requests using vLLM"""
        if not self.llm:
            raise RuntimeError("vLLM engine not initialized")

        results: List[BatchResultLine] = []

        # Prepare prompts for vLLM
        prompts = []
        sampling_params_list = []

        for req in requests:
            # Convert chat messages to prompt
            # Note: This is a simple implementation. In production, you'd use
            # the model's chat template from tokenizer
            prompt = self._messages_to_prompt(req.body.messages)
            prompts.append(prompt)

            # Create sampling parameters
            max_tokens = req.body.max_completion_tokens or req.body.max_tokens or 1024
            sampling_params = SamplingParams(
                temperature=req.body.temperature or 1.0,
                top_p=req.body.top_p or 1.0,
                max_tokens=max_tokens,
                frequency_penalty=req.body.frequency_penalty or 0.0,
                presence_penalty=req.body.presence_penalty or 0.0,
                stop=req.body.stop,
                n=req.body.n or 1,
            )
            sampling_params_list.append(sampling_params)

        # Run inference in thread pool
        loop = asyncio.get_event_loop()
        outputs = await loop.run_in_executor(
            None, lambda: self.llm.generate(prompts, sampling_params_list)
        )

        # Convert outputs to results
        for req, output in zip(requests, outputs):
            try:
                # Build response
                choices = []
                for i, completion_output in enumerate(output.outputs):
                    choice = ChatCompletionChoice(
                        index=i,
                        message=ChatMessage(role="assistant", content=completion_output.text),
                        finish_reason=completion_output.finish_reason or "stop",
                    )
                    choices.append(choice)

                # Calculate token usage
                prompt_tokens = len(output.prompt_token_ids)
                completion_tokens = sum(len(o.token_ids) for o in output.outputs)

                response = ChatCompletionResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    created=int(time.time()),
                    model=settings.model_name,
                    choices=choices,
                    usage=Usage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                )

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

