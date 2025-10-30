"""
Database models and utilities for batch processing system.

Models:
- BatchJob: Main batch job tracking
- FailedRequest: Dead letter queue for failed requests
- WorkerHeartbeat: Worker health monitoring
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()


class BatchJob(Base):
    """Batch job model."""
    
    __tablename__ = 'batch_jobs'
    
    # Primary key
    batch_id = Column(String(64), primary_key=True)
    
    # Job metadata
    model = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False, default='pending')  # pending, running, completed, failed
    
    # File paths
    input_file = Column(String(512), nullable=False)
    output_file = Column(String(512), nullable=True)
    log_file = Column(String(512), nullable=True)
    
    # Progress tracking
    total_requests = Column(Integer, default=0)
    completed_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    
    # Performance metrics
    throughput_tokens_per_sec = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'batch_id': self.batch_id,
            'model': self.model,
            'status': self.status,
            'progress': {
                'total': self.total_requests,
                'completed': self.completed_requests,
                'failed': self.failed_requests,
                'percent': round(self.completed_requests / self.total_requests * 100, 2) if self.total_requests > 0 else 0
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'throughput_tokens_per_sec': self.throughput_tokens_per_sec,
            'total_tokens': self.total_tokens,
            'error_message': self.error_message,
            'results_url': f'/v1/batches/{self.batch_id}/results' if self.status == 'completed' else None,
            'output_file': self.output_file
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
DATABASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'database')
os.makedirs(DATABASE_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'batch_jobs.db')}"
engine = create_engine(DATABASE_URL, echo=False)
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

