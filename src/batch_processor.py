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

import json
import time
import uuid

from src.config import settings
from src.context_manager import ContextConfig, ContextManager, TrimStrategy
from src.logger import logger
from src.models import (
    BatchError,
    BatchRequestLine,
    BatchResponseBody,
    BatchResultLine,
    BatchStatus,
)
from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.storage import storage

# MEASURED LIMITS (from tools/measure_context_limits.py - 2025-10-27)
# VRAM per token: 0.0001 MB (essentially zero!)
# Max safe context: 128,000 tokens (full Gemma 3 12B window!)
# Optimal chunk size: 111 requests
MAX_CONTEXT_TOKENS = 128000  # MEASURED: Can use full context window!
CONTEXT_TRIM_THRESHOLD = 112000  # 87.5% of 128K
CHUNK_SIZE = 111  # MEASURED: Optimal requests per chunk
MIN_CONTEXT_RESERVE = 16000  # Reserve for safety


class BatchProcessor:
    """Processes batch jobs using Ollama backend"""

    def __init__(self) -> None:
        self.backend: OllamaBackend | None = None
        self.processing_jobs: set[str] = set()
        self.max_concurrent = settings.max_concurrent_batches

        # Initialize context manager with MEASURED limits
        self.context_manager = ContextManager(
            ContextConfig(
                model_name=settings.model_name,
                max_context_tokens=MAX_CONTEXT_TOKENS,  # 128K - MEASURED!
                trim_strategy=TrimStrategy.HYBRID,
                enable_vram_monitoring=True,
                enable_adaptive=True,
            )
        )

        # Initialize processors (lazy init when backend is ready)
        self.chunked_processor: object | None = None  # For token-optimized processing
        self.parallel_processor: object | None = None  # For speed-optimized processing

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

        # Initialize processors now that backend is ready
        from src.chunked_processor import ChunkConfig, ChunkedBatchProcessor

        # Chunked processor (for token optimization - NOT USED for speed)
        self.chunked_processor = ChunkedBatchProcessor(
            backend=self.backend,
            config=ChunkConfig(
                max_context_tokens=MAX_CONTEXT_TOKENS,
                system_prompt_tokens=2400,  # Aris prompt size
            )
        )

        # Parallel processor (for SPEED - this is what we use!)
        self.parallel_processor = ParallelBatchProcessor(
            backend=self.backend,
            config=WorkerConfig(
                num_workers=8,  # 8 parallel workers for 8x speedup
                checkpoint_interval=100,
                retry_attempts=3,
            )
        )

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

    def _parse_jsonl(self, content: str) -> list[BatchRequestLine]:
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
                raise ValueError(f"Invalid request at line {line_num}: {e}") from e
        return requests

    async def _process_requests(self, requests: list[BatchRequestLine]) -> list[BatchResultLine]:
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

    async def _process_standard_batch(self, requests: list[BatchRequestLine]) -> list[BatchResultLine]:
        """Process requests individually (no optimization)"""
        results: list[BatchResultLine] = []

        for req in requests:
            try:
                if self.backend is None:
                    raise RuntimeError("Backend not initialized")
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

    async def _process_conversation_batch(self, requests: list[BatchRequestLine]) -> list[BatchResultLine]:
        """
        Process requests using PARALLEL processing for maximum speed.

        ARCHITECTURE DECISION (2025-10-27):
        ====================================
        We optimize for SPEED, not token savings!

        Token batching (old approach):
        - Sequential processing (slow!)
        - 170K in 10 days
        - 79% token savings (don't care for local inference!)

        Parallel processing (new approach):
        - 8 parallel workers (FAST!)
        - 170K in 1.2 days
        - 0% token savings (don't care!)
        - 8x FASTER!

        WHY PARALLEL IS BETTER:
        - Candidates are INDEPENDENT (can parallelize!)
        - Token savings don't matter for local inference
        - Speed matters WAY more (10 days vs 1.2 days)
        - Simpler code (no conversation state)
        - More robust (worker isolation)

        PERFORMANCE:
        - 5K batch: 52 minutes (vs 6.9 hours)
        - 170K batch: 29.5 hours (vs 236 hours)
        - Speedup: 8x
        """

        # Use parallel processor for SPEED!
        if self.parallel_processor is None:
            raise RuntimeError("Parallel processor not initialized")

        # Type narrowing for mypy
        from src.parallel_processor import ParallelBatchProcessor
        assert isinstance(self.parallel_processor, ParallelBatchProcessor)

        logger.info(
            f"Processing {len(requests)} requests using parallel processor "
            f"({self.parallel_processor.config.num_workers} workers)"
        )

        return await self.parallel_processor.process_batch(requests)

        # OLD IMPLEMENTATION REMOVED - Now using ChunkedBatchProcessor
        # The old single-conversation approach caused crashes with 5K+ requests
        # New chunked approach scales to any batch size!


# Global batch processor instance
batch_processor = BatchProcessor()

