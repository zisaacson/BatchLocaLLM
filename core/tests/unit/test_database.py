"""Unit tests for database models."""

import pytest
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from batch_app.database import Base, File, BatchJob, FailedRequest, WorkerHeartbeat


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestFileModel:
    """Test File model."""
    
    def test_create_file(self, db_session):
        """Test creating a file record."""
        file = File(
            file_id='file-test123',
            filename='test.jsonl',
            file_path='/data/files/test.jsonl',
            purpose='batch',
            bytes=1024,
            created_at=int(time.time())
        )
        db_session.add(file)
        db_session.commit()
        
        # Query it back
        retrieved = db_session.query(File).filter(File.file_id == 'file-test123').first()
        assert retrieved is not None
        assert retrieved.filename == 'test.jsonl'
        assert retrieved.purpose == 'batch'
        assert retrieved.bytes == 1024
    
    def test_file_to_dict(self, db_session):
        """Test File.to_dict() method."""
        file = File(
            file_id='file-test123',
            filename='test.jsonl',
            file_path='/data/files/test.jsonl',
            purpose='batch',
            bytes=1024,
            created_at=int(time.time())
        )
        db_session.add(file)
        db_session.commit()
        
        file_dict = file.to_dict()
        assert file_dict['id'] == 'file-test123'
        assert file_dict['object'] == 'file'
        assert file_dict['filename'] == 'test.jsonl'
        assert file_dict['purpose'] == 'batch'
        assert file_dict['bytes'] == 1024
    
    def test_file_soft_delete(self, db_session):
        """Test soft delete functionality."""
        file = File(
            file_id='file-test123',
            filename='test.jsonl',
            file_path='/data/files/test.jsonl',
            purpose='batch',
            bytes=1024,
            created_at=int(time.time()),
            deleted=False
        )
        db_session.add(file)
        db_session.commit()
        
        # Soft delete
        file.deleted = True
        db_session.commit()
        
        # Query should still find it
        retrieved = db_session.query(File).filter(File.file_id == 'file-test123').first()
        assert retrieved is not None
        assert retrieved.deleted is True
        
        # Query excluding deleted should not find it
        active = db_session.query(File).filter(
            File.file_id == 'file-test123',
            ~File.deleted
        ).first()
        assert active is None


class TestBatchJobModel:
    """Test BatchJob model."""

    def test_create_batch_job(self, db_session):
        """Test creating a batch job."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='validating',
            created_at=now,
            expires_at=now + 86400  # 24 hours later
        )
        db_session.add(batch)
        db_session.commit()

        retrieved = db_session.query(BatchJob).filter(BatchJob.batch_id == 'batch-test123').first()
        assert retrieved is not None
        assert retrieved.endpoint == '/v1/chat/completions'
        assert retrieved.status == 'validating'

    def test_batch_job_to_dict(self, db_session):
        """Test BatchJob.to_dict() method."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='validating',
            created_at=now,
            expires_at=now + 86400
        )
        db_session.add(batch)
        db_session.commit()

        batch_dict = batch.to_dict()
        assert batch_dict['id'] == 'batch-test123'
        assert batch_dict['object'] == 'batch'
        assert batch_dict['input_file_id'] == 'file-input123'
        assert batch_dict['endpoint'] == '/v1/chat/completions'
        assert batch_dict['status'] == 'validating'

    def test_batch_job_status_transitions(self, db_session):
        """Test batch job status transitions."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='validating',
            created_at=now,
            expires_at=now + 86400
        )
        db_session.add(batch)
        db_session.commit()

        # Transition to in_progress
        batch.status = 'in_progress'
        batch.in_progress_at = int(time.time())
        db_session.commit()

        assert batch.status == 'in_progress'
        assert batch.in_progress_at is not None

        # Transition to completed
        batch.status = 'completed'
        batch.completed_at = int(time.time())
        batch.output_file_id = 'file-output123'
        db_session.commit()

        assert batch.status == 'completed'
        assert batch.completed_at is not None
        assert batch.output_file_id == 'file-output123'

    def test_batch_job_with_metadata(self, db_session):
        """Test batch job with metadata."""
        import json
        now = int(time.time())
        metadata = {'user_id': '123', 'project': 'test'}
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='validating',
            metadata_json=json.dumps(metadata),
            created_at=now,
            expires_at=now + 86400
        )
        db_session.add(batch)
        db_session.commit()

        retrieved = db_session.query(BatchJob).filter(BatchJob.batch_id == 'batch-test123').first()
        # The to_dict() method parses metadata_json
        batch_dict = retrieved.to_dict()
        assert batch_dict['metadata'] == metadata
        assert batch_dict['metadata']['user_id'] == '123'

    def test_batch_job_to_dict_with_invalid_metadata(self, db_session):
        """Test batch job to_dict with invalid metadata JSON."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='validating',
            created_at=now,
            expires_at=now + 86400,
            metadata_json='{ invalid json }'  # Invalid JSON
        )
        db_session.add(batch)
        db_session.commit()

        # Should handle invalid JSON gracefully (returns empty dict)
        result = batch.to_dict()
        assert result['metadata'] == {}  # Should be empty dict for invalid JSON

    def test_batch_job_to_dict_with_errors_string(self, db_session):
        """Test batch job to_dict with errors as string."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='failed',
            created_at=now,
            expires_at=now + 86400,
            errors='Simple error message'  # String error
        )
        db_session.add(batch)
        db_session.commit()

        # Should wrap string error in dict
        result = batch.to_dict()
        assert result['errors'] == {"message": "Simple error message"}

    def test_batch_job_to_dict_with_errors_json(self, db_session):
        """Test batch job to_dict with errors as JSON."""
        now = int(time.time())
        batch = BatchJob(
            batch_id='batch-test123',
            input_file_id='file-input123',
            endpoint='/v1/chat/completions',
            completion_window='24h',
            status='failed',
            created_at=now,
            expires_at=now + 86400,
            errors='{"code": "validation_error", "message": "Invalid input"}'  # JSON error
        )
        db_session.add(batch)
        db_session.commit()

        # Should parse JSON error
        result = batch.to_dict()
        assert result['errors'] == {"code": "validation_error", "message": "Invalid input"}


class TestFailedRequestModel:
    """Test FailedRequest model (dead letter queue)."""

    def test_create_failed_request(self, db_session):
        """Test creating a failed request."""
        failed = FailedRequest(
            batch_id='batch-test123',
            custom_id='req-1',
            request_index=0,
            error_message='Test error',
            error_type='ValueError'
        )
        db_session.add(failed)
        db_session.commit()

        retrieved = db_session.query(FailedRequest).filter(
            FailedRequest.batch_id == 'batch-test123'
        ).first()
        assert retrieved is not None
        assert retrieved.custom_id == 'req-1'
        assert retrieved.error_message == 'Test error'

    def test_failed_request_to_dict(self, db_session):
        """Test FailedRequest.to_dict() method."""
        failed = FailedRequest(
            batch_id='batch-test123',
            custom_id='req-1',
            request_index=0,
            error_message='Test error',
            error_type='ValueError'
        )
        db_session.add(failed)
        db_session.commit()

        failed_dict = failed.to_dict()
        assert failed_dict['batch_id'] == 'batch-test123'
        assert failed_dict['custom_id'] == 'req-1'
        assert failed_dict['error_message'] == 'Test error'
        assert failed_dict['error_type'] == 'ValueError'

    def test_query_failed_requests_by_batch(self, db_session):
        """Test querying failed requests by batch ID."""
        # Create multiple failed requests
        for i in range(3):
            failed = FailedRequest(
                batch_id='batch-test123',
                custom_id=f'req-{i}',
                request_index=i,
                error_message=f'Error {i}',
                error_type='ValueError'
            )
            db_session.add(failed)
        db_session.commit()

        # Query all failed requests for batch
        failed_requests = db_session.query(FailedRequest).filter(
            FailedRequest.batch_id == 'batch-test123'
        ).all()

        assert len(failed_requests) == 3
        assert all(fr.batch_id == 'batch-test123' for fr in failed_requests)


class TestWorkerHeartbeatModel:
    """Test WorkerHeartbeat model."""

    def test_create_worker_heartbeat(self, db_session):
        """Test creating a worker heartbeat."""
        heartbeat = WorkerHeartbeat(
            status='processing',
            current_job_id='batch-test123',
            gpu_memory_percent=75.0,
            gpu_temperature=65.0
        )
        db_session.add(heartbeat)
        db_session.commit()

        retrieved = db_session.query(WorkerHeartbeat).filter(
            WorkerHeartbeat.id == 1
        ).first()
        assert retrieved is not None
        assert retrieved.status == 'processing'
        assert retrieved.current_job_id == 'batch-test123'

    def test_update_worker_heartbeat(self, db_session):
        """Test updating worker heartbeat."""
        heartbeat = WorkerHeartbeat(
            status='processing'
        )
        db_session.add(heartbeat)
        db_session.commit()

        # Update heartbeat
        heartbeat.current_job_id = 'batch-new123'
        heartbeat.gpu_memory_percent = 80.0
        db_session.commit()

        retrieved = db_session.query(WorkerHeartbeat).filter(
            WorkerHeartbeat.id == 1
        ).first()
        assert retrieved.current_job_id == 'batch-new123'
        assert retrieved.gpu_memory_percent == 80.0

    def test_worker_status_transitions(self, db_session):
        """Test worker status transitions."""
        heartbeat = WorkerHeartbeat(
            status='idle'
        )
        db_session.add(heartbeat)
        db_session.commit()

        # Transition to processing
        heartbeat.status = 'processing'
        heartbeat.current_job_id = 'batch-test123'
        db_session.commit()

        assert heartbeat.status == 'processing'

        # Transition back to idle
        heartbeat.status = 'idle'
        heartbeat.current_job_id = None
        db_session.commit()

        assert heartbeat.status == 'idle'
        assert heartbeat.current_job_id is None

