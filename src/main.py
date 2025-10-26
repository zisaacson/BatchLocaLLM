"""
vLLM Batch Server - Main Application

FastAPI application providing OpenAI-compatible batch processing API.
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.batch_processor import batch_processor
from src.config import settings
from src.logger import logger
from src.models import (
    BatchCreateRequest,
    BatchJob,
    BatchStatus,
    ErrorResponse,
    FileUploadResponse,
    HealthCheck,
    HealthStatus,
    RequestCounts,
)
from src.storage import storage


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    logger.info("Starting vLLM Batch Server")

    # Initialize storage
    await storage.initialize()

    # Initialize batch processor
    await batch_processor.initialize()

    logger.info("vLLM Batch Server started successfully")

    yield

    logger.info("Shutting down vLLM Batch Server")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="vLLM Batch Server",
    description="Production-ready OpenAI-compatible batch processing server powered by vLLM",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
if settings.enable_cors:
    origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# =============================================================================
# Health Check Endpoints
# =============================================================================


@app.get("/health", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    """Health check endpoint"""
    try:
        # Check if vLLM engine is loaded
        model_loaded = batch_processor.llm is not None

        # Get GPU info if available
        gpu_available = False
        gpu_memory_used_gb = None
        gpu_memory_total_gb = None

        try:
            import torch

            if torch.cuda.is_available():
                gpu_available = True
                gpu_memory_used_gb = torch.cuda.memory_allocated(0) / 1024**3
                gpu_memory_total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        except Exception:
            pass

        # Get active batches
        active_batches = len(batch_processor.processing_jobs)

        return HealthCheck(
            status=HealthStatus.HEALTHY if model_loaded else HealthStatus.DEGRADED,
            timestamp=time.time(),
            model_loaded=model_loaded,
            active_batches=active_batches,
            gpu_available=gpu_available,
            gpu_memory_used_gb=gpu_memory_used_gb,
            gpu_memory_total_gb=gpu_memory_total_gb,
        )
    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        return HealthCheck(
            status=HealthStatus.UNHEALTHY,
            timestamp=time.time(),
        )


@app.get("/readiness")
async def readiness_check() -> JSONResponse:
    """Kubernetes readiness probe"""
    if batch_processor.llm is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return JSONResponse({"status": "ready"})


@app.get("/liveness")
async def liveness_check() -> JSONResponse:
    """Kubernetes liveness probe"""
    return JSONResponse({"status": "alive"})


# =============================================================================
# File Endpoints
# =============================================================================


@app.post("/v1/files", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = Form("batch"),
) -> FileUploadResponse:
    """Upload a file for batch processing"""
    try:
        # Validate purpose
        if purpose not in ["batch", "batch_output", "batch_error"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid purpose: {purpose}. Must be 'batch', 'batch_output', or 'batch_error'",
            )

        # Read file content
        content = await file.read()

        # Validate file size
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > settings.max_batch_file_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size_mb:.2f} MB) exceeds maximum ({settings.max_batch_file_size_mb} MB)",
            )

        # Generate file ID
        file_id = f"file-{uuid.uuid4().hex}"

        # Save file
        file_obj = await storage.save_file(
            file_id=file_id,
            filename=file.filename or "batch_input.jsonl",
            content=content,
            purpose=purpose,
        )

        logger.info(
            "File uploaded",
            extra={
                "file_id": file_id,
                "filename": file.filename,
                "bytes": len(content),
                "purpose": purpose,
            },
        )

        return FileUploadResponse(
            id=file_obj.id,
            bytes=file_obj.bytes,
            created_at=file_obj.created_at,
            filename=file_obj.filename,
            purpose=file_obj.purpose,  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload failed", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/files/{file_id}/content")
async def get_file_content(file_id: str) -> PlainTextResponse:
    """Download file content"""
    try:
        content = await storage.read_file(file_id)
        if content is None:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        return PlainTextResponse(content.decode("utf-8"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File download failed", extra={"file_id": file_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Endpoints
# =============================================================================


@app.post("/v1/batches", response_model=BatchJob, status_code=status.HTTP_201_CREATED)
async def create_batch(request: BatchCreateRequest) -> BatchJob:
    """Create a new batch job"""
    try:
        # Verify input file exists
        file_obj = await storage.get_file(request.input_file_id)
        if not file_obj:
            raise HTTPException(
                status_code=404, detail=f"Input file not found: {request.input_file_id}"
            )

        # Create batch job
        batch_id = f"batch_{uuid.uuid4().hex}"
        batch_job = BatchJob(
            id=batch_id,
            status=BatchStatus.VALIDATING,
            input_file_id=request.input_file_id,
            endpoint=request.endpoint,
            completion_window=request.completion_window,
            created_at=int(time.time()),
            request_counts=RequestCounts(),
            metadata=request.metadata,
        )

        # Save to database
        await storage.create_batch_job(batch_job)

        logger.info(
            "Batch job created",
            extra={
                "batch_id": batch_id,
                "input_file_id": request.input_file_id,
                "metadata": request.metadata,
            },
        )

        # Start processing in background
        asyncio.create_task(batch_processor.process_batch(batch_id))

        return batch_job

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch creation failed", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/batches/{batch_id}", response_model=BatchJob)
async def get_batch(batch_id: str) -> BatchJob:
    """Get batch job status"""
    try:
        batch_job = await storage.get_batch_job(batch_id)
        if not batch_job:
            raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

        return batch_job

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get batch", extra={"batch_id": batch_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/batches/{batch_id}/cancel", response_model=BatchJob)
async def cancel_batch(batch_id: str) -> BatchJob:
    """Cancel a batch job"""
    try:
        batch_job = await storage.get_batch_job(batch_id)
        if not batch_job:
            raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

        # Only cancel if not already completed/failed
        if batch_job.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel batch in status: {batch_job.status}"
            )

        # Update status
        batch_job.status = BatchStatus.CANCELLED
        batch_job.cancelled_at = int(time.time())
        await storage.update_batch_job(batch_job)

        logger.info("Batch cancelled", extra={"batch_id": batch_id})

        return batch_job

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel batch", extra={"batch_id": batch_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Error Handlers
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error={
                "message": exc.detail,
                "type": "invalid_request_error",
                "code": str(exc.status_code),
            }
        ).model_dump(),
    )


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint"""
    return JSONResponse(
        {
            "name": "vLLM Batch Server",
            "version": "0.1.0",
            "model": settings.model_name,
            "endpoints": {
                "health": "/health",
                "files": "/v1/files",
                "batches": "/v1/batches",
            },
        }
    )

