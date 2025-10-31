"""
Database models and utilities for batch processing system.

Models:
- File: Uploaded files (OpenAI Files API compatible)
- BatchJob: Main batch job tracking (OpenAI Batch API compatible)
- FailedRequest: Dead letter queue for failed requests
- WorkerHeartbeat: Worker health monitoring
"""

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

Base = declarative_base()


class File(Base):  # type: ignore[valid-type,misc]
    """File model - OpenAI Files API compatible."""

    __tablename__ = 'files'

    # Primary key
    file_id = Column(String(64), primary_key=True)

    # OpenAI standard fields
    object = Column(String(32), default='file', nullable=False)
    bytes = Column(Integer, nullable=False)
    created_at = Column(Integer, nullable=False)  # Unix timestamp
    filename = Column(String(512), nullable=False)
    purpose = Column(String(32), nullable=False)  # "batch", "assistants", etc

    # Internal fields
    file_path = Column(String(512), nullable=False)
    deleted = Column(Boolean, default=False)

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
    """Batch job model - OpenAI Batch API compatible."""

    __tablename__ = 'batch_jobs'

    # Primary key
    batch_id = Column(String(64), primary_key=True)

    # OpenAI standard fields
    object = Column(String(32), default='batch', nullable=False)
    endpoint = Column(String(128), default='/v1/chat/completions', nullable=False)
    input_file_id = Column(String(64), ForeignKey('files.file_id'), nullable=False)
    completion_window = Column(String(16), default='24h', nullable=False)
    status = Column(String(32), nullable=False, default='validating')
    # Status values: validating, failed, in_progress, finalizing, completed, expired, cancelling, cancelled

    # OpenAI file references
    output_file_id = Column(String(64), ForeignKey('files.file_id'), nullable=True)
    error_file_id = Column(String(64), ForeignKey('files.file_id'), nullable=True)

    # OpenAI timestamps (Unix timestamps)
    created_at = Column(Integer, nullable=False)
    in_progress_at = Column(Integer, nullable=True)
    expires_at = Column(Integer, nullable=False)
    finalizing_at = Column(Integer, nullable=True)
    completed_at = Column(Integer, nullable=True)
    failed_at = Column(Integer, nullable=True)
    expired_at = Column(Integer, nullable=True)
    cancelling_at = Column(Integer, nullable=True)
    cancelled_at = Column(Integer, nullable=True)

    # OpenAI request counts
    total_requests = Column(Integer, default=0)
    completed_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)

    # OpenAI errors field
    errors = Column(Text, nullable=True)  # JSON string

    # OpenAI metadata
    metadata_json = Column(Text, nullable=True)  # JSON string

    # Internal fields (not in OpenAI response)
    model = Column(String(256), nullable=True)  # Extracted from input file
    log_file = Column(String(512), nullable=True)
    throughput_tokens_per_sec = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Webhook support (custom extension)
    webhook_url = Column(String(512), nullable=True)
    webhook_status = Column(String(32), nullable=True)
    webhook_attempts = Column(Integer, default=0)
    webhook_last_attempt = Column(DateTime, nullable=True)
    webhook_error = Column(Text, nullable=True)

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
    """Dead letter queue for failed requests."""

    __tablename__ = 'failed_requests'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to batch job
    batch_id = Column(String(64), ForeignKey('batch_jobs.batch_id'), nullable=False)

    # Request identification
    custom_id = Column(String(256), nullable=False)
    request_index = Column(Integer, nullable=False)

    # Error details
    error_message = Column(Text, nullable=False)
    error_type = Column(String(64), nullable=False)

    # Retry tracking
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

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
    """Worker health monitoring."""

    __tablename__ = 'worker_heartbeat'

    # Primary key (singleton table - only one row)
    id = Column(Integer, primary_key=True, default=1)

    # Worker status
    status = Column(String(32), default='idle')  # idle, processing, error
    current_job_id = Column(String(64), nullable=True)

    # GPU metrics
    gpu_memory_percent = Column(Float, nullable=True)
    gpu_temperature = Column(Float, nullable=True)

    # Timestamp
    last_seen = Column(DateTime, default=datetime.utcnow)

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


# Database setup
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL, echo=settings.DATABASE_ECHO)
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

