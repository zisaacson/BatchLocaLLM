# =============================================================================
# vLLM Batch Server - Production Dockerfile
# =============================================================================
# 
# Multi-stage build for optimized image size and security
# Supports NVIDIA GPUs with CUDA 12.1+
#
# Build: docker build -t vllm-batch-server .
# Run: docker run --gpus all -p 8000:8000 vllm-batch-server
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base image with CUDA and Python
# -----------------------------------------------------------------------------
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS base

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# -----------------------------------------------------------------------------
# Stage 2: Build vLLM and dependencies
# -----------------------------------------------------------------------------
FROM base AS builder

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml ./

# Install vLLM with CUDA support
# This is the most time-consuming step, so we do it separately for caching
RUN pip install --no-cache-dir vllm>=0.6.0

# Install application dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.32.0 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.6.0 \
    python-multipart>=0.0.12 \
    aiofiles>=24.1.0 \
    sqlalchemy>=2.0.0 \
    aiosqlite>=0.20.0 \
    python-json-logger>=3.2.0 \
    prometheus-client>=0.21.0

# -----------------------------------------------------------------------------
# Stage 3: Runtime image
# -----------------------------------------------------------------------------
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS runtime

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash vllm && \
    mkdir -p /app /data/batches && \
    chown -R vllm:vllm /app /data

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=vllm:vllm src/ ./src/

# Switch to non-root user
USER vllm

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    # vLLM environment variables
    VLLM_WORKER_MULTIPROC_METHOD=spawn \
    # CUDA environment variables
    CUDA_VISIBLE_DEVICES=0 \
    # Storage paths
    STORAGE_PATH=/data/batches \
    DATABASE_PATH=/data/vllm_batch.db

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

