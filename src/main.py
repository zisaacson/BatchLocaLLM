"""
Ollama Batch Server - Main Application

FastAPI application providing OpenAI-compatible batch processing API.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.batch_processor import batch_processor
from src.benchmark_storage import BenchmarkStorage
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

# Initialize benchmark storage
benchmark_storage = BenchmarkStorage()


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    logger.info("Starting Ollama Batch Server")

    # Initialize storage
    await storage.initialize()

    # Initialize benchmark storage
    await benchmark_storage.init_db()

    # Initialize batch processor
    await batch_processor.initialize()

    logger.info("Ollama Batch Server started successfully")

    yield

    logger.info("Shutting down Ollama Batch Server")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Ollama Batch Server",
    description="OpenAI-compatible batch processing server powered by Ollama for consumer GPUs",
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
    from datetime import datetime, timezone

    try:
        # Check if backend is loaded
        model_loaded = batch_processor.backend is not None

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
            timestamp=datetime.now(timezone.utc),
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
            timestamp=datetime.now(timezone.utc),
        )


@app.get("/readiness")
async def readiness_check() -> JSONResponse:
    """Kubernetes readiness probe"""
    if batch_processor.backend is None:
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
                "uploaded_filename": file.filename,
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Error Handlers
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: object, exc: HTTPException) -> JSONResponse:
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
                "benchmarks": "/v1/benchmarks",
            },
        }
    )


# =============================================================================
# Benchmark Endpoints
# =============================================================================


@app.get("/v1/benchmarks/models")
async def list_benchmarked_models() -> JSONResponse:
    """List all models that have been benchmarked"""
    try:
        models = await benchmark_storage.get_all_models()

        # Get latest benchmark for each model
        model_data = []
        for model in models:
            benchmarks = await benchmark_storage.get_benchmarks_for_model(model, limit=1)
            if benchmarks:
                latest = benchmarks[0]
                model_data.append({
                    "model": model,
                    "model_size_params": latest.model_size_params,
                    "context_window": latest.context_window,
                    "rate_req_per_sec": latest.requests_per_second,
                    "success_rate_pct": latest.success_rate,
                    "workers": latest.num_workers,
                    "last_benchmarked": latest.created_at,
                })

        return JSONResponse({
            "models": model_data,
            "total": len(model_data),
        })

    except Exception as e:
        logger.error("Failed to list benchmarked models", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/v1/benchmarks/models/{model_name}")
async def get_model_benchmarks(model_name: str, limit: int = 10) -> JSONResponse:
    """Get benchmark history for a specific model"""
    try:
        benchmarks = await benchmark_storage.get_benchmarks_for_model(model_name, limit=limit)

        if not benchmarks:
            raise HTTPException(status_code=404, detail=f"No benchmarks found for model: {model_name}")

        benchmark_data = []
        for b in benchmarks:
            benchmark_data.append({
                "model": b.model_name,
                "model_size_params": b.model_size_params,
                "context_window": b.context_window,
                "num_requests": b.num_requests,
                "num_workers": b.num_workers,
                "rate_req_per_sec": b.requests_per_second,
                "time_per_request_sec": b.time_per_request_seconds,
                "success_rate_pct": b.success_rate,
                "avg_prompt_tokens": b.avg_prompt_tokens,
                "avg_completion_tokens": b.avg_completion_tokens,
                "benchmark_type": b.benchmark_type,
                "created_at": b.created_at,
            })

        return JSONResponse({
            "model": model_name,
            "benchmarks": benchmark_data,
            "total": len(benchmark_data),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get model benchmarks", extra={"model": model_name, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/v1/benchmarks/estimate")
async def estimate_batch_time(model: str, num_requests: int) -> JSONResponse:
    """Estimate processing time for a batch based on benchmarks"""
    try:
        benchmarks = await benchmark_storage.get_benchmarks_for_model(model, limit=1)

        if not benchmarks:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark data for model: {model}. Run benchmarks first."
            )

        latest = benchmarks[0]

        # Calculate estimates
        estimated_time_sec = num_requests / latest.requests_per_second
        estimated_time_hours = estimated_time_sec / 3600
        estimated_time_days = estimated_time_hours / 24

        return JSONResponse({
            "model": model,
            "num_requests": num_requests,
            "estimate": {
                "total_time_seconds": estimated_time_sec,
                "total_time_hours": estimated_time_hours,
                "total_time_days": estimated_time_days,
                "rate_req_per_sec": latest.requests_per_second,
                "time_per_request_sec": latest.time_per_request_seconds,
            },
            "based_on_benchmark": {
                "test_size": latest.num_requests,
                "workers": latest.num_workers,
                "success_rate_pct": latest.success_rate,
                "date": latest.created_at,
            },
            "token_estimate": {
                "avg_prompt_tokens": latest.avg_prompt_tokens,
                "avg_completion_tokens": latest.avg_completion_tokens,
                "total_tokens": ((latest.avg_prompt_tokens or 0) + (latest.avg_completion_tokens or 0)) * num_requests if latest.avg_prompt_tokens else None,
            } if latest.avg_prompt_tokens else None,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to estimate batch time", extra={"model": model, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/v1/benchmarks/compare")
async def compare_models(num_requests: int = 50000) -> JSONResponse:
    """Compare all benchmarked models for a specific workload"""
    try:
        models = await benchmark_storage.get_all_models()

        if not models:
            raise HTTPException(status_code=404, detail="No benchmark data available")

        comparisons = []
        for model in models:
            benchmarks = await benchmark_storage.get_benchmarks_for_model(model, limit=1)
            if benchmarks:
                latest = benchmarks[0]
                estimated_time = num_requests / latest.requests_per_second

                comparisons.append({
                    "model": model,
                    "model_size_params": latest.model_size_params,
                    "context_window": latest.context_window,
                    "rate_req_per_sec": latest.requests_per_second,
                    "estimated_time_hours": estimated_time / 3600,
                    "estimated_time_days": estimated_time / 86400,
                    "success_rate_pct": latest.success_rate,
                    "workers": latest.num_workers,
                })

        # Sort by speed (fastest first)
        comparisons.sort(key=lambda x: float(x["estimated_time_hours"]))  # type: ignore[arg-type]

        # Calculate speedups vs slowest
        if comparisons:
            slowest_time_val = comparisons[-1]["estimated_time_hours"]
            if isinstance(slowest_time_val, (int, float)):
                slowest_time = float(slowest_time_val)
                for comp in comparisons:
                    comp_time_val = comp["estimated_time_hours"]
                    if isinstance(comp_time_val, (int, float)):
                        comp_time = float(comp_time_val)
                        comp["speedup_vs_slowest"] = slowest_time / comp_time
                        comp["time_saved_hours"] = slowest_time - comp_time

        return JSONResponse({
            "num_requests": num_requests,
            "models": comparisons,
            "total_models": len(comparisons),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to compare models", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e)) from e

