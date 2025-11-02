"""
FastAPI server for batch processing system.

Features:
- Queue limits to prevent overload
- GPU health checks before accepting jobs
- Request validation
- Request tracing with correlation IDs
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi import File as FastAPIFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio

from core.config import settings
from core.batch_app.logging_config import get_logger, set_request_context, clear_request_context
from core.batch_app import metrics
from core.batch_app.sentry_config import init_sentry

from .benchmarks import get_benchmark_manager
from .database import BatchJob, FailedRequest, File, WorkerHeartbeat, ModelRegistry, WebhookDeadLetter, get_db, init_db, SessionLocal
from models.registry import get_model_registry
from .model_manager import (
    AddModelRequest,
    TestModelRequest,
    RunBenchmarkRequest,
    add_model,
    start_model_test,
    get_test_status
)
from .model_installer import ModelInstaller

# Initialize logger
logger = get_logger(__name__)

# Initialize rate limiter (conditionally enabled)
limiter = Limiter(key_func=get_remote_address, enabled=settings.ENABLE_RATE_LIMITING)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Submit and manage large-scale LLM inference batch jobs",
    version=settings.APP_VERSION
)

# Add rate limit exception handler (only if rate limiting is enabled)
if settings.ENABLE_RATE_LIMITING:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================================================================
# Request Tracing Middleware
# ============================================================================

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request tracing with correlation IDs.

    Generates a unique request_id for each request and adds it to:
    - Response headers (X-Request-ID)
    - Logging context (for structured logs)
    - Metrics labels (for Prometheus)
    """

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Set request context for logging
        set_request_context(request_id=request_id)

        # Add request ID to request state (for access in endpoints)
        request.state.request_id = request_id

        # Log request
        logger.info("Request received", extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None
        })

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Track metrics
            metrics.track_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration=duration
            )

            # Log response
            logger.info("Request completed", extra={
                "status_code": response.status_code,
                "duration_seconds": round(duration, 3)
            })

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response
        except Exception as e:
            duration = time.time() - start_time

            # Track error metrics
            metrics.track_error(
                error_type=type(e).__name__,
                component="api",
                endpoint=request.url.path,
                method=request.method
            )

            logger.error("Request failed", exc_info=True, extra={
                "error": str(e),
                "duration_seconds": round(duration, 3)
            })
            raise
        finally:
            # Clear request context
            clear_request_context()


# Add middlewares
app.add_middleware(RequestTracingMiddleware)

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

# Queue limits (from config - match OpenAI Batch API)
MAX_REQUESTS_PER_JOB = settings.MAX_REQUESTS_PER_JOB
MAX_QUEUE_DEPTH = settings.MAX_QUEUE_DEPTH
MAX_TOTAL_QUEUED_REQUESTS = settings.MAX_TOTAL_QUEUED_REQUESTS


# ============================================================================
# PYDANTIC MODELS (OpenAI API Compatible)
# ============================================================================

class WebhookConfig(BaseModel):
    """Webhook configuration for batch job notifications."""
    url: str = Field(..., description="Webhook URL to receive notifications")
    secret: str | None = Field(None, description="HMAC secret for signature verification")
    max_retries: int | None = Field(None, description="Max retry attempts (default: 3)", ge=1, le=10)
    timeout: int | None = Field(None, description="Request timeout in seconds (default: 30)", ge=5, le=300)
    events: list[str] | None = Field(None, description="Events to subscribe to: completed, failed, progress")


class CreateBatchRequest(BaseModel):
    """
    OpenAI-compatible batch creation request.

    Extended with priority field and webhook configuration:
    - priority: -1 (low/testing), 0 (normal/default), 1 (high/production)
    - webhook: Optional webhook configuration for notifications
    """
    input_file_id: str = Field(..., description="ID of uploaded input file")
    endpoint: str = Field("/v1/chat/completions", description="API endpoint")
    completion_window: str = Field("24h", description="Completion window")
    metadata: dict[str, str] | None = Field(None, description="Custom metadata")
    priority: int = Field(0, description="Job priority: -1 (low), 0 (normal), 1 (high)", ge=-1, le=1)
    webhook: WebhookConfig | None = Field(None, description="Webhook configuration for notifications")


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

        prom_url = f"{settings.PROMETHEUS_URL}/api/v1/query"

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
    """Initialize database and monitoring on startup."""
    # Initialize Sentry error tracking
    init_sentry()

    # Initialize database
    init_db()

    logger.info("Batch API Server started", extra={
        "host": settings.BATCH_API_HOST,
        "port": settings.BATCH_API_PORT,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "sentry_enabled": bool(settings.SENTRY_DSN)
    })
    logger.info(f"Server ready at http://{settings.BATCH_API_HOST}:{settings.BATCH_API_PORT}")


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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    """Readiness check - verifies database connection and dependencies"""
    try:
        # Check database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))

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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}") from e


# ============================================================================
# FILES API (OpenAI Compatible)
# ============================================================================

@app.post("/v1/files")
@limiter.limit(settings.RATE_LIMIT_FILES)  # Rate limit configurable via settings
async def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    purpose: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload a file for batch processing (OpenAI Files API compatible).

    Args:
        request: FastAPI Request object (for rate limiting)
        file: JSONL file to upload
        purpose: Purpose of file (must be "batch")

    Returns:
        File metadata in OpenAI format

    Raises:
        HTTPException 400: Invalid purpose
        HTTPException 429: Rate limit exceeded
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
    db_file = db.query(File).filter(File.file_id == file_id, ~File.deleted).first()
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
    db_file = db.query(File).filter(File.file_id == file_id, ~File.deleted).first()
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
    db_file = db.query(File).filter(File.file_id == file_id, ~File.deleted).first()
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
        logger.warning("Could not delete file", extra={"file_path": str(file_path), "error": str(e)})

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
    query = db.query(File).filter(~File.deleted)

    if purpose:
        query = query.filter(File.purpose == purpose)

    files = query.order_by(File.created_at.desc()).all()

    return {
        "object": "list",
        "data": [f.to_dict() for f in files]
    }


@app.get("/api")
async def api_info():
    """API information endpoint (moved from root to /api)."""
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

    # Update queue metrics
    metrics.update_queue_metrics(len(pending_jobs))

    # Worker heartbeat
    heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    worker_status = "unknown"
    if heartbeat:
        age = (datetime.now(timezone.utc) - heartbeat.last_seen).total_seconds()
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


@app.get("/v1/queue")
async def get_queue_status(db: Session = Depends(get_db)):
    """
    Get current queue status with real-time progress tracking.

    Returns:
    - current_job: Currently processing job with progress, throughput, ETA
    - queue: List of queued jobs with position and estimated start time
    - worker_status: Worker health and current model
    """
    # Get worker status
    worker_heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    worker_status = {
        "status": "offline",
        "current_model": None,
        "last_seen": None
    }

    if worker_heartbeat and worker_heartbeat.last_seen:
        now_utc = datetime.now(timezone.utc)
        last_seen = worker_heartbeat.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        age_seconds = (now_utc - last_seen).total_seconds()
        worker_status = {
            "status": "online" if age_seconds < 60 else "offline",
            "current_model": worker_heartbeat.loaded_model,
            "last_seen": last_seen.isoformat(),
            "age_seconds": int(age_seconds)
        }

    # Get current job (in_progress)
    current_job = db.query(BatchJob).filter(BatchJob.status == 'in_progress').first()
    current_job_data = None

    if current_job:
        # Calculate progress percentage
        progress_pct = (current_job.completed_requests / current_job.total_requests * 100) if current_job.total_requests > 0 else 0

        # Calculate tokens remaining
        tokens_remaining = (current_job.total_tokens or 0) - (current_job.tokens_processed or 0)

        # Calculate ETA
        eta_seconds = None
        eta_iso = None
        if current_job.estimated_completion_time:
            eta_iso = current_job.estimated_completion_time.isoformat()
            eta_seconds = (current_job.estimated_completion_time - datetime.now(timezone.utc)).total_seconds()
            eta_seconds = max(0, eta_seconds)  # Don't show negative

        current_job_data = {
            "batch_id": current_job.batch_id,
            "model": current_job.model,
            "status": current_job.status,
            "progress": {
                "completed_requests": current_job.completed_requests,
                "total_requests": current_job.total_requests,
                "progress_percent": round(progress_pct, 1),
                "tokens_processed": current_job.tokens_processed or 0,
                "tokens_total": current_job.total_tokens or 0,
                "tokens_remaining": tokens_remaining
            },
            "throughput": {
                "current_tokens_per_sec": round(current_job.current_throughput or 0, 1),
                "average_tokens_per_sec": round(current_job.throughput_tokens_per_sec or 0, 1)
            },
            "timing": {
                "started_at": datetime.fromtimestamp(current_job.in_progress_at, tz=timezone.utc).isoformat() if current_job.in_progress_at else None,
                "last_update": current_job.last_progress_update.isoformat() if current_job.last_progress_update else None,
                "estimated_completion": eta_iso,
                "eta_seconds": int(eta_seconds) if eta_seconds is not None else None,
                "eta_minutes": round(eta_seconds / 60, 1) if eta_seconds is not None else None
            }
        }

    # Get queued jobs
    queued_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['validating', 'queued'])
    ).order_by(BatchJob.created_at).all()

    queue_data = []
    cumulative_eta_seconds = current_job_data["timing"]["eta_seconds"] if current_job_data and current_job_data["timing"]["eta_seconds"] else 0

    for idx, job in enumerate(queued_jobs, start=1):
        # Estimate time for this job based on average throughput
        est_time_seconds = None
        if job.total_tokens and current_job and current_job.throughput_tokens_per_sec:
            est_time_seconds = job.total_tokens / current_job.throughput_tokens_per_sec
        elif job.total_requests:
            # Fallback: assume 30 seconds per request
            est_time_seconds = job.total_requests * 30

        # Calculate when this job will start
        starts_in_seconds = cumulative_eta_seconds
        if est_time_seconds:
            cumulative_eta_seconds += est_time_seconds

        queue_data.append({
            "position": idx,
            "batch_id": job.batch_id,
            "model": job.model,
            "status": job.status,
            "total_requests": job.total_requests,
            "total_tokens": job.total_tokens,
            "created_at": datetime.fromtimestamp(job.created_at, tz=timezone.utc).isoformat(),
            "estimated_duration_seconds": int(est_time_seconds) if est_time_seconds else None,
            "estimated_duration_minutes": round(est_time_seconds / 60, 1) if est_time_seconds else None,
            "starts_in_seconds": int(starts_in_seconds),
            "starts_in_minutes": round(starts_in_seconds / 60, 1)
        })

    return {
        "worker": worker_status,
        "current_job": current_job_data,
        "queue": queue_data,
        "queue_length": len(queue_data)
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the documentation hub."""
    index_html_path = Path(__file__).parent / "static" / "index.html"
    if not index_html_path.exists():
        raise HTTPException(status_code=404, detail="Documentation hub not found")

    with open(index_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/queue", response_class=HTMLResponse)
async def queue_monitor():
    """Serve the queue monitoring UI."""
    queue_html_path = Path(__file__).parent / "static" / "queue.html"
    if not queue_html_path.exists():
        raise HTTPException(status_code=404, detail="Queue monitor page not found")

    with open(queue_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve the admin panel UI."""
    admin_html_path = Path(__file__).parent / "static" / "admin.html"
    if not admin_html_path.exists():
        raise HTTPException(status_code=404, detail="Admin panel not found")

    with open(admin_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/static/{filename}")
async def serve_static_file(filename: str):
    """Serve static files (docs, etc.)."""
    # Map of allowed files
    allowed_files = {
        "llm.txt": Path(__file__).parent.parent.parent / "llm.txt",
        "STATUS.md": Path(__file__).parent.parent.parent / "STATUS.md",
        "SYSTEM_MANAGEMENT.md": Path(__file__).parent.parent.parent / "SYSTEM_MANAGEMENT.md",
        "README.md": Path(__file__).parent.parent.parent / "README.md",
    }

    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = allowed_files[filename]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, media_type="text/plain", filename=filename)


@app.get("/config", response_class=HTMLResponse)
async def config_panel():
    """Serve the configuration panel UI."""
    config_html_path = Path(__file__).parent / "static" / "config.html"
    if not config_html_path.exists():
        raise HTTPException(status_code=404, detail="Configuration panel not found")

    with open(config_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/admin/config")
async def get_config():
    """Get current configuration values."""
    return {
        "ENABLE_RATE_LIMITING": settings.ENABLE_RATE_LIMITING,
        "RATE_LIMIT_BATCHES": settings.RATE_LIMIT_BATCHES,
        "RATE_LIMIT_FILES": settings.RATE_LIMIT_FILES,
        "GPU_MEMORY_UTILIZATION": settings.GPU_MEMORY_UTILIZATION,
        "GPU_MEMORY_THRESHOLD": settings.GPU_MEMORY_THRESHOLD,
        "GPU_TEMP_THRESHOLD": settings.GPU_TEMP_THRESHOLD,
        "CHUNK_SIZE": settings.CHUNK_SIZE,
        "WORKER_POLL_INTERVAL": settings.WORKER_POLL_INTERVAL,
    }


@app.post("/admin/config")
async def update_config(config_updates: dict):
    """
    Update configuration values at runtime.

    Changes are applied immediately but do NOT persist after server restart.
    To make changes permanent, update your .env file.
    """
    allowed_keys = {
        "ENABLE_RATE_LIMITING",
        "RATE_LIMIT_BATCHES",
        "RATE_LIMIT_FILES",
        "GPU_MEMORY_UTILIZATION",
        "GPU_MEMORY_THRESHOLD",
        "GPU_TEMP_THRESHOLD",
        "CHUNK_SIZE",
        "WORKER_POLL_INTERVAL",
    }

    updated = {}
    for key, value in config_updates.items():
        if key not in allowed_keys:
            raise HTTPException(status_code=400, detail=f"Cannot update config key: {key}")

        # Update the settings object
        setattr(settings, key, value)
        updated[key] = value

        logger.info(f"Configuration updated: {key} = {value}")

    # If rate limiting was toggled, we need to restart the server for it to take effect
    if "ENABLE_RATE_LIMITING" in updated:
        logger.warning(
            "Rate limiting toggle requires server restart to take full effect. "
            "Please restart the API server."
        )

    return {
        "status": "success",
        "message": "Configuration updated successfully",
        "updated": updated,
        "note": "Changes are active now but will be lost on server restart. Update .env file to persist."
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

    Uses prometheus_client for automatic metric collection and formatting.
    """
    from fastapi.responses import PlainTextResponse
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    # Update batch job active metrics
    validating_count = db.query(BatchJob).filter(BatchJob.status == 'validating').count()
    in_progress_count = db.query(BatchJob).filter(BatchJob.status == 'in_progress').count()
    completed_count = db.query(BatchJob).filter(BatchJob.status == 'completed').count()
    failed_count = db.query(BatchJob).filter(BatchJob.status == 'failed').count()
    cancelled_count = db.query(BatchJob).filter(BatchJob.status == 'cancelled').count()

    metrics.batch_jobs_active.labels(status='validating').set(validating_count)
    metrics.batch_jobs_active.labels(status='in_progress').set(in_progress_count)
    metrics.batch_jobs_active.labels(status='completed').set(completed_count)
    metrics.batch_jobs_active.labels(status='failed').set(failed_count)
    metrics.batch_jobs_active.labels(status='cancelled').set(cancelled_count)

    # Update queue metrics
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['validating', 'in_progress'])
    ).all()
    metrics.update_queue_metrics(len(pending_jobs))

    # Update GPU metrics (if available)
    gpu_status = check_gpu_health()
    if 'memory_percent' in gpu_status and gpu_status['memory_percent'] > 0:
        # Convert percentage to bytes (approximate)
        # This is a simplified calculation - actual implementation would need GPU info
        metrics.update_gpu_metrics(
            gpu_id="0",
            memory_used=int(gpu_status.get('memory_percent', 0) * 1024 * 1024 * 1024 / 100),  # Rough estimate
            memory_total=1024 * 1024 * 1024,  # Placeholder
            temperature=gpu_status.get('temperature_c', 0),
            utilization=gpu_status.get('memory_percent', 0)
        )

    # Generate Prometheus metrics in text format
    prometheus_metrics = generate_latest()

    # Also include legacy metrics for backward compatibility
    # Return prometheus_client generated metrics
    # This includes all the metrics we've registered plus automatic process metrics
    return PlainTextResponse(
        prometheus_metrics.decode('utf-8'),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/v1/batches")
@limiter.limit(settings.RATE_LIMIT_BATCHES)  # Rate limit configurable via settings
async def create_batch(
    request: Request,
    batch_request: CreateBatchRequest,
    db: Session = Depends(get_db)
):
    """
    Create a batch job (OpenAI Batch API compatible).

    The API accepts jobs up to MAX_QUEUE_DEPTH (20 jobs). The worker processes
    jobs sequentially (one at a time) to prevent OOM on single-GPU systems.

    Args:
        request: FastAPI Request object (for rate limiting)
        batch_request: Batch creation request with input_file_id, endpoint, completion_window, metadata

    Returns:
        Batch job information in OpenAI format

    Raises:
        HTTPException 400: Invalid request
        HTTPException 404: Input file not found
        HTTPException 429: Queue full (20+ jobs queued)
        HTTPException 503: Worker offline or GPU unhealthy
    """
    # Check GPU health before accepting job
    gpu_status = check_gpu_health()
    if not gpu_status['healthy']:
        raise HTTPException(
            status_code=503,
            detail=f"GPU unhealthy: {gpu_status['reason']}. Try again later."
        )

    # Check worker status - ensure worker is alive
    worker_heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    if worker_heartbeat:
        # Check if worker is alive (heartbeat within last 60 seconds)
        if worker_heartbeat.last_seen:
            # Make sure both datetimes are timezone-aware for comparison
            now_utc = datetime.now(timezone.utc)
            last_seen = worker_heartbeat.last_seen
            if last_seen.tzinfo is None:
                # If last_seen is naive, assume it's UTC
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            age_seconds = (now_utc - last_seen).total_seconds()
            if age_seconds > 60:
                raise HTTPException(
                    status_code=503,
                    detail=f"Worker offline (last seen {int(age_seconds)}s ago). Cannot accept jobs."
                )

        # NOTE: We do NOT check if worker is busy processing
        # The worker processes jobs sequentially (one at a time) to prevent OOM on RTX 4080
        # But the API should accept jobs up to MAX_QUEUE_DEPTH (20 jobs)
        # Queue depth check below is sufficient to prevent resource exhaustion

    # Validate endpoint
    if batch_request.endpoint != "/v1/chat/completions":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid endpoint: {batch_request.endpoint}. Only /v1/chat/completions is supported."
        )

    # Validate completion_window
    if batch_request.completion_window != "24h":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid completion_window: {batch_request.completion_window}. Only 24h is supported."
        )

    # Get input file
    input_file = db.query(File).filter(
        File.file_id == batch_request.input_file_id,
        ~File.deleted
    ).first()

    if not input_file:
        raise HTTPException(
            status_code=404,
            detail=f"Input file not found: {batch_request.input_file_id}"
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
            detail=f"Input file content not found: {batch_request.input_file_id}"
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
                    ) from e

        if num_requests == 0:
            raise HTTPException(status_code=400, detail="No valid requests found in file")

        if not model:
            raise HTTPException(status_code=400, detail="No model specified in requests")

        # Validate model exists in database registry and is compatible
        model_config = db.query(ModelRegistry).filter(ModelRegistry.model_id == model).first()
        if not model_config:
            available_models = db.query(ModelRegistry).all()
            available_ids = [m.model_id for m in available_models]
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model: {model}. Available models: {', '.join(available_ids)}"
            )

        # Check if model is compatible with RTX 4080
        if not model_config.rtx4080_compatible:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model} requires {model_config.estimated_memory_gb}GB GPU memory. RTX 4080 has 16GB."
            )

        # Validate job size
        if num_requests > MAX_REQUESTS_PER_JOB:
            raise HTTPException(
                status_code=400,
                detail=f"Too many requests ({num_requests:,}). Maximum is {MAX_REQUESTS_PER_JOB:,} per job."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to validate file: {str(e)}") from e

    # Generate batch ID
    batch_id = f"batch_{uuid.uuid4().hex[:16]}"

    # Create timestamps
    created_at = int(time.time())
    expires_at = created_at + (settings.BATCH_EXPIRY_HOURS * 3600)  # Convert hours to seconds

    # Create log file path
    log_file_path = LOGS_DIR / f"{batch_id}.log"

    # Create batch job in database
    batch_job = BatchJob(
        batch_id=batch_id,
        object='batch',
        endpoint=batch_request.endpoint,
        input_file_id=batch_request.input_file_id,
        completion_window=batch_request.completion_window,
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
        metadata_json=json.dumps(batch_request.metadata) if batch_request.metadata else None,
        model=model,
        log_file=str(log_file_path),
        throughput_tokens_per_sec=None,
        total_tokens=None,
        priority=batch_request.priority,  # Priority queue support
        webhook_url=batch_request.webhook.url if batch_request.webhook else None,
        webhook_status=None,
        webhook_attempts=0,
        webhook_last_attempt=None,
        webhook_error=None,
        webhook_secret=batch_request.webhook.secret if batch_request.webhook else None,
        webhook_max_retries=batch_request.webhook.max_retries if batch_request.webhook else None,
        webhook_timeout=batch_request.webhook.timeout if batch_request.webhook else None,
        webhook_events=",".join(batch_request.webhook.events) if batch_request.webhook and batch_request.webhook.events else None
    )

    db.add(batch_job)
    db.commit()
    db.refresh(batch_job)

    # Track batch job creation metrics
    metrics.track_batch_job(status='validating', model=model)
    metrics.batch_jobs_active.labels(status='validating').inc()

    # Set batch context for logging
    set_request_context(batch_id=batch_id)
    logger.info("Batch job created", extra={
        "batch_id": batch_id,
        "model": model,
        "total_requests": num_requests
    })

    return batch_job.to_dict()


@app.get("/v1/batches/{batch_id}")
async def get_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Get batch job status (OpenAI Batch API compatible).

    Extended with queue visibility:
    - queue_position: Position in queue (1 = next to process)
    - estimated_start_time: When job is expected to start processing
    - estimated_completion_time: When job is expected to complete
    """
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    # Get base response
    response = batch_job.to_dict()

    # Add queue visibility for queued jobs
    if batch_job.status == 'validating':
        # Calculate queue position (1-based)
        queue_position = db.query(BatchJob).filter(
            BatchJob.status == 'validating',
            BatchJob.created_at < batch_job.created_at
        ).count() + 1

        response['queue_position'] = queue_position

        # Estimate start time based on current job progress
        current_job = db.query(BatchJob).filter(
            BatchJob.status == 'in_progress'
        ).first()

        if current_job and current_job.estimated_completion_time:
            # Current job has ETA, use it as base
            estimated_start = current_job.estimated_completion_time
        else:
            # No current job or no ETA, assume immediate start
            estimated_start = datetime.now(timezone.utc)

        # Add estimated time for jobs ahead in queue
        # Rough estimate: 2 minutes per job (conservative)
        jobs_ahead = queue_position - 1
        if jobs_ahead > 0:
            estimated_start += timedelta(minutes=2 * jobs_ahead)

        response['estimated_start_time'] = estimated_start.isoformat()

        # Estimate completion time (start + job duration)
        # Use total_requests to estimate duration (rough: 100 req/min)
        if batch_job.total_requests:
            estimated_duration_minutes = max(1, batch_job.total_requests / 100)
            estimated_completion = estimated_start + timedelta(minutes=estimated_duration_minutes)
            response['estimated_completion_time'] = estimated_completion.isoformat()

    elif batch_job.status == 'in_progress':
        # Job is currently processing
        response['queue_position'] = 0  # 0 = currently processing

        if batch_job.estimated_completion_time:
            response['estimated_completion_time'] = batch_job.estimated_completion_time.isoformat()

    return response


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


# ============================================================================
# MODEL MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/admin/models")
async def list_models_admin(db: Session = Depends(get_db)):
    """
    List all models in the registry (admin endpoint).

    Returns:
        List of models with their status, test results, and benchmarks
    """
    models = db.query(ModelRegistry).order_by(ModelRegistry.created_at).all()
    return {
        "models": [model.to_dict() for model in models],
        "count": len(models)
    }


@app.get("/admin/models/{model_id:path}")
async def get_model_admin(model_id: str, db: Session = Depends(get_db)):
    """
    Get a specific model by ID (admin endpoint).

    Args:
        model_id: HuggingFace model ID (e.g., 'allenai/OLMo-2-1124-7B-Instruct')

    Returns:
        Model details with test results and benchmarks
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return model.to_dict()


@app.post("/admin/models")
async def create_model_admin(request: AddModelRequest, db: Session = Depends(get_db)):
    """
    Add a new model to the registry (admin endpoint).

    Args:
        request: Model configuration (HuggingFace ID, name, size, etc.)

    Returns:
        Created model details

    Raises:
        HTTPException 400: Model already exists or invalid configuration
    """
    try:
        model = add_model(db, request)
        return model.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/models/{model_id:path}/test")
async def test_model_admin(
    model_id: str,
    request: TestModelRequest,
    db: Session = Depends(get_db)
):
    """
    Start a background test for a model (admin endpoint).

    Args:
        model_id: HuggingFace model ID
        request: Test configuration (number of requests)

    Returns:
        Test status with log file location and PID

    Raises:
        HTTPException 400: Model not found or already testing
    """
    try:
        result = start_model_test(db, model_id, request.num_requests)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/models/{model_id:path}/status")
async def get_model_test_status_admin(model_id: str, db: Session = Depends(get_db)):
    """
    Get the status of a model test (admin endpoint).

    Args:
        model_id: HuggingFace model ID

    Returns:
        Test status with progress, log tail, and results
    """
    try:
        status = get_test_status(db, model_id)
        return status.dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/admin/models/{model_id:path}")
async def delete_model_admin(model_id: str, db: Session = Depends(get_db)):
    """
    Delete a model from the registry (admin endpoint).

    Args:
        model_id: HuggingFace model ID

    Returns:
        Success message

    Raises:
        HTTPException 404: Model not found
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    db.delete(model)
    db.commit()

    logger.info(f"Deleted model {model.name} ({model_id})")
    return {"message": f"Model '{model_id}' deleted successfully"}


# ============================================================================
# WORKBENCH API ENDPOINTS
# ============================================================================

@app.post("/admin/datasets/upload")
async def upload_dataset(file: UploadFile, db: Session = Depends(get_db)):
    """
    Upload a dataset (JSONL file) for benchmarking.

    Args:
        file: JSONL file with batch requests

    Returns:
        Dataset metadata
    """
    import uuid
    from pathlib import Path

    # Generate dataset ID
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"

    # Save file
    datasets_dir = Path("data/datasets")
    datasets_dir.mkdir(parents=True, exist_ok=True)

    file_path = datasets_dir / f"{dataset_id}_{file.filename}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Count requests
    count = 0
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                count += 1

    # Create dataset record
    from core.batch_app.database import Dataset

    dataset = Dataset(
        id=dataset_id,
        name=file.filename,
        file_path=str(file_path),
        count=count,
        uploaded_at=datetime.now(timezone.utc)
    )

    db.add(dataset)
    db.commit()

    logger.info(f"Uploaded dataset {file.filename} ({count} requests)")

    return {
        "dataset_id": dataset_id,
        "name": file.filename,
        "count": count,
        "uploaded_at": dataset.uploaded_at.isoformat()
    }


@app.get("/admin/datasets")
async def list_datasets(db: Session = Depends(get_db)):
    """
    List all uploaded datasets.

    Returns:
        List of datasets with metadata
    """
    from core.batch_app.database import Dataset

    datasets = db.query(Dataset).order_by(Dataset.uploaded_at.desc()).all()

    return {
        "datasets": [
            {
                "id": ds.id,
                "name": ds.name,
                "count": ds.count,
                "uploaded_at": ds.uploaded_at.isoformat()
            }
            for ds in datasets
        ]
    }


@app.delete("/admin/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """
    Delete a dataset.

    Args:
        dataset_id: Dataset ID

    Returns:
        Success message
    """
    from core.batch_app.database import Dataset
    from pathlib import Path

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    # Delete file
    file_path = Path(dataset.file_path)
    if file_path.exists():
        file_path.unlink()

    # Delete database record
    db.delete(dataset)
    db.commit()

    logger.info(f"Deleted dataset {dataset.name} ({dataset_id})")

    return {"message": f"Dataset '{dataset.name}' deleted successfully"}


@app.post("/admin/benchmarks/run")
async def run_benchmark(request: RunBenchmarkRequest, db: Session = Depends(get_db)):
    """
    Run a benchmark - execute a model on a dataset.

    Args:
        request: Model ID and dataset ID

    Returns:
        Benchmark ID and status
    """
    import uuid
    from core.batch_app.database import Dataset, Benchmark

    # Validate model exists
    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == request.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{request.model_id}' not found")

    # Validate dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{request.dataset_id}' not found")

    # Create benchmark record
    benchmark_id = f"bm_{uuid.uuid4().hex[:12]}"

    benchmark = Benchmark(
        id=benchmark_id,
        model_id=request.model_id,
        dataset_id=request.dataset_id,
        status="running",
        total=dataset.count,
        started_at=datetime.now(timezone.utc)
    )

    db.add(benchmark)
    db.commit()

    # Start background process
    from core.batch_app.model_manager import start_benchmark
    start_benchmark(benchmark_id, request.model_id, request.dataset_id, db)

    logger.info(f"Started benchmark {benchmark_id}: {model.name} on {dataset.name}")

    return {
        "benchmark_id": benchmark_id,
        "status": "running",
        "started_at": benchmark.started_at.isoformat()
    }


@app.get("/admin/benchmarks/active")
async def list_active_benchmarks(db: Session = Depends(get_db)):
    """
    List all active (running) benchmarks.

    Returns:
        List of active benchmarks with progress
    """
    from core.batch_app.database import Benchmark

    benchmarks = db.query(Benchmark).filter(Benchmark.status == "running").all()

    jobs = []
    for bm in benchmarks:
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
        from core.batch_app.database import Dataset
        dataset = db.query(Dataset).filter(Dataset.id == bm.dataset_id).first()

        jobs.append({
            "benchmark_id": bm.id,
            "model_id": bm.model_id,
            "model_name": model.name if model else bm.model_id,
            "dataset_id": bm.dataset_id,
            "dataset_name": dataset.name if dataset else bm.dataset_id,
            "status": bm.status,
            "progress": bm.progress,
            "completed": bm.completed,
            "total": bm.total,
            "throughput": bm.throughput,
            "eta_seconds": bm.eta_seconds,
            "started_at": bm.started_at.isoformat()
        })

    return {"jobs": jobs}


@app.get("/admin/workbench/results")
async def get_workbench_results(dataset_id: str, db: Session = Depends(get_db)):
    """
    Get results for a dataset across all models.

    Args:
        dataset_id: Dataset ID

    Returns:
        Results with model outputs side-by-side
    """
    from core.batch_app.database import Dataset, Benchmark, Annotation
    from pathlib import Path
    import json

    # Validate dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    # Find all benchmarks for this dataset
    benchmarks = db.query(Benchmark).filter(Benchmark.dataset_id == dataset_id).all()

    # Load results from each benchmark
    results_by_candidate = {}

    for bm in benchmarks:
        if not bm.results_file:
            continue

        results_path = Path(bm.results_file)
        if not results_path.exists():
            continue

        # Read results
        with open(results_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                result = json.loads(line)
                candidate_id = result.get("custom_id", "")

                if candidate_id not in results_by_candidate:
                    results_by_candidate[candidate_id] = {
                        "candidate_id": candidate_id,
                        "candidate_name": None,
                        "candidate_title": None,
                        "models": {},
                        "is_golden": False,
                        "is_fixed": False,
                        "is_wrong": False
                    }

                # Extract candidate info from request
                request_body = result.get("request", {}).get("body", {})
                messages = request_body.get("messages", [])
                if messages:
                    # Try to extract name/title from user message
                    user_msg = next((m for m in messages if m.get("role") == "user"), None)
                    if user_msg:
                        content = user_msg.get("content", "")
                        # Simple extraction - can be improved
                        if "name:" in content.lower():
                            lines = content.split("\n")
                            for line in lines:
                                if "name:" in line.lower():
                                    results_by_candidate[candidate_id]["candidate_name"] = line.split(":", 1)[1].strip()
                                if "title:" in line.lower():
                                    results_by_candidate[candidate_id]["candidate_title"] = line.split(":", 1)[1].strip()

                # Extract model response
                response_body = result.get("response", {}).get("body", {})
                choices = response_body.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")

                    # Parse JSON response
                    try:
                        parsed = json.loads(content)
                        results_by_candidate[candidate_id]["models"][bm.model_id] = {
                            "recommendation": parsed.get("recommendation"),
                            "trajectory": parsed.get("trajectory_rating"),
                            "pedigree": parsed.get("company_pedigree_rating"),
                            "is_software_engineer": parsed.get("is_software_engineer")
                        }
                    except:
                        # Fallback to raw content
                        results_by_candidate[candidate_id]["models"][bm.model_id] = {
                            "raw_content": content
                        }

    # Load annotations
    annotations = db.query(Annotation).filter(Annotation.dataset_id == dataset_id).all()
    for ann in annotations:
        if ann.candidate_id in results_by_candidate:
            results_by_candidate[ann.candidate_id]["is_golden"] = ann.is_golden
            results_by_candidate[ann.candidate_id]["is_fixed"] = ann.is_fixed
            results_by_candidate[ann.candidate_id]["is_wrong"] = ann.is_wrong

    return {
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "count": dataset.count
        },
        "results": list(results_by_candidate.values())
    }


@app.post("/admin/annotations/golden/{dataset_id}/{candidate_id}")
async def toggle_golden(dataset_id: str, candidate_id: str, model_id: str, db: Session = Depends(get_db)):
    """
    Toggle golden status for a candidate result.

    Args:
        dataset_id: Dataset ID
        candidate_id: Candidate ID
        model_id: Model ID

    Returns:
        Updated annotation
    """
    from core.batch_app.database import Annotation
    import uuid

    # Find or create annotation
    annotation = db.query(Annotation).filter(
        Annotation.dataset_id == dataset_id,
        Annotation.candidate_id == candidate_id,
        Annotation.model_id == model_id
    ).first()

    if not annotation:
        annotation = Annotation(
            id=f"ann_{uuid.uuid4().hex[:12]}",
            dataset_id=dataset_id,
            candidate_id=candidate_id,
            model_id=model_id,
            is_golden=True
        )
        db.add(annotation)
    else:
        annotation.is_golden = not annotation.is_golden
        annotation.updated_at = datetime.now(timezone.utc)

    db.commit()

    logger.info(f"Toggled golden for {candidate_id}: {annotation.is_golden}")

    return {
        "candidate_id": candidate_id,
        "is_golden": annotation.is_golden
    }


@app.post("/admin/annotations/fix/{dataset_id}/{candidate_id}")
async def mark_fixed(dataset_id: str, candidate_id: str, model_id: str, db: Session = Depends(get_db)):
    """
    Mark a candidate result as fixed.

    Args:
        dataset_id: Dataset ID
        candidate_id: Candidate ID
        model_id: Model ID

    Returns:
        Updated annotation
    """
    from core.batch_app.database import Annotation
    import uuid

    annotation = db.query(Annotation).filter(
        Annotation.dataset_id == dataset_id,
        Annotation.candidate_id == candidate_id,
        Annotation.model_id == model_id
    ).first()

    if not annotation:
        annotation = Annotation(
            id=f"ann_{uuid.uuid4().hex[:12]}",
            dataset_id=dataset_id,
            candidate_id=candidate_id,
            model_id=model_id,
            is_fixed=True
        )
        db.add(annotation)
    else:
        annotation.is_fixed = True
        annotation.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "candidate_id": candidate_id,
        "is_fixed": annotation.is_fixed
    }


@app.post("/admin/annotations/wrong/{dataset_id}/{candidate_id}")
async def mark_wrong(dataset_id: str, candidate_id: str, model_id: str, db: Session = Depends(get_db)):
    """
    Mark a candidate result as wrong.

    Args:
        dataset_id: Dataset ID
        candidate_id: Candidate ID
        model_id: Model ID

    Returns:
        Updated annotation
    """
    from core.batch_app.database import Annotation
    import uuid

    annotation = db.query(Annotation).filter(
        Annotation.dataset_id == dataset_id,
        Annotation.candidate_id == candidate_id,
        Annotation.model_id == model_id
    ).first()

    if not annotation:
        annotation = Annotation(
            id=f"ann_{uuid.uuid4().hex[:12]}",
            dataset_id=dataset_id,
            candidate_id=candidate_id,
            model_id=model_id,
            is_wrong=True
        )
        db.add(annotation)
    else:
        annotation.is_wrong = True
        annotation.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "candidate_id": candidate_id,
        "is_wrong": annotation.is_wrong
    }


# ============================================================================
# System Management Endpoints
# ============================================================================

@app.post("/admin/system/restart-worker")
async def restart_worker():
    """
    Restart the worker process.

    This kills the current worker and starts a new one.

    Returns:
        dict: Status message
    """
    import subprocess
    import signal
    import time

    try:
        # Find worker process
        result = subprocess.run(
            ["pgrep", "-f", "python -m core.batch_app.worker"],
            capture_output=True,
            text=True
        )

        old_pids = []
        if result.returncode == 0:
            old_pids = result.stdout.strip().split('\n')
            for pid in old_pids:
                if pid:
                    logger.info(f"Killing worker process {pid}")
                    os.kill(int(pid), signal.SIGTERM)

            # Wait for processes to die
            time.sleep(2)

            # Force kill if still alive
            for pid in old_pids:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead

        # Start new worker
        project_root = Path(__file__).parent.parent.parent
        venv_python = project_root / "venv" / "bin" / "python"
        log_file = project_root / "logs" / "worker.log"

        # Ensure logs directory exists
        log_file.parent.mkdir(exist_ok=True)

        # Start worker in background
        with open(log_file, "a") as f:
            process = subprocess.Popen(
                [str(venv_python), "-m", "core.batch_app.worker"],
                cwd=str(project_root),
                stdout=f,
                stderr=f,
                start_new_session=True  # Detach from parent
            )

        logger.info(f"Started new worker process (PID: {process.pid})")

        return {
            "status": "success",
            "message": f"Worker restarted successfully",
            "old_pids": old_pids,
            "new_pid": process.pid,
            "note": "Wait 10-15 seconds for worker to initialize and load models"
        }
    except Exception as e:
        logger.error(f"Error restarting worker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/system/clear-gpu-memory")
async def clear_gpu_memory():
    """
    Clear GPU memory by force-killing and restarting the worker.

    This is useful when models fail to load or GPU memory is fragmented.

    Returns:
        dict: Status message
    """
    import subprocess
    import signal
    import time

    try:
        # Find worker process
        result = subprocess.run(
            ["pgrep", "-f", "python -m core.batch_app.worker"],
            capture_output=True,
            text=True
        )

        old_pids = []
        if result.returncode == 0:
            old_pids = result.stdout.strip().split('\n')
            for pid in old_pids:
                if pid:
                    logger.info(f"Force killing worker process {pid} to clear GPU memory")
                    os.kill(int(pid), signal.SIGKILL)  # Force kill

            # Wait for GPU memory to clear
            time.sleep(3)

        # Start new worker
        project_root = Path(__file__).parent.parent.parent
        venv_python = project_root / "venv" / "bin" / "python"
        log_file = project_root / "logs" / "worker.log"

        # Ensure logs directory exists
        log_file.parent.mkdir(exist_ok=True)

        # Start worker in background
        with open(log_file, "a") as f:
            process = subprocess.Popen(
                [str(venv_python), "-m", "core.batch_app.worker"],
                cwd=str(project_root),
                stdout=f,
                stderr=f,
                start_new_session=True  # Detach from parent
            )

        logger.info(f"Started new worker after GPU clear (PID: {process.pid})")

        return {
            "status": "success",
            "message": "GPU memory cleared and worker restarted",
            "old_pids": old_pids,
            "new_pid": process.pid,
            "note": "Wait 10-15 seconds for worker to initialize and load models"
        }
    except Exception as e:
        logger.error(f"Error clearing GPU memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/system/status")
async def system_status():
    """
    Get system status including processes, GPU, and queue.

    Returns:
        dict: System status information
    """
    import subprocess

    status = {
        "processes": {},
        "gpu": {},
        "queue": {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Check API server process
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python -m uvicorn core.batch_app.api_server"],
            capture_output=True,
            text=True
        )
        status["processes"]["api_server"] = {
            "running": result.returncode == 0,
            "pids": result.stdout.strip().split('\n') if result.returncode == 0 else []
        }
    except Exception as e:
        status["processes"]["api_server"] = {"running": False, "error": str(e)}

    # Check worker process
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python -m core.batch_app.worker"],
            capture_output=True,
            text=True
        )
        status["processes"]["worker"] = {
            "running": result.returncode == 0,
            "pids": result.stdout.strip().split('\n') if result.returncode == 0 else []
        }
    except Exception as e:
        status["processes"]["worker"] = {"running": False, "error": str(e)}

    # Check GPU status
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)

        status["gpu"] = {
            "memory_used_mb": mem_info.used // (1024 * 1024),
            "memory_total_mb": mem_info.total // (1024 * 1024),
            "memory_percent": (mem_info.used / mem_info.total) * 100,
            "temperature_c": temp,
            "utilization_percent": util.gpu
        }

        pynvml.nvmlShutdown()
    except Exception as e:
        status["gpu"] = {"error": str(e)}

    return status


# ============================================================================
# Model Parser Endpoint
# ============================================================================

@app.post("/admin/models/parse-huggingface")
async def parse_huggingface_content(request: Request):
    """
    Parse copy/pasted HuggingFace model page content.

    Accepts raw text from HuggingFace model page and extracts:
    - Model ID
    - vLLM serve command
    - Installation instructions
    - Memory requirements
    - Quantization info

    Returns:
        Parsed model configuration ready for adding to registry
    """
    from core.batch_app.model_parser import parse_and_prepare_model

    # Get raw content from request body
    content = await request.body()
    content_str = content.decode('utf-8')

    try:
        # Parse content
        model_config = parse_and_prepare_model(content_str)

        return {
            "success": True,
            "model_config": model_config,
            "message": f"Successfully parsed model: {model_config['name']}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to parse HuggingFace content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse content: {str(e)}")


# ============================================================================
# Active Learning & Pre-labeling Endpoints
# ============================================================================

@app.post("/admin/active-learning/select-tasks")
async def select_tasks_for_review(
    dataset_id: str,
    max_tasks: int = 100,
    strategy: str = "uncertainty",
    db: Session = Depends(get_db)
):
    """
    Select tasks for human review using active learning.

    Args:
        dataset_id: Dataset ID
        max_tasks: Maximum number of tasks to select (default 100)
        strategy: Selection strategy ("uncertainty", "random")

    Returns:
        List of candidate IDs to review, sorted by priority
    """
    from core.batch_app.label_studio_integration import select_tasks_for_review as select_tasks

    # Get results for dataset
    results_response = await get_workbench_results(dataset_id, db)
    results = results_response.get("results", [])

    # Select tasks using active learning
    selected = select_tasks(results, max_tasks=max_tasks, strategy=strategy)

    return {
        "dataset_id": dataset_id,
        "strategy": strategy,
        "total_candidates": len(results),
        "selected_count": len(selected),
        "candidates": [
            {
                "candidate_id": r["candidate_id"],
                "candidate_name": r.get("candidate_name"),
                "uncertainty_score": r.get("uncertainty_score", 0.0)
            }
            for r in selected
        ]
    }


@app.post("/admin/label-studio/export-golden")
async def export_golden_dataset(
    dataset_id: str,
    output_format: str = "jsonl",
    db: Session = Depends(get_db)
):
    """
    Export golden dataset for training.

    Args:
        dataset_id: Dataset ID
        output_format: Export format ("jsonl", "json")

    Returns:
        File path to exported dataset
    """
    from core.batch_app.database import Annotation
    from core.batch_app.label_studio_integration import export_golden_dataset as export_golden
    from pathlib import Path

    # Get all golden annotations for this dataset
    golden_annotations = db.query(Annotation).filter(
        Annotation.dataset_id == dataset_id,
        Annotation.is_golden == True
    ).all()

    if not golden_annotations:
        raise HTTPException(status_code=404, detail="No golden examples found for this dataset")

    # Convert to export format
    export_data = []
    for annotation in golden_annotations:
        export_data.append({
            "candidate_id": annotation.candidate_id,
            "model_id": annotation.model_id,
            "is_golden": annotation.is_golden,
            "is_fixed": annotation.is_fixed,
            "created_at": annotation.created_at.isoformat(),
            "updated_at": annotation.updated_at.isoformat()
        })

    # Export to file
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"data/exports/golden_{dataset_id}_{timestamp}.{output_format}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_golden(export_data, output_path, format=output_format)

    return {
        "dataset_id": dataset_id,
        "count": len(export_data),
        "output_path": str(output_path),
        "format": output_format
    }


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws/workbench")
async def workbench_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for live workbench updates.

    Sends real-time updates for:
    - Benchmark progress (every 2 seconds)
    - New results as they complete
    - Job status changes

    Client receives JSON messages:
    {
        "type": "progress",
        "jobs": [{"benchmark_id": "...", "progress": 50, ...}]
    }
    {
        "type": "result",
        "result": {"candidate_id": "...", "model_outputs": {...}}
    }
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            db = SessionLocal()
            try:
                # Get active benchmarks
                from core.batch_app.database import Benchmark

                active_benchmarks = db.query(Benchmark).filter(
                    Benchmark.status == "running"
                ).all()

                jobs = []
                for benchmark in active_benchmarks:
                    # Get latest status
                    from core.batch_app.model_manager import get_benchmark_status
                    status = get_benchmark_status(benchmark.id, db)

                    jobs.append({
                        "benchmark_id": benchmark.id,
                        "model_id": benchmark.model_id,
                        "dataset_id": benchmark.dataset_id,
                        "status": status.get("status", "running"),
                        "progress": status.get("progress", 0),
                        "completed": status.get("completed", 0),
                        "total": status.get("total", 0),
                        "throughput": status.get("throughput", 0.0),
                        "eta_seconds": status.get("eta_seconds", 0)
                    })

                # Send progress update
                await websocket.send_json({
                    "type": "progress",
                    "jobs": jobs,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            finally:
                db.close()

            # Wait 2 seconds before next update
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass


# ============================================================================
# Model Installation Endpoints
# ============================================================================

class AnalyzeModelRequest(BaseModel):
    """Request to analyze a model from HuggingFace content."""
    content: str = Field(..., description="HuggingFace page content or URL")


class InstallModelRequest(BaseModel):
    """Request to install a model."""
    model_id: str = Field(..., description="HuggingFace model ID")
    gguf_file: str = Field(..., description="Specific GGUF file to download")


@app.post("/api/models/analyze")
async def analyze_model_endpoint(request: AnalyzeModelRequest):
    """
    Analyze a model from HuggingFace content.

    Returns:
    - Will it fit on GPU?
    - CPU offload needed?
    - Estimated speed
    - Quality tier
    - Comparison to existing models
    """
    try:
        installer = ModelInstaller()
        result = installer.analyze_model(request.content)
        return result
    except Exception as e:
        logger.error(f"Error analyzing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/install")
async def install_model_endpoint(request: InstallModelRequest):
    """
    Download and install a model.

    This is a long-running operation. Use WebSocket for progress updates.
    """
    try:
        installer = ModelInstaller()

        # Start installation in background
        # For now, run synchronously (TODO: make async)
        result = installer.install_model(
            model_id=request.model_id,
            gguf_file=request.gguf_file
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Installation failed'))

        # Add to model registry
        db = SessionLocal()
        try:
            # Check if model already exists
            existing = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == request.model_id
            ).first()

            if existing:
                # Update existing
                existing.local_path = result['local_path']
                existing.size_gb = result['file_size_gb']
                existing.status = 'downloaded'
            else:
                # Create new
                model = ModelRegistry(
                    model_id=request.model_id,
                    name=request.model_id.split('/')[-1],
                    local_path=result['local_path'],
                    size_gb=result['file_size_gb'],
                    status='downloaded'
                )
                db.add(model)

            db.commit()
        finally:
            db.close()

        return result

    except Exception as e:
        logger.error(f"Error installing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/model-install/{model_id}")
async def model_install_websocket(websocket: WebSocket, model_id: str):
    """
    WebSocket endpoint for real-time model installation progress.

    Sends progress updates as model downloads and benchmarks.
    """
    await websocket.accept()

    try:
        installer = ModelInstaller()

        # Progress callback
        async def send_progress(update: dict):
            await websocket.send_json(update)

        # Get GGUF file from query params
        gguf_file = websocket.query_params.get('gguf_file')
        if not gguf_file:
            await websocket.send_json({
                'status': 'error',
                'error': 'Missing gguf_file parameter'
            })
            return

        # Install model
        result = installer.install_model(
            model_id=model_id,
            gguf_file=gguf_file,
            progress_callback=lambda update: asyncio.create_task(send_progress(update))
        )

        if result['success']:
            # Run benchmark
            benchmark_result = installer.benchmark_model(
                model_path=result['local_path'],
                progress_callback=lambda update: asyncio.create_task(send_progress(update))
            )

            await websocket.send_json({
                'status': 'complete',
                'install': result,
                'benchmark': benchmark_result
            })
        else:
            await websocket.send_json({
                'status': 'error',
                'error': result.get('error', 'Installation failed')
            })

    except WebSocketDisconnect:
        logger.info("Model install WebSocket disconnected")
    except Exception as e:
        logger.error(f"Model install WebSocket error: {e}")
        try:
            await websocket.send_json({
                'status': 'error',
                'error': str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# ============================================================================
# Webhook Dead Letter Queue Endpoints
# ============================================================================

@app.get("/v1/webhooks/dead-letter")
async def list_failed_webhooks(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List failed webhook deliveries from the dead letter queue.

    Returns webhooks that failed after all retry attempts.
    """
    failed_webhooks = db.query(WebhookDeadLetter).order_by(
        WebhookDeadLetter.created_at.desc()
    ).limit(limit).offset(offset).all()

    total = db.query(WebhookDeadLetter).count()

    return {
        "object": "list",
        "data": [
            {
                "id": wh.id,
                "batch_id": wh.batch_id,
                "webhook_url": wh.webhook_url,
                "error_message": wh.error_message,
                "attempts": wh.attempts,
                "last_attempt_at": wh.last_attempt_at.isoformat() if wh.last_attempt_at else None,
                "created_at": wh.created_at.isoformat() if wh.created_at else None,
                "retried_at": wh.retried_at.isoformat() if wh.retried_at else None,
                "retry_success": wh.retry_success
            }
            for wh in failed_webhooks
        ],
        "has_more": (offset + limit) < total,
        "total": total
    }


@app.post("/v1/webhooks/dead-letter/{dead_letter_id}/retry")
async def retry_failed_webhook(
    dead_letter_id: int,
    db: Session = Depends(get_db)
):
    """
    Retry a failed webhook delivery from the dead letter queue.

    Attempts to resend the webhook with the original payload.
    """
    from .webhooks import send_webhook

    # Get dead letter entry
    dead_letter = db.query(WebhookDeadLetter).filter(
        WebhookDeadLetter.id == dead_letter_id
    ).first()

    if not dead_letter:
        raise HTTPException(status_code=404, detail="Dead letter entry not found")

    # Get batch job
    batch_job = db.query(BatchJob).filter(
        BatchJob.batch_id == dead_letter.batch_id
    ).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    # Reset webhook status for retry
    batch_job.webhook_status = None
    batch_job.webhook_attempts = 0
    batch_job.webhook_error = None

    # Attempt to send webhook
    success = send_webhook(batch_job, db)

    # Update dead letter entry
    dead_letter.retried_at = datetime.now(timezone.utc)
    dead_letter.retry_success = success
    db.commit()

    return {
        "id": dead_letter_id,
        "batch_id": dead_letter.batch_id,
        "retry_success": success,
        "retried_at": dead_letter.retried_at.isoformat()
    }


@app.delete("/v1/webhooks/dead-letter/{dead_letter_id}")
async def delete_failed_webhook(
    dead_letter_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a failed webhook entry from the dead letter queue.

    Use this after manually resolving the issue or if the webhook is no longer needed.
    """
    dead_letter = db.query(WebhookDeadLetter).filter(
        WebhookDeadLetter.id == dead_letter_id
    ).first()

    if not dead_letter:
        raise HTTPException(status_code=404, detail="Dead letter entry not found")

    db.delete(dead_letter)
    db.commit()

    return {"deleted": True, "id": dead_letter_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4080)
