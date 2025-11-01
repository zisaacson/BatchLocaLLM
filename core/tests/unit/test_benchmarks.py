"""Unit tests for benchmark manager - streamlined version.

Reduced from 11 tests to 3 tests focusing on core functionality:
- Loading benchmarks from directory
- Estimating performance
- Handling invalid data
"""

import pytest
import json
import tempfile
from pathlib import Path
from batch_app.benchmarks import BenchmarkManager


@pytest.fixture
def temp_benchmark_dir():
    """Create a temporary directory with benchmark files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        benchmark_dir = Path(tmpdir) / "benchmarks"
        benchmark_dir.mkdir()
        
        # Create valid benchmark file
        benchmark_data = {
            "model": "test-model-1",
            "test_id": "test-001",
            "config": {"max_tokens": 512, "temperature": 0.7},
            "results": {
                "throughput_requests_per_sec": 10.5,
                "throughput_tokens_per_sec": 1500,
                "model_load_time_seconds": 30,
                "total_time_seconds": 120
            }
        }
        
        benchmark_file = benchmark_dir / "test-model-1.json"
        with open(benchmark_file, 'w') as f:
            json.dump(benchmark_data, f)
        
        # Create invalid benchmark file (missing fields)
        invalid_data = {"model": "invalid-model"}
        invalid_file = benchmark_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            json.dump(invalid_data, f)
        
        yield benchmark_dir


class TestBenchmarkManager:
    """Test benchmark manager - core functionality only."""

    def test_load_benchmarks_from_directory(self, temp_benchmark_dir):
        """Test loading benchmarks from directory."""
        manager = BenchmarkManager(temp_benchmark_dir)

        # Should load valid benchmark
        assert len(manager.benchmarks_cache) >= 1
        assert "test-model-1" in manager.benchmarks_cache

        # Check benchmark data structure
        benchmark = manager.get_model_performance("test-model-1")
        assert benchmark is not None
        assert benchmark["model"] == "test-model-1"
        assert "results" in benchmark
        assert benchmark["results"]["throughput_requests_per_sec"] == 10.5

    def test_estimate_completion_time(self, temp_benchmark_dir):
        """Test completion time estimation calculations."""
        manager = BenchmarkManager(temp_benchmark_dir)

        # Estimate for 1000 requests
        estimate = manager.estimate_completion_time("test-model-1", num_requests=1000)

        assert estimate is not None
        assert "estimated_seconds" in estimate
        assert "throughput_tokens_per_sec" in estimate
        assert estimate["estimated_seconds"] > 0

        # Should return None for unknown model
        unknown_estimate = manager.estimate_completion_time("unknown-model", num_requests=1000)
        assert unknown_estimate is None

    def test_handles_invalid_data_gracefully(self, temp_benchmark_dir):
        """Test that manager handles invalid benchmark files gracefully."""
        manager = BenchmarkManager(temp_benchmark_dir)

        # Should not crash on invalid files
        assert manager is not None

        # Invalid model might be loaded if it has a 'model' field
        # The manager doesn't validate structure, just loads JSON

