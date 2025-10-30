#!/usr/bin/env python3
"""
UNIFIED BENCHMARK SYSTEM

One format. One location. One source of truth.

This replaces all the scattered benchmark scripts with a single, consistent approach.
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from vllm import LLM, SamplingParams
import requests

# ============================================================================
# UNIFIED BENCHMARK RESULT FORMAT
# ============================================================================

class BenchmarkResult:
    """Single source of truth for benchmark data structure."""
    
    def __init__(self, test_name: str, model: str, mode: str):
        self.test_name = test_name
        self.model = model
        self.mode = mode  # 'offline_batch' or 'server'
        self.timestamp = datetime.now().isoformat()
        
        # Timing
        self.model_load_time_seconds = 0.0
        self.inference_time_seconds = 0.0
        self.total_time_seconds = 0.0
        
        # Requests
        self.num_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Tokens
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        
        # Per-request latencies (for percentile calculation)
        self.latencies_ms = []
        
        # Config
        self.config = {}
        
        # Notes
        self.notes = ""
    
    def calculate_metrics(self):
        """Calculate derived metrics."""
        if self.inference_time_seconds > 0:
            self.throughput_req_per_sec = self.successful_requests / self.inference_time_seconds
            self.throughput_tokens_per_sec = self.total_tokens / self.inference_time_seconds
        else:
            self.throughput_req_per_sec = 0
            self.throughput_tokens_per_sec = 0
        
        if self.successful_requests > 0:
            self.avg_prompt_tokens = self.prompt_tokens / self.successful_requests
            self.avg_completion_tokens = self.completion_tokens / self.successful_requests
            self.success_rate_pct = (self.successful_requests / self.num_requests) * 100
        else:
            self.avg_prompt_tokens = 0
            self.avg_completion_tokens = 0
            self.success_rate_pct = 0
        
        # Calculate latency percentiles
        if self.latencies_ms:
            sorted_latencies = sorted(self.latencies_ms)
            n = len(sorted_latencies)
            self.latency_p50_ms = sorted_latencies[int(n * 0.50)]
            self.latency_p95_ms = sorted_latencies[int(n * 0.95)]
            self.latency_p99_ms = sorted_latencies[int(n * 0.99)]
            self.latency_min_ms = sorted_latencies[0]
            self.latency_max_ms = sorted_latencies[-1]
        else:
            self.latency_p50_ms = 0
            self.latency_p95_ms = 0
            self.latency_p99_ms = 0
            self.latency_min_ms = 0
            self.latency_max_ms = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        self.calculate_metrics()
        
        return {
            'test_name': self.test_name,
            'model': self.model,
            'mode': self.mode,
            'timestamp': self.timestamp,
            
            # Timing
            'model_load_time_seconds': round(self.model_load_time_seconds, 2),
            'inference_time_seconds': round(self.inference_time_seconds, 2),
            'total_time_seconds': round(self.total_time_seconds, 2),
            
            # Requests
            'num_requests': self.num_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate_pct': round(self.success_rate_pct, 2),
            
            # Tokens
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'avg_prompt_tokens': round(self.avg_prompt_tokens, 1),
            'avg_completion_tokens': round(self.avg_completion_tokens, 1),
            
            # Throughput
            'throughput_req_per_sec': round(self.throughput_req_per_sec, 2),
            'throughput_tokens_per_sec': round(self.throughput_tokens_per_sec, 0),
            
            # Latency
            'latency_p50_ms': round(self.latency_p50_ms, 2),
            'latency_p95_ms': round(self.latency_p95_ms, 2),
            'latency_p99_ms': round(self.latency_p99_ms, 2),
            'latency_min_ms': round(self.latency_min_ms, 2),
            'latency_max_ms': round(self.latency_max_ms, 2),
            
            # Config
            'config': self.config,
            'notes': self.notes
        }
    
    def save(self, output_dir: str = 'benchmark_results'):
        """Save to unified location."""
        Path(output_dir).mkdir(exist_ok=True)
        
        # Filename: {test_name}_{timestamp}.json
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/{self.test_name}_{timestamp_str}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename

# ============================================================================
# BENCHMARK RUNNERS
# ============================================================================

def load_batch_data(batch_file: str, limit: int = None) -> List[Dict]:
    """Load batch requests from JSONL file."""
    requests_data = []
    with open(batch_file, 'r') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            if line.strip():
                requests_data.append(json.loads(line))
    return requests_data

def run_offline_batch(batch_data: List[Dict], model: str, test_name: str) -> BenchmarkResult:
    """Run vLLM offline batch mode benchmark."""
    print(f"\n{'='*80}")
    print(f"🔬 OFFLINE BATCH MODE - {model}")
    print(f"{'='*80}")
    
    result = BenchmarkResult(test_name, model, 'offline_batch')
    result.num_requests = len(batch_data)
    
    # Load model
    print("Loading model...")
    load_start = time.time()
    llm = LLM(
        model=model,
        max_model_len=4096,
        gpu_memory_utilization=0.9,
        enable_prefix_caching=True,
        enforce_eager=True
    )
    result.model_load_time_seconds = time.time() - load_start
    print(f"✅ Model loaded in {result.model_load_time_seconds:.2f}s")
    
    result.config = {
        'max_model_len': 4096,
        'gpu_memory_utilization': 0.9,
        'enable_prefix_caching': True,
        'enforce_eager': True
    }
    
    # Prepare prompts
    prompts = [req['body']['messages'] for req in batch_data]
    
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000
    )
    
    # Run batch inference
    print(f"Processing {len(prompts)} requests in batch...")
    inference_start = time.time()
    
    outputs = llm.generate(prompts, sampling_params, use_tqdm=True)
    
    result.inference_time_seconds = time.time() - inference_start
    result.total_time_seconds = result.model_load_time_seconds + result.inference_time_seconds
    
    # Collect stats
    result.successful_requests = len(outputs)
    result.failed_requests = result.num_requests - result.successful_requests
    
    for output in outputs:
        result.prompt_tokens += len(output.prompt_token_ids)
        result.completion_tokens += len(output.outputs[0].token_ids)
        # Note: vLLM batch mode doesn't give per-request latency easily
        # We'll estimate based on total time
    
    result.total_tokens = result.prompt_tokens + result.completion_tokens
    
    # For batch mode, estimate average latency
    if result.successful_requests > 0:
        avg_latency_ms = (result.inference_time_seconds / result.successful_requests) * 1000
        result.latencies_ms = [avg_latency_ms] * result.successful_requests
    
    result.calculate_metrics()
    
    print(f"\n📊 Results:")
    print(f"  Load Time: {result.model_load_time_seconds:.2f}s")
    print(f"  Inference Time: {result.inference_time_seconds:.2f}s ({result.inference_time_seconds/60:.2f} min)")
    print(f"  Total Time: {result.total_time_seconds:.2f}s ({result.total_time_seconds/60:.2f} min)")
    print(f"  Throughput: {result.throughput_req_per_sec:.2f} req/s")
    print(f"  Throughput: {result.throughput_tokens_per_sec:.0f} tokens/s")
    print(f"  Success Rate: {result.success_rate_pct:.1f}%")
    
    return result

def run_server_mode(batch_data: List[Dict], model: str, server_url: str, test_name: str) -> BenchmarkResult:
    """Run vLLM server mode benchmark."""
    print(f"\n{'='*80}")
    print(f"🌐 SERVER MODE - {model}")
    print(f"{'='*80}")
    
    result = BenchmarkResult(test_name, model, 'server')
    result.num_requests = len(batch_data)
    
    # Check server
    try:
        response = requests.get(f"{server_url}/v1/models", timeout=5)
        if response.status_code != 200:
            raise Exception("Server not responding")
        print(f"✅ Server is running at {server_url}")
    except Exception as e:
        print(f"❌ ERROR: vLLM server not running at {server_url}")
        print(f"   Start server with: vllm serve {model} --port 4080")
        return None
    
    result.config = {'server_url': server_url}
    
    # Send requests
    print(f"Processing {len(batch_data)} requests via server...")
    
    from tqdm import tqdm
    inference_start = time.time()
    
    for req in tqdm(batch_data, desc="Sending requests"):
        req_start = time.time()
        try:
            response = requests.post(
                f"{server_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": req['body']['messages'],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2000
                },
                timeout=120
            )
            
            req_latency_ms = (time.time() - req_start) * 1000
            
            if response.status_code == 200:
                res_data = response.json()
                result.successful_requests += 1
                result.latencies_ms.append(req_latency_ms)
                
                usage = res_data.get('usage', {})
                result.prompt_tokens += usage.get('prompt_tokens', 0)
                result.completion_tokens += usage.get('completion_tokens', 0)
            else:
                result.failed_requests += 1
                
        except Exception as e:
            result.failed_requests += 1
    
    result.inference_time_seconds = time.time() - inference_start
    result.total_time_seconds = result.inference_time_seconds
    result.total_tokens = result.prompt_tokens + result.completion_tokens
    
    result.calculate_metrics()
    
    print(f"\n📊 Results:")
    print(f"  Inference Time: {result.inference_time_seconds:.2f}s ({result.inference_time_seconds/60:.2f} min)")
    print(f"  Successful: {result.successful_requests}/{result.num_requests}")
    print(f"  Throughput: {result.throughput_req_per_sec:.2f} req/s")
    print(f"  Throughput: {result.throughput_tokens_per_sec:.0f} tokens/s")
    print(f"  Latency P50: {result.latency_p50_ms:.2f}ms")
    print(f"  Latency P95: {result.latency_p95_ms:.2f}ms")
    print(f"  Success Rate: {result.success_rate_pct:.1f}%")
    
    return result

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Unified vLLM Benchmark System')
    parser.add_argument('--name', type=str, required=True, help='Test name (e.g., gemma3_4b_5k)')
    parser.add_argument('--model', type=str, default='google/gemma-3-4b-it', help='Model to benchmark')
    parser.add_argument('--batch-file', type=str, default='batch_5k.jsonl', help='Input batch file')
    parser.add_argument('--size', type=int, help='Limit number of requests')
    parser.add_argument('--mode', type=str, choices=['offline', 'server', 'both'], default='offline', 
                        help='Benchmark mode')
    parser.add_argument('--server-url', type=str, default='http://localhost:4080', help='vLLM server URL')
    
    args = parser.parse_args()
    
    print(f"🚀 Unified Benchmark System")
    print(f"   Test: {args.name}")
    print(f"   Model: {args.model}")
    print(f"   Mode: {args.mode}")
    
    # Load data
    batch_data = load_batch_data(args.batch_file, limit=args.size)
    print(f"✅ Loaded {len(batch_data)} requests")
    
    results = []
    
    # Run benchmarks
    if args.mode in ['offline', 'both']:
        result = run_offline_batch(batch_data, args.model, args.name)
        if result:
            result.save()
            results.append(result)
    
    if args.mode in ['server', 'both']:
        result = run_server_mode(batch_data, args.model, args.server_url, args.name)
        if result:
            result.save()
            results.append(result)
    
    # Print comparison if both modes
    if len(results) == 2:
        print(f"\n{'='*80}")
        print(f"📊 COMPARISON: Offline vs Server")
        print(f"{'='*80}")
        offline, server = results
        print(f"Offline: {offline.total_time_seconds:.2f}s @ {offline.throughput_req_per_sec:.2f} req/s")
        print(f"Server:  {server.total_time_seconds:.2f}s @ {server.throughput_req_per_sec:.2f} req/s")
        speedup = offline.throughput_req_per_sec / server.throughput_req_per_sec
        print(f"Speedup: {speedup:.2f}x ({'Offline' if speedup > 1 else 'Server'} is faster)")

if __name__ == '__main__':
    main()

