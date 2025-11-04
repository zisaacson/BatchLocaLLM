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
from typing import Optional, Dict, Any, List, cast

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.batch_app.database import ModelRegistry
from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)

# Global state for tracking active tests
_active_tests = {}  # model_id -> {process, log_file, start_time}


def search_models(
    db: Session,
    query: Optional[str] = None,
    status: Optional[str] = None,
    rtx4080_compatible: Optional[bool] = None,
    min_size_gb: Optional[float] = None,
    max_size_gb: Optional[float] = None,
    min_memory_gb: Optional[float] = None,
    max_memory_gb: Optional[float] = None,
    quantization_type: Optional[str] = None,
    sort_by: str = 'created_at',
    sort_order: str = 'desc',
    limit: int = 100,
    offset: int = 0
):
    """
    Search and filter models with advanced criteria.

    Args:
        db: Database session
        query: Text search in model_id, name, or notes
        status: Filter by status (downloading, ready, failed, etc.)
        rtx4080_compatible: Filter by RTX 4080 compatibility
        min_size_gb: Minimum model size in GB
        max_size_gb: Maximum model size in GB
        min_memory_gb: Minimum GPU memory requirement
        max_memory_gb: Maximum GPU memory requirement
        quantization_type: Filter by quantization (Q4_K_M, Q8_0, F16, etc.)
        sort_by: Field to sort by (created_at, size_gb, name, etc.)
        sort_order: Sort order (asc, desc)
        limit: Maximum results to return
        offset: Offset for pagination

    Returns:
        List of models matching criteria
    """
    # Start with base query
    query_obj = db.query(ModelRegistry)

    # Text search
    if query:
        search_pattern = f"%{query}%"
        query_obj = query_obj.filter(
            (ModelRegistry.model_id.ilike(search_pattern)) |
            (ModelRegistry.name.ilike(search_pattern))
        )

    # Status filter
    if status:
        query_obj = query_obj.filter(ModelRegistry.status == status)

    # RTX 4080 compatibility
    if rtx4080_compatible is not None:
        query_obj = query_obj.filter(ModelRegistry.rtx4080_compatible == rtx4080_compatible)

    # Size filters
    if min_size_gb is not None:
        query_obj = query_obj.filter(ModelRegistry.size_gb >= min_size_gb)
    if max_size_gb is not None:
        query_obj = query_obj.filter(ModelRegistry.size_gb <= max_size_gb)

    # Memory filters
    if min_memory_gb is not None:
        query_obj = query_obj.filter(ModelRegistry.estimated_memory_gb >= min_memory_gb)
    if max_memory_gb is not None:
        query_obj = query_obj.filter(ModelRegistry.estimated_memory_gb <= max_memory_gb)

    # Quantization filter
    if quantization_type:
        query_obj = query_obj.filter(ModelRegistry.quantization_type == quantization_type)

    # Sorting
    sort_field = getattr(ModelRegistry, sort_by, ModelRegistry.created_at)
    if sort_order == 'desc':
        query_obj = query_obj.order_by(sort_field.desc())
    else:
        query_obj = query_obj.order_by(sort_field.asc())

    # Pagination
    query_obj = query_obj.limit(limit).offset(offset)

    # Execute
    models = query_obj.all()

    # Get total count (without pagination)
    total_query = db.query(ModelRegistry)
    if query:
        search_pattern = f"%{query}%"
        total_query = total_query.filter(
            (ModelRegistry.model_id.ilike(search_pattern)) |
            (ModelRegistry.name.ilike(search_pattern))
        )
    if status:
        total_query = total_query.filter(ModelRegistry.status == status)
    if rtx4080_compatible is not None:
        total_query = total_query.filter(ModelRegistry.rtx4080_compatible == rtx4080_compatible)
    if min_size_gb is not None:
        total_query = total_query.filter(ModelRegistry.size_gb >= min_size_gb)
    if max_size_gb is not None:
        total_query = total_query.filter(ModelRegistry.size_gb <= max_size_gb)
    if min_memory_gb is not None:
        total_query = total_query.filter(ModelRegistry.estimated_memory_gb >= min_memory_gb)
    if max_memory_gb is not None:
        total_query = total_query.filter(ModelRegistry.estimated_memory_gb <= max_memory_gb)
    if quantization_type:
        total_query = total_query.filter(ModelRegistry.quantization_type == quantization_type)

    total_count = total_query.count()

    return {
        'models': models,
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(models)) < total_count
    }


def get_model_usage_analytics(db: Session, model_id: Optional[str] = None):
    """
    Get usage analytics for models.

    Args:
        db: Database session
        model_id: Optional model ID to filter by

    Returns:
        Usage analytics including job counts, success rates, avg throughput
    """
    from core.batch_app.database import Benchmark

    # Build query
    query = db.query(Benchmark)
    if model_id:
        query = query.filter(Benchmark.model_id == model_id)

    benchmarks = query.all()

    if not benchmarks:
        return {
            'model_id': model_id,
            'total_jobs': 0,
            'total_requests': 0,
            'success_rate': 0.0,
            'avg_throughput': 0.0,
            'total_runtime_seconds': 0.0
        }

    # Calculate metrics
    total_jobs = len(benchmarks)
    completed_jobs = sum(1 for b in benchmarks if b.status == 'completed')
    failed_jobs = sum(1 for b in benchmarks if b.status == 'failed')
    total_requests = sum(b.total for b in benchmarks if b.total)
    completed_requests = sum(b.completed for b in benchmarks if b.completed)

    # Calculate throughput
    throughputs = [b.throughput for b in benchmarks if b.throughput and b.throughput > 0]
    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0.0

    # Calculate runtime
    total_runtime = 0.0
    for b in benchmarks:
        if b.started_at and b.completed_at:
            runtime = (b.completed_at - b.started_at).total_seconds()
            total_runtime += runtime

    # Success rate
    success_rate = completed_jobs / total_jobs if total_jobs > 0 else 0.0

    # Group by model if no specific model requested
    if not model_id:
        # Get analytics per model
        model_stats: Dict[str, Dict[str, Any]] = {}
        for b in benchmarks:
            if b.model_id not in model_stats:
                model_stats[b.model_id] = {
                    'jobs': 0,
                    'completed': 0,
                    'failed': 0,
                    'requests': 0,
                    'throughputs': [],
                    'runtime': 0.0
                }

            stats = model_stats[b.model_id]
            stats['jobs'] = int(stats['jobs']) + 1
            if b.status == 'completed':
                stats['completed'] = int(stats['completed']) + 1
            elif b.status == 'failed':
                stats['failed'] = int(stats['failed']) + 1
            if b.total:
                stats['requests'] = int(stats['requests']) + b.total
            if b.throughput and b.throughput > 0:
                throughputs_list = cast(List[float], stats['throughputs'])
                throughputs_list.append(b.throughput)
            if b.started_at and b.completed_at:
                stats['runtime'] = float(stats['runtime']) + (b.completed_at - b.started_at).total_seconds()

        # Format results
        by_model: Dict[str, Dict[str, Any]] = {}
        for mid, stats in model_stats.items():
            throughputs_list = cast(List[float], stats['throughputs'])
            avg_tp = sum(throughputs_list) / len(throughputs_list) if throughputs_list else 0.0
            jobs_count = int(stats['jobs'])
            completed_count = int(stats['completed'])
            success = completed_count / jobs_count if jobs_count > 0 else 0.0

            by_model[mid] = {
                'total_jobs': stats['jobs'],
                'completed_jobs': stats['completed'],
                'failed_jobs': stats['failed'],
                'success_rate': success,
                'total_requests': stats['requests'],
                'avg_throughput': avg_tp,
                'total_runtime_seconds': stats['runtime']
            }

        return {
            'total_jobs': total_jobs,
            'total_requests': total_requests,
            'overall_success_rate': success_rate,
            'by_model': by_model
        }

    return {
        'model_id': model_id,
        'total_jobs': total_jobs,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'success_rate': success_rate,
        'total_requests': total_requests,
        'completed_requests': completed_requests,
        'avg_throughput': avg_throughput,
        'total_runtime_seconds': total_runtime
    }


def batch_install_models(db: Session, model_ids: list[str]):
    """
    Install multiple models in sequence.

    Args:
        db: Database session
        model_ids: List of model IDs to install

    Returns:
        Installation status for each model
    """
    from core.batch_app.model_installer import ModelInstaller

    installer = ModelInstaller()
    results = []

    for model_id in model_ids:
        # Check if model exists
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
        if not model:
            results.append({
                'model_id': model_id,
                'status': 'error',
                'message': 'Model not found in registry'
            })
            continue

        # Check if already installed
        if model.status == 'ready':
            results.append({
                'model_id': model_id,
                'status': 'skipped',
                'message': 'Already installed'
            })
            continue

        # Validate pre-installation
        try:
            # Use model registry data for validation
            gguf_file = model.local_path or ''
            estimated_size_gb = model.size_gb

            validation = installer.validate_pre_installation(model_id, gguf_file, estimated_size_gb)
            if not validation['can_install']:
                results.append({
                    'model_id': model_id,
                    'status': 'error',
                    'message': f"Validation failed: {', '.join(validation['errors'])}"
                })
                continue
        except Exception as e:
            results.append({
                'model_id': model_id,
                'status': 'error',
                'message': f'Validation error: {str(e)}'
            })
            continue

        # Start installation
        try:
            installer.install_model(model_id, gguf_file)
            results.append({
                'model_id': model_id,
                'status': 'installing',
                'message': 'Installation started'
            })
        except Exception as e:
            results.append({
                'model_id': model_id,
                'status': 'error',
                'message': f'Installation error: {str(e)}'
            })

    return {
        'total': len(model_ids),
        'results': results,
        'summary': {
            'installing': sum(1 for r in results if r['status'] == 'installing'),
            'skipped': sum(1 for r in results if r['status'] == 'skipped'),
            'errors': sum(1 for r in results if r['status'] == 'error')
        }
    }


def compare_models_dashboard(db: Session, model_ids: list[str]):
    """
    Generate comparison dashboard for multiple models.

    Compares models across:
    - Specifications (size, memory, quantization)
    - Performance (throughput, latency)
    - Usage (job count, success rate)
    - Cost (estimated per request)

    Args:
        db: Database session
        model_ids: List of model IDs to compare

    Returns:
        Comparison data for dashboard
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.cost_tracking import get_model_tier

    comparisons = []

    for model_id in model_ids:
        # Get model info
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
        if not model:
            continue

        # Get benchmarks for this model
        benchmarks = db.query(Benchmark).filter(Benchmark.model_id == model_id).all()

        # Calculate performance metrics
        throughputs = [b.throughput for b in benchmarks if b.throughput and b.throughput > 0]
        avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0.0
        max_throughput = max(throughputs) if throughputs else 0.0
        min_throughput = min(throughputs) if throughputs else 0.0

        # Calculate success rate
        total_jobs = len(benchmarks)
        completed_jobs = sum(1 for b in benchmarks if b.status == 'completed')
        success_rate = completed_jobs / total_jobs if total_jobs > 0 else 0.0

        # Calculate average latency (inverse of throughput)
        avg_latency = 1.0 / avg_throughput if avg_throughput > 0 else 0.0

        # Get cost tier
        tier = get_model_tier(model_id)

        # Estimate cost per 1K requests (assuming 250 input, 150 output tokens)
        from core.batch_app.cost_tracking import DEFAULT_PRICING
        pricing = DEFAULT_PRICING[tier]
        cost_per_request = (250 * pricing['input_per_1m'] / 1_000_000) + (150 * pricing['output_per_1m'] / 1_000_000)
        cost_per_1k = cost_per_request * 1000

        comparisons.append({
            'model_id': model_id,
            'name': model.name,
            'specifications': {
                'size_gb': model.size_gb,
                'estimated_memory_gb': model.estimated_memory_gb,
                'quantization_type': model.quantization_type,
                'max_model_len': model.max_model_len,
                'rtx4080_compatible': model.rtx4080_compatible
            },
            'performance': {
                'avg_throughput': round(avg_throughput, 2),
                'max_throughput': round(max_throughput, 2),
                'min_throughput': round(min_throughput, 2),
                'avg_latency_seconds': round(avg_latency, 3)
            },
            'usage': {
                'total_jobs': total_jobs,
                'completed_jobs': completed_jobs,
                'success_rate': round(success_rate, 3)
            },
            'cost': {
                'tier': tier,
                'cost_per_request': round(cost_per_request, 6),
                'cost_per_1k_requests': round(cost_per_1k, 4),
                'pricing': pricing
            },
            'status': model.status
        })

    # Calculate rankings
    if comparisons:
        # Rank by throughput (higher is better)
        def get_throughput(x: Dict[str, Any]) -> float:
            perf = cast(Dict[str, Any], x.get('performance', {}))
            return float(perf.get('avg_throughput', 0))

        sorted_by_throughput = sorted(comparisons, key=get_throughput, reverse=True)
        for i, comp in enumerate(sorted_by_throughput):
            comp_dict = cast(Dict[str, Any], comp)
            comp_dict['rankings'] = comp_dict.get('rankings', {})
            rankings = cast(Dict[str, Any], comp_dict['rankings'])
            rankings['throughput'] = i + 1

        # Rank by cost (lower is better)
        def get_cost(x: Dict[str, Any]) -> float:
            cost_info = cast(Dict[str, Any], x.get('cost', {}))
            return float(cost_info.get('cost_per_request', 0))

        sorted_by_cost = sorted(comparisons, key=get_cost)
        for i, comp in enumerate(sorted_by_cost):
            comp_dict = cast(Dict[str, Any], comp)
            rankings = cast(Dict[str, Any], comp_dict['rankings'])
            rankings['cost'] = i + 1

        # Rank by success rate (higher is better)
        def get_success_rate(x: Dict[str, Any]) -> float:
            usage = cast(Dict[str, Any], x.get('usage', {}))
            return float(usage.get('success_rate', 0))

        sorted_by_success = sorted(comparisons, key=get_success_rate, reverse=True)
        for i, comp in enumerate(sorted_by_success):
            comp_dict = cast(Dict[str, Any], comp)
            rankings = cast(Dict[str, Any], comp_dict['rankings'])
            rankings['reliability'] = i + 1

        # Calculate overall score (lower is better - sum of ranks)
        for comp in comparisons:
            comp_dict = cast(Dict[str, Any], comp)
            ranks = cast(Dict[str, Any], comp_dict['rankings'])
            ranks['overall_score'] = int(ranks['throughput']) + int(ranks['cost']) + int(ranks['reliability'])

        # Sort by overall score
        def get_overall_score(x: Dict[str, Any]) -> int:
            rankings = cast(Dict[str, Any], x.get('rankings', {}))
            return int(rankings.get('overall_score', 0))

        comparisons.sort(key=get_overall_score)

    # Calculate summary
    fastest_model = None
    cheapest_model = None
    most_reliable_model = None
    best_overall_model = None

    if comparisons:
        fastest_model = cast(Dict[str, Any], comparisons[0]).get('model_id')

        cheapest_comp = min(comparisons, key=get_cost)
        cheapest_model = cast(Dict[str, Any], cheapest_comp).get('model_id')

        most_reliable_comp = max(comparisons, key=get_success_rate)
        most_reliable_model = cast(Dict[str, Any], most_reliable_comp).get('model_id')

        best_overall_model = cast(Dict[str, Any], comparisons[0]).get('model_id')

    return {
        'total_models': len(comparisons),
        'comparisons': comparisons,
        'summary': {
            'fastest': fastest_model,
            'cheapest': cheapest_model,
            'most_reliable': most_reliable_model,
            'best_overall': best_overall_model
        }
    }


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
    process: subprocess.Popen[str] = subprocess.Popen(
        ["python", str(script_path)],
        stdout=open(log_file, 'w'),
        stderr=subprocess.STDOUT,
        cwd=Path.cwd(),
        text=True
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
        process = cast(subprocess.Popen[str], test_info['process'])
        log_file = str(test_info['log_file'])

        # Check if process is still running
        if process.poll() is None:
            # Still running - read log tail
            log_tail = _read_log_tail(log_file, 20)
            num_requests_val = test_info['num_requests']
            num_requests = int(num_requests_val) if isinstance(num_requests_val, (int, str)) else 0
            progress = _estimate_progress(log_tail, num_requests)
            start_time = cast(datetime, test_info['start_time'])

            return ModelTestStatus(
                model_id=model_id,
                status='testing',
                progress=progress,
                log_tail=log_tail,
                started_at=start_time.isoformat()
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
                started_at=cast(datetime, test_info['start_time']).isoformat(),
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
    process: subprocess.Popen[str] = subprocess.Popen(
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
        process = cast(subprocess.Popen[str], proc_info["process"])

        if process.poll() is not None:
            # Process finished
            _active_benchmarks.pop(benchmark_id)
            log_file_obj = cast(Any, proc_info["log_file"])
            log_file_obj.close()

            # Update benchmark status
            benchmark.status = "completed"
            benchmark.completed_at = datetime.now(timezone.utc)
            start_time_val = proc_info["start_time"]
            benchmark.total_time_seconds = time.time() - (float(start_time_val) if isinstance(start_time_val, (int, float)) else 0.0)
            benchmark.progress = 100
            benchmark.completed = benchmark.total

            # Calculate final throughput
            if benchmark.total_time_seconds > 0:
                benchmark.throughput = benchmark.total / benchmark.total_time_seconds

            # Save metadata file
            metadata_path = Path(f"benchmarks/metadata/{benchmark_id}.json")
            metadata_path.parent.mkdir(parents=True, exist_ok=True)

            metadata = {
                "benchmark_id": benchmark_id,
                "model_id": benchmark.model_id,
                "dataset_id": benchmark.dataset_id,
                "total_requests": benchmark.total,
                "completed_requests": benchmark.completed,
                "total_time_seconds": benchmark.total_time_seconds,
                "throughput_req_per_sec": benchmark.throughput,
                "started_at": benchmark.started_at.isoformat(),
                "completed_at": benchmark.completed_at.isoformat(),
                "results_file": benchmark.results_file
            }

            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            benchmark.metadata_file = str(metadata_path)
            db.commit()
        else:
            # Parse log for progress
            log_path = cast(Path, proc_info["log_path"])
            if log_path.exists():
                with open(str(log_path), "r") as f:
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


def cancel_benchmark(benchmark_id: str):
    """
    Cancel a running benchmark.

    Terminates the background process and cleans up resources.
    """
    if benchmark_id not in _active_benchmarks:
        logger.warning(f"Benchmark {benchmark_id} not in active benchmarks")
        return

    proc_info = _active_benchmarks[benchmark_id]
    process = cast(subprocess.Popen[str], proc_info["process"])

    # Terminate process
    if process.poll() is None:
        logger.info(f"Terminating benchmark process {benchmark_id}")
        process.terminate()

        # Wait up to 5 seconds for graceful shutdown
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"Benchmark {benchmark_id} did not terminate gracefully, killing")
            process.kill()
            process.wait()

    # Close log file
    if "log_file" in proc_info and proc_info["log_file"]:
        try:
            log_file_obj = cast(Any, proc_info["log_file"])
            log_file_obj.close()
        except:
            pass

    # Remove from active benchmarks
    _active_benchmarks.pop(benchmark_id)
    logger.info(f"Cancelled benchmark {benchmark_id}")

