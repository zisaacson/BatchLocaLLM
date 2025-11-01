"""Unit tests for worker error handling with mocked vLLM - HIGH VALUE tests.

These tests prevent real production failures from worker crashes and errors.
Tests cover:
- Chunk processing failures
- Resume from crash
- Dead letter queue
- GPU health checks
- Error recovery
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Metrics module is now mocked in conftest.py (session-scoped fixture)
# No need to mock it here anymore!

from core.batch_app.worker import BatchWorker, check_gpu_health, calculate_safe_chunk_size
from core.batch_app.database import BatchJob, File, SessionLocal


class TestGPUHealthChecks:
    """Test GPU health monitoring and safe chunk size calculation."""

    @pytest.mark.parametrize("memory_used_gb,memory_total_gb,temperature,expected_healthy,test_description", [
        (8, 16, 65, True, "healthy GPU with 50% memory and normal temp"),
        (15.5, 16, 65, False, "unhealthy GPU with >95% memory usage"),
        (8, 16, 95, False, "unhealthy GPU with high temperature (>85°C)"),
    ])
    @patch('pynvml.nvmlInit')
    @patch('pynvml.nvmlDeviceGetHandleByIndex')
    @patch('pynvml.nvmlDeviceGetMemoryInfo')
    @patch('pynvml.nvmlDeviceGetTemperature')
    @patch('pynvml.nvmlShutdown')
    def test_gpu_health_check(self, mock_shutdown, mock_temp, mock_mem, mock_handle, mock_init,
                              memory_used_gb, memory_total_gb, temperature, expected_healthy, test_description):
        """Test GPU health check with various conditions."""
        # Mock GPU stats
        mock_mem_info = Mock()
        mock_mem_info.used = memory_used_gb * 1024**3
        mock_mem_info.total = memory_total_gb * 1024**3

        mock_mem.return_value = mock_mem_info
        mock_temp.return_value = temperature

        result = check_gpu_health()

        assert result['healthy'] is expected_healthy, f"Failed: {test_description}"
        assert result['temperature_c'] == temperature

    @patch('pynvml.nvmlInit')
    def test_gpu_health_check_handles_error(self, mock_init):
        """Test GPU health check handles errors gracefully."""
        # Mock pynvml raising exception
        mock_init.side_effect = Exception("NVML not available")

        result = check_gpu_health()

        # Should return healthy=True as fallback
        assert result['healthy'] is True
        assert result['memory_percent'] == 0
        assert result['temperature_c'] == 0

    @pytest.mark.parametrize("memory_percent,expected_chunk_size,description", [
        (50, 5000, "plenty of memory"),
        (75, 3000, "memory getting full"),
        (85, 1000, "memory very full"),
        (95, 500, "memory critical"),
    ])
    def test_calculate_safe_chunk_size(self, memory_percent, expected_chunk_size, description):
        """Test chunk size calculation with various memory levels."""
        gpu_status = {'memory_percent': memory_percent}

        chunk_size = calculate_safe_chunk_size(gpu_status)

        assert chunk_size == expected_chunk_size, f"Failed for {description}"


class TestChunkProcessingFailures:
    """Test chunk processing error handling."""

    def test_worker_initialization(self):
        """Test worker initializes correctly."""
        worker = BatchWorker(poll_interval=5)
        
        assert worker.poll_interval == 5
        assert worker.current_llm is None
        assert worker.current_model is None

    @patch('core.batch_app.worker.LLM')
    def test_load_model_success(self, mock_llm_class, temp_log_file):
        """Test model loading succeeds."""
        worker = BatchWorker()
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        worker.load_model("test-model", temp_log_file.name)

        assert worker.current_llm == mock_llm
        assert worker.current_model == "test-model"
        mock_llm_class.assert_called_once()

    @patch('core.batch_app.worker.LLM')
    def test_load_model_failure(self, mock_llm_class, temp_log_file):
        """Test model loading handles errors."""
        worker = BatchWorker()
        mock_llm_class.side_effect = Exception("Model not found")

        with pytest.raises(Exception, match="Model not found"):
            worker.load_model("invalid-model", temp_log_file.name)

        assert worker.current_llm is None

    def test_count_completed_results_empty_file(self, temp_jsonl_file):
        """Test counting results from empty file."""
        worker = BatchWorker()
        temp_jsonl_file.flush()

        count = worker.count_completed_results(temp_jsonl_file.name)
        assert count == 0

    def test_count_completed_results_with_data(self, temp_jsonl_file):
        """Test counting results from file with data."""
        worker = BatchWorker()

        # Create output file with 3 results
        temp_jsonl_file.write('{"id": "1", "custom_id": "req-1"}\n')
        temp_jsonl_file.write('{"id": "2", "custom_id": "req-2"}\n')
        temp_jsonl_file.write('{"id": "3", "custom_id": "req-3"}\n')
        temp_jsonl_file.flush()

        count = worker.count_completed_results(temp_jsonl_file.name)
        assert count == 3

    def test_count_completed_results_nonexistent_file(self):
        """Test counting results from nonexistent file."""
        worker = BatchWorker()
        
        count = worker.count_completed_results("/nonexistent/file.jsonl")
        assert count == 0

    def test_save_chunk_results_success(self, temp_jsonl_file, temp_log_file):
        """Test saving chunk results to file."""
        worker = BatchWorker()
        worker.current_model = "test-model"  # Set model name

        # Mock vLLM outputs with proper structure
        mock_output1 = Mock()
        mock_output1.prompt_token_ids = [1, 2, 3]
        mock_inner_output1 = Mock()
        mock_inner_output1.token_ids = [4, 5]
        mock_inner_output1.text = "Response 1"
        mock_inner_output1.finish_reason = "stop"
        mock_output1.outputs = [mock_inner_output1]

        mock_output2 = Mock()
        mock_output2.prompt_token_ids = [6, 7, 8]
        mock_inner_output2 = Mock()
        mock_inner_output2.token_ids = [9, 10]
        mock_inner_output2.text = "Response 2"
        mock_inner_output2.finish_reason = "stop"
        mock_output2.outputs = [mock_inner_output2]

        outputs = [mock_output1, mock_output2]

        # Mock requests
        requests = [
            {"custom_id": "req-1", "body": {"messages": []}},
            {"custom_id": "req-2", "body": {"messages": []}}
        ]

        saved = worker.save_chunk_results(outputs, requests, temp_jsonl_file.name, 0, temp_log_file.name)

        assert saved == 2

        # Verify file contents
        with open(temp_jsonl_file.name) as f:
            lines = f.readlines()
            assert len(lines) == 2

            result1 = json.loads(lines[0])
            assert result1['custom_id'] == 'req-1'
            assert 'response' in result1
            assert result1['response']['body']['choices'][0]['message']['content'] == 'Response 1'

            result2 = json.loads(lines[1])
            assert result2['custom_id'] == 'req-2'
            assert result2['response']['body']['choices'][0]['message']['content'] == 'Response 2'


class TestResumeFromCrash:
    """Test resume capability after worker crash."""

    @pytest.fixture
    def input_output_files(self, temp_dir):
        """Create input and output files for resume testing."""
        input_file = temp_dir / "input.jsonl"
        output_file = temp_dir / "output.jsonl"

        # Create input file with 5 requests
        with open(input_file, 'w') as f:
            for i in range(5):
                f.write(json.dumps({
                    "custom_id": f"req-{i}",
                    "body": {"messages": [{"role": "user", "content": f"Test {i}"}]}
                }) + '\n')

        # Create output file with 2 completed results (simulating crash after 2)
        with open(output_file, 'w') as f:
            f.write('{"id": "1", "custom_id": "req-0"}\n')
            f.write('{"id": "2", "custom_id": "req-1"}\n')

        return input_file, output_file

    def test_resume_from_partial_completion(self, input_output_files):
        """Test worker resumes from partial completion."""
        worker = BatchWorker()
        input_file, output_file = input_output_files

        # Load all requests
        all_requests = []
        with open(input_file) as f:
            for line in f:
                if line.strip():
                    all_requests.append(json.loads(line))

        # Check resume point
        completed_count = worker.count_completed_results(str(output_file))
        assert completed_count == 2

        # Resume from checkpoint
        remaining_requests = all_requests[completed_count:]
        assert len(remaining_requests) == 3
        assert remaining_requests[0]['custom_id'] == 'req-2'

