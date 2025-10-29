"""
Chunked Batch Processor

Processes large batches by splitting them into context-sized chunks.
Each chunk is processed as a conversation to maximize token caching.

MEASURED LIMITS (from tools/measure_context_limits.py):
- Max context: 128,000 tokens
- VRAM per token: 0.0001 MB (negligible!)
- Optimal chunk size: 111 requests
- Token savings: 99.1%
"""

import time
import uuid
from dataclasses import dataclass

from src.batch_metrics import BatchMetrics
from src.context_manager import ContextConfig, ContextManager, TrimStrategy
from src.logger import logger
from src.models import BatchError, BatchRequestLine, BatchResultLine
from src.ollama_backend import OllamaBackend


@dataclass
class ChunkConfig:
    """Configuration for chunked batch processing"""

    # Measured limits (from measurement tool)
    max_context_tokens: int = 128000  # Full Gemma 3 12B context window
    vram_per_token_mb: float = 0.0001  # Measured: essentially zero!

    # Batch parameters (from Aris use case)
    system_prompt_tokens: int = 2400
    user_message_tokens: int = 600
    assistant_response_tokens: int = 300

    # Safety margins
    context_safety_margin: float = 0.8  # Use 80% of max
    chunk_safety_margin: float = 0.8  # Use 80% of calculated max

    @property
    def tokens_per_exchange(self) -> int:
        """Tokens per user+assistant exchange"""
        return self.user_message_tokens + self.assistant_response_tokens

    @property
    def safe_max_context(self) -> int:
        """Maximum safe context with safety margin"""
        return int(self.max_context_tokens * self.context_safety_margin)

    @property
    def available_for_exchanges(self) -> int:
        """Context available after system prompt"""
        return self.safe_max_context - self.system_prompt_tokens

    @property
    def optimal_chunk_size(self) -> int:
        """Optimal number of requests per chunk"""
        max_exchanges = self.available_for_exchanges // self.tokens_per_exchange
        return int(max_exchanges * self.chunk_safety_margin)

    def chunks_needed(self, total_requests: int) -> int:
        """Calculate number of chunks needed"""
        return (total_requests + self.optimal_chunk_size - 1) // self.optimal_chunk_size

    def update_prompt_size(self, new_prompt_tokens: int) -> None:
        """Recalculate chunk size when prompt changes"""
        old_chunk_size = self.optimal_chunk_size
        self.system_prompt_tokens = new_prompt_tokens
        new_chunk_size = self.optimal_chunk_size

        logger.info(
            f"Prompt size updated: {new_prompt_tokens} tokens. "
            f"Chunk size: {old_chunk_size} → {new_chunk_size} requests"
        )


class ChunkedBatchProcessor:
    """
    Process large batches in context-sized chunks.

    Each chunk is processed as a single conversation to maximize
    token caching benefits while staying within context limits.
    """

    def __init__(self, backend: OllamaBackend, config: ChunkConfig | None = None):
        self.backend = backend
        self.config = config or ChunkConfig()

        # Initialize context manager for monitoring
        self.context_manager = ContextManager(
            ContextConfig(
                max_context_tokens=self.config.max_context_tokens,
                trim_strategy=TrimStrategy.HYBRID,
                enable_vram_monitoring=True,
                enable_adaptive=True,
            )
        )

        logger.info(
            f"Initialized ChunkedBatchProcessor: "
            f"max_context={self.config.max_context_tokens:,}, "
            f"chunk_size={self.config.optimal_chunk_size}"
        )

    def split_into_chunks(
        self,
        requests: list[BatchRequestLine],
        chunk_size: int
    ) -> list[list[BatchRequestLine]]:
        """Split requests into chunks of specified size"""
        chunks = []
        for i in range(0, len(requests), chunk_size):
            chunk = requests[i:i + chunk_size]
            chunks.append(chunk)
        return chunks

    async def process_batch(
        self,
        requests: list[BatchRequestLine]
    ) -> list[BatchResultLine]:
        """
        Process batch in optimal chunks.

        Args:
            requests: List of batch requests to process

        Returns:
            List of batch results
        """
        total_requests = len(requests)
        chunk_size = self.config.optimal_chunk_size
        chunks = self.split_into_chunks(requests, chunk_size)

        logger.info(
            f"Processing {total_requests:,} requests in {len(chunks)} chunks "
            f"of {chunk_size} requests each"
        )

        # Overall batch metrics
        batch_start = time.time()
        all_results = []

        # Process each chunk
        for chunk_idx, chunk in enumerate(chunks):
            chunk_num = chunk_idx + 1
            logger.info(
                f"\n{'='*60}\n"
                f"Processing chunk {chunk_num}/{len(chunks)} "
                f"({len(chunk)} requests)\n"
                f"{'='*60}"
            )

            try:
                chunk_results = await self.process_chunk(chunk, chunk_num)
                all_results.extend(chunk_results)

                # Log progress
                completed = len(all_results)
                pct = (completed / total_requests) * 100
                elapsed = time.time() - batch_start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total_requests - completed) / rate if rate > 0 else 0

                logger.info(
                    f"Batch progress: {completed:,}/{total_requests:,} "
                    f"({pct:.1f}%) | "
                    f"Rate: {rate:.2f} req/s | "
                    f"ETA: {eta/60:.1f} min"
                )

            except Exception as e:
                logger.error(
                    f"Chunk {chunk_num} failed: {e}",
                    exc_info=True
                )
                # Continue with next chunk (don't fail entire batch)
                # Add error results for failed chunk
                for req in chunk:
                    error_result = BatchResultLine(
                        id=f"batch-{uuid.uuid4().hex[:8]}",
                        custom_id=req.custom_id,
                        response=None,
                        error=BatchError(
                            message=f"Chunk processing failed: {str(e)}",
                            type="chunk_error",
                            code="chunk_processing_error"
                        )
                    )
                    all_results.append(error_result)

        # Final summary
        total_time = time.time() - batch_start
        success_count = sum(1 for r in all_results if r.error is None)
        fail_count = len(all_results) - success_count

        logger.info(
            f"\n{'='*60}\n"
            f"BATCH COMPLETE\n"
            f"{'='*60}\n"
            f"Total requests: {total_requests:,}\n"
            f"Successful: {success_count:,}\n"
            f"Failed: {fail_count:,}\n"
            f"Total time: {total_time/60:.1f} minutes\n"
            f"Average rate: {total_requests/total_time:.2f} req/s\n"
            f"Chunks processed: {len(chunks)}\n"
            f"System prompt tokenizations: {len(chunks)} (vs {total_requests:,} naive)\n"
            f"Token savings: {(1 - len(chunks)/total_requests)*100:.1f}%\n"
            f"{'='*60}"
        )

        return all_results

    async def process_chunk(
        self,
        chunk: list[BatchRequestLine],
        chunk_num: int
    ) -> list[BatchResultLine]:
        """
        Process a single chunk as a conversation.

        This is where the token caching magic happens!
        System prompt is tokenized ONCE per chunk, then reused.
        """
        results = []

        # Initialize metrics for this chunk
        metrics = BatchMetrics(
            batch_id=f"chunk-{chunk_num}",
            total_requests=len(chunk)
        )

        # Extract system prompt (should be same for all requests)
        system_msg = None
        for msg in chunk[0].body.messages:
            if msg.role == "system":
                system_msg = msg
                break

        # Estimate system prompt tokens
        system_prompt_tokens = 0
        if system_msg:
            system_prompt_tokens = self.context_manager.estimate_message_tokens(
                [{"role": "system", "content": system_msg.content}]
            )

        # Build conversation
        conversation = []
        if system_msg:
            conversation.append({"role": "system", "content": system_msg.content})

        # Process each request in chunk
        for idx, req in enumerate(chunk):
            request_start_time = time.time()

            try:
                # Extract user message
                user_msg = None
                for msg in req.body.messages:
                    if msg.role == "user":
                        user_msg = msg
                        break

                if not user_msg:
                    raise ValueError("No user message found in request")

                # Add user message to conversation
                conversation.append({"role": "user", "content": user_msg.content})

                # Estimate current context size
                estimated_tokens = self.context_manager.estimate_message_tokens(conversation)
                metrics.update_context(estimated_tokens)

                # Get VRAM usage
                vram_gb = metrics.get_vram_usage()
                if vram_gb:
                    metrics.update_vram(vram_gb)

                # Call Ollama with full conversation
                from src.models import ChatCompletionBody, ChatMessage

                ollama_request = ChatCompletionBody(
                    model=req.body.model,
                    messages=[
                        ChatMessage(role=m["role"], content=m["content"])  # type: ignore[arg-type]
                        for m in conversation
                    ],
                    temperature=req.body.temperature,
                    max_tokens=req.body.max_tokens,
                )

                response = await self.backend.generate_chat_completion(ollama_request)

                # Extract assistant response
                assistant_content = response.choices[0].message.content

                # Add assistant response to conversation
                conversation.append({"role": "assistant", "content": assistant_content})

                # Update metrics
                request_time = time.time() - request_start_time
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0

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
                    response={  # type: ignore[arg-type]
                        "status_code": 200,
                        "request_id": f"req-{uuid.uuid4().hex[:8]}",
                        "body": response.model_dump()
                    },
                    error=None
                )

                results.append(result)

                # Log progress every 10 requests
                if (idx + 1) % 10 == 0:
                    logger.info(
                        f"Chunk {chunk_num} progress: {idx + 1}/{len(chunk)} | "
                        f"Context: {estimated_tokens:,} tokens | "
                        f"VRAM: {vram_gb:.2f} GB" if vram_gb else ""
                    )

            except Exception as e:
                request_time = time.time() - request_start_time
                error_msg = str(e)

                logger.error(
                    f"Request failed in chunk {chunk_num}: {error_msg}",
                    extra={"custom_id": req.custom_id}
                )

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
                        message=error_msg,
                        type="request_error",
                        code="processing_error"
                    )
                )

                results.append(result)

        # Log chunk metrics
        logger.info(f"\nChunk {chunk_num} metrics:\n{metrics.log_summary()}")

        return results

