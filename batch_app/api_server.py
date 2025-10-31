"""
FastAPI server for batch processing system.

Features:
- Queue limits to prevent overload
- GPU health checks before accepting jobs
- Request validation
"""

from fastapi import FastAPI, UploadFile, File as FastAPIFile, Form, Depends, HTTPException, Body
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import time

from config import settings
from .database import get_db, init_db, BatchJob, FailedRequest, WorkerHeartbeat, File
from .benchmarks import get_benchmark_manager

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Submit and manage large-scale LLM inference batch jobs",
    version=settings.APP_VERSION
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
)

# Data directories (from config)
DATA_DIR = Path(settings.BATCHES_DIR)
INPUT_DIR = Path(settings.INPUT_DIR)
OUTPUT_DIR = Path(settings.OUTPUT_DIR)
LOGS_DIR = Path(settings.LOGS_DIR)
FILES_DIR = Path(settings.FILES_DIR)

# Queue limits (match OpenAI Batch API)
MAX_REQUESTS_PER_JOB = 50000  # Max requests per batch job
MAX_QUEUE_DEPTH = 20  # Max concurrent jobs in queue (supports up to 1M queued requests)
MAX_TOTAL_QUEUED_REQUESTS = 1000000  # Max total requests across all queued jobs (1M = 20 jobs × 50K)


# ============================================================================
# PYDANTIC MODELS (OpenAI API Compatible)
# ============================================================================

class CreateBatchRequest(BaseModel):
    """OpenAI-compatible batch creation request."""
    input_file_id: str = Field(..., description="ID of uploaded input file")
    endpoint: str = Field("/v1/chat/completions", description="API endpoint")
    completion_window: str = Field("24h", description="Completion window")
    metadata: dict[str, any] | None = Field(None, description="Custom metadata")


class CancelBatchRequest(BaseModel):
    """Request to cancel a batch."""
    pass  # No body needed


def check_gpu_health() -> dict:
    """
    Check GPU health before accepting new jobs.
    Now queries Prometheus instead of using pynvml directly.

    Returns:
        dict with 'healthy' (bool), 'reason' (str), 'memory_percent' (float), 'temperature_c' (float)
    """
    try:
        import requests

        prom_url = "http://localhost:4022/api/v1/query"

        # Query GPU temperature from Prometheus
        temp_resp = requests.get(prom_url, params={"query": "nvidia_gpu_temperature_celsius"}, timeout=2)
        temp_data = temp_resp.json()
        temp = None
        if temp_data.get("status") == "success" and temp_data.get("data", {}).get("result"):
            temp = float(temp_data["data"]["result"][0]["value"][1])

        # Query GPU memory from Prometheus
        mem_resp = requests.get(prom_url, params={"query": "nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes * 100"}, timeout=2)
        mem_data = mem_resp.json()
        mem_percent = None
        if mem_data.get("status") == "success" and mem_data.get("data", {}).get("result"):
            mem_percent = float(mem_data["data"]["result"][0]["value"][1])

        # If Prometheus doesn't have GPU metrics, fall back to pynvml
        if temp is None or mem_percent is None:
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                if temp is None:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

                if mem_percent is None:
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    mem_percent = (mem_info.used / mem_info.total) * 100

                pynvml.nvmlShutdown()
            except Exception as e:
                # If both Prometheus and pynvml fail, assume healthy
                return {
                    'healthy': True,
                    'reason': None,
                    'memory_percent': 0,
                    'temperature_c': 0,
                    'warning': f'GPU monitoring unavailable: {e}'
                }

        # Health check
        healthy = mem_percent < 95 and temp < 85
        reason = None
        if mem_percent >= 95:
            reason = f"GPU memory at {mem_percent:.1f}%"
        if temp >= 85:
            reason = f"GPU temperature at {temp}°C"

        return {
            'healthy': healthy,
            'reason': reason,
            'memory_percent': mem_percent,
            'temperature_c': temp
        }
    except Exception as e:
        # If everything fails, assume healthy (for development)
        return {
            'healthy': True,
            'reason': None,
            'memory_percent': 0,
            'temperature_c': 0,
            'warning': f'GPU monitoring unavailable: {e}'
        }


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    print("✅ Batch API Server started")
    print(f"🚀 Server ready at http://{settings.BATCH_API_HOST}:{settings.BATCH_API_PORT}")


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health")
async def health():
    """Basic health check - returns 200 if service is running"""
    return {
        "status": "healthy",
        "service": "batch-api",
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    """Readiness check - verifies database connection and dependencies"""
    try:
        # Check database connection
        db.execute("SELECT 1")

        # Check if data directories exist
        dirs_ok = all([
            INPUT_DIR.exists(),
            OUTPUT_DIR.exists(),
            LOGS_DIR.exists(),
            FILES_DIR.exists()
        ])

        if not dirs_ok:
            raise HTTPException(status_code=503, detail="Data directories not ready")

        return {
            "status": "ready",
            "service": "batch-api",
            "database": "connected",
            "directories": "ok",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


# ============================================================================
# FILES API (OpenAI Compatible)
# ============================================================================

@app.post("/v1/files")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    purpose: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload a file for batch processing (OpenAI Files API compatible).

    Args:
        file: JSONL file to upload
        purpose: Purpose of file (must be "batch")

    Returns:
        File metadata in OpenAI format
    """
    # Validate purpose
    if purpose != "batch":
        raise HTTPException(status_code=400, detail=f"Invalid purpose: {purpose}. Must be 'batch'")

    # Generate file ID
    file_id = f"file-{uuid.uuid4().hex[:24]}"

    # Save file
    file_path = FILES_DIR / f"{file_id}.jsonl"
    content = await file.read()
    file_path.write_bytes(content)

    # Get file size
    file_size = len(content)

    # Create database entry
    created_at = int(time.time())
    db_file = File(
        file_id=file_id,
        object='file',
        bytes=file_size,
        created_at=created_at,
        filename=file.filename or "upload.jsonl",
        purpose=purpose,
        file_path=str(file_path),
        deleted=False
    )
    db.add(db_file)
    db.commit()

    return db_file.to_dict()


@app.get("/v1/files/{file_id}")
async def get_file(file_id: str, db: Session = Depends(get_db)):
    """
    Get file metadata (OpenAI Files API compatible).

    Args:
        file_id: File ID

    Returns:
        File metadata in OpenAI format
    """
    db_file = db.query(File).filter(File.file_id == file_id, File.deleted == False).first()
    if not db_file:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    return db_file.to_dict()


@app.get("/v1/files/{file_id}/content")
async def get_file_content(file_id: str, db: Session = Depends(get_db)):
    """
    Download file content (OpenAI Files API compatible).

    Args:
        file_id: File ID

    Returns:
        File content as JSONL
    """
    db_file = db.query(File).filter(File.file_id == file_id, File.deleted == False).first()
    if not db_file:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    file_path = Path(db_file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File content not found: {file_id}")

    return FileResponse(
        path=str(file_path),
        media_type="application/x-ndjson",
        filename=db_file.filename
    )


@app.delete("/v1/files/{file_id}")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    """
    Delete a file (OpenAI Files API compatible).

    Args:
        file_id: File ID

    Returns:
        Deletion confirmation
    """
    db_file = db.query(File).filter(File.file_id == file_id, File.deleted == False).first()
    if not db_file:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    # Mark as deleted (soft delete)
    db_file.deleted = True
    db.commit()

    # Optionally delete physical file
    try:
        file_path = Path(db_file.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"Warning: Could not delete file {file_path}: {e}")

    return {
        "id": file_id,
        "object": "file.deleted",
        "deleted": True
    }


@app.get("/v1/files")
async def list_files(
    purpose: (str) | None = None,
    db: Session = Depends(get_db)
):
    """
    List all files (OpenAI Files API compatible).

    Args:
        purpose: Filter by purpose (optional)

    Returns:
        List of files in OpenAI format
    """
    query = db.query(File).filter(File.deleted == False)

    if purpose:
        query = query.filter(File.purpose == purpose)

    files = query.order_by(File.created_at.desc()).all()

    return {
        "object": "list",
        "data": [f.to_dict() for f in files]
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    benchmark_mgr = get_benchmark_manager()
    available_models = benchmark_mgr.get_available_models()
    
    return {
        "service": "vLLM Batch Processing API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "submit_batch": "POST /v1/batches",
            "get_batch": "GET /v1/batches/{batch_id}",
            "list_batches": "GET /v1/batches",
            "get_results": "GET /v1/batches/{batch_id}/results",
            "available_models": "GET /v1/models"
        },
        "available_models": available_models
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint with GPU status and queue info.

    Returns:
        System health status including GPU, queue depth, and limits
    """
    # GPU health
    gpu_status = check_gpu_health()

    # Queue status
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['pending', 'running'])
    ).all()

    total_queued_requests = sum(
        j.total_requests - j.completed_requests
        for j in pending_jobs
    )

    # Worker heartbeat
    heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    worker_status = "unknown"
    if heartbeat:
        age = (datetime.utcnow() - heartbeat.last_seen).total_seconds()
        if age < 60:
            worker_status = "healthy"
        else:
            worker_status = "dead"

    return {
        "status": "healthy" if gpu_status['healthy'] and worker_status == "healthy" else "degraded",
        "gpu": {
            "healthy": gpu_status['healthy'],
            "memory_percent": gpu_status.get('memory_percent', 0),
            "temperature_c": gpu_status.get('temperature_c', 0),
            "reason": gpu_status.get('reason'),
            "warning": gpu_status.get('warning')
        },
        "worker": heartbeat.to_dict() if heartbeat else {"status": "unknown"},
        "queue": {
            "active_jobs": len(pending_jobs),
            "max_queue_depth": MAX_QUEUE_DEPTH,
            "queue_available": MAX_QUEUE_DEPTH - len(pending_jobs),
            "total_queued_requests": total_queued_requests,
            "max_queued_requests": MAX_TOTAL_QUEUED_REQUESTS,
            "requests_available": MAX_TOTAL_QUEUED_REQUESTS - total_queued_requests
        },
        "limits": {
            "max_requests_per_job": MAX_REQUESTS_PER_JOB,
            "max_queue_depth": MAX_QUEUE_DEPTH,
            "max_total_queued_requests": MAX_TOTAL_QUEUED_REQUESTS
        }
    }


@app.get("/v1/models")
async def list_models():
    """
    List available models (OpenAI/Parasail compatible).

    Returns model list matching OpenAI Models API format:
    https://platform.openai.com/docs/api-reference/models/list
    """
    benchmark_mgr = get_benchmark_manager()
    data = []

    for model_name in benchmark_mgr.get_available_models():
        model_info = benchmark_mgr.get_model_info(model_name)
        if model_info:
            data.append(model_info)

    # OpenAI/Parasail compatible response format
    return {
        "object": "list",  # OpenAI standard
        "data": data  # OpenAI uses "data" not "models"
    }


@app.get("/metrics")
async def prometheus_metrics(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint.

    Exposes metrics in Prometheus text format for scraping.
    Includes batch job metrics, GPU metrics, and system health.
    """
    from fastapi.responses import PlainTextResponse

    # Collect metrics
    metrics = []

    # Batch job metrics
    total_batches = db.query(BatchJob).count()
    pending_batches = db.query(BatchJob).filter(BatchJob.status == 'validating').count()
    running_batches = db.query(BatchJob).filter(BatchJob.status == 'in_progress').count()
    completed_batches = db.query(BatchJob).filter(BatchJob.status == 'completed').count()
    failed_batches = db.query(BatchJob).filter(BatchJob.status == 'failed').count()
    cancelled_batches = db.query(BatchJob).filter(BatchJob.status == 'cancelled').count()

    metrics.append(f"# HELP vllm_batch_total Total number of batch jobs")
    metrics.append(f"# TYPE vllm_batch_total counter")
    metrics.append(f"vllm_batch_total {total_batches}")

    metrics.append(f"# HELP vllm_batch_status Number of batches by status")
    metrics.append(f"# TYPE vllm_batch_status gauge")
    metrics.append(f'vllm_batch_status{{status="validating"}} {pending_batches}')
    metrics.append(f'vllm_batch_status{{status="in_progress"}} {running_batches}')
    metrics.append(f'vllm_batch_status{{status="completed"}} {completed_batches}')
    metrics.append(f'vllm_batch_status{{status="failed"}} {failed_batches}')
    metrics.append(f'vllm_batch_status{{status="cancelled"}} {cancelled_batches}')

    # Request metrics
    total_requests = db.query(BatchJob).with_entities(
        db.func.sum(BatchJob.total_requests)
    ).scalar() or 0
    completed_requests = db.query(BatchJob).with_entities(
        db.func.sum(BatchJob.completed_requests)
    ).scalar() or 0
    failed_requests_count = db.query(FailedRequest).count()

    metrics.append(f"# HELP vllm_requests_total Total number of requests processed")
    metrics.append(f"# TYPE vllm_requests_total counter")
    metrics.append(f"vllm_requests_total {total_requests}")

    metrics.append(f"# HELP vllm_requests_completed Number of completed requests")
    metrics.append(f"# TYPE vllm_requests_completed counter")
    metrics.append(f"vllm_requests_completed {completed_requests}")

    metrics.append(f"# HELP vllm_requests_failed Number of failed requests")
    metrics.append(f"# TYPE vllm_requests_failed counter")
    metrics.append(f"vllm_requests_failed {failed_requests_count}")

    # Queue metrics
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['validating', 'in_progress'])
    ).all()

    queue_depth = len(pending_jobs)
    total_queued_requests = sum(
        j.total_requests - j.completed_requests
        for j in pending_jobs
    )

    metrics.append(f"# HELP vllm_queue_depth Number of jobs in queue")
    metrics.append(f"# TYPE vllm_queue_depth gauge")
    metrics.append(f"vllm_queue_depth {queue_depth}")

    metrics.append(f"# HELP vllm_queue_requests Number of requests in queue")
    metrics.append(f"# TYPE vllm_queue_requests gauge")
    metrics.append(f"vllm_queue_requests {total_queued_requests}")

    # Worker health
    heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    worker_healthy = 0
    if heartbeat:
        age = (datetime.utcnow() - heartbeat.last_seen).total_seconds()
        worker_healthy = 1 if age < 60 else 0

    metrics.append(f"# HELP vllm_worker_healthy Worker health status (1=healthy, 0=unhealthy)")
    metrics.append(f"# TYPE vllm_worker_healthy gauge")
    metrics.append(f"vllm_worker_healthy {worker_healthy}")

    # GPU metrics (if available)
    gpu_status = check_gpu_health()
    if 'memory_percent' in gpu_status and gpu_status['memory_percent'] > 0:
        metrics.append(f"# HELP vllm_gpu_memory_percent GPU memory utilization percentage")
        metrics.append(f"# TYPE vllm_gpu_memory_percent gauge")
        metrics.append(f"vllm_gpu_memory_percent {gpu_status['memory_percent']}")

        metrics.append(f"# HELP vllm_gpu_temperature_celsius GPU temperature in Celsius")
        metrics.append(f"# TYPE vllm_gpu_temperature_celsius gauge")
        metrics.append(f"vllm_gpu_temperature_celsius {gpu_status['temperature_c']}")

        metrics.append(f"# HELP vllm_gpu_healthy GPU health status (1=healthy, 0=unhealthy)")
        metrics.append(f"# TYPE vllm_gpu_healthy gauge")
        metrics.append(f"vllm_gpu_healthy {1 if gpu_status['healthy'] else 0}")

    # File metrics
    total_files = db.query(File).filter(File.deleted == False).count()
    total_bytes = db.query(File).filter(File.deleted == False).with_entities(
        db.func.sum(File.bytes)
    ).scalar() or 0

    metrics.append(f"# HELP vllm_files_total Total number of uploaded files")
    metrics.append(f"# TYPE vllm_files_total gauge")
    metrics.append(f"vllm_files_total {total_files}")

    metrics.append(f"# HELP vllm_files_bytes Total bytes of uploaded files")
    metrics.append(f"# TYPE vllm_files_bytes gauge")
    metrics.append(f"vllm_files_bytes {total_bytes}")

    return PlainTextResponse("\n".join(metrics) + "\n")


@app.post("/v1/batches")
async def create_batch(
    request: CreateBatchRequest,
    db: Session = Depends(get_db)
):
    """
    Create a batch job (OpenAI Batch API compatible).

    Args:
        request: Batch creation request with input_file_id, endpoint, completion_window, metadata

    Returns:
        Batch job information in OpenAI format

    Raises:
        HTTPException 400: Invalid request
        HTTPException 404: Input file not found
        HTTPException 429: Queue full
        HTTPException 503: GPU unhealthy
    """
    # Check GPU health before accepting job
    gpu_status = check_gpu_health()
    if not gpu_status['healthy']:
        raise HTTPException(
            status_code=503,
            detail=f"GPU unhealthy: {gpu_status['reason']}. Try again later."
        )

    # Validate endpoint
    if request.endpoint != "/v1/chat/completions":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid endpoint: {request.endpoint}. Only /v1/chat/completions is supported."
        )

    # Validate completion_window
    if request.completion_window != "24h":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid completion_window: {request.completion_window}. Only 24h is supported."
        )

    # Get input file
    input_file = db.query(File).filter(
        File.file_id == request.input_file_id,
        File.deleted == False
    ).first()

    if not input_file:
        raise HTTPException(
            status_code=404,
            detail=f"Input file not found: {request.input_file_id}"
        )

    # Check queue depth
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['validating', 'in_progress'])
    ).all()

    if len(pending_jobs) >= MAX_QUEUE_DEPTH:
        raise HTTPException(
            status_code=429,
            detail=f"Queue full ({len(pending_jobs)}/{MAX_QUEUE_DEPTH} jobs). Try again later."
        )

    # Read and validate input file
    input_file_path = Path(input_file.file_path)
    if not input_file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Input file content not found: {request.input_file_id}"
        )

    try:
        content = input_file_path.read_text()
        lines = content.strip().split('\n')

        # Count requests and extract model from first request
        num_requests = 0
        model = None
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    req = json.loads(line)
                    num_requests += 1

                    # Extract model from first request
                    if model is None and 'body' in req and 'model' in req['body']:
                        model = req['body']['model']
                except json.JSONDecodeError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid JSON on line {i+1}: {e}"
                    )

        if num_requests == 0:
            raise HTTPException(status_code=400, detail="No valid requests found in file")

        if not model:
            raise HTTPException(status_code=400, detail="No model specified in requests")

        # Validate job size
        if num_requests > MAX_REQUESTS_PER_JOB:
            raise HTTPException(
                status_code=400,
                detail=f"Too many requests ({num_requests:,}). Maximum is {MAX_REQUESTS_PER_JOB:,} per job."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to validate file: {str(e)}")

    # Generate batch ID
    batch_id = f"batch_{uuid.uuid4().hex[:16]}"

    # Create timestamps
    created_at = int(time.time())
    expires_at = created_at + 86400  # 24 hours

    # Create log file path
    log_file_path = LOGS_DIR / f"{batch_id}.log"

    # Create batch job in database
    batch_job = BatchJob(
        batch_id=batch_id,
        object='batch',
        endpoint=request.endpoint,
        input_file_id=request.input_file_id,
        completion_window=request.completion_window,
        status='validating',
        output_file_id=None,
        error_file_id=None,
        created_at=created_at,
        in_progress_at=None,
        expires_at=expires_at,
        finalizing_at=None,
        completed_at=None,
        failed_at=None,
        expired_at=None,
        cancelling_at=None,
        cancelled_at=None,
        total_requests=num_requests,
        completed_requests=0,
        failed_requests=0,
        errors=None,
        metadata_json=json.dumps(request.metadata) if request.metadata else None,
        model=model,
        log_file=str(log_file_path),
        throughput_tokens_per_sec=None,
        total_tokens=None,
        webhook_url=None,
        webhook_status=None,
        webhook_attempts=0,
        webhook_last_attempt=None,
        webhook_error=None
    )

    db.add(batch_job)
    db.commit()
    db.refresh(batch_job)

    return batch_job.to_dict()


@app.get("/v1/batches/{batch_id}")
async def get_batch(batch_id: str, db: Session = Depends(get_db)):
    """Get batch job status (OpenAI Batch API compatible)."""
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    return batch_job.to_dict()


@app.get("/v1/batches")
async def list_batches(
    limit: int = 20,
    after: (str) | None = None,
    db: Session = Depends(get_db)
):
    """
    List batch jobs (OpenAI Batch API compatible).

    Args:
        limit: Maximum number of results (default 20)
        after: Cursor for pagination (batch_id)
    """
    query = db.query(BatchJob).order_by(BatchJob.created_at.desc())

    if after:
        # Find the batch with this ID and get batches created after it
        after_batch = db.query(BatchJob).filter(BatchJob.batch_id == after).first()
        if after_batch:
            query = query.filter(BatchJob.created_at < after_batch.created_at)

    batches = query.limit(limit + 1).all()

    has_more = len(batches) > limit
    if has_more:
        batches = batches[:limit]

    return {
        "object": "list",
        "data": [batch.to_dict() for batch in batches],
        "first_id": batches[0].batch_id if batches else None,
        "last_id": batches[-1].batch_id if batches else None,
        "has_more": has_more
    }


@app.post("/v1/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Cancel a batch job (OpenAI Batch API compatible).

    Args:
        batch_id: Batch ID to cancel

    Returns:
        Updated batch with status 'cancelling' or 'cancelled'
    """
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    # Can only cancel if not already completed/failed/cancelled
    if batch_job.status in ['completed', 'failed', 'expired', 'cancelled']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel batch with status: {batch_job.status}"
        )

    # Set status to cancelling
    batch_job.status = 'cancelling'
    batch_job.cancelling_at = int(time.time())
    db.commit()
    db.refresh(batch_job)

    return batch_job.to_dict()


@app.get("/v1/batches/{batch_id}/results")
async def get_results(batch_id: str, db: Session = Depends(get_db)):
    """
    Download batch job results (DEPRECATED - use /v1/files/{output_file_id}/content instead).

    This endpoint is kept for backward compatibility.
    """
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    if batch_job.status != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Batch is not completed yet. Current status: {batch_job.status}"
        )

    if not batch_job.output_file_id:
        raise HTTPException(status_code=404, detail="No output file available")

    # Redirect to Files API
    output_file = db.query(File).filter(File.file_id == batch_job.output_file_id).first()
    if not output_file:
        raise HTTPException(status_code=404, detail="Output file not found")

    file_path = Path(output_file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Output file content not found")

    return FileResponse(
        path=str(file_path),
        media_type='application/x-ndjson',
        filename=f"{batch_id}_results.jsonl"
    )


@app.get("/v1/batches/{batch_id}/logs")
async def get_logs(batch_id: str, db: Session = Depends(get_db)):
    """Get batch job logs."""
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    
    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found")
    
    if not batch_job.log_file or not os.path.exists(batch_job.log_file):
        return {"logs": "No logs available yet"}
    
    with open(batch_job.log_file) as f:
        logs = f.read()
    
    return {"logs": logs}


@app.delete("/v1/batches/{batch_id}")
async def cancel_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Cancel a pending batch job.
    Note: Cannot cancel jobs that are already running.
    """
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    
    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found")
    
    if batch_job.status == 'running':
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel a running job. Please contact administrator."
        )
    
    if batch_job.status in ['completed', 'failed']:
        raise HTTPException(
            status_code=400,
            detail=f"Job already {batch_job.status}"
        )
    
    # Mark as failed with cancellation message
    batch_job.status = 'failed'
    batch_job.error_message = 'Cancelled by user'
    batch_job.completed_at = datetime.utcnow()
    db.commit()

    return {"message": f"Batch job '{batch_id}' cancelled", "batch": batch_job.to_dict()}


@app.get("/v1/batches/{batch_id}/failed")
async def get_failed_requests(batch_id: str, db: Session = Depends(get_db)):
    """
    Get failed requests for a batch job (dead letter queue).

    Returns:
        List of failed requests with error details
    """
    # Verify batch exists
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found")

    # Get failed requests
    failed_requests = db.query(FailedRequest).filter(
        FailedRequest.batch_id == batch_id
    ).all()

    return {
        "batch_id": batch_id,
        "failed_count": len(failed_requests),
        "failed_requests": [fr.to_dict() for fr in failed_requests]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4080)
