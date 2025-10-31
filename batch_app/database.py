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
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import settings


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

    # Webhook support (custom extension)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    webhook_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0)
    webhook_last_attempt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    webhook_error: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    status: Mapped[str] = mapped_column(String(32), default='idle')  # idle, processing, error
    current_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # GPU metrics
    gpu_memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamp
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'status': self.status,
            'current_job_id': self.current_job_id,
            'gpu_memory_percent': self.gpu_memory_percent,
            'gpu_temperature': self.gpu_temperature,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'age_seconds': (datetime.utcnow() - self.last_seen).total_seconds() if self.last_seen else None
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

