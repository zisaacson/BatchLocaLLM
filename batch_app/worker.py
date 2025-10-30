"""
Background worker for processing batch jobs with vLLM Offline.

Features:
- Intelligent chunking for memory management (5K chunks)
- Incremental saves with resume capability
- Per-request error handling
- GPU health monitoring
"""

import time
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from vllm import LLM, SamplingParams

from .database import SessionLocal, BatchJob, FailedRequest, WorkerHeartbeat
from .benchmarks import get_benchmark_manager

# Configuration
CHUNK_SIZE = 5000  # Process 5K requests at a time (proven safe from benchmarks)
GPU_MEMORY_UTILIZATION = 0.85  # Conservative (was 0.90)


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
            'healthy': mem_percent < 95 and temp < 85,
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


class BatchWorker:
    """Background worker that processes batch jobs with chunking and resume capability."""

    def __init__(self, poll_interval: int = 10):
        """
        Initialize batch worker.

        Args:
            poll_interval: Seconds to wait between polling for new jobs
        """
        self.poll_interval = poll_interval
        self.current_llm = None
        self.current_model = None
        self.benchmark_mgr = get_benchmark_manager()

    def update_heartbeat(self, db: Session, status: str = 'idle', job_id: Optional[str] = None):
        """Update worker heartbeat for health monitoring."""
        try:
            gpu_status = check_gpu_health()

            heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
            if not heartbeat:
                heartbeat = WorkerHeartbeat(id=1)
                db.add(heartbeat)

            heartbeat.last_seen = datetime.utcnow()
            heartbeat.status = status
            heartbeat.current_job_id = job_id
            heartbeat.gpu_memory_percent = gpu_status.get('memory_percent')
            heartbeat.gpu_temperature = gpu_status.get('temperature_c')

            db.commit()
        except Exception as e:
            # Don't fail the worker if heartbeat update fails
            print(f"⚠️  Heartbeat update failed: {e}")

    def get_next_pending_job(self, db: Session) -> Optional[BatchJob]:
        """Get the next pending job from the queue."""
        return db.query(BatchJob).filter(
            BatchJob.status == 'pending'
        ).order_by(BatchJob.created_at).first()

    def count_completed_results(self, output_file: str) -> int:
        """Count how many results have already been saved (for resume capability)."""
        if not os.path.exists(output_file):
            return 0

        try:
            with open(output_file) as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def save_chunk_results(self, outputs, requests, output_file: str, start_idx: int, log_file: str):
        """
        Save chunk results incrementally in append mode.

        Args:
            outputs: vLLM outputs for this chunk
            requests: Original requests for this chunk
            output_file: Path to output file
            start_idx: Starting index in original request list
            log_file: Path to log file
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

                    # Format result
                    result = {
                        'id': req.get('custom_id', f'request-{start_idx + i}'),
                        'custom_id': req.get('custom_id', f'request-{start_idx + i}'),
                        'response': {
                            'status_code': 200,
                            'body': {
                                'id': f'chatcmpl-{start_idx + i}',
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
                        'error': None
                    }

                    # Write to file
                    f.write(json.dumps(result) + '\n')
                    f.flush()  # Force write to disk immediately
                    saved_count += 1

                except Exception as e:
                    self.log(log_file, f"⚠️  Failed to save result {start_idx + i}: {e}")

        return saved_count
    
    def load_model(self, model: str, log_file: str):
        """Load vLLM model if not already loaded."""
        if self.current_model == model and self.current_llm is not None:
            self.log(log_file, f"✅ Model {model} already loaded, reusing")
            return
        
        self.log(log_file, f"🚀 Loading model: {model}")
        
        try:
            # Unload previous model if exists
            if self.current_llm is not None:
                self.log(log_file, f"Unloading previous model: {self.current_model}")
                del self.current_llm
                self.current_llm = None
                self.current_model = None
                time.sleep(2)  # Give GPU time to free memory
            
            # Load new model with conservative GPU memory
            start_time = time.time()
            self.current_llm = LLM(
                model=model,
                max_model_len=4096,
                gpu_memory_utilization=GPU_MEMORY_UTILIZATION,  # 0.85 for safety
                disable_log_stats=True,
            )
            load_time = time.time() - start_time
            
            self.current_model = model
            self.log(log_file, f"✅ Model loaded in {load_time:.1f}s")
            
        except Exception as e:
            self.log(log_file, f"❌ Failed to load model: {e}")
            raise
    
    def process_job(self, job: BatchJob, db: Session):
        """Process a single batch job with chunking and resume capability."""
        log_file = job.log_file

        try:
            # Update status to running
            job.status = 'running'
            job.started_at = datetime.utcnow()
            db.commit()

            self.log(log_file, "=" * 80)
            self.log(log_file, f"BATCH JOB: {job.batch_id}")
            self.log(log_file, "=" * 80)
            self.log(log_file, f"Model: {job.model}")
            self.log(log_file, f"Input: {job.input_file}")
            self.log(log_file, f"Output: {job.output_file}")
            self.log(log_file, f"Total requests: {job.total_requests}")
            self.log(log_file, f"Chunk size: {CHUNK_SIZE}")
            self.log(log_file, "=" * 80)

            # Load model
            self.load_model(job.model, log_file)

            # Load requests
            self.log(log_file, f"\n📥 Loading requests from {job.input_file}")
            all_requests = []
            with open(job.input_file) as f:
                for line in f:
                    if line.strip():
                        all_requests.append(json.loads(line))

            total_requests = len(all_requests)
            self.log(log_file, f"✅ Loaded {total_requests} requests")

            # Check for resume point
            completed_count = self.count_completed_results(job.output_file)
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
                max_tokens=2000,
            )

            # Process in chunks
            total_inference_time = 0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_tokens = 0

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
                    outputs = self.current_llm.generate(chunk_prompts, sampling_params)
                    chunk_inference_time = time.time() - chunk_start_time
                    total_inference_time += chunk_inference_time

                    self.log(log_file, f"✅ Chunk inference complete in {chunk_inference_time:.1f}s ({chunk_inference_time/60:.1f} min)")

                    # Calculate chunk tokens
                    chunk_prompt_tokens = sum(len(o.prompt_token_ids) for o in outputs)
                    chunk_completion_tokens = sum(len(o.outputs[0].token_ids) for o in outputs)
                    chunk_total_tokens = chunk_prompt_tokens + chunk_completion_tokens

                    total_prompt_tokens += chunk_prompt_tokens
                    total_completion_tokens += chunk_completion_tokens
                    total_tokens += chunk_total_tokens

                    chunk_throughput = chunk_total_tokens / chunk_inference_time
                    self.log(log_file, f"📊 Chunk throughput: {chunk_throughput:.0f} tokens/sec")

                    # Save chunk results incrementally
                    self.log(log_file, f"💾 Saving chunk results...")
                    saved = self.save_chunk_results(
                        outputs,
                        chunk_requests,
                        job.output_file,
                        completed_count + chunk_idx,
                        log_file
                    )

                    # Update job progress
                    job.completed_requests += saved
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
                    raise

            self.log(log_file, f"\n✅ All chunks processed successfully!")

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

            # Update job in database
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.failed_requests = total_requests - job.completed_requests
            job.total_tokens = total_tokens
            job.throughput_tokens_per_sec = int(throughput)
            db.commit()

            self.log(log_file, "\n🎉 Batch job completed successfully!")

            # Save benchmark data
            self.save_benchmark(job, total_inference_time)
            
        except Exception as e:
            # Mark job as failed
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            db.commit()
            
            self.log(log_file, f"\n❌ ERROR: {e}")
            self.log(log_file, "Batch job failed")
            
            import traceback
            self.log(log_file, traceback.format_exc())
    
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
                'input_file': job.input_file,
                'output_file': job.output_file
            }
            
            self.benchmark_mgr.save_job_benchmark(job_data)
        except Exception as e:
            print(f"⚠️  Failed to save benchmark: {e}")
    
    def log(self, log_file: str, message: str):
        """Write to log file and stdout."""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        print(log_message)
        
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(log_message + '\n')
    
    def run(self):
        """Main worker loop with heartbeat monitoring."""
        print("=" * 80)
        print("🚀 BATCH WORKER STARTED")
        print("=" * 80)
        print(f"Poll interval: {self.poll_interval}s")
        print(f"Chunk size: {CHUNK_SIZE}")
        print(f"GPU memory utilization: {GPU_MEMORY_UTILIZATION}")
        print("Waiting for jobs...")
        print("=" * 80)

        while True:
            try:
                db = SessionLocal()

                # Update heartbeat (idle)
                self.update_heartbeat(db, status='idle')

                # Get next pending job
                job = self.get_next_pending_job(db)

                if job:
                    print(f"\n📋 Found pending job: {job.batch_id}")

                    # Update heartbeat (processing)
                    self.update_heartbeat(db, status='processing', job_id=job.batch_id)

                    self.process_job(job, db)
                else:
                    # No jobs, wait
                    time.sleep(self.poll_interval)
                
                db.close()
                
            except KeyboardInterrupt:
                print("\n\n🛑 Worker stopped by user")
                break
            except Exception as e:
                print(f"❌ Worker error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.poll_interval)


if __name__ == "__main__":
    worker = BatchWorker(poll_interval=10)
    worker.run()

