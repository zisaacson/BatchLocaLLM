#!/usr/bin/env python3
"""
Benchmark vLLM: Offline Batch vs Serve Mode (with/without prefix caching)

This script tests three approaches:
1. Offline Batch Processing (with prefix caching)
2. Serve Mode with Prefix Caching (batched requests)
3. Serve Mode without Prefix Caching (Inngest-style independent requests)

Measures: throughput, latency, GPU utilization, total time, cost/benefit
"""

import json
import time
import asyncio
import aiohttp
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any
import statistics
from datetime import datetime

def log(msg):
    """Print with immediate flush for real-time logging"""
    print(msg, flush=True)
    sys.stdout.flush()

# Configuration
BATCH_FILE = "batch_5k.jsonl"
RESULTS_DIR = Path("benchmark_results")
VLLM_PORT = 4080
VLLM_HOST = "http://localhost"

# Test sizes (start small, scale up)
TEST_SIZES = [10, 100, 5000]


class BenchmarkResult:
    def __init__(self, mode: str, size: int):
        self.mode = mode
        self.size = size
        self.start_time = None
        self.end_time = None
        self.latencies = []
        self.gpu_samples = []
        self.errors = 0
        
    def start(self):
        self.start_time = time.time()
        
    def end(self):
        self.end_time = time.time()
        
    def add_latency(self, latency: float):
        self.latencies.append(latency)
        
    def add_gpu_sample(self, memory_used: float, utilization: float):
        self.gpu_samples.append({"memory": memory_used, "util": utilization})
        
    def get_stats(self) -> Dict[str, Any]:
        total_time = self.end_time - self.start_time if self.end_time else 0
        throughput = self.size / total_time if total_time > 0 else 0
        
        return {
            "mode": self.mode,
            "size": self.size,
            "total_time_seconds": round(total_time, 2),
            "throughput_req_per_sec": round(throughput, 2),
            "latency_p50_ms": round(statistics.median(self.latencies) * 1000, 2) if self.latencies else 0,
            "latency_p95_ms": round(statistics.quantiles(self.latencies, n=20)[18] * 1000, 2) if len(self.latencies) > 20 else 0,
            "latency_p99_ms": round(statistics.quantiles(self.latencies, n=100)[98] * 1000, 2) if len(self.latencies) > 100 else 0,
            "avg_gpu_memory_gb": round(statistics.mean([s["memory"] for s in self.gpu_samples]) / 1024, 2) if self.gpu_samples else 0,
            "avg_gpu_utilization_pct": round(statistics.mean([s["util"] for s in self.gpu_samples]), 2) if self.gpu_samples else 0,
            "errors": self.errors,
            "success_rate_pct": round((self.size - self.errors) / self.size * 100, 2) if self.size > 0 else 0
        }


def load_batch_requests(limit: int = None) -> List[Dict[str, Any]]:
    """Load batch requests from JSONL file"""
    requests = []
    with open(BATCH_FILE, 'r') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            req = json.loads(line)
            # Fix model name for vLLM (convert from Ollama format)
            req["body"]["model"] = "google/gemma-3-4b-it"
            requests.append(req)
    return requests


def get_gpu_stats() -> tuple[float, float]:
    """Get current GPU memory usage and utilization"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        memory, util = result.stdout.strip().split(',')
        return float(memory), float(util)
    except:
        return 0.0, 0.0


async def monitor_gpu(result: BenchmarkResult, interval: float = 1.0):
    """Monitor GPU stats during benchmark"""
    while result.end_time is None:
        memory, util = get_gpu_stats()
        result.add_gpu_sample(memory, util)
        await asyncio.sleep(interval)


async def benchmark_offline_batch(requests: List[Dict], result: BenchmarkResult):
    """
    Approach 1: Offline Batch Processing
    - Uses vLLM's native offline batch API
    - Automatic prefix caching
    - Processes all requests in one batch
    """
    print(f"\n{'='*60}")
    print(f"🔄 OFFLINE BATCH MODE - {len(requests)} requests")
    print(f"{'='*60}")
    
    from vllm import LLM, SamplingParams
    
    result.start()
    
    # Start GPU monitoring
    monitor_task = asyncio.create_task(monitor_gpu(result))
    
    try:
        # Initialize LLM with prefix caching
        llm = LLM(
            model="google/gemma-3-4b-it",
            max_model_len=8192,
            gpu_memory_utilization=0.90,
            enable_prefix_caching=True,
            max_num_seqs=256
        )
        
        # Prepare prompts
        prompts = []
        for req in requests:
            messages = req["body"]["messages"]
            # Convert to prompt format
            prompt = ""
            for msg in messages:
                if msg["role"] == "system":
                    prompt += f"System: {msg['content']}\n\n"
                elif msg["role"] == "user":
                    prompt += f"User: {msg['content']}\n\n"
            prompts.append(prompt)
        
        sampling_params = SamplingParams(
            temperature=0.7,
            max_tokens=2000
        )
        
        # Process all at once
        batch_start = time.time()
        outputs = llm.generate(prompts, sampling_params)
        batch_latency = time.time() - batch_start
        
        # Record latency for each request (approximation)
        avg_latency = batch_latency / len(requests)
        for _ in requests:
            result.add_latency(avg_latency)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        result.errors = len(requests)
    finally:
        result.end()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


async def benchmark_serve_batched(requests: List[Dict], result: BenchmarkResult, enable_prefix_cache: bool = True):
    """
    Approach 2: Serve Mode with Batched Requests
    - Uses OpenAI-compatible API
    - Can enable/disable prefix caching
    - Sends requests in parallel batches
    """
    mode_name = "SERVE MODE (Batched)" if enable_prefix_cache else "SERVE MODE (No Cache, Batched)"
    log(f"\n{'='*60}")
    log(f"🌐 {mode_name} - {len(requests)} requests")
    log(f"{'='*60}")
    
    result.start()
    
    # Start GPU monitoring
    monitor_task = asyncio.create_task(monitor_gpu(result))
    
    # Batch size for parallel requests
    BATCH_SIZE = 50
    
    async def send_request(session: aiohttp.ClientSession, req: Dict) -> tuple[float, int]:
        """Send single request and return (latency, tokens_generated)"""
        req_start = time.time()
        try:
            async with session.post(
                f"{VLLM_HOST}:{VLLM_PORT}/v1/chat/completions",
                json=req["body"],
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                data = await response.json()
                latency = time.time() - req_start
                tokens = data.get("usage", {}).get("completion_tokens", 0)
                return latency, tokens
        except Exception as e:
            print(f"❌ Request error: {e}")
            result.errors += 1
            return time.time() - req_start, 0
    
    total_tokens = 0
    try:
        async with aiohttp.ClientSession() as session:
            # Process in batches
            for i in range(0, len(requests), BATCH_SIZE):
                batch = requests[i:i+BATCH_SIZE]
                tasks = [send_request(session, req) for req in batch]
                results_batch = await asyncio.gather(*tasks)

                for lat, tokens in results_batch:
                    result.add_latency(lat)
                    total_tokens += tokens

                log(f"  ✅ Processed {min(i+BATCH_SIZE, len(requests))}/{len(requests)}")
                
    finally:
        result.end()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


async def benchmark_serve_independent(requests: List[Dict], result: BenchmarkResult):
    """
    Approach 3: Serve Mode with Independent Requests (Inngest-style)
    - Uses OpenAI-compatible API
    - No prefix caching benefit (each request independent)
    - Simulates Inngest execution model
    """
    log(f"\n{'='*60}")
    log(f"🔀 SERVE MODE (Independent/Inngest-style) - {len(requests)} requests")
    log(f"{'='*60}")
    
    result.start()
    
    # Start GPU monitoring
    monitor_task = asyncio.create_task(monitor_gpu(result))
    
    # Concurrency limit (simulating Inngest concurrency)
    CONCURRENCY = 10
    
    async def send_request(session: aiohttp.ClientSession, req: Dict, semaphore: asyncio.Semaphore) -> tuple[float, int]:
        """Send single request with concurrency limit"""
        async with semaphore:
            req_start = time.time()
            try:
                async with session.post(
                    f"{VLLM_HOST}:{VLLM_PORT}/v1/chat/completions",
                    json=req["body"],
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    data = await response.json()
                    latency = time.time() - req_start
                    tokens = data.get("usage", {}).get("completion_tokens", 0)
                    return latency, tokens
            except Exception as e:
                log(f"❌ Request error: {e}")
                result.errors += 1
                return time.time() - req_start, 0
    
    total_tokens = 0
    try:
        semaphore = asyncio.Semaphore(CONCURRENCY)
        async with aiohttp.ClientSession() as session:
            tasks = [send_request(session, req, semaphore) for req in requests]
            results_list = await asyncio.gather(*tasks)

            for lat, tokens in results_list:
                result.add_latency(lat)
                total_tokens += tokens
                
    finally:
        result.end()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


async def run_benchmarks():
    """Run all benchmarks and save results"""
    RESULTS_DIR.mkdir(exist_ok=True)

    all_results = []

    for size in TEST_SIZES:
        log(f"\n{'#'*60}")
        log(f"# BENCHMARK SET: {size} requests")
        log(f"{'#'*60}")

        requests = load_batch_requests(limit=size)

        # Test 1: Serve Mode with High Parallelism (simulates batch with prefix cache)
        # This sends many requests in parallel, allowing vLLM to batch them internally
        result1 = BenchmarkResult("serve_high_parallelism", size)
        await benchmark_serve_batched(requests, result1, enable_prefix_cache=True)
        all_results.append(result1.get_stats())

        # Wait between tests
        await asyncio.sleep(5)

        # Test 2: Serve Mode Independent (Inngest-style, limited concurrency)
        # This simulates Inngest's execution model with limited concurrency
        result2 = BenchmarkResult("serve_inngest_style", size)
        await benchmark_serve_independent(requests, result2)
        all_results.append(result2.get_stats())

        # Wait between tests
        await asyncio.sleep(5)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"benchmark_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    log(f"\n{'='*60}")
    log(f"✅ Results saved to: {results_file}")
    log(f"{'='*60}")
    
    return all_results


if __name__ == "__main__":
    log("🚀 Starting vLLM Benchmark Suite")
    log(f"📊 Test sizes: {TEST_SIZES}")
    log(f"🎯 Testing: High Parallelism vs Inngest-Style\n")

    results = asyncio.run(run_benchmarks())

    # Print summary
    log("\n" + "="*80)
    log("BENCHMARK SUMMARY")
    log("="*80)
    log(f"{'Mode':<35} {'Size':<8} {'Time(s)':<10} {'Throughput':<12} {'P50(ms)':<10} {'GPU%':<8}")
    log("-"*80)

    for r in results:
        log(f"{r['mode']:<35} {r['size']:<8} {r['total_time_seconds']:<10} "
              f"{r['throughput_req_per_sec']:<12.2f} {r['latency_p50_ms']:<10} {r['avg_gpu_utilization_pct']:<8}")

