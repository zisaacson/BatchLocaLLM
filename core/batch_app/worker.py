"""
Background worker for processing batch jobs with vLLM Offline.

Features:
- Intelligent chunking for memory management (5K chunks)
- Incremental saves with resume capability
- Per-request error handling
- GPU health monitoring
"""

import json
import os
import sys
import time
import uuid
import subprocess
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, cast

print("🔄 Worker starting...", flush=True)
print("📦 Importing dependencies...", flush=True)

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

print("✅ SQLAlchemy imported", flush=True)

from vllm import LLM, SamplingParams

print("✅ vLLM imported", flush=True)

from core.config import settings
from core.batch_app.logging_config import get_logger, set_request_context, clear_request_context
from core.batch_app import metrics
from core.batch_app.sentry_config import init_sentry, set_batch_context

print("✅ Core modules imported", flush=True)

from .benchmarks import get_benchmark_manager
from .database import BatchJob, File, SessionLocal, WorkerHeartbeat, ModelRegistry
from .webhooks import send_webhook_async

print("✅ All imports complete", flush=True)

# Initialize logger
logger = get_logger(__name__)
print("✅ Logger initialized", flush=True)

# Configuration (all from settings)
CHUNK_SIZE = settings.CHUNK_SIZE
GPU_MEMORY_UTILIZATION = settings.GPU_MEMORY_UTILIZATION


def check_gpu_health() -> dict:
    """Check GPU health for resource management."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_percent = (mem_info.used / mem_info.total) * 100
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        pynvml.nvmlShutdown()

        return {
            'healthy': mem_percent < settings.GPU_MEMORY_THRESHOLD and temp < settings.GPU_TEMP_THRESHOLD,
            'memory_percent': mem_percent,
            'temperature_c': temp
        }
    except Exception:
        return {'healthy': True, 'memory_percent': 0, 'temperature_c': 0}


def calculate_safe_chunk_size(gpu_status: dict) -> int:
    """Dynamically adjust chunk size based on GPU memory."""
    mem_percent = gpu_status.get('memory_percent', 0)

    if mem_percent < 70:
        return 5000  # Plenty of room
    elif mem_percent < 80:
        return 3000  # Getting full
    elif mem_percent < 90:
        return 1000  # Very full
    else:
        return 500   # Critical


def cleanup_zombie_vllm_processes(log_func: Optional[Callable] = None) -> int:
    """
    Kill zombie vLLM EngineCore processes that are blocking GPU memory.

    vLLM V1 engine has a bug where failed EngineCore subprocesses become zombies
    and hold onto GPU memory indefinitely. This function finds and kills them.

    Returns:
        Number of zombie processes killed
    """
    def log(msg: str):
        if log_func:
            log_func(None, msg)
        else:
            print(msg, flush=True)

    try:
        # Find all vLLM EngineCore processes
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )

        zombie_pids = []
        for line in result.stdout.split('\n'):
            if 'VLLM::EngineCore' in line or 'EngineCore_DP' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        zombie_pids.append(pid)
                    except (ValueError, IndexError):
                        continue

        if zombie_pids:
            log(f"🧹 Found {len(zombie_pids)} zombie vLLM processes: {zombie_pids}")

            for pid in zombie_pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    log(f"  ✅ Killed zombie process {pid}")
                except ProcessLookupError:
                    log(f"  ⚠️  Process {pid} already dead")
                except PermissionError:
                    log(f"  ❌ No permission to kill process {pid}")
                except Exception as e:
                    log(f"  ❌ Failed to kill process {pid}: {e}")

            # Give GPU time to free memory
            time.sleep(3)
            log(f"✅ Zombie cleanup complete, GPU memory should be freed")
            return len(zombie_pids)
        else:
            log("✅ No zombie vLLM processes found")
            return 0

    except Exception as e:
        log(f"⚠️  Failed to cleanup zombies: {e}")
        return 0


class BatchWorker:
    """Background worker that processes batch jobs with chunking and resume capability."""

    def __init__(self, poll_interval: int = 10):
        """
        Initialize batch worker.

        Args:
            poll_interval: Seconds to wait between polling for new jobs
        """
        self.poll_interval = poll_interval
        self.current_llm: LLM | None = None
        self.current_model: str | None = None
        self.benchmark_mgr = get_benchmark_manager()

    def update_heartbeat(self, db: Session, status: str = 'idle', job_id: str | None = None):
        """Update worker heartbeat for health monitoring."""
        try:
            gpu_status = check_gpu_health()

            heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
            if not heartbeat:
                heartbeat = WorkerHeartbeat(id=1)
                db.add(heartbeat)

            heartbeat.last_seen = datetime.now(timezone.utc)
            heartbeat.status = status
            heartbeat.current_job_id = job_id
            heartbeat.loaded_model = self.current_model  # Track what model is loaded
            heartbeat.gpu_memory_percent = gpu_status.get('memory_percent')
            heartbeat.gpu_temperature = gpu_status.get('temperature_c')

            db.commit()
        except Exception as e:
            # Don't fail the worker if heartbeat update fails
            logger.warning("Heartbeat update failed", exc_info=True, extra={"error": str(e)})

    def _should_send_webhook(self, job: BatchJob, event: str) -> bool:
        """
        Check if webhook should be sent for this event.

        Args:
            job: Batch job
            event: Event type (completed, failed, progress)

        Returns:
            True if webhook should be sent, False otherwise
        """
        if not job.webhook_events:
            # No filter configured - send all events
            return True

        # Parse comma-separated events
        subscribed_events = [e.strip() for e in job.webhook_events.split(",")]
        return event in subscribed_events

    def get_next_pending_job(self, db: Session) -> BatchJob | None:
        """
        Get the next pending job from the queue (OpenAI status: validating).

        Jobs are processed in priority order:
        1. High priority (priority=1) - Production jobs
        2. Normal priority (priority=0) - Standard jobs
        3. Low priority (priority=-1) - Testing/benchmarking

        Within each priority level, jobs are processed FIFO (created_at).
        """
        return db.query(BatchJob).filter(
            BatchJob.status == 'validating'
        ).order_by(
            BatchJob.priority.desc(),  # High priority first
            BatchJob.created_at        # Then FIFO
        ).first()

    def count_completed_results(self, output_file: str) -> int:
        """Count how many results have already been saved (for resume capability)."""
        if not os.path.exists(output_file):
            return 0

        try:
            with open(output_file) as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def save_chunk_results(self, outputs, requests, output_file: str, start_idx: int, log_file: str | None):
        """
        Save chunk results incrementally in append mode.

        Args:
            outputs: vLLM outputs for this chunk
            requests: Original requests for this chunk
            output_file: Path to output file
            start_idx: Starting index in original request list
            log_file: Path to log file (optional)
        """
        saved_count = 0

        # Open in append mode
        with open(output_file, 'a') as f:
            for i, output in enumerate(outputs):
                try:
                    # Get original request
                    req = requests[i]

                    # Calculate tokens
                    prompt_tok = len(output.prompt_token_ids)
                    completion_tok = len(output.outputs[0].token_ids)

                    # Format result (OpenAI Batch API compatible)
                    # Generate unique batch result ID
                    batch_result_id = f'batch_req_{uuid.uuid4().hex[:24]}'

                    result = {
                        'id': batch_result_id,  # Unique batch result ID
                        'custom_id': req.get('custom_id', f'request-{start_idx + i}'),
                        'response': {
                            'status_code': 200,
                            'request_id': f'req-{uuid.uuid4().hex[:12]}',
                            'body': {
                                'id': f'chatcmpl-{uuid.uuid4().hex[:12]}',
                                'object': 'chat.completion',
                                'created': int(time.time()),
                                'model': self.current_model,
                                'choices': [{
                                    'index': 0,
                                    'message': {
                                        'role': 'assistant',
                                        'content': output.outputs[0].text
                                    },
                                    'finish_reason': output.outputs[0].finish_reason
                                }],
                                'usage': {
                                    'prompt_tokens': prompt_tok,
                                    'completion_tokens': completion_tok,
                                    'total_tokens': prompt_tok + completion_tok
                                }
                            }
                        },
                        'error': None,
                        # Include input data for Label Studio integration
                        'input': {
                            'messages': req.get('body', {}).get('messages', []),
                            'model': req.get('body', {}).get('model', self.current_model),
                            'temperature': req.get('body', {}).get('temperature'),
                            'max_tokens': req.get('body', {}).get('max_tokens')
                        }
                    }

                    # Write to file
                    f.write(json.dumps(result) + '\n')
                    f.flush()  # Force write to disk immediately
                    saved_count += 1

                except Exception as e:
                    self.log(log_file, f"⚠️  Failed to save result {start_idx + i}: {e}")

        return saved_count

    def load_model(self, model: str, log_file: str | None):
        """
        Load vLLM model if not already loaded.

        Supports:
        - HuggingFace models (model ID)
        - Local GGUF models (from ModelRegistry)
        - CPU offload (from ModelRegistry)
        - Model-specific configs (from ModelRegistry)

        CRITICAL: Model hot-swapping strategy
        ======================================
        When switching models, we MUST:
        1. Delete the LLM object (releases CUDA context)
        2. Run gc.collect() (forces Python garbage collection)
        3. Sleep 3 seconds (gives GPU driver time to free VRAM)

        Without this sequence, GPU memory leaks and causes OOM on next model load.
        The 3-second sleep is empirically determined - shorter delays cause OOM.
        """
        if self.current_model == model and self.current_llm is not None:
            self.log(log_file, f"✅ Model {model} already loaded, reusing")
            return

        self.log(log_file, f"🚀 Loading model: {model}")

        try:
            # CRITICAL: Clean up zombie vLLM processes first
            # ===============================================
            # vLLM V1 engine has a bug where failed EngineCore subprocesses become
            # zombies and hold GPU memory. Kill them before attempting to load.
            self.log(log_file, f"🧹 Checking for zombie vLLM processes...")
            zombies_killed = cleanup_zombie_vllm_processes(self.log)
            if zombies_killed > 0:
                self.log(log_file, f"✅ Killed {zombies_killed} zombie processes, GPU memory freed")

            # CRITICAL: Unload previous model to prevent OOM
            # ================================================
            # vLLM holds GPU memory until explicitly freed. Without this block,
            # loading a second model will OOM even if the first model would fit.
            if self.current_llm is not None:
                self.log(log_file, f"🔄 Unloading previous model: {self.current_model}")
                del self.current_llm
                self.current_llm = None
                self.current_model = None

                # Force garbage collection and give GPU time to free memory
                # The 3-second sleep is REQUIRED - GPU driver needs time to release VRAM
                import gc
                gc.collect()
                time.sleep(3)
                self.log(log_file, f"✅ Previous model unloaded, GPU memory freed")

            # Try to get model config from registry
            db = SessionLocal()
            try:
                model_config = db.query(ModelRegistry).filter(
                    ModelRegistry.model_id == model
                ).first()
            finally:
                db.close()

            # Determine model path and config
            if model_config:
                self.log(log_file, f"📋 Found model config in registry: {model_config.name}")

                # Use local path if available (GGUF), otherwise HuggingFace ID
                model_path = model_config.local_path or model_config.model_id
                max_model_len = model_config.max_model_len
                gpu_mem_util = model_config.gpu_memory_utilization
                cpu_offload = model_config.cpu_offload_gb
                enable_prefix_cache = model_config.enable_prefix_caching
                enable_chunked = model_config.chunked_prefill_enabled

                self.log(log_file, f"  Model path: {model_path}")
                self.log(log_file, f"  Max length: {max_model_len}")
                self.log(log_file, f"  GPU memory: {gpu_mem_util}")
                self.log(log_file, f"  CPU offload: {cpu_offload} GB")

            else:
                # Fallback to defaults for models not in registry
                self.log(log_file, f"⚠️  Model not in registry, using defaults")
                model_path = model
                max_model_len = settings.DEFAULT_MAX_MODEL_LEN
                gpu_mem_util = GPU_MEMORY_UTILIZATION
                cpu_offload = 0.0
                enable_prefix_cache = True
                enable_chunked = True

            # Build vLLM config
            vllm_config = {
                "model": model_path,
                "max_model_len": max_model_len,
                "gpu_memory_utilization": gpu_mem_util,
                "disable_log_stats": True,
                "enable_prefix_caching": enable_prefix_cache,
                "enable_chunked_prefill": enable_chunked,
            }

            # Add CPU offload if needed
            if cpu_offload > 0:
                vllm_config["cpu_offload_gb"] = cpu_offload
                self.log(log_file, f"⚠️  CPU offload enabled: {cpu_offload} GB (will be slower)")

            # Load model with retry logic for GPU memory issues
            start_time = time.time()
            self.log(log_file, f"⏳ Loading model with vLLM...")

            max_retries = 3
            retry_delay = 10  # seconds
            last_error: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                try:
                    self.current_llm = LLM(**cast(Any, vllm_config))

                    load_time = time.time() - start_time
                    self.current_model = model
                    self.log(log_file, f"✅ Model loaded in {load_time:.1f}s (attempt {attempt}/{max_retries})")

                    # Log GPU status after load
                    gpu_status = check_gpu_health()
                    self.log(log_file, f"📊 GPU Memory: {gpu_status.get('memory_percent', 0):.1f}% used")
                    self.log(log_file, f"🌡️  GPU Temp: {gpu_status.get('temperature_c', 0)}°C")

                    # Success! Break out of retry loop
                    break

                except ValueError as e:
                    last_error = e
                    error_msg = str(e)

                    # Check if it's a GPU memory error
                    if "Free memory on device" in error_msg or "not enough memory" in error_msg.lower():
                        if attempt < max_retries:
                            self.log(log_file, f"⚠️  GPU memory error on attempt {attempt}/{max_retries}: {error_msg}")
                            self.log(log_file, f"🧹 Cleaning up zombie processes from failed attempt...")

                            # Kill zombie EngineCore processes from failed attempt
                            cleanup_zombie_vllm_processes(self.log)

                            # Force garbage collection
                            import gc
                            gc.collect()

                            self.log(log_file, f"🔄 Waiting {retry_delay}s before retry...")
                            time.sleep(retry_delay)

                            # Check GPU status
                            gpu_status = check_gpu_health()
                            self.log(log_file, f"📊 GPU Memory before retry: {gpu_status.get('memory_percent', 0):.1f}% used")
                        else:
                            self.log(log_file, f"❌ GPU memory error persists after {max_retries} attempts")
                            # Final cleanup attempt
                            cleanup_zombie_vllm_processes(self.log)
                            raise
                    else:
                        # Not a memory error, don't retry
                        raise

                except Exception as e:
                    # Other errors, don't retry
                    last_error = e
                    # Clean up any zombie processes before failing
                    cleanup_zombie_vllm_processes(self.log)
                    raise

        except Exception as e:
            self.log(log_file, f"❌ Failed to load model: {e}")
            import traceback
            self.log(log_file, f"Traceback: {traceback.format_exc()}")
            raise

    def process_job(self, job: BatchJob, db: Session):
        """Process a single batch job with chunking and resume capability (OpenAI compatible)."""
        log_file = job.log_file
        job_start_time = time.time()

        try:
            # Update status to in_progress (OpenAI format)
            job.status = 'in_progress'
            job.in_progress_at = int(time.time())
            db.commit()

            # Track batch job status change
            metrics.track_batch_job(status='in_progress', model=job.model)
            metrics.batch_jobs_active.labels(status='validating').dec()
            metrics.batch_jobs_active.labels(status='in_progress').inc()

            # Set Sentry context for this batch
            set_batch_context(
                batch_id=job.batch_id,
                model=job.model or "unknown",
                requests=job.total_requests
            )

            # Get input file
            input_file = db.query(File).filter(File.file_id == job.input_file_id).first()
            if not input_file:
                raise Exception(f"Input file not found: {job.input_file_id}")

            input_file_path = input_file.file_path

            # Create output file path
            output_file_path = Path("data/batches/output") / f"{job.batch_id}_results.jsonl"
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            self.log(log_file, "=" * 80)
            self.log(log_file, f"BATCH JOB: {job.batch_id}")
            self.log(log_file, "=" * 80)
            self.log(log_file, f"Model: {job.model}")
            self.log(log_file, f"Input file ID: {job.input_file_id}")
            self.log(log_file, f"Input path: {input_file_path}")
            self.log(log_file, f"Output path: {output_file_path}")
            self.log(log_file, f"Total requests: {job.total_requests}")
            self.log(log_file, f"Chunk size: {CHUNK_SIZE}")
            self.log(log_file, "=" * 80)

            # Validate model is specified
            if not job.model:
                raise Exception("Model not specified in batch job")

            # Load model
            self.load_model(job.model, log_file)

            # Load requests
            self.log(log_file, f"\n📥 Loading requests from {input_file_path}")
            all_requests = []
            with open(input_file_path) as f:
                for line in f:
                    if line.strip():
                        all_requests.append(json.loads(line))

            total_requests = len(all_requests)
            self.log(log_file, f"✅ Loaded {total_requests} requests")

            # Check for resume point
            completed_count = self.count_completed_results(str(output_file_path))
            if completed_count > 0:
                self.log(log_file, f"\n📍 RESUMING from request {completed_count + 1}")
                self.log(log_file, f"Already completed: {completed_count}/{total_requests}")
                all_requests = all_requests[completed_count:]
                job.completed_requests = completed_count
                db.commit()

            # Sampling parameters
            sampling_params = SamplingParams(
                temperature=0.7,
                top_p=0.9,
                max_tokens=settings.DEFAULT_MAX_TOKENS,
            )

            # Process in chunks
            total_inference_time = 0.0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_tokens = 0

            # CRITICAL: Chunking Strategy
            # ============================
            # Process requests in chunks of 100 to:
            # 1. Prevent OOM from loading all prompts into GPU at once
            # 2. Enable incremental saves (lose max 100 requests on crash, not entire batch)
            # 3. Provide progress updates every ~2-5 minutes
            #
            # Why 100?
            # - Small enough to fit in memory (100 * ~800 tokens = 80K tokens)
            # - Large enough for vLLM to batch efficiently (vLLM batches within chunk)
            # - Fast enough for responsive progress updates
            #
            # vLLM's internal batching:
            # - vLLM automatically batches the 100 prompts for parallel processing
            # - We don't need to batch manually - just pass all 100 at once
            num_chunks = (len(all_requests) + CHUNK_SIZE - 1) // CHUNK_SIZE
            self.log(log_file, f"\n⚡ Processing {len(all_requests)} requests in {num_chunks} chunks")
            self.log(log_file, f"vLLM will handle batching within each {CHUNK_SIZE}-request chunk")

            for chunk_idx in range(0, len(all_requests), CHUNK_SIZE):
                chunk_end = min(chunk_idx + CHUNK_SIZE, len(all_requests))
                chunk_requests = all_requests[chunk_idx:chunk_end]
                chunk_num = (chunk_idx // CHUNK_SIZE) + 1

                self.log(log_file, f"\n{'─' * 80}")
                self.log(log_file, f"📦 CHUNK {chunk_num}/{num_chunks}: Requests {completed_count + chunk_idx + 1}-{completed_count + chunk_end}")
                self.log(log_file, f"{'─' * 80}")

                # Extract prompts for this chunk
                chunk_prompts = []
                for req in chunk_requests:
                    messages = req['body']['messages']
                    prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                    chunk_prompts.append(prompt)

                # Run inference on chunk
                self.log(log_file, f"⚡ Running inference on {len(chunk_prompts)} prompts...")
                chunk_start_time = time.time()

                try:
                    # Assert model is loaded (should be guaranteed by load_model above)
                    assert self.current_llm is not None, "Model not loaded"
                    outputs = self.current_llm.generate(chunk_prompts, sampling_params)
                    chunk_inference_time = time.time() - chunk_start_time
                    total_inference_time += chunk_inference_time

                    self.log(log_file, f"✅ Chunk inference complete in {chunk_inference_time:.1f}s ({chunk_inference_time/60:.1f} min)")

                    # Track chunk metrics
                    metrics.chunk_processing_duration.labels(model=job.model).observe(chunk_inference_time)
                    metrics.chunk_size.observe(len(chunk_prompts))
                    metrics.chunks_processed.labels(model=job.model, status='completed').inc()

                    # Calculate chunk tokens
                    chunk_prompt_tokens = sum(len(o.prompt_token_ids) if o.prompt_token_ids else 0 for o in outputs)
                    chunk_completion_tokens = sum(len(o.outputs[0].token_ids) for o in outputs)
                    chunk_total_tokens = chunk_prompt_tokens + chunk_completion_tokens

                    total_prompt_tokens += chunk_prompt_tokens
                    total_completion_tokens += chunk_completion_tokens
                    total_tokens += chunk_total_tokens

                    chunk_throughput = chunk_total_tokens / chunk_inference_time
                    self.log(log_file, f"📊 Chunk throughput: {chunk_throughput:.0f} tokens/sec")

                    # Track token metrics
                    metrics.tokens_generated.labels(model=job.model).inc(chunk_total_tokens)
                    metrics.throughput_tokens_per_second.labels(model=job.model).set(chunk_throughput)

                    # CRITICAL: Incremental Saves
                    # ============================
                    # Save results after EVERY chunk (not just at the end) to prevent data loss.
                    # If worker crashes, we can resume from the last saved chunk.
                    #
                    # Without this, a crash at 4,900/5,000 requests loses ALL work.
                    # With this, we only lose the current chunk (max 100 requests).
                    self.log(log_file, "💾 Saving chunk results...")
                    saved = self.save_chunk_results(
                        outputs,
                        chunk_requests,
                        str(output_file_path),
                        completed_count + chunk_idx,
                        log_file
                    )

                    # Update job progress with real-time stats
                    job.completed_requests += saved
                    job.tokens_processed = total_tokens
                    job.current_throughput = chunk_throughput
                    job.last_progress_update = datetime.now(timezone.utc)

                    # Calculate ETA
                    if chunk_num < num_chunks:
                        avg_time_per_chunk = total_inference_time / chunk_num
                        remaining_chunks = num_chunks - chunk_num
                        est_remaining_seconds = avg_time_per_chunk * remaining_chunks
                        from datetime import timedelta
                        job.estimated_completion_time = datetime.now(timezone.utc) + timedelta(seconds=est_remaining_seconds)

                    db.commit()

                    self.log(log_file, f"✅ Saved {saved} results ({job.completed_requests}/{total_requests} total)")

                    # Estimate time remaining
                    if chunk_num < num_chunks:
                        avg_time_per_chunk = total_inference_time / chunk_num
                        remaining_chunks = num_chunks - chunk_num
                        est_remaining_time = avg_time_per_chunk * remaining_chunks
                        self.log(log_file, f"⏱️  Estimated time remaining: {est_remaining_time/60:.1f} minutes")

                except Exception as e:
                    self.log(log_file, f"❌ Chunk {chunk_num} failed: {e}")
                    # Track chunk failure
                    metrics.chunks_processed.labels(model=job.model, status='failed').inc()
                    raise

            self.log(log_file, "\n✅ All chunks processed successfully!")

            # Calculate final metrics
            throughput = total_tokens / total_inference_time if total_inference_time > 0 else 0
            requests_per_sec = job.completed_requests / total_inference_time if total_inference_time > 0 else 0

            self.log(log_file, "\n" + "=" * 80)
            self.log(log_file, "📊 FINAL RESULTS")
            self.log(log_file, "=" * 80)
            self.log(log_file, f"Total requests:        {total_requests}")
            self.log(log_file, f"Completed:             {job.completed_requests} ({job.completed_requests/total_requests*100:.1f}%)")
            self.log(log_file, f"Inference time:        {total_inference_time:.1f}s ({total_inference_time/60:.1f} minutes)")
            self.log(log_file, f"Prompt tokens:         {total_prompt_tokens:,}")
            self.log(log_file, f"Completion tokens:     {total_completion_tokens:,}")
            self.log(log_file, f"Total tokens:          {total_tokens:,}")
            self.log(log_file, f"Throughput:            {throughput:.0f} tokens/sec")
            self.log(log_file, f"Requests/sec:          {requests_per_sec:.2f}")
            self.log(log_file, "=" * 80)

            # Create output file in Files API
            self.log(log_file, "\n📤 Registering output file...")
            output_file_id = f"file-out-{uuid.uuid4().hex[:20]}"
            output_file_size = output_file_path.stat().st_size if output_file_path.exists() else 0

            output_file_db = File(
                file_id=output_file_id,
                object='file',
                bytes=output_file_size,
                created_at=int(time.time()),
                filename=f"{job.batch_id}_results.jsonl",
                purpose='batch',
                file_path=str(output_file_path),
                deleted=False
            )
            db.add(output_file_db)

            # Update job status to finalizing then completed (OpenAI format)
            job.status = 'finalizing'
            job.finalizing_at = int(time.time())
            db.commit()

            self.log(log_file, f"✅ Output file registered: {output_file_id}")

            # Mark as completed
            job.status = 'completed'
            job.completed_at = int(time.time())
            job.output_file_id = output_file_id
            job.failed_requests = total_requests - job.completed_requests
            job.total_tokens = total_tokens
            job.throughput_tokens_per_sec = int(throughput)
            db.commit()

            # Track batch completion metrics
            job_duration = time.time() - job_start_time
            metrics.track_batch_job(status='completed', model=job.model, duration=job_duration)
            metrics.batch_jobs_active.labels(status='in_progress').dec()
            metrics.batch_jobs_active.labels(status='completed').inc()
            metrics.batch_requests_processed.labels(model=job.model, status='completed').inc(job.completed_requests)
            if job.failed_requests > 0:
                metrics.batch_requests_processed.labels(model=job.model, status='failed').inc(job.failed_requests)

            self.log(log_file, "\n🎉 Batch job completed successfully!")

            # Save benchmark data
            self.save_benchmark(job, total_inference_time)

            # Auto-import to curation system (if enabled)
            self.auto_import_to_curation(job, db, log_file)

            # Send webhook notification (async, non-blocking)
            if job.webhook_url and self._should_send_webhook(job, "completed"):
                self.log(log_file, f"📡 Sending webhook to {job.webhook_url}...")
                send_webhook_async(job.batch_id, job.webhook_url)

        except Exception as e:
            # Mark job as failed (OpenAI format)
            job.status = 'failed'
            job.failed_at = int(time.time())
            job.errors = json.dumps({"message": str(e)})
            db.commit()

            # Track batch failure metrics
            job_duration = time.time() - job_start_time
            metrics.track_batch_job(status='failed', model=job.model, duration=job_duration)
            metrics.batch_jobs_active.labels(status='in_progress').dec()
            metrics.batch_jobs_active.labels(status='failed').inc()
            metrics.track_error(error_type=type(e).__name__, component="worker")

            self.log(log_file, f"\n❌ ERROR: {e}")
            self.log(log_file, "Batch job failed")

            import traceback
            self.log(log_file, traceback.format_exc())

            # Send webhook notification for failure (async, non-blocking)
            if job.webhook_url and self._should_send_webhook(job, "failed"):
                self.log(log_file, f"📡 Sending failure webhook to {job.webhook_url}...")
                send_webhook_async(job.batch_id, job.webhook_url)

    def auto_import_to_curation(self, job: BatchJob, db: Session, log_file: str | None):
        """
        Automatically import batch results to Label Studio for curation.

        This enables viewing all batch results in Label Studio where you can:
        - Review LLM outputs for quality
        - Correct errors in responses
        - Mark gold-star examples for training
        - Export curated datasets (ICL, fine-tuning)
        """
        try:
            # Check if Label Studio is configured
            if not settings.LABEL_STUDIO_URL or not settings.LABEL_STUDIO_API_KEY:
                self.log(log_file, "⏭️  Label Studio not configured (set LABEL_STUDIO_URL and LABEL_STUDIO_API_KEY)")
                return

            if not settings.LABEL_STUDIO_PROJECT_ID:
                self.log(log_file, "⏭️  No Label Studio project configured (set LABEL_STUDIO_PROJECT_ID)")
                return

            self.log(log_file, f"\n📥 Auto-importing to Label Studio at {settings.LABEL_STUDIO_URL}...")

            # Read output file
            output_file = db.query(File).filter(File.file_id == job.output_file_id).first()
            if not output_file:
                self.log(log_file, "⚠️  No output file found, skipping auto-import")
                return

            output_path = Path(output_file.file_path)
            if not output_path.exists():
                self.log(log_file, "⚠️  Output file not found on disk, skipping auto-import")
                return

            # Parse results
            results = []
            with open(output_path) as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))

            self.log(log_file, f"📊 Found {len(results)} results to import")

            # ========================================================================
            # REGISTER DEFAULT HANDLERS
            # ========================================================================
            # Register Label Studio handler if not already registered
            # This ensures backward compatibility with existing code

            from core.result_handlers.base import get_registry
            from core.result_handlers.label_studio import LabelStudioHandler

            registry = get_registry()

            # Check if Label Studio handler is already registered
            has_ls_handler = any(
                isinstance(h, LabelStudioHandler) for h in registry.handlers
            )

            if not has_ls_handler:
                # Register default Label Studio handler
                ls_handler = LabelStudioHandler(config={
                    'url': settings.LABEL_STUDIO_URL,
                    'api_key': settings.LABEL_STUDIO_API_KEY,
                    'project_id': settings.LABEL_STUDIO_PROJECT_ID,
                    'priority': 50  # Run after metadata extraction (priority=10)
                })
                registry.register(ls_handler)
                self.log(log_file, "✅ Registered default Label Studio handler")

            # Prepare metadata
            metadata = json.loads(job.metadata_json) if job.metadata_json else {}
            metadata['label_studio_project_id'] = settings.LABEL_STUDIO_PROJECT_ID
            metadata['batch_id'] = job.batch_id

            # Add completion timestamp
            if job.completed_at:
                from datetime import datetime, timezone
                metadata['completed_at'] = datetime.fromtimestamp(job.completed_at, tz=timezone.utc).isoformat()
            else:
                metadata['completed_at'] = None

            # ========================================================================
            # RESULT HANDLER PIPELINE
            # ========================================================================
            # Execute all registered result handlers (plugins)
            # This allows custom integrations (e.g., metadata extraction, database sync)
            # to be triggered via the plugin system

            # Process results through all registered handlers
            # Handlers run in priority order (lower priority number = runs first)
            # Example handlers:
            # - ConquestMetadataHandler (priority=10) - extracts custom metadata
            # - LabelStudioHandler (priority=50) - imports to Label Studio
            # - AristotleGoldStarHandler (priority=100) - syncs to Aristotle DB

            self.log(log_file, f"📋 Processing batch through {len(registry.handlers)} result handlers")

            success = registry.process_results(job.batch_id, results, metadata)

            if success:
                self.log(log_file, f"✅ Imported {len(results)} tasks to Label Studio")
                self.log(log_file, f"🌐 View at: {settings.LABEL_STUDIO_URL}/projects/{settings.LABEL_STUDIO_PROJECT_ID}")
            else:
                self.log(log_file, f"⚠️  Label Studio import failed (check logs for details)")

        except Exception as e:
            self.log(log_file, f"⚠️  Auto-import error (non-fatal): {e}")
            import traceback
            self.log(log_file, f"   Traceback: {traceback.format_exc()}")
            # Don't fail the job if Label Studio import fails

    def save_benchmark(self, job: BatchJob, processing_time: float):
        """Save benchmark data from completed job."""
        try:
            job_data = {
                'batch_id': job.batch_id,
                'model': job.model,
                'total_requests': job.total_requests,
                'completed_requests': job.completed_requests,
                'failed_requests': job.failed_requests,
                'total_tokens': job.total_tokens,
                'throughput_tokens_per_sec': job.throughput_tokens_per_sec,
                'processing_time_seconds': processing_time,
                'input_file_id': job.input_file_id,
                'output_file_id': job.output_file_id
            }

            self.benchmark_mgr.save_job_benchmark(job_data)
        except Exception as e:
            logger.warning("Failed to save benchmark", extra={"error": str(e), "batch_id": job.batch_id})

    def log(self, log_file: str | None, message: str):
        """
        Write to log file and stdout.

        DEPRECATED: Use logger.info() instead for structured logging.
        This method is kept for backward compatibility with existing log() calls.
        """
        # Parse message to extract emoji and actual message
        # This maintains backward compatibility while using structured logging
        if message.startswith('✅'):
            logger.info(message[2:].strip())
        elif message.startswith('❌'):
            logger.error(message[2:].strip())
        elif message.startswith('⚠️'):
            logger.warning(message[2:].strip())
        elif message.startswith('🚀'):
            logger.info(message[2:].strip())
        elif message.startswith('📋'):
            logger.info(message[2:].strip())
        else:
            logger.info(message)

        # Still write to log file if specified (for backward compatibility)
        if log_file:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            log_message = f"[{timestamp}] {message}"
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(log_message + '\n')

    def run(self):
        """
        Main worker loop with heartbeat monitoring.

        ARCHITECTURE: Separate API + Worker Design
        ===========================================
        The worker is a SEPARATE process from the API server. This design:

        1. API Server (api_server.py):
           - Handles HTTP requests (create batch, check status, download results)
           - Writes jobs to PostgreSQL queue
           - Returns immediately (never blocks on inference)

        2. Worker (this file):
           - Polls PostgreSQL queue every 10 seconds
           - Processes ONE job at a time (sequential, not parallel)
           - Automatically switches models when job.model changes
           - Updates job status in database (API reads this for status checks)

        Why separate processes?
        - API stays responsive (never blocked by slow inference)
        - Worker can crash/restart without affecting API
        - Easy to scale (run multiple workers on different GPUs)
        - Clean separation of concerns

        Why sequential (not parallel)?
        - Consumer GPUs (RTX 4080) can only fit ONE model at a time
        - Loading multiple models causes OOM
        - Model hot-swapping requires sequential processing
        """
        logger.info("=" * 80)
        logger.info("BATCH WORKER STARTED", extra={
            "poll_interval_seconds": self.poll_interval,
            "chunk_size": CHUNK_SIZE,
            "gpu_memory_utilization": GPU_MEMORY_UTILIZATION
        })
        logger.info("=" * 80)
        logger.info("Waiting for jobs...")

        while True:
            try:
                db = SessionLocal()

                # Update heartbeat (idle)
                self.update_heartbeat(db, status='idle')

                # Get next pending job (FIFO queue)
                job = self.get_next_pending_job(db)

                if job:
                    logger.info("Found pending job", extra={"batch_id": job.batch_id})

                    # Set request context for tracing
                    set_request_context(batch_id=job.batch_id)

                    # Update heartbeat (processing)
                    self.update_heartbeat(db, status='processing', job_id=job.batch_id)

                    # Process job (blocks until complete)
                    self.process_job(job, db)

                    # Clear request context
                    clear_request_context()
                else:
                    # No jobs in queue, sleep and poll again
                    time.sleep(self.poll_interval)

                db.close()

            except KeyboardInterrupt:
                logger.info("Worker stopped by user")
                break
            except Exception as e:
                logger.error("Worker error", exc_info=True, extra={"error": str(e)})
                time.sleep(self.poll_interval)


if __name__ == "__main__":
    try:
        # Initialize Sentry error tracking (skip if SENTRY_DSN not set)
        print("🔄 Initializing Sentry...", flush=True)
        try:
            init_sentry()
            print("✅ Sentry initialized", flush=True)
        except Exception as e:
            print(f"⚠️  Sentry init failed (continuing anyway): {e}", flush=True)

        # Test database connection
        print("🔄 Testing database connection...", flush=True)
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Database connection OK", flush=True)

        # Start worker
        print("🔄 Starting batch worker...", flush=True)
        worker = BatchWorker(poll_interval=10)
        print("✅ Worker initialized, starting main loop...", flush=True)
        worker.run()
    except KeyboardInterrupt:
        print("\n⚠️  Worker stopped by user", flush=True)
    except Exception as e:
        print(f"❌ FATAL ERROR during worker startup: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise

