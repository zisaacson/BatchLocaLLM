"""
FastAPI server for batch processing system.

Features:
- Queue limits to prevent overload
- GPU health checks before accepting jobs
- Request validation
"""

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from .database import get_db, init_db, BatchJob, FailedRequest, WorkerHeartbeat
from .benchmarks import get_benchmark_manager

# Initialize FastAPI app
app = FastAPI(
    title="vLLM Batch Processing API",
    description="Submit and manage large-scale LLM inference batch jobs",
    version="1.0.0"
)

# Data directories
DATA_DIR = Path("data/batches")
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
LOGS_DIR = DATA_DIR / "logs"

# Create directories
for dir_path in [INPUT_DIR, OUTPUT_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Queue limits (match OpenAI Batch API)
MAX_REQUESTS_PER_JOB = 50000  # Max requests per batch job
MAX_QUEUE_DEPTH = 10  # Max concurrent jobs in queue (increased for 170K+ candidates)
MAX_TOTAL_QUEUED_REQUESTS = 500000  # Max total requests across all queued jobs (future-proof)


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
    """List available models with benchmark data."""
    benchmark_mgr = get_benchmark_manager()
    models = []

    for model_name in benchmark_mgr.get_available_models():
        model_info = benchmark_mgr.get_model_info(model_name)
        if model_info:
            models.append(model_info)

    return {
        "models": models,
        "count": len(models)
    }


@app.post("/v1/batches")
async def create_batch(
    file: UploadFile = File(...),
    model: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Submit a new batch job with queue limits and GPU health checks.

    Args:
        file: JSONL file with batch requests
        model: Model to use for inference

    Returns:
        Batch job information with estimated completion time

    Raises:
        HTTPException 400: Invalid request (bad model, too many requests, invalid JSON)
        HTTPException 429: Queue full or too many queued requests
        HTTPException 503: GPU unhealthy
    """
    # Check GPU health before accepting job
    gpu_status = check_gpu_health()
    if not gpu_status['healthy']:
        raise HTTPException(
            status_code=503,
            detail=f"GPU unhealthy: {gpu_status['reason']}. Try again later."
        )

    # Check queue depth
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['pending', 'running'])
    ).all()

    if len(pending_jobs) >= MAX_QUEUE_DEPTH:
        raise HTTPException(
            status_code=429,
            detail=f"Queue full ({len(pending_jobs)}/{MAX_QUEUE_DEPTH} jobs). Try again later."
        )

    # Check total queued requests
    total_queued = sum(
        j.total_requests - j.completed_requests
        for j in pending_jobs
    )

    if total_queued >= MAX_TOTAL_QUEUED_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many queued requests ({total_queued:,}/{MAX_TOTAL_QUEUED_REQUESTS:,}). Try again later."
        )

    # Validate model
    benchmark_mgr = get_benchmark_manager()
    if model not in benchmark_mgr.get_available_models():
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' not found. Available models: {benchmark_mgr.get_available_models()}"
        )

    # Generate batch ID
    batch_id = f"batch_{uuid.uuid4().hex[:16]}"

    # Save uploaded file
    input_file_path = INPUT_DIR / f"{batch_id}.jsonl"

    try:
        # Read and validate JSONL
        content = await file.read()
        lines = content.decode('utf-8').strip().split('\n')

        # Count requests and validate format
        num_requests = 0
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    json.loads(line)
                    num_requests += 1
                except json.JSONDecodeError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid JSON on line {i+1}: {e}"
                    )

        if num_requests == 0:
            raise HTTPException(status_code=400, detail="No valid requests found in file")

        # Validate job size
        if num_requests > MAX_REQUESTS_PER_JOB:
            raise HTTPException(
                status_code=400,
                detail=f"Too many requests ({num_requests:,}). Maximum is {MAX_REQUESTS_PER_JOB:,} per job."
            )
        
        # Save file
        with open(input_file_path, 'wb') as f:
            f.write(content)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(e)}")
    
    # Get performance estimate
    estimate = benchmark_mgr.estimate_completion_time(model, num_requests)
    
    # Create batch job in database
    output_file_path = OUTPUT_DIR / f"{batch_id}_results.jsonl"
    log_file_path = LOGS_DIR / f"{batch_id}.log"
    
    batch_job = BatchJob(
        batch_id=batch_id,
        model=model,
        status='pending',
        input_file=str(input_file_path),
        output_file=str(output_file_path),
        log_file=str(log_file_path),
        total_requests=num_requests,
        completed_requests=0,
        failed_requests=0
    )
    
    db.add(batch_job)
    db.commit()
    db.refresh(batch_job)
    
    # Build response
    response = batch_job.to_dict()
    if estimate:
        response['estimate'] = estimate
    
    return response


@app.get("/v1/batches/{batch_id}")
async def get_batch(batch_id: str, db: Session = Depends(get_db)):
    """Get batch job status and progress."""
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    
    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found")
    
    return batch_job.to_dict()


@app.get("/v1/batches")
async def list_batches(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List batch jobs.
    
    Args:
        status: Filter by status (pending, running, completed, failed)
        limit: Maximum number of results
    """
    query = db.query(BatchJob)
    
    if status:
        query = query.filter(BatchJob.status == status)
    
    query = query.order_by(BatchJob.created_at.desc()).limit(limit)
    
    batches = query.all()
    
    return {
        "batches": [batch.to_dict() for batch in batches],
        "count": len(batches)
    }


@app.get("/v1/batches/{batch_id}/results")
async def get_results(batch_id: str, db: Session = Depends(get_db)):
    """Download batch job results."""
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    
    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found")
    
    if batch_job.status != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Batch job is not completed yet. Current status: {batch_job.status}"
        )
    
    if not batch_job.output_file or not os.path.exists(batch_job.output_file):
        raise HTTPException(status_code=404, detail="Results file not found")
    
    return FileResponse(
        batch_job.output_file,
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
