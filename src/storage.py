"""
Storage layer for batch jobs and files

Handles:
- File storage (JSONL input/output files)
- Job metadata persistence (SQLite)
- Cleanup of old jobs
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import aiofiles
from sqlalchemy import Column, Integer, String, Text, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings
from src.logger import logger
from src.models import BatchJob, BatchStatus, FileObject, RequestCounts

# =============================================================================
# Database Models
# =============================================================================

Base = declarative_base()


class BatchJobDB(Base):
    """Database model for batch jobs"""

    __tablename__ = "batch_jobs"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    input_file_id = Column(String, nullable=False)
    output_file_id = Column(String, nullable=True)
    error_file_id = Column(String, nullable=True)
    created_at = Column(Integer, nullable=False)
    in_progress_at = Column(Integer, nullable=True)
    completed_at = Column(Integer, nullable=True)
    failed_at = Column(Integer, nullable=True)
    cancelled_at = Column(Integer, nullable=True)
    request_counts_json = Column(Text, nullable=False, default="{}")
    metadata_json = Column(Text, nullable=True)
    endpoint = Column(String, nullable=False, default="/v1/chat/completions")
    completion_window = Column(String, nullable=False, default="24h")


class FileDB(Base):
    """Database model for files"""

    __tablename__ = "files"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    bytes = Column(Integer, nullable=False)
    created_at = Column(Integer, nullable=False)
    purpose = Column(String, nullable=False)


# =============================================================================
# Storage Manager
# =============================================================================


class StorageManager:
    """Manages file storage and database operations"""

    def __init__(self) -> None:
        self.storage_path = Path(settings.storage_path)
        self.files_path = self.storage_path / "files"
        self.results_path = self.storage_path / "results"

        # Create directories
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.files_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)

        # Database setup
        db_url = f"sqlite+aiosqlite:///{settings.database_path}"
        self.engine = create_async_engine(db_url, echo=settings.debug)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info(
            "Storage manager initialized",
            extra={
                "storage_path": str(self.storage_path),
                "database_path": settings.database_path,
            },
        )

    async def initialize(self) -> None:
        """Initialize database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    # =========================================================================
    # File Operations
    # =========================================================================

    async def save_file(
        self, file_id: str, filename: str, content: bytes, purpose: str = "batch"
    ) -> FileObject:
        """Save a file to storage"""
        file_path = self.files_path / file_id
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        file_obj = FileObject(
            id=file_id,
            filename=filename,
            bytes=len(content),
            created_at=int(time.time()),
            purpose=purpose,  # type: ignore
        )

        # Save to database
        async with self.async_session() as session:
            file_db = FileDB(
                id=file_id,
                filename=filename,
                bytes=len(content),
                created_at=file_obj.created_at,
                purpose=purpose,
            )
            session.add(file_db)
            await session.commit()

        logger.info(
            "File saved",
            extra={
                "file_id": file_id,
                "filename": filename,
                "bytes": len(content),
                "purpose": purpose,
            },
        )

        return file_obj

    async def get_file(self, file_id: str) -> Optional[FileObject]:
        """Get file metadata"""
        async with self.async_session() as session:
            result = await session.execute(select(FileDB).where(FileDB.id == file_id))
            file_db = result.scalar_one_or_none()

            if not file_db:
                return None

            return FileObject(
                id=file_db.id,
                filename=file_db.filename,
                bytes=file_db.bytes,
                created_at=file_db.created_at,
                purpose=file_db.purpose,  # type: ignore
            )

    async def read_file(self, file_id: str) -> Optional[bytes]:
        """Read file content"""
        file_path = self.files_path / file_id
        if not file_path.exists():
            # Try results path
            file_path = self.results_path / file_id
            if not file_path.exists():
                return None

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file"""
        file_path = self.files_path / file_id
        if file_path.exists():
            file_path.unlink()

        result_path = self.results_path / file_id
        if result_path.exists():
            result_path.unlink()

        async with self.async_session() as session:
            result = await session.execute(select(FileDB).where(FileDB.id == file_id))
            file_db = result.scalar_one_or_none()
            if file_db:
                await session.delete(file_db)
                await session.commit()

        logger.info("File deleted", extra={"file_id": file_id})
        return True

    # =========================================================================
    # Batch Job Operations
    # =========================================================================

    async def create_batch_job(self, batch_job: BatchJob) -> BatchJob:
        """Create a new batch job"""
        async with self.async_session() as session:
            job_db = BatchJobDB(
                id=batch_job.id,
                status=batch_job.status.value,
                input_file_id=batch_job.input_file_id,
                output_file_id=batch_job.output_file_id,
                error_file_id=batch_job.error_file_id,
                created_at=batch_job.created_at,
                in_progress_at=batch_job.in_progress_at,
                completed_at=batch_job.completed_at,
                failed_at=batch_job.failed_at,
                cancelled_at=batch_job.cancelled_at,
                request_counts_json=batch_job.request_counts.model_dump_json(),
                metadata_json=json.dumps(batch_job.metadata) if batch_job.metadata else None,
                endpoint=batch_job.endpoint,
                completion_window=batch_job.completion_window,
            )
            session.add(job_db)
            await session.commit()

        logger.info("Batch job created", extra={"batch_id": batch_job.id})
        return batch_job

    async def get_batch_job(self, batch_id: str) -> Optional[BatchJob]:
        """Get batch job by ID"""
        async with self.async_session() as session:
            result = await session.execute(select(BatchJobDB).where(BatchJobDB.id == batch_id))
            job_db = result.scalar_one_or_none()

            if not job_db:
                return None

            return self._db_to_batch_job(job_db)

    async def update_batch_job(self, batch_job: BatchJob) -> BatchJob:
        """Update batch job"""
        async with self.async_session() as session:
            result = await session.execute(select(BatchJobDB).where(BatchJobDB.id == batch_job.id))
            job_db = result.scalar_one_or_none()

            if not job_db:
                raise ValueError(f"Batch job not found: {batch_job.id}")

            job_db.status = batch_job.status.value
            job_db.output_file_id = batch_job.output_file_id
            job_db.error_file_id = batch_job.error_file_id
            job_db.in_progress_at = batch_job.in_progress_at
            job_db.completed_at = batch_job.completed_at
            job_db.failed_at = batch_job.failed_at
            job_db.cancelled_at = batch_job.cancelled_at
            job_db.request_counts_json = batch_job.request_counts.model_dump_json()

            await session.commit()

        logger.info("Batch job updated", extra={"batch_id": batch_job.id, "status": batch_job.status})
        return batch_job

    async def list_batch_jobs(self, limit: int = 100) -> List[BatchJob]:
        """List all batch jobs"""
        async with self.async_session() as session:
            result = await session.execute(select(BatchJobDB).limit(limit))
            jobs_db = result.scalars().all()
            return [self._db_to_batch_job(job_db) for job_db in jobs_db]

    def _db_to_batch_job(self, job_db: BatchJobDB) -> BatchJob:
        """Convert database model to BatchJob"""
        request_counts = RequestCounts.model_validate_json(job_db.request_counts_json)
        metadata = json.loads(job_db.metadata_json) if job_db.metadata_json else None

        return BatchJob(
            id=job_db.id,
            status=BatchStatus(job_db.status),
            input_file_id=job_db.input_file_id,
            output_file_id=job_db.output_file_id,
            error_file_id=job_db.error_file_id,
            created_at=job_db.created_at,
            in_progress_at=job_db.in_progress_at,
            completed_at=job_db.completed_at,
            failed_at=job_db.failed_at,
            cancelled_at=job_db.cancelled_at,
            request_counts=request_counts,
            metadata=metadata,
            endpoint=job_db.endpoint,
            completion_window=job_db.completion_window,
        )


# Global storage manager instance
storage = StorageManager()

