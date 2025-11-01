"""
Model Management API

Handles:
- Adding new models from HuggingFace
- Running background tests
- Tracking download/test progress
- Storing benchmark results
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.batch_app.database import ModelRegistry
from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)

# Global state for tracking active tests
_active_tests = {}  # model_id -> {process, log_file, start_time}


class AddModelRequest(BaseModel):
    """Request to add a new model."""
    model_id: str = Field(..., description="HuggingFace model ID (e.g., 'allenai/OLMo-2-1124-7B-Instruct')")
    name: str = Field(..., description="Display name (e.g., 'OLMo 2 7B')")
    size_gb: float = Field(..., description="Model size in GB")
    estimated_memory_gb: float = Field(..., description="Estimated GPU memory needed")
    max_model_len: int = Field(default=4096, description="Maximum context length")
    gpu_memory_utilization: float = Field(default=0.90, description="GPU memory utilization (0.0-1.0)")
    cpu_offload_gb: float = Field(default=0, description="GB of model weights to offload to CPU RAM (0 = no offload)")
    enable_prefix_caching: bool = Field(default=True)
    chunked_prefill_enabled: bool = Field(default=True)
    rtx4080_compatible: bool = Field(default=True)
    requires_hf_auth: bool = Field(default=False)

    # New fields for easy copy/paste setup
    vllm_serve_command: str | None = Field(default=None, description="Full vLLM serve command (e.g., 'vllm serve google/gemma-3-12b-it-qat-q4_0-gguf')")
    installation_notes: str | None = Field(default=None, description="Installation instructions from HuggingFace (pip install, auth, etc.)")
    huggingface_url: str | None = Field(default=None, description="HuggingFace model page URL")


class TestModelRequest(BaseModel):
    """Request to test a model."""
    num_requests: int = Field(default=1, description="Number of test requests (1, 100, or 5000)")


class RunBenchmarkRequest(BaseModel):
    """Request to run a benchmark on a dataset."""
    model_id: str = Field(..., description="Model ID to benchmark")
    dataset_id: str = Field(..., description="Dataset ID to run on")


class ModelTestStatus(BaseModel):
    """Status of a model test."""
    model_id: str
    status: str  # idle, downloading, testing, completed, failed
    progress: float  # 0.0 to 1.0
    log_tail: list[str]  # Last 20 lines of log
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


def add_model(db: Session, request: AddModelRequest) -> ModelRegistry:
    """Add a new model to the registry."""
    # Check if model already exists
    existing = db.query(ModelRegistry).filter(ModelRegistry.model_id == request.model_id).first()
    if existing:
        raise ValueError(f"Model {request.model_id} already exists")

    # Create new model
    model = ModelRegistry(
        model_id=request.model_id,
        name=request.name,
        size_gb=request.size_gb,
        estimated_memory_gb=request.estimated_memory_gb,
        max_model_len=request.max_model_len,
        gpu_memory_utilization=request.gpu_memory_utilization,
        cpu_offload_gb=request.cpu_offload_gb,
        enable_prefix_caching=request.enable_prefix_caching,
        chunked_prefill_enabled=request.chunked_prefill_enabled,
        rtx4080_compatible=request.rtx4080_compatible,
        requires_hf_auth=request.requires_hf_auth,
        status='untested'
    )

    db.add(model)
    db.commit()
    db.refresh(model)

    logger.info(f"Added model {request.name} ({request.model_id})")
    return model


def start_model_test(db: Session, model_id: str, num_requests: int = 1) -> dict:
    """Start a background test for a model."""
    # Get model from database
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    if not model:
        raise ValueError(f"Model {model_id} not found")

    # Check if already testing
    if model_id in _active_tests:
        raise ValueError(f"Model {model_id} is already being tested")

    # Update status
    model.status = 'testing'
    db.commit()

    # Create log file
    log_dir = Path("logs/model_tests")
    log_dir.mkdir(parents=True, exist_ok=True)

    safe_model_id = model_id.replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{safe_model_id}_{num_requests}req_{timestamp}.log"

    # Create test script dynamically
    test_script = _create_test_script(model, num_requests)
    script_path = log_dir / f"{safe_model_id}_test.py"
    script_path.write_text(test_script)

    # Start background process
    process = subprocess.Popen(
        ["python", str(script_path)],
        stdout=open(log_file, 'w'),
        stderr=subprocess.STDOUT,
        cwd=Path.cwd()
    )

    # Track active test
    _active_tests[model_id] = {
        'process': process,
        'log_file': str(log_file),
        'start_time': datetime.now(timezone.utc),
        'num_requests': num_requests
    }

    logger.info(f"Started test for {model.name} (PID: {process.pid}, {num_requests} requests)")

    return {
        'model_id': model_id,
        'status': 'testing',
        'log_file': str(log_file),
        'pid': process.pid
    }


def get_test_status(db: Session, model_id: str) -> ModelTestStatus:
    """Get the status of a model test."""
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    if not model:
        raise ValueError(f"Model {model_id} not found")

    # Check if test is active
    if model_id in _active_tests:
        test_info = _active_tests[model_id]
        process = test_info['process']
        log_file = test_info['log_file']

        # Check if process is still running
        if process.poll() is None:
            # Still running - read log tail
            log_tail = _read_log_tail(log_file, 20)
            progress = _estimate_progress(log_tail, test_info['num_requests'])

            return ModelTestStatus(
                model_id=model_id,
                status='testing',
                progress=progress,
                log_tail=log_tail,
                started_at=test_info['start_time'].isoformat()
            )
        else:
            # Process finished - check exit code
            exit_code = process.returncode
            log_tail = _read_log_tail(log_file, 20)

            if exit_code == 0:
                # Success - parse results and update database
                _process_test_results(db, model, log_file)
                status = 'completed'
                error = None
            else:
                # Failed
                model.status = 'failed'
                db.commit()
                status = 'failed'
                error = f"Test failed with exit code {exit_code}"

            # Clean up
            del _active_tests[model_id]

            return ModelTestStatus(
                model_id=model_id,
                status=status,
                progress=1.0 if status == 'completed' else 0.0,
                log_tail=log_tail,
                started_at=test_info['start_time'].isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
                error=error
            )

    # No active test - return model status
    return ModelTestStatus(
        model_id=model_id,
        status=model.status,
        progress=0.0 if model.status == 'untested' else 1.0,
        log_tail=[],
        started_at=model.tested_at.isoformat() if model.tested_at else None
    )


def _create_test_script(model: ModelRegistry, num_requests: int) -> str:
    """Generate a test script for the model."""
    # Calculate max_num_seqs based on model size
    # Larger models need fewer concurrent sequences
    if model.estimated_memory_gb >= 14:
        max_num_seqs = 16  # 7B+ models with CPU offload
    elif model.estimated_memory_gb >= 10:
        max_num_seqs = 64  # 4B models
    else:
        max_num_seqs = 128  # Small models

    # Build vLLM kwargs
    vllm_kwargs = f"""
    model=MODEL_ID,
    max_model_len=MAX_MODEL_LEN,
    gpu_memory_utilization=GPU_MEMORY_UTILIZATION,
    max_num_seqs=MAX_NUM_SEQS,
    enable_prefix_caching={str(model.enable_prefix_caching)},
    enable_chunked_prefill={str(model.chunked_prefill_enabled)},
    disable_log_stats=True"""

    # Add CPU offload if configured
    if model.cpu_offload_gb > 0:
        vllm_kwargs += """,
    cpu_offload_gb=CPU_OFFLOAD_GB,
    swap_space=4"""

    return f"""#!/usr/bin/env python3
import sys
import time
from pathlib import Path
from vllm import LLM, SamplingParams

# Test configuration
MODEL_ID = "{model.model_id}"
NUM_REQUESTS = {num_requests}
MAX_MODEL_LEN = {model.max_model_len}
GPU_MEMORY_UTILIZATION = {model.gpu_memory_utilization}
CPU_OFFLOAD_GB = {model.cpu_offload_gb}
MAX_NUM_SEQS = {max_num_seqs}

print("=" * 80)
print(f"Testing {{MODEL_ID}}")
print(f"Requests: {{NUM_REQUESTS}}")
print(f"Max concurrent sequences: {{MAX_NUM_SEQS}}")
if CPU_OFFLOAD_GB > 0:
    print(f"CPU Offload: {{CPU_OFFLOAD_GB}} GB")
print("=" * 80)

# Load model
print("\\n🚀 Loading model...")
start_time = time.time()

llm = LLM({vllm_kwargs}
)

load_time = time.time() - start_time
print(f"✅ Model loaded in {{load_time:.1f}}s")

# Create test prompts
prompts = [f"Write a short story about {{i}}" for i in range(NUM_REQUESTS)]

# Run inference
print(f"\\n🧪 Running {{NUM_REQUESTS}} requests...")
sampling_params = SamplingParams(temperature=0.7, max_tokens=100)

inference_start = time.time()
outputs = llm.generate(prompts, sampling_params)
inference_time = time.time() - inference_start

# Calculate metrics
total_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
tokens_per_sec = total_tokens / inference_time
requests_per_sec = NUM_REQUESTS / inference_time

print(f"\\n📊 Results:")
print(f"   Total time: {{inference_time:.1f}}s")
print(f"   Total tokens: {{total_tokens:,}}")
print(f"   Throughput: {{tokens_per_sec:.1f}} tokens/sec")
print(f"   Throughput: {{requests_per_sec:.2f}} requests/sec")
print(f"   Avg latency: {{(inference_time / NUM_REQUESTS) * 1000:.1f}}ms")

print("\\n✅ Test completed successfully")
"""


def _read_log_tail(log_file: str, num_lines: int = 20) -> list[str]:
    """Read the last N lines from a log file."""
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return [line.rstrip() for line in lines[-num_lines:]]
    except Exception:
        return []


def _estimate_progress(log_tail: list[str], num_requests: int) -> float:
    """Estimate test progress from log output."""
    # Look for progress indicators in log
    for line in reversed(log_tail):
        if "Loading model" in line or "Downloading" in line:
            return 0.2
        if "Model loaded" in line:
            return 0.5
        if "Running" in line and "requests" in line:
            return 0.7
        if "Results:" in line or "completed" in line:
            return 1.0
    return 0.1


def _process_test_results(db: Session, model: ModelRegistry, log_file: str):
    """Parse test results from log and update database."""
    try:
        log_content = Path(log_file).read_text()

        # Extract metrics from log
        results = {}
        for line in log_content.split('\n'):
            if "Throughput:" in line and "tokens/sec" in line:
                tokens_per_sec = float(line.split(':')[1].split('tokens/sec')[0].strip().replace(',', ''))
                results['throughput_tokens_per_sec'] = tokens_per_sec
            elif "Throughput:" in line and "requests/sec" in line:
                requests_per_sec = float(line.split(':')[1].split('requests/sec')[0].strip())
                results['throughput_requests_per_sec'] = requests_per_sec
            elif "Avg latency:" in line:
                latency_ms = float(line.split(':')[1].split('ms')[0].strip())
                results['avg_latency_ms'] = latency_ms

        # Update model
        model.status = 'tested'
        model.tested_at = datetime.now(timezone.utc)
        model.throughput_tokens_per_sec = results.get('throughput_tokens_per_sec')
        model.throughput_requests_per_sec = results.get('throughput_requests_per_sec')
        model.avg_latency_ms = results.get('avg_latency_ms')
        model.test_results = json.dumps(results)

        db.commit()
        logger.info(f"Updated test results for {model.name}")

    except Exception as e:
        logger.error(f"Failed to process test results: {e}")
        model.status = 'failed'
        db.commit()


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

_active_benchmarks = {}  # benchmark_id -> {process, log_file, start_time}


def start_benchmark(benchmark_id: str, model_id: str, dataset_id: str, db: Session):
    """
    Start a benchmark run in the background.

    Creates a Python script that runs vLLM on the dataset and tracks progress.
    """
    from core.batch_app.database import Dataset, Benchmark

    # Get model and dataset
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()

    if not model or not dataset:
        logger.error(f"Model or dataset not found: {model_id}, {dataset_id}")
        return

    # Create benchmark script
    script_path = Path(f"scripts/benchmark_{benchmark_id}.py")
    results_path = Path(f"benchmarks/raw/{benchmark_id}.jsonl")
    log_path = Path(f"logs/benchmark_{benchmark_id}.log")

    # Ensure directories exist
    script_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate script
    script_content = f'''"""
Benchmark: {model.name} on {dataset.name}
Generated: {datetime.now(timezone.utc).isoformat()}
"""

import json
import time
from datetime import datetime
from pathlib import Path
from vllm import LLM, SamplingParams

# Load dataset
dataset_path = Path("{dataset.file_path}")
requests = []
with open(dataset_path, "r") as f:
    for line in f:
        if line.strip():
            requests.append(json.loads(line))

print(f"Loaded {{len(requests)}} requests from {{dataset_path}}")

# Initialize model
print(f"Loading model: {model_id}")
llm = LLM(
    model="{model_id}",
    max_model_len={model.max_model_len},
    gpu_memory_utilization={model.gpu_memory_utilization},
    {"cpu_offload_gb=" + str(model.cpu_offload_gb) + "," if model.cpu_offload_gb > 0 else ""}
    enable_prefix_caching={str(model.enable_prefix_caching)},
    enable_chunked_prefill={str(model.chunked_prefill_enabled)},
)

# Sampling params
sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=1024
)

# Process in batches
batch_size = 100
results_file = Path("{results_path}")
total_batches = (len(requests) + batch_size - 1) // batch_size

print(f"Processing {{len(requests)}} requests in {{total_batches}} batches of {{batch_size}}")

start_time = time.time()
completed = 0

for batch_idx in range(total_batches):
    batch_start = batch_idx * batch_size
    batch_end = min(batch_start + batch_size, len(requests))
    batch = requests[batch_start:batch_end]

    print(f"Processing batch {{batch_idx + 1}}/{{total_batches}} ({{batch_start + 1}}-{{batch_end}})...")

    # Extract prompts
    prompts = []
    for req in batch:
        messages = req["body"]["messages"]
        # Simple prompt construction - can be improved
        prompt = "\\n".join([f"{{m['role']}}: {{m['content']}}" for m in messages])
        prompts.append(prompt)

    # Generate
    batch_start_time = time.time()
    outputs = llm.generate(prompts, sampling_params)
    batch_time = time.time() - batch_start_time

    # Save results
    with open(results_file, "a") as f:
        for req, output in zip(batch, outputs):
            result = {{
                "custom_id": req["custom_id"],
                "request": req,
                "response": {{
                    "status_code": 200,
                    "body": {{
                        "choices": [{{
                            "message": {{
                                "role": "assistant",
                                "content": output.outputs[0].text
                            }}
                        }}]
                    }}
                }}
            }}
            f.write(json.dumps(result) + "\\n")

    completed += len(batch)
    elapsed = time.time() - start_time
    throughput = completed / elapsed if elapsed > 0 else 0

    print(f"Batch complete: {{completed}}/{{len(requests)}} ({{completed/len(requests)*100:.1f}}%) - {{throughput:.1f}} req/s")

total_time = time.time() - start_time
print(f"\\nBenchmark complete!")
print(f"Total time: {{total_time:.1f}}s")
print(f"Throughput: {{len(requests)/total_time:.1f}} req/s")
print(f"Results: {{results_file}}")
'''

    # Write script
    with open(script_path, "w") as f:
        f.write(script_content)

    # Start process
    log_file = open(log_path, "w")
    process = subprocess.Popen(
        ["python", str(script_path)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Track process
    _active_benchmarks[benchmark_id] = {
        "process": process,
        "log_file": log_file,
        "log_path": log_path,
        "results_path": results_path,
        "start_time": time.time()
    }

    # Update benchmark record
    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if benchmark:
        benchmark.results_file = str(results_path)
        db.commit()

    logger.info(f"Started benchmark {benchmark_id}: {model.name} on {dataset.name}")


def get_benchmark_status(benchmark_id: str, db: Session) -> dict:
    """
    Get status of a running benchmark.

    Returns progress, throughput, ETA, etc.
    """
    from core.batch_app.database import Benchmark

    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise ValueError(f"Benchmark {benchmark_id} not found")

    # Check if process is still running
    if benchmark_id in _active_benchmarks:
        proc_info = _active_benchmarks[benchmark_id]
        process = proc_info["process"]

        if process.poll() is not None:
            # Process finished
            _active_benchmarks.pop(benchmark_id)
            proc_info["log_file"].close()

            # Update benchmark status
            benchmark.status = "completed"
            benchmark.completed_at = datetime.now(timezone.utc)
            benchmark.total_time_seconds = time.time() - proc_info["start_time"]
            benchmark.progress = 100
            benchmark.completed = benchmark.total
            db.commit()
        else:
            # Parse log for progress
            log_path = proc_info["log_path"]
            if log_path.exists():
                with open(log_path, "r") as f:
                    lines = f.readlines()

                # Find last progress line
                for line in reversed(lines):
                    if "Batch complete:" in line:
                        # Extract progress: "Batch complete: 500/5000 (10.0%) - 32.5 req/s"
                        try:
                            parts = line.split(":")
                            if len(parts) >= 2:
                                progress_part = parts[1].strip()
                                completed_str = progress_part.split("/")[0].strip()
                                completed = int(completed_str)

                                # Extract throughput
                                if " - " in progress_part:
                                    throughput_str = progress_part.split(" - ")[1].split(" ")[0]
                                    throughput = float(throughput_str)
                                else:
                                    throughput = 0

                                # Update benchmark
                                benchmark.completed = completed
                                benchmark.progress = int((completed / benchmark.total) * 100)
                                benchmark.throughput = throughput

                                # Calculate ETA
                                if throughput > 0:
                                    remaining = benchmark.total - completed
                                    benchmark.eta_seconds = int(remaining / throughput)

                                db.commit()
                                break
                        except Exception as e:
                            logger.error(f"Failed to parse progress: {e}")

    return {
        "benchmark_id": benchmark.id,
        "status": benchmark.status,
        "progress": benchmark.progress,
        "completed": benchmark.completed,
        "total": benchmark.total,
        "throughput": benchmark.throughput,
        "eta_seconds": benchmark.eta_seconds
    }

