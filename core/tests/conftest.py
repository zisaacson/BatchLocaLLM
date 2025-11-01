"""Shared pytest fixtures for all tests.

This module provides reusable fixtures to reduce code duplication and
standardize test setup across the test suite.

Fixtures:
- temp_jsonl_file: Temporary JSONL file for testing
- temp_log_file: Temporary log file for testing
- temp_dir: Temporary directory for testing
- mock_prometheus_metrics: Mock Prometheus metrics (session-scoped)
- mock_vllm_engine: Mock vLLM engine for testing
- test_db_session: Test database session
"""

import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.batch_app.database import Base


# ============================================================================
# Prometheus Metrics Mock (Session-scoped, Auto-use)
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def mock_prometheus_metrics():
    """Mock Prometheus metrics module to avoid registration conflicts.
    
    This fixture runs once per test session and automatically mocks the
    metrics module before any tests import it. This prevents the
    "Duplicated timeseries" error from Prometheus.
    
    Auto-use: Yes (runs automatically for all tests)
    Scope: Session (runs once per pytest session)
    """
    if 'core.batch_app.metrics' not in sys.modules:
        # Create mock metrics module
        mock_metrics = Mock()
        
        # Mock all metric objects
        mock_metrics.chunk_processing_duration = Mock()
        mock_metrics.chunk_size = Mock()
        mock_metrics.chunks_processed = Mock()
        mock_metrics.tokens_generated = Mock()
        mock_metrics.throughput_tokens_per_second = Mock()
        mock_metrics.request_count = Mock()
        mock_metrics.batch_jobs_total = Mock()
        mock_metrics.errors_total = Mock()
        mock_metrics.gpu_memory_used = Mock()
        mock_metrics.gpu_temperature = Mock()
        mock_metrics.active_batches = Mock()
        mock_metrics.queue_depth = Mock()
        mock_metrics.processing_duration = Mock()
        
        # Add labels() method that returns self for chaining
        # This allows: metrics.chunk_size.labels(batch_id="123").set(100)
        for attr_name in dir(mock_metrics):
            attr = getattr(mock_metrics, attr_name)
            if isinstance(attr, Mock) and not attr_name.startswith('_'):
                attr.labels = Mock(return_value=attr)
                attr.observe = Mock()
                attr.inc = Mock()
                attr.dec = Mock()
                attr.set = Mock()
        
        # Inject mock into sys.modules
        sys.modules['core.batch_app.metrics'] = mock_metrics
    
    yield sys.modules['core.batch_app.metrics']


# ============================================================================
# Temporary File Fixtures
# ============================================================================

@pytest.fixture
def temp_jsonl_file():
    """Create a temporary JSONL file for testing.
    
    Usage:
        def test_something(temp_jsonl_file):
            temp_jsonl_file.write('{"custom_id": "1", "body": {...}}\\n')
            temp_jsonl_file.flush()
            # Use temp_jsonl_file.name for the file path
    
    The file is automatically deleted after the test completes.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        yield f
    
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing.
    
    Usage:
        def test_something(temp_log_file):
            temp_log_file.write('log entry\\n')
            temp_log_file.flush()
            # Use temp_log_file.name for the file path
    
    The file is automatically deleted after the test completes.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False, encoding='utf-8') as f:
        yield f
    
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing.
    
    Usage:
        def test_something(temp_dir):
            file_path = temp_dir / "test.txt"
            file_path.write_text("content")
    
    The directory and all contents are automatically deleted after the test.
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_path, ignore_errors=True)


# ============================================================================
# vLLM Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_vllm_engine():
    """Create a mock vLLM engine for testing.
    
    Usage:
        def test_something(mock_vllm_engine):
            mock_vllm_engine.generate.return_value = [
                {"text": "response", "tokens": 10}
            ]
            # Use mock_vllm_engine in tests
    
    The mock includes:
    - generate() method that returns mock responses
    - get_model_config() method
    - Configurable return values
    """
    mock_engine = MagicMock()
    
    # Mock generate method
    mock_engine.generate.return_value = [
        MagicMock(
            outputs=[
                MagicMock(
                    text="This is a test response",
                    token_ids=[1, 2, 3, 4, 5]
                )
            ]
        )
    ]
    
    # Mock model config
    mock_config = MagicMock()
    mock_config.max_model_len = 8192
    mock_engine.get_model_config.return_value = mock_config
    
    return mock_engine


@pytest.fixture
def mock_vllm_llm_class():
    """Create a mock vLLM LLM class for testing.
    
    Usage:
        def test_something(mock_vllm_llm_class):
            with patch('core.batch_app.worker.LLM', mock_vllm_llm_class):
                # Test code that creates LLM instances
    
    The mock LLM class returns a mock engine when instantiated.
    """
    mock_llm_class = MagicMock()
    mock_engine = MagicMock()
    
    # Configure mock engine
    mock_engine.generate.return_value = [
        MagicMock(
            outputs=[
                MagicMock(
                    text="Test response",
                    token_ids=[1, 2, 3]
                )
            ]
        )
    ]
    
    mock_llm_class.return_value = mock_engine
    
    return mock_llm_class


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def test_db_engine():
    """Create an in-memory SQLite database engine for testing.
    
    Usage:
        def test_something(test_db_engine):
            # Use test_db_engine for database operations
    
    The database is created fresh for each test and destroyed after.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session.
    
    Usage:
        def test_something(test_db_session):
            # Use test_db_session for database operations
            batch = BatchJob(...)
            test_db_session.add(batch)
            test_db_session.commit()
    
    The session is automatically rolled back and closed after the test.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    
    session = TestingSessionLocal()
    
    yield session
    
    # Cleanup
    session.rollback()
    session.close()


# ============================================================================
# GPU Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_gpu_healthy():
    """Mock pynvml to return healthy GPU status.
    
    Usage:
        def test_something(mock_gpu_healthy):
            with mock_gpu_healthy:
                result = check_gpu_health()
                assert result['healthy'] is True
    
    Returns a context manager that patches pynvml functions.
    """
    from unittest.mock import patch
    
    def _mock_gpu(memory_used_gb=8, memory_total_gb=16, temperature_c=65):
        """Create GPU mock with specified values."""
        mock_mem_info = Mock()
        mock_mem_info.used = memory_used_gb * 1024**3
        mock_mem_info.total = memory_total_gb * 1024**3
        
        patches = [
            patch('pynvml.nvmlInit'),
            patch('pynvml.nvmlDeviceGetHandleByIndex'),
            patch('pynvml.nvmlDeviceGetMemoryInfo', return_value=mock_mem_info),
            patch('pynvml.nvmlDeviceGetTemperature', return_value=temperature_c),
            patch('pynvml.nvmlShutdown'),
        ]
        
        return patches
    
    return _mock_gpu


# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def make_batch_request():
    """Factory for creating test batch requests.
    
    Usage:
        def test_something(make_batch_request):
            request = make_batch_request(metadata={"custom": "value"})
    
    Returns a function that creates CreateBatchRequest objects with defaults.
    """
    from core.batch_app.api_server import CreateBatchRequest
    
    def _make_request(**overrides):
        defaults = {
            "input_file_id": "file-test123",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        }
        return CreateBatchRequest(**{**defaults, **overrides})
    
    return _make_request


@pytest.fixture
def make_jsonl_request():
    """Factory for creating test JSONL request objects.
    
    Usage:
        def test_something(make_jsonl_request):
            request = make_jsonl_request(custom_id="req-1", content="Hello")
    
    Returns a function that creates JSONL request dicts with defaults.
    """
    def _make_request(custom_id="req-1", content="Test message", model="test-model", **overrides):
        defaults = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "user", "content": content}
                ]
            }
        }
        
        # Merge overrides
        result = {**defaults, **overrides}
        if "body" in overrides:
            result["body"] = {**defaults["body"], **overrides["body"]}
        
        return result
    
    return _make_request

