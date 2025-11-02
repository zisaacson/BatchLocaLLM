"""
Database models and utilities for batch processing system.

Models:
- File: Uploaded files (OpenAI Files API compatible)
- BatchJob: Main batch job tracking (OpenAI Batch API compatible)
- FailedRequest: Dead letter queue for failed requests
- WorkerHeartbeat: Worker health monitoring

SQLAlchemy 2.0 with full type safety using Mapped[T] pattern.
"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

from core.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models with SQLAlchemy 2.0 type safety."""
    pass


class File(Base):
    """File model - OpenAI Files API compatible.

    SQLAlchemy 2.0 with Mapped[T] for full type safety.
    """

    __tablename__ = 'files'

    # Primary key
    file_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # OpenAI standard fields
    object: Mapped[str] = mapped_column(String(32), default='file')
    bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)  # Unix timestamp
    filename: Mapped[str] = mapped_column(String(512))
    purpose: Mapped[str] = mapped_column(String(32))  # "batch", "assistants", etc

    # Internal fields
    file_path: Mapped[str] = mapped_column(String(512))
    deleted: Mapped[bool] = mapped_column(default=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI Files API format."""
        return {
            'id': self.file_id,
            'object': self.object,
            'bytes': self.bytes,
            'created_at': self.created_at,
            'filename': self.filename,
            'purpose': self.purpose
        }


class BatchJob(Base):
    """Batch job model - OpenAI Batch API compatible.

    SQLAlchemy 2.0 with Mapped[T] for full type safety.
    """

    __tablename__ = 'batch_jobs'

    # Primary key
    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # OpenAI standard fields
    object: Mapped[str] = mapped_column(String(32), default='batch')
    endpoint: Mapped[str] = mapped_column(String(128), default='/v1/chat/completions')
    input_file_id: Mapped[str] = mapped_column(String(64), ForeignKey('files.file_id'))
    completion_window: Mapped[str] = mapped_column(String(16), default='24h')
    status: Mapped[str] = mapped_column(String(32), default='validating')
    # Status values: validating, failed, in_progress, finalizing, completed, expired, cancelling, cancelled

    # OpenAI file references (nullable)
    output_file_id: Mapped[str | None] = mapped_column(String(64), ForeignKey('files.file_id'), nullable=True)
    error_file_id: Mapped[str | None] = mapped_column(String(64), ForeignKey('files.file_id'), nullable=True)

    # OpenAI timestamps (Unix timestamps)
    created_at: Mapped[int] = mapped_column(Integer)
    in_progress_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[int] = mapped_column(Integer)
    finalizing_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expired_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelling_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # OpenAI request counts
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    completed_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)

    # OpenAI errors field (JSON string)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OpenAI metadata (JSON string)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Internal fields (not in OpenAI response)
    model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    log_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    throughput_tokens_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Progress tracking fields
    tokens_processed: Mapped[int] = mapped_column(Integer, default=0)
    current_throughput: Mapped[float] = mapped_column(Float, default=0.0)
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_progress_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_completion_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Priority queue support (custom extension)
    # -1 = low (testing/benchmarking), 0 = normal (default), 1 = high (production)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Webhook support (custom extension)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    webhook_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0)
    webhook_last_attempt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    webhook_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Per-webhook HMAC secret
    webhook_max_retries: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Custom retry count
    webhook_timeout: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Custom timeout in seconds
    webhook_events: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Comma-separated: completed,failed,progress

    def to_dict(self):
        """Convert to OpenAI Batch API format."""
        # Parse metadata
        metadata = {}
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass

        # Parse errors
        errors = None
        if self.errors:
            try:
                errors = json.loads(self.errors)
            except (json.JSONDecodeError, TypeError):
                errors = {"message": self.errors}

        return {
            'id': self.batch_id,
            'object': self.object,
            'endpoint': self.endpoint,
            'errors': errors,
            'input_file_id': self.input_file_id,
            'completion_window': self.completion_window,
            'status': self.status,
            'output_file_id': self.output_file_id,
            'error_file_id': self.error_file_id,
            'created_at': self.created_at,
            'in_progress_at': self.in_progress_at,
            'expires_at': self.expires_at,
            'finalizing_at': self.finalizing_at,
            'completed_at': self.completed_at,
            'failed_at': self.failed_at,
            'expired_at': self.expired_at,
            'cancelling_at': self.cancelling_at,
            'cancelled_at': self.cancelled_at,
            'request_counts': {
                'total': self.total_requests,
                'completed': self.completed_requests,
                'failed': self.failed_requests
            },
            'metadata': metadata
        }


class FailedRequest(Base):
    """Dead letter queue for failed requests.

    SQLAlchemy 2.0 with Mapped[T] for full type safety.
    """

    __tablename__ = 'failed_requests'

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to batch job
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey('batch_jobs.batch_id'))

    # Request identification
    custom_id: Mapped[str] = mapped_column(String(256))
    request_index: Mapped[int] = mapped_column(Integer)

    # Error details
    error_message: Mapped[str] = mapped_column(Text)
    error_type: Mapped[str] = mapped_column(String(64))

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'custom_id': self.custom_id,
            'request_index': self.request_index,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'retry_count': self.retry_count,
            'last_retry_at': self.last_retry_at.isoformat() if self.last_retry_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WorkerHeartbeat(Base):
    """Worker health monitoring.

    SQLAlchemy 2.0 with Mapped[T] for full type safety.
    """

    __tablename__ = 'worker_heartbeat'

    # Primary key (singleton table - only one row)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Worker status
    status: Mapped[str] = mapped_column(String(32), default='idle')  # idle, processing, error, testing
    current_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Model tracking (NEW - know what's loaded in GPU)
    loaded_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model_loaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Worker process tracking (NEW - detect zombies)
    worker_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worker_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # GPU metrics
    gpu_memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamp
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ModelRegistry(Base):
    """Model registry for tracking available models and their test results.

    SQLAlchemy 2.0 with Mapped[T] for full type safety.
    """

    __tablename__ = 'model_registry'

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Model identification
    model_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)  # HuggingFace ID
    name: Mapped[str] = mapped_column(String(256), nullable=False)  # Display name

    # Model metadata
    size_gb: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_memory_gb: Mapped[float] = mapped_column(Float, nullable=False)
    max_model_len: Mapped[int] = mapped_column(Integer, default=4096)
    gpu_memory_utilization: Mapped[float] = mapped_column(Float, default=0.90)
    cpu_offload_gb: Mapped[float] = mapped_column(Float, default=0.0)

    # GGUF-specific fields
    local_path: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Path to downloaded GGUF file
    quantization_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Q4_0, Q2_K, FP16, etc.

    # vLLM configuration
    enable_prefix_caching: Mapped[bool] = mapped_column(Boolean, default=True)
    chunked_prefill_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Compatibility
    rtx4080_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_hf_auth: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status tracking
    status: Mapped[str] = mapped_column(String(32), default='untested')  # untested, downloading, testing, tested, failed
    download_progress: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 to 1.0

    # Test results (JSON)
    test_results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    benchmark_results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # Performance metrics
    throughput_tokens_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    throughput_requests_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'name': self.name,
            'size_gb': self.size_gb,
            'estimated_memory_gb': self.estimated_memory_gb,
            'max_model_len': self.max_model_len,
            'gpu_memory_utilization': self.gpu_memory_utilization,
            'enable_prefix_caching': self.enable_prefix_caching,
            'chunked_prefill_enabled': self.chunked_prefill_enabled,
            'rtx4080_compatible': self.rtx4080_compatible,
            'requires_hf_auth': self.requires_hf_auth,
            'status': self.status,
            'download_progress': self.download_progress,
            'test_results': json.loads(self.test_results) if self.test_results else None,
            'benchmark_results': json.loads(self.benchmark_results) if self.benchmark_results else None,
            'throughput_tokens_per_sec': self.throughput_tokens_per_sec,
            'throughput_requests_per_sec': self.throughput_requests_per_sec,
            'avg_latency_ms': self.avg_latency_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tested_at': self.tested_at.isoformat() if self.tested_at else None
        }


# Database setup with PostgreSQL connection pooling
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    echo=settings.DATABASE_ECHO,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized at {DATABASE_URL}")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Dataset(Base):
    """
    Uploaded datasets for benchmarking.

    Stores JSONL files with candidate data that can be run through multiple models.
    """
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Benchmark(Base):
    """
    Benchmark runs - tracks running a model on a dataset.

    Stores progress, metrics, and results for model evaluation runs.
    """
    __tablename__ = "benchmarks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    model_id: Mapped[str] = mapped_column(String, ForeignKey("model_registry.model_id"), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # 'running', 'completed', 'failed'
    progress: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    throughput: Mapped[float] = mapped_column(Float, default=0.0)
    eta_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    results_file: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_file: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Annotation(Base):
    """
    Annotations for candidate results - golden examples, fixes, flags.

    Integrates with Label Studio for training data curation.
    """
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, ForeignKey("model_registry.model_id"), nullable=False)
    is_golden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_wrong: Mapped[bool] = mapped_column(Boolean, default=False)
    label_studio_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class WebhookDeadLetter(Base):
    """
    Dead Letter Queue for failed webhook deliveries.

    Tracks webhooks that failed after all retry attempts.
    Allows manual inspection and retry.
    """
    __tablename__ = "webhook_dead_letter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String, ForeignKey("batch_jobs.batch_id"), nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON payload
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    retried_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

