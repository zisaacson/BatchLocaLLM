"""Unit tests for Prometheus metrics - streamlined version.

Reduced from 25 tests to 5 tests focusing on core functionality:
- Metric registration
- Counter operations
- Histogram operations
- Gauge operations
- Helper functions
"""

import pytest

# Metrics module is now mocked in conftest.py (session-scoped fixture)
# No need to conditionally import it here anymore!
from core.batch_app import metrics


class TestMetrics:
    """Test Prometheus metrics collection - core functionality only."""

    def test_all_critical_metrics_registered(self):
        """Test that all critical metrics are registered and accessible."""
        # Counters
        assert metrics.request_count is not None
        assert metrics.batch_jobs_total is not None
        assert metrics.errors_total is not None
        assert metrics.tokens_generated is not None
        
        # Histograms
        assert metrics.request_duration is not None
        assert metrics.batch_processing_duration is not None
        assert metrics.chunk_size is not None
        
        # Gauges
        assert metrics.gpu_temperature_celsius is not None
        assert metrics.gpu_memory_used_bytes is not None
        assert metrics.queue_depth is not None
        assert metrics.batch_jobs_active is not None

    def test_counter_operations(self):
        """Test that counters can increment correctly."""
        initial = metrics.request_count.labels(
            endpoint='/test', method='POST', status_code='200'
        )._value.get()
        
        metrics.request_count.labels(
            endpoint='/test', method='POST', status_code='200'
        ).inc()
        
        final = metrics.request_count.labels(
            endpoint='/test', method='POST', status_code='200'
        )._value.get()
        
        assert final == initial + 1

    def test_histogram_operations(self):
        """Test that histograms can observe values."""
        try:
            metrics.request_duration.labels(
                endpoint='/test', method='POST', status_code='200'
            ).observe(0.5)
            
            metrics.chunk_size.observe(5000)
            
            assert True
        except Exception as e:
            pytest.fail(f"Failed to observe histogram value: {e}")

    def test_gauge_operations(self):
        """Test that gauges can be set and read."""
        metrics.gpu_temperature_celsius.labels(gpu_id='0').set(65.0)
        assert metrics.gpu_temperature_celsius.labels(gpu_id='0')._value.get() == 65.0
        
        metrics.queue_depth.set(10)
        assert metrics.queue_depth._value.get() == 10

    def test_helper_functions(self):
        """Test that metric helper functions work correctly."""
        # Test track_request
        metrics.track_request('/v1/batches', 'POST', 200, 0.5)
        
        # Test track_batch_job
        metrics.track_batch_job('completed', model='test-model', duration=120.5)
        
        # Test update_queue_metrics
        metrics.update_queue_metrics(5)
        assert metrics.queue_depth._value.get() == 5
        
        # Test update_gpu_metrics
        metrics.update_gpu_metrics('0', 8_000_000_000, 16_000_000_000, 65.0, 75.0)
        assert metrics.gpu_memory_used_bytes.labels(gpu_id='0')._value.get() == 8_000_000_000
        assert metrics.gpu_temperature_celsius.labels(gpu_id='0')._value.get() == 65.0

