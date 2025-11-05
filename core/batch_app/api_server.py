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
from typing import Dict, Any, List, Optional

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect, Response
from fastapi import File as FastAPIFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator
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
from core.plugins.registry import get_plugin_registry

# Initialize logger
logger = get_logger(__name__)

# Initialize rate limiter (conditionally enabled)
limiter = Limiter(key_func=get_remote_address, enabled=settings.ENABLE_RATE_LIMITING)


# ============================================================================
# Lifespan Context Manager
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # Startup
    init_sentry()
    init_db()

    logger.info("Batch API Server started", extra={
        "host": settings.BATCH_API_HOST,
        "port": settings.BATCH_API_PORT,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "sentry_enabled": bool(settings.SENTRY_DSN)
    })
    logger.info(f"Server ready at http://{settings.BATCH_API_HOST}:{settings.BATCH_API_PORT}")

    yield

    # Shutdown (if needed in future)
    logger.info("Batch API Server shutting down")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    description="Submit and manage large-scale LLM inference batch jobs",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Add rate limit exception handler (only if rate limiting is enabled)
if settings.ENABLE_RATE_LIMITING:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Include fine-tuning router (generic OSS version)
from core.batch_app.fine_tuning import router as fine_tuning_router
app.include_router(fine_tuning_router, prefix="/v1/fine-tuning", tags=["fine-tuning"])

# Conquest router moved to Aris repository (integrations/aris/conquest_api.py)
# For OSS users: Create your own custom API endpoints as needed


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

    @field_validator('events')
    @classmethod
    def validate_events(cls, v):
        """Validate that webhook events are valid."""
        if v is None:
            return v

        valid_events = {"completed", "failed", "progress"}
        invalid = set(v) - valid_events

        if invalid:
            raise ValueError(f"Invalid events: {invalid}. Valid events: {valid_events}")

        return v


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
        "worker": heartbeat.__dict__ if heartbeat else {"status": "unknown"},
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
    worker_status: Dict[str, Any] = {
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
    cumulative_eta_seconds: float = 0.0
    if current_job_data and isinstance(current_job_data, dict):
        timing = current_job_data.get("timing")
        if timing and isinstance(timing, dict):
            eta = timing.get("eta_seconds")
            if eta and isinstance(eta, (int, float)):
                cumulative_eta_seconds = float(eta)

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


@app.get("/history", response_class=HTMLResponse)
async def job_history():
    """Serve the job history UI."""
    history_html_path = Path(__file__).parent / "static" / "history.html"
    if not history_html_path.exists():
        raise HTTPException(status_code=404, detail="Job history page not found")

    with open(history_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/add-model", response_class=HTMLResponse)
async def add_model_page():
    """Serve the add model UI."""
    # Check both locations: static/ and root static/
    add_model_paths = [
        Path(__file__).parent / "static" / "add-model.html",
        Path(__file__).parent.parent.parent / "static" / "add-model.html"
    ]

    for add_model_path in add_model_paths:
        if add_model_path.exists():
            with open(add_model_path) as f:
                return HTMLResponse(content=f.read())

    raise HTTPException(status_code=404, detail="Add model page not found")


@app.get("/fine-tuning", response_class=HTMLResponse)
async def fine_tuning_dashboard():
    """Serve the fine-tuning dashboard UI."""
    fine_tuning_path = Path(__file__).parent.parent.parent / "static" / "fine-tuning.html"
    if not fine_tuning_path.exists():
        raise HTTPException(status_code=404, detail="Fine-tuning dashboard not found")

    with open(fine_tuning_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/model-comparison", response_class=HTMLResponse)
async def model_comparison_page():
    """Serve the model comparison UI."""
    comparison_path = Path(__file__).parent.parent.parent / "static" / "model-comparison.html"
    if not comparison_path.exists():
        raise HTTPException(status_code=404, detail="Model comparison page not found")

    with open(comparison_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve the admin panel UI."""
    admin_html_path = Path(__file__).parent / "static" / "admin.html"
    if not admin_html_path.exists():
        raise HTTPException(status_code=404, detail="Admin panel not found")

    with open(admin_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/admin/worker-logs", response_class=HTMLResponse)
async def worker_logs_page():
    """Serve the worker logs viewer UI."""
    logs_html_path = Path(__file__).parent / "static" / "worker-logs.html"
    if not logs_html_path.exists():
        raise HTTPException(status_code=404, detail="Worker logs page not found")

    with open(logs_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/admin/worker-logs/content")
async def worker_logs_content(tail: int = 500):
    """
    Get worker log content.

    Args:
        tail: Number of lines to return from end of log (default: 500)

    Returns:
        JSON with logs array and statistics
    """
    try:
        # Find project root
        project_root = Path(__file__).parent.parent.parent
        log_file = project_root / "logs" / "worker.log"

        if not log_file.exists():
            return {
                "logs": ["Worker log file not found. Worker may not have started yet."],
                "total_lines": 0,
                "error_count": 0,
                "warning_count": 0
            }

        # Read log file
        with open(log_file, 'r') as f:
            all_lines = f.readlines()

        # Get last N lines
        lines = all_lines[-tail:] if len(all_lines) > tail else all_lines

        # Count errors and warnings
        error_count = sum(1 for line in lines if 'ERROR' in line or '❌' in line or 'Failed' in line)
        warning_count = sum(1 for line in lines if 'WARNING' in line or '⚠️' in line)

        return {
            "logs": [line.rstrip() for line in lines],
            "total_lines": len(lines),
            "error_count": error_count,
            "warning_count": warning_count
        }

    except Exception as e:
        logger.error(f"Error reading worker logs: {e}")
        return {
            "logs": [f"Error reading logs: {str(e)}"],
            "total_lines": 0,
            "error_count": 0,
            "warning_count": 0
        }


@app.get("/static/{filename}")
async def serve_static_file(filename: str):
    """Serve static files (docs, JS, etc.)."""
    # Map of allowed files
    allowed_files = {
        "llm.txt": Path(__file__).parent.parent.parent / "llm.txt",
        "STATUS.md": Path(__file__).parent.parent.parent / "STATUS.md",
        "SYSTEM_MANAGEMENT.md": Path(__file__).parent.parent.parent / "SYSTEM_MANAGEMENT.md",
        "README.md": Path(__file__).parent.parent.parent / "README.md",
        "history.js": Path(__file__).parent / "static" / "history.js",
    }

    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = allowed_files[filename]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine media type
    media_type = "text/plain"
    if filename.endswith(".js"):
        media_type = "application/javascript"
    elif filename.endswith(".md"):
        media_type = "text/markdown"

    return FileResponse(file_path, media_type=media_type, filename=filename)


@app.get("/config", response_class=HTMLResponse)
async def config_panel():
    """Serve the configuration panel UI."""
    config_html_path = Path(__file__).parent / "static" / "config.html"
    if not config_html_path.exists():
        raise HTTPException(status_code=404, detail="Configuration panel not found")

    with open(config_html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/plugins", response_class=HTMLResponse)
async def plugins_page():
    """Serve the plugin management UI."""
    plugins_html_path = Path(__file__).parent.parent.parent / "static" / "plugins.html"
    if not plugins_html_path.exists():
        raise HTTPException(status_code=404, detail="Plugin management page not found")

    with open(plugins_html_path) as f:
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

    # Use user-provided metadata or empty dict
    merged_metadata = batch_request.metadata.copy() if batch_request.metadata else {}

    # Ensure we have default schema_type if not provided
    if 'schema_type' not in merged_metadata:
        merged_metadata['schema_type'] = 'generic'

    logger.info(f"Batch metadata: {merged_metadata}")

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
        metadata_json=json.dumps(merged_metadata),  # ✅ CHANGED: Use merged metadata
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


@app.post("/v1/inference")
async def single_inference(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Single inference endpoint for real-time predictions.

    Used by Label Studio ML Backend for interactive labeling.

    Request body:
        {
            "model_id": "google/gemma-3-4b-it",  # Optional, defaults to first available
            "prompt": "Your prompt here",         # For simple prompts
            "messages": [...],                    # For chat format (alternative to prompt)
            "max_tokens": 500,                    # Optional
            "temperature": 0.7,                   # Optional
            "top_p": 0.9,                         # Optional
            "stop": ["</s>"]                      # Optional
        }

    Returns:
        {
            "text": "Generated response",
            "model": "model_id",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            },
            "latency_ms": 1234
        }
    """
    from core.batch_app.inference import get_inference_engine

    try:
        body = await request.json()

        # Get model ID (default to first available model)
        model_id = body.get('model_id')
        if not model_id:
            # Get default model from registry
            models = db.query(ModelRegistry).filter(
                ModelRegistry.status == 'ready'
            ).order_by(ModelRegistry.created_at.desc()).all()

            if not models:
                raise HTTPException(status_code=400, detail="No models available. Please install a model first.")

            model_id = models[0].model_id
            logger.info(f"No model_id specified, using default: {model_id}")

        # Get prompt or messages
        prompt = body.get('prompt')
        messages = body.get('messages')

        if not prompt and not messages:
            raise HTTPException(status_code=400, detail="Missing 'prompt' or 'messages' field")

        # Get parameters
        max_tokens = body.get('max_tokens', 500)
        temperature = body.get('temperature', 0.7)
        top_p = body.get('top_p', 0.9)
        stop = body.get('stop')

        # Get inference engine
        engine = get_inference_engine()

        # Generate response
        if messages:
            result = engine.generate_chat(
                messages=messages,
                model_id=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop
            )
        else:
            result = engine.generate(
                prompt=prompt,
                model_id=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop
            )

        logger.info(f"Single inference complete: model={model_id}, latency={result['latency_ms']}ms")

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error in single inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

def validate_dataset(file_path: Path) -> Dict[str, Any]:
    """
    Validate JSONL dataset before accepting upload.

    Checks:
    - Valid JSONL format
    - Required fields present
    - OpenAI batch format compliance
    - Reasonable file size

    Returns:
        {
            'valid': bool,
            'errors': List[str],
            'warnings': List[str],
            'count': int,
            'preview': List[dict]  # First 3 requests
        }
    """
    errors = []
    warnings = []
    count = 0
    preview: List[Dict[str, Any]] = []

    try:
        with open(file_path, 'r') as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    count += 1

                    # Check required fields
                    if 'custom_id' not in data:
                        errors.append(f"Line {i}: Missing 'custom_id'")
                    if 'method' not in data:
                        errors.append(f"Line {i}: Missing 'method'")
                    if 'url' not in data:
                        errors.append(f"Line {i}: Missing 'url'")
                    if 'body' not in data:
                        errors.append(f"Line {i}: Missing 'body'")

                    # Check OpenAI format
                    if data.get('method') != 'POST':
                        warnings.append(f"Line {i}: Method should be POST (got {data.get('method')})")

                    if data.get('url') != '/v1/chat/completions':
                        warnings.append(f"Line {i}: URL should be /v1/chat/completions")

                    # Check body structure
                    body = data.get('body', {})
                    if 'model' not in body:
                        errors.append(f"Line {i}: Missing 'model' in body")
                    if 'messages' not in body:
                        errors.append(f"Line {i}: Missing 'messages' in body")

                    # Add to preview (first 3)
                    if len(preview) < 3:
                        preview.append({
                            'custom_id': data.get('custom_id', 'unknown'),
                            'model': body.get('model', 'unknown'),
                            'prompt_preview': str(body.get('messages', []))[:100] + '...'
                        })

                    # Stop after 100 errors
                    if len(errors) >= 100:
                        errors.append("Too many errors, stopping validation")
                        break

                except json.JSONDecodeError as e:
                    errors.append(f"Line {i}: Invalid JSON - {str(e)}")

    except Exception as e:
        errors.append(f"Failed to read file: {str(e)}")

    # Check file size
    if count == 0:
        errors.append("No valid requests found in file")
    elif count > 50000:
        warnings.append(f"Large dataset ({count:,} requests). Processing may take a long time.")

    return {
        'valid': len(errors) == 0,
        'errors': errors[:20],  # Limit to first 20 errors
        'warnings': warnings[:10],  # Limit to first 10 warnings
        'count': count,
        'preview': preview
    }


@app.post("/admin/datasets/upload")
async def upload_dataset(file: UploadFile, db: Session = Depends(get_db)):
    """
    Upload a dataset (JSONL file) for benchmarking with validation.

    Args:
        file: JSONL file with batch requests

    Returns:
        Dataset metadata with validation results
    """
    import uuid
    from pathlib import Path

    # Validate file extension
    if not file.filename or not file.filename.endswith('.jsonl'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .jsonl files are supported."
        )

    # Generate dataset ID
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"

    # Save file temporarily
    datasets_dir = Path("data/datasets")
    datasets_dir.mkdir(parents=True, exist_ok=True)

    file_path = datasets_dir / f"{dataset_id}_{file.filename}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Validate dataset
    validation = validate_dataset(file_path)

    if not validation['valid']:
        # Delete invalid file
        file_path.unlink()
        raise HTTPException(
            status_code=400,
            detail={
                'message': 'Dataset validation failed',
                'errors': validation['errors'],
                'warnings': validation['warnings']
            }
        )

    # Create dataset record
    from core.batch_app.database import Dataset

    dataset = Dataset(
        id=dataset_id,
        name=file.filename,
        file_path=str(file_path),
        count=validation['count'],
        uploaded_at=datetime.now(timezone.utc)
    )

    db.add(dataset)
    db.commit()

    logger.info(f"Uploaded dataset {file.filename} ({validation['count']} requests)")

    return {
        "dataset_id": dataset_id,
        "name": file.filename,
        "count": validation['count'],
        "uploaded_at": dataset.uploaded_at.isoformat(),
        "validation": {
            'warnings': validation['warnings'],
            'preview': validation['preview']
        }
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


@app.post("/admin/benchmarks/{benchmark_id}/cancel")
async def cancel_benchmark(benchmark_id: str, db: Session = Depends(get_db)):
    """
    Cancel a running benchmark.

    Args:
        benchmark_id: Benchmark ID to cancel

    Returns:
        Updated benchmark status
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.model_manager import cancel_benchmark as cancel_benchmark_process

    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")

    if benchmark.status != 'running':
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel benchmark with status '{benchmark.status}'"
        )

    # Cancel the background process
    try:
        cancel_benchmark_process(benchmark_id)
    except Exception as e:
        logger.error(f"Error cancelling benchmark process: {e}")

    # Update status
    benchmark.status = 'cancelled'
    benchmark.completed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"Cancelled benchmark {benchmark_id}")

    return {
        "benchmark_id": benchmark_id,
        "status": "cancelled",
        "completed": benchmark.completed,
        "total": benchmark.total
    }


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
# Workbench Comparison Endpoints
# ============================================================================

class CompareModelsRequest(BaseModel):
    """Request to compare two models."""
    benchmark_id_a: str = Field(..., description="First benchmark ID")
    benchmark_id_b: str = Field(..., description="Second benchmark ID")


@app.post("/admin/workbench/compare")
async def compare_models(request: CompareModelsRequest, db: Session = Depends(get_db)):
    """
    Compare responses from two models.

    Provides:
    - Diff viewer for responses
    - Agreement rate
    - Unique answers

    Returns detailed comparison analysis.
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.result_comparison import compare_responses

    # Get benchmarks
    bm_a = db.query(Benchmark).filter(Benchmark.id == request.benchmark_id_a).first()
    bm_b = db.query(Benchmark).filter(Benchmark.id == request.benchmark_id_b).first()

    if not bm_a or not bm_b:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    # Load results
    if not bm_a.results_file or not Path(bm_a.results_file).exists():
        raise HTTPException(status_code=404, detail=f"Results file not found for benchmark {request.benchmark_id_a}")

    if not bm_b.results_file or not Path(bm_b.results_file).exists():
        raise HTTPException(status_code=404, detail=f"Results file not found for benchmark {request.benchmark_id_b}")

    with open(bm_a.results_file, 'r') as f:
        results_a = [json.loads(line) for line in f if line.strip()]

    with open(bm_b.results_file, 'r') as f:
        results_b = [json.loads(line) for line in f if line.strip()]

    # Get model names
    model_a = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm_a.model_id).first()
    model_b = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm_b.model_id).first()

    model_a_name = model_a.name if model_a else bm_a.model_id
    model_b_name = model_b.name if model_b else bm_b.model_id

    # Compare
    comparison = compare_responses(results_a, results_b, model_a_name, model_b_name)

    return comparison


class FindUniqueAnswersRequest(BaseModel):
    """Request to find unique answers across models."""
    benchmark_ids: List[str] = Field(..., description="List of benchmark IDs to compare")


@app.post("/admin/workbench/unique-answers")
async def find_unique_answers(request: FindUniqueAnswersRequest, db: Session = Depends(get_db)):
    """
    Find unique answers across multiple models.

    Identifies cases where one model gives a different answer than all others.
    Useful for finding interesting examples for in-context learning.

    Returns analysis of unique answers.
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.result_comparison import find_unique_answers as find_unique

    if len(request.benchmark_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 benchmarks to compare")

    # Load all benchmarks and results
    results_list = []
    model_names = []

    for benchmark_id in request.benchmark_ids:
        bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not bm:
            raise HTTPException(status_code=404, detail=f"Benchmark {benchmark_id} not found")

        if not bm.results_file or not Path(bm.results_file).exists():
            raise HTTPException(status_code=404, detail=f"Results file not found for benchmark {benchmark_id}")

        with open(bm.results_file, 'r') as f:
            results = [json.loads(line) for line in f if line.strip()]

        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
        model_name = model.name if model else bm.model_id

        results_list.append(results)
        model_names.append(model_name)

    # Find unique answers
    analysis = find_unique(results_list, model_names)

    return analysis


@app.get("/admin/workbench/quality-metrics/{benchmark_id}")
async def get_quality_metrics(benchmark_id: str, db: Session = Depends(get_db)):
    """
    Get quality metrics for a benchmark.

    Metrics include:
    - Average response length
    - Token usage
    - Error rate

    Returns quality metrics.
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.result_comparison import calculate_quality_metrics

    bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    if not bm.results_file or not Path(bm.results_file).exists():
        raise HTTPException(status_code=404, detail="Results file not found")

    with open(bm.results_file, 'r') as f:
        results = [json.loads(line) for line in f if line.strip()]

    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
    model_name = model.name if model else bm.model_id

    metrics = calculate_quality_metrics(results, model_name)

    return metrics


# ============================================================================
# Cost Tracking Endpoints
# ============================================================================

@app.get("/admin/workbench/cost/{benchmark_id}")
async def get_benchmark_cost(benchmark_id: str, db: Session = Depends(get_db)):
    """
    Get cost analysis for a benchmark.

    Returns:
        Cost breakdown with token usage
    """
    from core.batch_app.database import Benchmark
    from core.batch_app.cost_tracking import calculate_batch_cost

    bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    if not bm.results_file or not Path(bm.results_file).exists():
        raise HTTPException(status_code=404, detail="Results file not found")

    with open(bm.results_file, 'r') as f:
        results = [json.loads(line) for line in f if line.strip()]

    cost_analysis = calculate_batch_cost(results, bm.model_id)

    return {
        'benchmark_id': benchmark_id,
        'model_id': bm.model_id,
        **cost_analysis
    }


class EstimateCostRequest(BaseModel):
    """Request to estimate batch cost."""
    num_requests: int = Field(..., description="Number of requests")
    avg_prompt_tokens: int = Field(..., description="Average prompt tokens per request")
    avg_completion_tokens: int = Field(..., description="Average completion tokens per request")
    model_id: str = Field(..., description="Model identifier")


@app.post("/admin/workbench/estimate-cost")
async def estimate_cost(request: EstimateCostRequest):
    """
    Estimate cost for a batch before running.

    Returns:
        Cost estimate
    """
    from core.batch_app.cost_tracking import estimate_batch_cost

    estimate = estimate_batch_cost(
        num_requests=request.num_requests,
        avg_prompt_tokens=request.avg_prompt_tokens,
        avg_completion_tokens=request.avg_completion_tokens,
        model_id=request.model_id
    )

    return estimate


@app.get("/admin/workbench/usage-summary")
async def get_usage_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get usage summary for a time period.

    Args:
        start_date: Start date (ISO format, optional)
        end_date: End date (ISO format, optional)
        model_id: Filter by model (optional)

    Returns:
        Usage summary with costs
    """
    from core.batch_app.cost_tracking import get_usage_summary as get_summary
    from datetime import datetime

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    summary = get_summary(db, start_dt, end_dt, model_id)

    return summary


class BudgetAlertRequest(BaseModel):
    """Request to check budget alert."""
    budget_limit: float = Field(..., description="Budget limit in dollars")
    alert_threshold: float = Field(default=0.8, description="Alert threshold (0-1)")


@app.post("/admin/workbench/budget-alert")
async def check_budget_alert(request: BudgetAlertRequest, db: Session = Depends(get_db)):
    """
    Check budget alert status.

    Returns:
        Alert status and remaining budget
    """
    from core.batch_app.cost_tracking import get_usage_summary as get_summary, check_budget_alert as check_alert

    # Get current spending
    summary = get_summary(db)
    current_cost = summary['total_cost']

    # Check alert
    alert = check_alert(current_cost, request.budget_limit, request.alert_threshold)

    return alert


# ============================================================================
# Label Studio Integration Endpoints
# ============================================================================

@app.get("/admin/label-studio/export/{project_id}")
async def export_label_studio_annotations(
    project_id: int,
    only_completed: bool = True
):
    """
    Export annotations from Label Studio.

    Args:
        project_id: Label Studio project ID
        only_completed: Only export completed annotations

    Returns:
        List of exported annotations
    """
    from core.result_handlers.label_studio import LabelStudioHandler

    handler = LabelStudioHandler()
    annotations = handler.export_annotations(project_id, only_completed)

    return {
        'project_id': project_id,
        'total_annotations': len(annotations),
        'annotations': annotations
    }


@app.get("/admin/label-studio/export-curated/{project_id}")
async def export_curated_data(project_id: int):
    """
    Export curated training data from Label Studio.

    Converts Label Studio annotations back to training-ready format.

    Args:
        project_id: Label Studio project ID

    Returns:
        List of curated training examples
    """
    from core.result_handlers.label_studio import LabelStudioHandler

    handler = LabelStudioHandler()
    curated = handler.export_curated_data(project_id)

    return {
        'project_id': project_id,
        'total_examples': len(curated),
        'examples': curated
    }


class MultiModelComparisonRequest(BaseModel):
    """Request to create multi-model comparison task."""
    project_id: int = Field(..., description="Label Studio project ID")
    custom_id: str = Field(..., description="Request custom ID")
    benchmark_ids: List[str] = Field(..., description="List of benchmark IDs to compare")


@app.post("/admin/label-studio/multi-model-comparison")
async def create_multi_model_comparison(
    request: MultiModelComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    Create a Label Studio task with predictions from multiple models.

    Useful for comparing model outputs side-by-side.

    Args:
        project_id: Label Studio project ID
        custom_id: Request custom ID to compare
        benchmark_ids: List of benchmark IDs

    Returns:
        Task ID
    """
    from core.batch_app.database import Benchmark
    from core.result_handlers.label_studio import LabelStudioHandler

    if len(request.benchmark_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 benchmarks to compare")

    # Load results from each benchmark
    model_responses = {}
    input_data = None

    for benchmark_id in request.benchmark_ids:
        bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not bm:
            raise HTTPException(status_code=404, detail=f"Benchmark {benchmark_id} not found")

        if not bm.results_file or not Path(bm.results_file).exists():
            raise HTTPException(status_code=404, detail=f"Results file not found for benchmark {benchmark_id}")

        # Find result for this custom_id
        with open(bm.results_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                result = json.loads(line)
                if result.get('custom_id') == request.custom_id:
                    # Extract response
                    response = result.get('response', {}).get('body', {}).get('choices', [{}])[0].get('message', {}).get('content', '')

                    # Get model name
                    model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
                    model_name = model.name if model else bm.model_id

                    model_responses[model_name] = response

                    # Save input data (same for all models)
                    if not input_data:
                        input_data = result.get('input', {})

                    break

    if not model_responses:
        raise HTTPException(status_code=404, detail=f"No results found for custom_id {request.custom_id}")

    # Create multi-model task
    handler = LabelStudioHandler()
    if not input_data:
        raise HTTPException(status_code=400, detail="input_data is required")
    task_id = handler.create_multi_model_task(
        project_id=request.project_id,
        input_data=input_data,
        model_responses=model_responses
    )

    return {
        'task_id': task_id,
        'project_id': request.project_id,
        'custom_id': request.custom_id,
        'models': list(model_responses.keys())
    }


# ============================================================================
# Model Management Advanced Endpoints (Sprint 3)
# ============================================================================

@app.get("/api/models/search")
async def search_models_endpoint(
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
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Search and filter models with advanced criteria.

    Query Parameters:
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
        Paginated list of models matching criteria
    """
    from core.batch_app.model_manager import search_models

    result = search_models(
        db=db,
        query=query,
        status=status,
        rtx4080_compatible=rtx4080_compatible,
        min_size_gb=min_size_gb,
        max_size_gb=max_size_gb,
        min_memory_gb=min_memory_gb,
        max_memory_gb=max_memory_gb,
        quantization_type=quantization_type,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )

    return result


@app.get("/api/models/usage-analytics")
async def get_model_usage_analytics_endpoint(
    model_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get usage analytics for models.

    Query Parameters:
        model_id: Optional model ID to filter by (if not provided, returns analytics for all models)

    Returns:
        Usage analytics including job counts, success rates, avg throughput
    """
    from core.batch_app.model_manager import get_model_usage_analytics

    analytics = get_model_usage_analytics(db, model_id)
    return analytics


class BatchInstallRequest(BaseModel):
    """Request to install multiple models."""
    model_ids: List[str] = Field(..., description="List of model IDs to install")


@app.post("/api/models/batch-install")
async def batch_install_models_endpoint(
    request: BatchInstallRequest,
    db: Session = Depends(get_db)
):
    """
    Install multiple models in sequence.

    Args:
        model_ids: List of model IDs to install

    Returns:
        Installation status for each model
    """
    from core.batch_app.model_manager import batch_install_models

    result = batch_install_models(db, request.model_ids)
    return result


class CompareModelsRequestDashboard(BaseModel):
    """Request to compare multiple models."""
    model_ids: List[str] = Field(..., description="List of model IDs to compare (2-10 models)")


@app.post("/api/models/compare-dashboard")
async def compare_models_dashboard_endpoint(
    request: CompareModelsRequestDashboard,
    db: Session = Depends(get_db)
):
    """
    Generate comparison dashboard for multiple models.

    Compares models across:
    - Specifications (size, memory, quantization)
    - Performance (throughput, latency)
    - Usage (job count, success rate)
    - Cost (estimated per request)

    Args:
        model_ids: List of model IDs to compare (2-10 models)

    Returns:
        Comparison data with rankings
    """
    from core.batch_app.model_manager import compare_models_dashboard

    if len(request.model_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 models to compare")
    if len(request.model_ids) > 10:
        raise HTTPException(status_code=400, detail="Can compare maximum 10 models at once")

    comparison = compare_models_dashboard(db, request.model_ids)
    return comparison


# ============================================================================
# Workbench Analytics Endpoints (Sprint 3)
# ============================================================================

@app.get("/admin/workbench/benchmark-history")
async def get_benchmark_history_endpoint(
    model_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get benchmark history with filtering and pagination.

    Query Parameters:
        model_id: Filter by model ID
        dataset_id: Filter by dataset ID
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        status: Filter by status (running, completed, failed, cancelled)
        limit: Maximum results to return
        offset: Offset for pagination

    Returns:
        Paginated benchmark history
    """
    from core.batch_app.workbench_analytics import get_benchmark_history
    from datetime import datetime

    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    history = get_benchmark_history(
        db=db,
        model_id=model_id,
        dataset_id=dataset_id,
        start_date=start_dt,
        end_date=end_dt,
        status=status,
        limit=limit,
        offset=offset
    )

    return history


class QualityDashboardRequest(BaseModel):
    """Request for quality metrics dashboard."""
    benchmark_ids: List[str] = Field(..., description="List of benchmark IDs to analyze")


@app.post("/admin/workbench/quality-dashboard")
async def get_quality_dashboard_endpoint(
    request: QualityDashboardRequest,
    db: Session = Depends(get_db)
):
    """
    Generate quality metrics dashboard for multiple benchmarks.

    Compares quality across benchmarks:
    - Response quality scores
    - Consistency metrics
    - Error analysis
    - Token efficiency

    Args:
        benchmark_ids: List of benchmark IDs to analyze

    Returns:
        Quality metrics dashboard data
    """
    from core.batch_app.workbench_analytics import get_quality_metrics_dashboard

    dashboard = get_quality_metrics_dashboard(db, request.benchmark_ids)
    return dashboard


class ExportReportRequest(BaseModel):
    """Request to export comparison report."""
    benchmark_ids: List[str] = Field(..., description="List of benchmark IDs to compare")
    format: str = Field(default='json', description="Export format (json, csv, markdown)")


@app.post("/admin/workbench/export-report")
async def export_comparison_report_endpoint(
    request: ExportReportRequest,
    db: Session = Depends(get_db)
):
    """
    Export detailed comparison report for benchmarks.

    Args:
        benchmark_ids: List of benchmark IDs to compare
        format: Export format (json, csv, markdown)

    Returns:
        Comparison report in requested format
    """
    from core.batch_app.workbench_analytics import export_comparison_report

    if request.format not in ['json', 'csv', 'markdown']:
        raise HTTPException(status_code=400, detail="Format must be json, csv, or markdown")

    report = export_comparison_report(db, request.benchmark_ids, request.format)

    # Return appropriate content type
    if request.format == 'markdown':
        return Response(content=report, media_type='text/markdown')
    elif request.format == 'csv':
        return Response(content=report, media_type='text/csv')
    else:
        return report


# ============================================================================
# Label Studio Advanced Endpoints (Sprint 3)
# ============================================================================

@app.get("/admin/label-studio/suggest-tasks/{project_id}")
async def suggest_next_tasks_endpoint(
    project_id: int,
    strategy: str = 'uncertainty',
    limit: int = 10
):
    """
    Active learning: Suggest next tasks to label.

    Strategies:
    - uncertainty: Tasks with lowest prediction confidence
    - disagreement: Tasks where models disagree most
    - random: Random unlabeled tasks

    Args:
        project_id: Label Studio project ID
        strategy: Selection strategy (uncertainty, disagreement, random)
        limit: Number of tasks to suggest

    Returns:
        List of suggested tasks
    """
    from core.result_handlers.label_studio import LabelStudioHandler

    if strategy not in ['uncertainty', 'disagreement', 'random']:
        raise HTTPException(status_code=400, detail="Strategy must be uncertainty, disagreement, or random")

    handler = LabelStudioHandler()
    suggestions = handler.suggest_next_tasks(project_id, strategy, limit)

    return {
        'project_id': project_id,
        'strategy': strategy,
        'total_suggested': len(suggestions),
        'tasks': suggestions
    }


@app.get("/admin/label-studio/quality-metrics/{project_id}")
async def get_annotation_quality_metrics_endpoint(project_id: int):
    """
    Get annotation quality metrics for a project.

    Metrics:
    - Inter-annotator agreement
    - Annotation speed
    - Completion rate
    - Quality scores

    Args:
        project_id: Label Studio project ID

    Returns:
        Quality metrics
    """
    from core.result_handlers.label_studio import LabelStudioHandler

    handler = LabelStudioHandler()
    metrics = handler.get_annotation_quality_metrics(project_id)

    return metrics


class BulkImportRequest(BaseModel):
    """Request to bulk import tasks."""
    project_id: int = Field(..., description="Label Studio project ID")
    tasks_data: List[Dict[str, Any]] = Field(..., description="List of task data dictionaries")


@app.post("/admin/label-studio/bulk-import")
async def bulk_import_tasks_endpoint(request: BulkImportRequest):
    """
    Bulk import tasks to Label Studio.

    Args:
        project_id: Label Studio project ID
        tasks_data: List of task data dictionaries

    Returns:
        Import results
    """
    from core.result_handlers.label_studio import LabelStudioHandler

    handler = LabelStudioHandler()
    result = handler.bulk_import_tasks(request.project_id, request.tasks_data)

    return result


# ============================================================================
# System Management Endpoints
# ============================================================================

@app.get("/admin/worker/status")
async def get_worker_status(db: Session = Depends(get_db)):
    """
    Get detailed worker status for settings UI.

    Returns:
        Worker health, heartbeat, GPU metrics, loaded model, uptime, etc.
    """
    worker_heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()

    if not worker_heartbeat:
        return {
            "healthy": False,
            "last_heartbeat": None,
            "heartbeat_age_seconds": None,
            "uptime_seconds": None,
            "restart_count": 0,
            "loaded_model": None,
            "gpu_memory_percent": 0,
            "gpu_utilization": 0,
            "gpu_temperature": 0
        }

    now_utc = datetime.now(timezone.utc)
    last_seen = worker_heartbeat.last_seen
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    age_seconds = (now_utc - last_seen).total_seconds() if last_seen else None
    healthy = age_seconds < 60 if age_seconds is not None else False

    # Calculate uptime (time since worker started)
    uptime_seconds = None
    if worker_heartbeat.model_loaded_at:
        loaded_at = worker_heartbeat.model_loaded_at
        if loaded_at.tzinfo is None:
            loaded_at = loaded_at.replace(tzinfo=timezone.utc)
        uptime_seconds = (now_utc - loaded_at).total_seconds()

    return {
        "healthy": healthy,
        "last_heartbeat": last_seen.isoformat() if last_seen else None,
        "heartbeat_age_seconds": age_seconds,
        "uptime_seconds": uptime_seconds,
        "restart_count": 0,  # TODO: Track this in watchdog
        "loaded_model": worker_heartbeat.loaded_model,
        "gpu_memory_percent": worker_heartbeat.gpu_memory_percent or 0,
        "gpu_utilization": worker_heartbeat.gpu_utilization or 0,
        "gpu_temperature": worker_heartbeat.gpu_temperature or 0
    }


@app.get("/admin/systemd/status")
async def get_systemd_status():
    """
    Get systemd service status for settings UI.

    Returns:
        Status of vllm-api-server and vllm-watchdog services
    """
    import subprocess

    def check_service(service_name: str) -> dict:
        try:
            # Check if service is enabled
            enabled_result = subprocess.run(
                ["systemctl", "is-enabled", service_name],
                capture_output=True,
                text=True
            )
            enabled = enabled_result.returncode == 0

            # Check if service is active
            active_result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True
            )
            active = active_result.returncode == 0

            return {"enabled": enabled, "active": active}
        except Exception as e:
            logger.error(f"Error checking systemd service {service_name}: {e}")
            return {"enabled": False, "active": False, "error": str(e)}

    return {
        "api_server": check_service("vllm-api-server"),
        "watchdog": check_service("vllm-watchdog")
    }


@app.post("/admin/systemd/{service_name}/{action}")
async def control_systemd_service(service_name: str, action: str):
    """
    Control systemd services (enable/disable/start/stop/restart).

    Args:
        service_name: vllm-api-server or vllm-watchdog
        action: enable, disable, start, stop, restart
    """
    import subprocess

    # Validate inputs
    valid_services = ["vllm-api-server", "vllm-watchdog"]
    valid_actions = ["enable", "disable", "start", "stop", "restart"]

    if service_name not in valid_services:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service_name}")

    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, service_name],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to {action} {service_name}: {result.stderr}"
            )

        return {"success": True, "message": f"Successfully {action}d {service_name}"}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Command timed out")
    except Exception as e:
        logger.error(f"Error controlling systemd service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/worker/restart")
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
# Plugin System API Endpoints
# ============================================================================

@app.get("/api/plugins")
async def list_plugins():
    """
    List all available plugins.

    Returns:
        List of plugin metadata (id, name, version, description, enabled status)
    """
    registry = get_plugin_registry()
    plugins = []

    for plugin_id, plugin in registry.plugins.items():
        manifest = registry.get_manifest(plugin_id)
        plugins.append({
            "id": plugin_id,
            "name": plugin.get_name(),
            "version": plugin.get_version(),
            "description": plugin.get_description(),
            "enabled": registry.is_enabled(plugin_id),
            "provides": manifest.get("provides", {}) if manifest else {},
            "config": manifest.get("config", {}) if manifest else {}
        })

    return {"plugins": plugins}


@app.get("/api/plugins/{plugin_id}")
async def get_plugin_details(plugin_id: str):
    """
    Get detailed information about a specific plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        Plugin details including manifest, capabilities, and status
    """
    registry = get_plugin_registry()
    plugin = registry.get_plugin(plugin_id)

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    manifest = registry.get_manifest(plugin_id)

    return {
        "id": plugin_id,
        "name": plugin.get_name(),
        "version": plugin.get_version(),
        "description": plugin.get_description(),
        "enabled": registry.is_enabled(plugin_id),
        "manifest": manifest,
        "capabilities": {
            "is_schema_plugin": hasattr(plugin, "get_schema"),
            "is_parser_plugin": hasattr(plugin, "parse_response"),
            "is_ui_plugin": hasattr(plugin, "get_ui_routes"),
            "is_export_plugin": hasattr(plugin, "export"),
            "is_rating_plugin": hasattr(plugin, "get_rating_categories")
        }
    }


@app.post("/api/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str):
    """
    Enable a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        Success message
    """
    registry = get_plugin_registry()
    plugin = registry.get_plugin(plugin_id)

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    registry.enable_plugin(plugin_id)

    return {
        "success": True,
        "message": f"Plugin {plugin_id} enabled",
        "plugin_id": plugin_id,
        "enabled": True
    }


@app.post("/api/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str):
    """
    Disable a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        Success message
    """
    registry = get_plugin_registry()
    plugin = registry.get_plugin(plugin_id)

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    registry.disable_plugin(plugin_id)

    return {
        "success": True,
        "message": f"Plugin {plugin_id} disabled",
        "plugin_id": plugin_id,
        "enabled": False
    }


@app.get("/api/plugins/{plugin_id}/ui-components")
async def get_plugin_ui_components(plugin_id: str):
    """
    Get UI components provided by a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        List of UI components with their templates and metadata
    """
    registry = get_plugin_registry()
    plugin = registry.get_plugin(plugin_id)

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    if not hasattr(plugin, "get_ui_components"):
        return {"components": []}

    components = plugin.get_ui_components()

    return {
        "plugin_id": plugin_id,
        "components": components
    }


@app.get("/api/plugins/by-type/{plugin_type}")
async def get_plugins_by_type(plugin_type: str):
    """
    Get all plugins of a specific type.

    Args:
        plugin_type: Plugin type (schema, parser, ui, export, rating)

    Returns:
        List of plugins matching the type
    """
    registry = get_plugin_registry()

    type_map = {
        "schema": registry.get_schema_plugins,
        "parser": registry.get_parser_plugins,
        "ui": registry.get_ui_plugins,
        "export": registry.get_export_plugins,
        "rating": registry.get_rating_plugins
    }

    if plugin_type not in type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plugin type. Must be one of: {', '.join(type_map.keys())}"
        )

    plugins = type_map[plugin_type]()

    return {
        "type": plugin_type,
        "plugins": [
            {
                "id": p.get_id(),
                "name": p.get_name(),
                "version": p.get_version(),
                "enabled": registry.is_enabled(p.get_id())
            }
            for p in plugins
        ]
    }


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


class ValidateModelRequest(BaseModel):
    """Request to validate model before installation."""
    model_id: str = Field(..., description="HuggingFace model ID")
    gguf_file: str = Field(..., description="Specific GGUF file to download")
    estimated_size_gb: float = Field(..., description="Estimated file size in GB")


@app.post("/api/models/validate")
async def validate_model_endpoint(request: ValidateModelRequest):
    """
    Validate model before installation.

    Checks:
    - Disk space available
    - Model not already installed
    - GGUF format supported

    Returns validation result with errors/warnings.
    """
    try:
        installer = ModelInstaller()
        result = installer.validate_pre_installation(
            model_id=request.model_id,
            gguf_file=request.gguf_file,
            estimated_size_gb=request.estimated_size_gb
        )
        return result
    except Exception as e:
        logger.error(f"Error validating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/{model_id}/verify")
async def verify_model_endpoint(model_id: str, gguf_file: str):
    """
    Verify model installation after download.

    Runs comprehensive verification:
    - File integrity check
    - Load test
    - Inference test
    - Mini-benchmark

    Returns verification results.
    """
    try:
        installer = ModelInstaller()
        result = installer.verify_installation(
            model_id=model_id,
            gguf_file=gguf_file
        )
        return result
    except Exception as e:
        logger.error(f"Error verifying model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RecommendQuantizationRequest(BaseModel):
    """Request to get quantization recommendation."""
    model_id: str = Field(..., description="HuggingFace model ID")
    gpu_memory_gb: float = Field(default=16.0, description="Available GPU memory in GB")
    use_case: str = Field(default='balanced', description="Use case: 'speed', 'balanced', or 'quality'")


@app.post("/api/models/recommend-quantization")
async def recommend_quantization_endpoint(request: RecommendQuantizationRequest):
    """
    Get quantization recommendation for a model.

    Analyzes model size and hardware constraints to recommend
    optimal quantization level.

    Args:
        model_id: HuggingFace model ID
        gpu_memory_gb: Available GPU memory (default: 16 GB for RTX 4080)
        use_case: Optimization target ('speed', 'balanced', 'quality')

    Returns:
        Recommended quantization with reasoning and alternatives
    """
    try:
        installer = ModelInstaller()
        result = installer.recommend_quantization(
            model_id=request.model_id,
            gpu_memory_gb=request.gpu_memory_gb,
            use_case=request.use_case
        )
        return result
    except Exception as e:
        logger.error(f"Error recommending quantization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Install model synchronously
        # Future: Could be made async for large downloads
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


@app.post("/v1/webhooks/label-studio")
async def label_studio_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive webhooks from Label Studio.

    Handles events:
    - TASK_CREATED: New task added
    - TASK_DELETED: Task removed
    - ANNOTATION_CREATED: New annotation submitted
    - ANNOTATION_UPDATED: Annotation modified
    - ANNOTATION_DELETED: Annotation removed
    - PROJECT_CREATED: New project created
    - PROJECT_UPDATED: Project settings changed
    - START_TRAINING: Training initiated

    Automated actions:
    - Validation on ANNOTATION_CREATED
    - Training trigger on 100th annotation
    - Data export on project completion
    """
    try:
        payload = await request.json()
        event_type = payload.get('action')

        logger.info(f"Received Label Studio webhook: {event_type}")

        # NOTE: Event storage not yet implemented
        # Future enhancement: Store events in LabelStudioEvent table for audit trail
        # For now, events are logged but not persisted to database

        # Handle different event types
        if event_type == 'ANNOTATION_CREATED':
            # Run validation checks
            annotation = payload.get('annotation', {})
            task = payload.get('task', {})
            project_id = payload.get('project', {}).get('id')

            logger.info(f"New annotation created: task_id={task.get('id')}, annotation_id={annotation.get('id')}")

            # Validation: Check if annotation is complete
            result = annotation.get('result', [])
            is_complete = len(result) > 0

            if not is_complete:
                logger.warning(f"Annotation {annotation.get('id')} is incomplete (no results)")

            # ========================================================================
            # RESULT HANDLER PROCESSING
            # ========================================================================
            # Process annotation through result handler pipeline
            # This allows custom integrations (e.g., database sync, webhooks)
            # to be triggered via plugins

            from core.result_handlers.base import get_registry

            task_data = task.get('data', {})
            is_gold_star = task.get('meta', {}).get('is_gold_star', False)

            # Also check annotation result for gold star flag
            for item in result:
                if item.get('type') == 'choices' and 'gold_star' in str(item.get('value', {})).lower():
                    is_gold_star = True
                    break

            if is_gold_star:
                logger.info(f"🌟 Gold star annotation detected")

                # Prepare metadata for result handlers
                metadata = {
                    'event_type': 'ANNOTATION_CREATED',
                    'action': action,
                    'project_id': project_id,
                    'task_id': task.get('id'),
                    'annotation_id': annotation.get('id'),
                    'is_gold_star': True,
                    **task_data  # Include all task data (may contain custom fields)
                }

                # Prepare results payload
                results = [{
                    'task_id': task.get('id'),
                    'annotation_id': annotation.get('id'),
                    'gold_star': True,
                    'notes': annotation.get('notes'),
                    'completed_by': annotation.get('completed_by', {}).get('email'),
                    'result': result
                }]

                # Execute all registered result handlers
                registry = get_registry()
                try:
                    registry.process_results(
                        batch_id=f"webhook_{annotation.get('id')}",
                        results=results,
                        metadata=metadata
                    )
                except Exception as e:
                    logger.error(f"❌ Error processing result handlers: {e}", exc_info=True)

            # Check annotation count for training trigger
            if project_id:
                from core.result_handlers.label_studio import LabelStudioHandler
                ls_handler = LabelStudioHandler()

                try:
                    # Get annotation count
                    annotations = ls_handler.export_annotations(project_id)
                    annotation_count = len(annotations)

                    logger.info(f"Project {project_id} now has {annotation_count} annotations")

                    # Trigger training at milestones (100, 500, 1000, etc.)
                    if annotation_count in [100, 500, 1000, 5000, 10000]:
                        logger.info(f"🎯 Milestone reached: {annotation_count} annotations! Consider training.")
                        # Note: Actual training would be triggered manually or via START_TRAINING event

                except Exception as e:
                    logger.error(f"Failed to check annotation count: {e}")

        elif event_type == 'ANNOTATION_UPDATED':
            annotation = payload.get('annotation', {})
            task = payload.get('task', {})
            logger.info(f"Annotation updated: annotation_id={annotation.get('id')}")

            # ========================================================================
            # RESULT HANDLER PROCESSING (for updates)
            # ========================================================================
            # Process annotation updates through result handler pipeline

            from core.result_handlers.base import get_registry

            task_data = task.get('data', {})
            is_gold_star = task.get('meta', {}).get('is_gold_star', False)

            # Also check annotation result for gold star flag
            result = annotation.get('result', [])
            for item in result:
                if item.get('type') == 'choices' and 'gold_star' in str(item.get('value', {})).lower():
                    is_gold_star = True
                    break

            if is_gold_star:
                logger.info(f"🌟 Gold star annotation updated")

                # Prepare metadata for result handlers
                metadata = {
                    'event_type': 'ANNOTATION_UPDATED',
                    'action': action,
                    'project_id': project_id,
                    'task_id': task.get('id'),
                    'annotation_id': annotation.get('id'),
                    'is_gold_star': True,
                    **task_data  # Include all task data
                }

                # Prepare results payload
                results = [{
                    'task_id': task.get('id'),
                    'annotation_id': annotation.get('id'),
                    'gold_star': True,
                    'notes': annotation.get('notes'),
                    'updated_by': annotation.get('updated_by', {}).get('email'),
                    'result': result
                }]

                # Execute all registered result handlers
                registry = get_registry()
                try:
                    registry.process_results(
                        batch_id=f"webhook_{annotation.get('id')}",
                        results=results,
                        metadata=metadata
                    )
                except Exception as e:
                    logger.error(f"❌ Error processing result handlers: {e}", exc_info=True)

            # Recalculate quality metrics if this is a ground truth annotation
            if annotation.get('ground_truth'):
                logger.info(f"Ground truth annotation updated: {annotation.get('id')}")

        elif event_type == 'TASK_CREATED':
            task = payload.get('task', {})
            logger.info(f"New task created: task_id={task.get('id')}")

        elif event_type == 'PROJECT_CREATED':
            project = payload.get('project', {})
            logger.info(f"New project created: project_id={project.get('id')}")

        elif event_type == 'PROJECT_UPDATED':
            project = payload.get('project', {})
            logger.info(f"Project updated: project_id={project.get('id')}")

        elif event_type == 'START_TRAINING':
            project = payload.get('project', {})
            project_id = project.get('id')
            logger.info(f"Training requested for project: project_id={project_id}")

            # Export annotations for training
            if project_id:
                from core.result_handlers.label_studio import LabelStudioHandler
                ls_handler = LabelStudioHandler()

                try:
                    # Export curated data
                    export_data = ls_handler.export_curated_data(
                        project_id=project_id
                    )

                    # Save to file
                    export_path = Path(settings.DATA_DIR) / "training" / f"project_{project_id}_export.json"
                    export_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(export_path, 'w') as f:
                        json.dump(export_data, f, indent=2)

                    logger.info(f"✅ Exported {len(export_data)} annotations to {export_path}")

                    return {
                        "status": "training_data_exported",
                        "event": event_type,
                        "export_path": str(export_path),
                        "annotation_count": len(export_data)
                    }

                except Exception as e:
                    logger.error(f"Failed to export training data: {e}")
                    return {
                        "status": "export_failed",
                        "event": event_type,
                        "error": str(e)
                    }

        return {"status": "received", "event": event_type}

    except Exception as e:
        logger.error(f"Error processing Label Studio webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DEPRECATED: Aris-specific endpoints
# ============================================================================
# The following endpoints are specific to the Aris integration and should be
# moved to the Aris repository (vllm-batch-server-aris).
# They are commented out here to prepare for OSS release.
# ============================================================================

# @app.get("/v1/icl/examples")
# async def get_icl_examples(...):
#     """
#     DEPRECATED: This endpoint is Aris-specific and should be moved to
#     the Aris repository. It fetches gold star examples from the Aristotle
#     database for in-context learning.
#
#     For OSS users: Implement your own ICL endpoint using the result handler
#     plugin system to fetch examples from your database.
#     """
#     pass


# @app.post("/v1/sync/victory-to-gold-star")
# async def sync_victory_to_gold_star(...):
#     """
#     DEPRECATED: This endpoint is Aris-specific and should be moved to
#     the Aris repository. It syncs VICTORY conquests from Aristotle to
#     Label Studio as gold stars (bidirectional sync).
#
#     For OSS users: Implement your own sync endpoint using the result handler
#     plugin system to integrate with your application's database.
#     """
#     pass


@app.post("/v1/webhooks/dead-letter/{dead_letter_id}/retry")
async def retry_failed_webhook(
    dead_letter_id: int,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Retry a failed webhook delivery from the dead letter queue.

    Attempts to resend the webhook with the original payload.

    Args:
        dead_letter_id: ID of the dead letter entry to retry
        force: If True, retry even if already successfully retried (default: False)
    """
    from .webhooks import send_webhook

    # Get dead letter entry
    dead_letter = db.query(WebhookDeadLetter).filter(
        WebhookDeadLetter.id == dead_letter_id
    ).first()

    if not dead_letter:
        raise HTTPException(status_code=404, detail="Dead letter entry not found")

    # Check if already successfully retried (unless force=True)
    if dead_letter.retry_success and not force:
        raise HTTPException(
            status_code=400,
            detail="Webhook already successfully retried. Use force=true to retry anyway."
        )

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
        "retried_at": dead_letter.retried_at.isoformat(),
        "forced": force
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


# ============================================================================
# Job History API
# ============================================================================

@app.get("/v1/jobs/history")
async def get_job_history(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    model: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Get job history with filtering and pagination.

    Args:
        limit: Number of jobs to return (default: 50, max: 500)
        offset: Number of jobs to skip (for pagination)
        status: Filter by status (validating, queued, in_progress, finalizing, completed, failed, cancelled, expired)
        model: Filter by model name
        start_date: Filter jobs created after this Unix timestamp
        end_date: Filter jobs created before this Unix timestamp

    Returns:
        {
            "jobs": [...],
            "total": 1234,
            "limit": 50,
            "offset": 0,
            "has_more": true
        }
    """
    # Validate limit
    limit = min(limit, 500)

    # Build query
    query = db.query(BatchJob)

    # Apply filters
    if status:
        query = query.filter(BatchJob.status == status)
    if model:
        query = query.filter(BatchJob.model == model)
    if start_date:
        query = query.filter(BatchJob.created_at >= start_date)
    if end_date:
        query = query.filter(BatchJob.created_at <= end_date)

    # Get total count
    total = query.count()

    # Get paginated results
    jobs = query.order_by(BatchJob.created_at.desc()).offset(offset).limit(limit).all()

    # Format response
    job_list = []
    for job in jobs:
        # Calculate duration
        duration = None
        if job.completed_at and job.created_at:
            duration = job.completed_at - job.created_at
        elif job.failed_at and job.created_at:
            duration = job.failed_at - job.created_at

        # Calculate request throughput
        request_throughput = None
        if duration and duration > 0 and job.completed_requests > 0:
            request_throughput = job.completed_requests / duration

        # Calculate token throughput (use stored value or calculate)
        token_throughput = job.throughput_tokens_per_sec
        if not token_throughput and duration and duration > 0 and job.total_tokens:
            token_throughput = job.total_tokens / duration

        job_list.append({
            "batch_id": job.batch_id,
            "status": job.status,
            "model": job.model,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "failed_at": job.failed_at,
            "cancelled_at": job.cancelled_at,
            "total_requests": job.total_requests,
            "completed_requests": job.completed_requests,
            "failed_requests": job.failed_requests,
            "duration": duration,
            "request_throughput": request_throughput,
            "total_tokens": job.total_tokens,
            "token_throughput": token_throughput,
            "priority": job.priority,
            "webhook_url": job.webhook_url is not None,
            "has_errors": job.errors is not None
        })

    return {
        "jobs": job_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }


@app.get("/v1/jobs/stats")
async def get_job_stats(
    start_date: int | None = None,
    end_date: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Get job statistics and analytics.

    Args:
        start_date: Filter jobs created after this Unix timestamp
        end_date: Filter jobs created before this Unix timestamp

    Returns:
        {
            "total_jobs": 1234,
            "by_status": {...},
            "by_model": {...},
            "success_rate": 0.978,
            "avg_duration": 45.2,
            "total_requests": 5678,
            "timeline": [...]
        }
    """
    from sqlalchemy import func

    # Build base query
    query = db.query(BatchJob)

    # Apply date filters
    if start_date:
        query = query.filter(BatchJob.created_at >= start_date)
    if end_date:
        query = query.filter(BatchJob.created_at <= end_date)

    # Total jobs
    total_jobs = query.count()

    # Jobs by status
    status_query = db.query(
        BatchJob.status,
        func.count(BatchJob.batch_id).label('count')
    )
    if start_date:
        status_query = status_query.filter(BatchJob.created_at >= start_date)
    if end_date:
        status_query = status_query.filter(BatchJob.created_at <= end_date)
    status_counts = status_query.group_by(BatchJob.status).all()

    by_status = {status: count for status, count in status_counts}

    # Jobs by model
    model_query = db.query(
        BatchJob.model,
        func.count(BatchJob.batch_id).label('count')
    )
    if start_date:
        model_query = model_query.filter(BatchJob.created_at >= start_date)
    if end_date:
        model_query = model_query.filter(BatchJob.created_at <= end_date)
    model_counts = model_query.group_by(BatchJob.model).all()

    by_model = {model: count for model, count in model_counts if model}

    # Success rate
    completed = by_status.get('completed', 0)
    failed = by_status.get('failed', 0)
    success_rate = completed / (completed + failed) if (completed + failed) > 0 else 0

    # Average duration (for completed jobs)
    completed_jobs = query.filter(BatchJob.status == 'completed').all()
    durations = []
    for job in completed_jobs:
        if job.completed_at and job.created_at:
            durations.append(job.completed_at - job.created_at)

    avg_duration = sum(durations) / len(durations) if durations else 0

    # Total requests
    total_requests_query = db.query(func.sum(BatchJob.total_requests))
    if start_date:
        total_requests_query = total_requests_query.filter(BatchJob.created_at >= start_date)
    if end_date:
        total_requests_query = total_requests_query.filter(BatchJob.created_at <= end_date)
    total_requests = total_requests_query.scalar() or 0

    completed_requests_query = db.query(func.sum(BatchJob.completed_requests))
    if start_date:
        completed_requests_query = completed_requests_query.filter(BatchJob.created_at >= start_date)
    if end_date:
        completed_requests_query = completed_requests_query.filter(BatchJob.created_at <= end_date)
    completed_requests = completed_requests_query.scalar() or 0

    # Total tokens
    total_tokens_query = db.query(func.sum(BatchJob.total_tokens)).filter(BatchJob.total_tokens.isnot(None))
    if start_date:
        total_tokens_query = total_tokens_query.filter(BatchJob.created_at >= start_date)
    if end_date:
        total_tokens_query = total_tokens_query.filter(BatchJob.created_at <= end_date)
    total_tokens = total_tokens_query.scalar() or 0

    # Average token throughput
    avg_token_throughput = db.query(func.avg(BatchJob.throughput_tokens_per_sec)).filter(
        BatchJob.created_at >= start_date if start_date else True,
        BatchJob.created_at <= end_date if end_date else True,
        BatchJob.throughput_tokens_per_sec.isnot(None)
    ).scalar() or 0

    # Timeline (jobs per hour for last 24 hours)
    import time
    now = int(time.time())
    timeline = []

    for i in range(24):
        hour_start = now - (i + 1) * 3600
        hour_end = now - i * 3600

        hour_jobs = db.query(func.count(BatchJob.batch_id)).filter(
            BatchJob.created_at >= hour_start,
            BatchJob.created_at < hour_end
        ).scalar() or 0

        timeline.append({
            "timestamp": hour_start,
            "jobs": hour_jobs
        })

    timeline.reverse()  # Oldest to newest

    return {
        "total_jobs": total_jobs,
        "by_status": by_status,
        "by_model": by_model,
        "success_rate": round(success_rate, 4),
        "avg_duration": round(avg_duration, 2),
        "total_requests": total_requests,
        "completed_requests": completed_requests,
        "total_tokens": total_tokens,
        "avg_token_throughput": round(avg_token_throughput, 2),
        "timeline": timeline
    }


# ============================================================================
# Aris Integration (Optional)
# ============================================================================

if settings.ENABLE_ARIS_INTEGRATION:
    try:
        from integrations.aris.conquest_api import router as aris_router
        app.include_router(aris_router)
        logger.info("✅ Aris integration enabled - mounted at /v1/aris")
    except ImportError as e:
        logger.warning(f"⚠️  Aris integration enabled but module not found: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to load Aris integration: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4080)
