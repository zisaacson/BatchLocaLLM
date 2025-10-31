"""
Benchmark data integration for job estimation and tracking.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class BenchmarkManager:
    """Manages benchmark data for performance estimation."""
    
    def __init__(self, benchmarks_dir: str = "benchmarks/metadata"):
        self.benchmarks_dir = Path(benchmarks_dir)
        self.benchmarks_cache = {}
        self._load_benchmarks()
    
    def _load_benchmarks(self):
        """Load all benchmark metadata files."""
        if not self.benchmarks_dir.exists():
            print(f"⚠️  Benchmark directory not found: {self.benchmarks_dir}")
            return
        
        for file_path in self.benchmarks_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    model = data.get('model')
                    if model:
                        self.benchmarks_cache[model] = data
                        print(f"✅ Loaded benchmark for {model}")
            except Exception as e:
                print(f"⚠️  Failed to load {file_path}: {e}")
    
    def get_model_performance(self, model: str) -> (dict[str, Any]]:
        """Get performance metrics for a model."""
        return self.benchmarks_cache.get(model)
    
    def estimate_completion_time(self, model: str, num_requests: int) -> (dict[str, Any]]:
        """
        Estimate completion time based on benchmark data.
        
        Returns:
            {
                'estimated_seconds': int,
                'estimated_completion': datetime,
                'throughput_tokens_per_sec': int,
                'based_on_benchmark': str
            }
        """
        benchmark = self.get_model_performance(model)
        if not benchmark:
            return None
        
        results = benchmark.get('results', {})
        
        # Get throughput from benchmark
        throughput_req_per_sec = results.get('throughput_requests_per_sec', 0)
        throughput_tok_per_sec = results.get('throughput_tokens_per_sec', 0)
        
        if throughput_req_per_sec == 0:
            return None
        
        # Estimate time based on request throughput
        estimated_seconds = int(num_requests / throughput_req_per_sec)
        
        # Add model load time
        model_load_time = results.get('model_load_time_seconds', 30)
        estimated_seconds += int(model_load_time)
        
        # Calculate estimated completion time
        estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_seconds)
        
        return {
            'estimated_seconds': estimated_seconds,
            'estimated_hours': round(estimated_seconds / 3600, 2),
            'estimated_completion': estimated_completion.isoformat() + 'Z',
            'throughput_tokens_per_sec': throughput_tok_per_sec,
            'throughput_requests_per_sec': round(throughput_req_per_sec, 2),
            'based_on_benchmark': benchmark.get('test_id', 'unknown')
        }
    
    def get_available_models(self) -> list:
        """Get list of models with benchmark data."""
        return list(self.benchmarks_cache.keys())
    
    def get_model_info(self, model: str) -> (dict[str, Any]]:
        """
        Get detailed model information in OpenAI/Parasail format.

        Returns model object matching OpenAI Models API format:
        https://platform.openai.com/docs/api-reference/models/object
        """
        benchmark = self.get_model_performance(model)
        if not benchmark:
            return None

        results = benchmark.get('results', {})
        config = benchmark.get('config', {})
        timestamp = benchmark.get('timestamp', 'unknown')

        # Convert timestamp to Unix epoch (OpenAI format)
        import time
        from datetime import datetime
        try:
            if isinstance(timestamp, str) and timestamp != 'unknown':
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                created = int(dt.timestamp())
            else:
                created = int(time.time())
        except:
            created = int(time.time())

        # OpenAI/Parasail compatible model object
        return {
            "id": model,  # OpenAI uses "id" not "model"
            "object": "model",  # OpenAI standard
            "created": created,  # Unix timestamp
            "owned_by": "vllm-local",  # Indicates local vLLM instance
            # Custom vLLM-specific metadata (not in OpenAI spec, but useful)
            "vllm_metadata": {
                "platform": benchmark.get('platform', 'unknown'),
                "throughput_tokens_per_sec": results.get('throughput_tokens_per_sec', 0),
                "throughput_requests_per_sec": results.get('throughput_requests_per_sec', 0),
                "max_model_len": config.get('max_model_len', 4096),
                "gpu_memory_utilization": config.get('gpu_memory_utilization', 0.9),
                "last_benchmark": timestamp,
                "success_rate": round(results.get('success_count', 0) / max(results.get('success_count', 0) + results.get('failure_count', 0), 1) * 100, 2)
            }
        }
    
    def save_job_benchmark(self, job_data: dict[str, Any], output_dir: str = "benchmarks/metadata"):
        """
        Save benchmark data from a completed job.
        
        Args:
            job_data: Dictionary with job results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create benchmark metadata
        benchmark = {
            "test_id": f"batch-job-{job_data['batch_id']}",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "platform": "vllm-native",
            "model": job_data['model'],
            "config": {
                "max_model_len": 4096,
                "gpu_memory_utilization": 0.9,
                "enable_prefix_caching": True,
                "chunked_prefill_enabled": True
            },
            "test": {
                "num_requests": job_data['total_requests'],
                "input_file": job_data['input_file'],
                "output_file": job_data['output_file']
            },
            "results": {
                "success_count": job_data['completed_requests'],
                "failure_count": job_data['failed_requests'],
                "total_tokens": job_data.get('total_tokens', 0),
                "throughput_tokens_per_sec": job_data.get('throughput_tokens_per_sec', 0),
                "throughput_requests_per_sec": round(
                    job_data['completed_requests'] / max(job_data.get('processing_time_seconds', 1), 1), 
                    2
                )
            },
            "status": "completed"
        }
        
        # Save to file
        filename = f"batch-job-{job_data['model'].replace('/', '-')}-{job_data['total_requests']}-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
        filepath = output_path / filename
        
        with open(filepath, 'w') as f:
            json.dump(benchmark, f, indent=2)
        
        print(f"✅ Saved benchmark data: {filepath}")
        
        # Reload benchmarks cache
        self._load_benchmarks()


# Global instance
benchmark_manager = BenchmarkManager()


def get_benchmark_manager() -> BenchmarkManager:
    """Get the global benchmark manager instance."""
    return benchmark_manager

