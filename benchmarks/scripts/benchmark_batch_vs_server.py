#!/usr/bin/env python3
"""
Benchmark: vLLM Offline Batch Mode vs vLLM Server Mode

Tests whether there are differences in token caching and processing
between sending requests in a batch (offline) vs sending to vLLM server.

Usage:
    python benchmark_batch_vs_server.py --size 100
    python benchmark_batch_vs_server.py --size 1000
    python benchmark_batch_vs_server.py --size 5000
"""

import argparse
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from vllm import LLM, SamplingParams
from tqdm import tqdm

def load_batch_data(batch_file, limit=None):
    """Load batch requests from JSONL file."""
    requests_data = []
    with open(batch_file, 'r') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            if line.strip():
                requests_data.append(json.loads(line))
    return requests_data

def benchmark_offline_batch(batch_data, model_name):
    """Benchmark using vLLM offline batch mode (LLM class)."""
    print(f"\n{'='*60}")
    print(f"🔬 OFFLINE BATCH MODE - {model_name}")
    print(f"{'='*60}")
    
    # Initialize LLM
    print("Loading model...")
    load_start = time.time()
    llm = LLM(
        model=model_name,
        max_model_len=4096,
        gpu_memory_utilization=0.9,
        enable_prefix_caching=True,
        enforce_eager=True
    )
    load_time = time.time() - load_start
    print(f"✅ Model loaded in {load_time:.2f}s")
    
    # Prepare prompts
    prompts = []
    for req in batch_data:
        messages = req['body']['messages']
        # Convert messages to prompt string (vLLM will handle chat template)
        prompts.append(messages)
    
    # Sampling params
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000
    )
    
    # Run batch inference
    print(f"Processing {len(prompts)} requests in batch...")
    inference_start = time.time()
    
    outputs = llm.generate(prompts, sampling_params, use_tqdm=True)
    
    inference_time = time.time() - inference_start
    total_time = load_time + inference_time
    
    # Calculate token stats
    total_prompt_tokens = sum(len(output.prompt_token_ids) for output in outputs)
    total_completion_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
    total_tokens = total_prompt_tokens + total_completion_tokens
    
    results = {
        'mode': 'offline_batch',
        'model': model_name,
        'num_requests': len(prompts),
        'load_time_seconds': load_time,
        'inference_time_seconds': inference_time,
        'total_time_seconds': total_time,
        'prompt_tokens': total_prompt_tokens,
        'completion_tokens': total_completion_tokens,
        'total_tokens': total_tokens,
        'throughput_tokens_per_sec': total_tokens / inference_time,
        'throughput_requests_per_sec': len(prompts) / inference_time,
        'avg_time_per_request_seconds': inference_time / len(prompts),
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n📊 Results:")
    print(f"  Load Time: {load_time:.2f}s")
    print(f"  Inference Time: {inference_time:.2f}s ({inference_time/60:.2f} min)")
    print(f"  Total Time: {total_time:.2f}s ({total_time/60:.2f} min)")
    print(f"  Throughput: {results['throughput_requests_per_sec']:.2f} req/s")
    print(f"  Throughput: {results['throughput_tokens_per_sec']:.0f} tokens/s")
    print(f"  Avg Time/Request: {results['avg_time_per_request_seconds']:.3f}s")
    
    return results, outputs

def benchmark_server_mode(batch_data, server_url, model_name):
    """Benchmark using vLLM server mode (OpenAI-compatible API)."""
    print(f"\n{'='*60}")
    print(f"🌐 SERVER MODE - {model_name}")
    print(f"{'='*60}")
    
    # Check if server is running
    try:
        response = requests.get(f"{server_url}/v1/models", timeout=5)
        if response.status_code != 200:
            raise Exception("Server not responding")
        print(f"✅ Server is running at {server_url}")
    except Exception as e:
        print(f"❌ ERROR: vLLM server not running at {server_url}")
        print(f"   Start server with: vllm serve {model_name} --port 4080")
        return None, None
    
    # Send requests one by one (simulating server mode)
    print(f"Processing {len(batch_data)} requests via server...")
    
    results_list = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    
    inference_start = time.time()
    
    for req in tqdm(batch_data, desc="Sending requests"):
        try:
            response = requests.post(
                f"{server_url}/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": req['body']['messages'],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2000
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                results_list.append(result)
                usage = result.get('usage', {})
                total_prompt_tokens += usage.get('prompt_tokens', 0)
                total_completion_tokens += usage.get('completion_tokens', 0)
            else:
                print(f"❌ Request failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    inference_time = time.time() - inference_start
    total_tokens = total_prompt_tokens + total_completion_tokens
    
    results = {
        'mode': 'server',
        'model': model_name,
        'num_requests': len(batch_data),
        'successful_requests': len(results_list),
        'inference_time_seconds': inference_time,
        'total_time_seconds': inference_time,  # No separate load time for server
        'prompt_tokens': total_prompt_tokens,
        'completion_tokens': total_completion_tokens,
        'total_tokens': total_tokens,
        'throughput_tokens_per_sec': total_tokens / inference_time if inference_time > 0 else 0,
        'throughput_requests_per_sec': len(results_list) / inference_time if inference_time > 0 else 0,
        'avg_time_per_request_seconds': inference_time / len(results_list) if results_list else 0,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n📊 Results:")
    print(f"  Inference Time: {inference_time:.2f}s ({inference_time/60:.2f} min)")
    print(f"  Successful: {len(results_list)}/{len(batch_data)}")
    print(f"  Throughput: {results['throughput_requests_per_sec']:.2f} req/s")
    print(f"  Throughput: {results['throughput_tokens_per_sec']:.0f} tokens/s")
    print(f"  Avg Time/Request: {results['avg_time_per_request_seconds']:.3f}s")
    
    return results, results_list

def save_results(offline_results, server_results, size):
    """Save benchmark results to file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save to benchmark_results directory
    output_file = f"benchmark_results/batch_vs_server_{size}_{timestamp}.json"
    Path("benchmark_results").mkdir(exist_ok=True)
    
    comparison = {
        'test_size': size,
        'timestamp': timestamp,
        'offline_batch': offline_results,
        'server': server_results,
        'comparison': {
            'speedup_factor': offline_results['throughput_requests_per_sec'] / server_results['throughput_requests_per_sec'] if server_results else None,
            'offline_faster': offline_results['total_time_seconds'] < server_results['total_time_seconds'] if server_results else None,
            'time_difference_seconds': abs(offline_results['total_time_seconds'] - server_results['total_time_seconds']) if server_results else None
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump([comparison], f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Print comparison
    if server_results:
        print(f"\n{'='*60}")
        print(f"📊 COMPARISON")
        print(f"{'='*60}")
        print(f"Offline Batch: {offline_results['total_time_seconds']:.2f}s ({offline_results['throughput_requests_per_sec']:.2f} req/s)")
        print(f"Server Mode:   {server_results['total_time_seconds']:.2f}s ({server_results['throughput_requests_per_sec']:.2f} req/s)")
        print(f"Speedup:       {comparison['comparison']['speedup_factor']:.2f}x")
        print(f"Winner:        {'Offline Batch' if comparison['comparison']['offline_faster'] else 'Server Mode'}")

def main():
    parser = argparse.ArgumentParser(description='Benchmark vLLM batch vs server mode')
    parser.add_argument('--size', type=int, default=100, help='Number of requests to test (default: 100)')
    parser.add_argument('--batch-file', type=str, default='batch_5k.jsonl', help='Input batch file')
    parser.add_argument('--model', type=str, default='google/gemma-3-4b-it', help='Model to use')
    parser.add_argument('--server-url', type=str, default='http://localhost:4080', help='vLLM server URL')
    parser.add_argument('--skip-offline', action='store_true', help='Skip offline batch test')
    parser.add_argument('--skip-server', action='store_true', help='Skip server test')
    
    args = parser.parse_args()
    
    print(f"🚀 Benchmark: Batch vs Server Mode")
    print(f"   Model: {args.model}")
    print(f"   Test Size: {args.size} requests")
    print(f"   Batch File: {args.batch_file}")
    
    # Load data
    batch_data = load_batch_data(args.batch_file, limit=args.size)
    print(f"✅ Loaded {len(batch_data)} requests")
    
    offline_results = None
    server_results = None
    
    # Run offline batch test
    if not args.skip_offline:
        offline_results, _ = benchmark_offline_batch(batch_data, args.model)
    
    # Run server test
    if not args.skip_server:
        server_results, _ = benchmark_server_mode(batch_data, args.server_url, args.model)
    
    # Save results
    if offline_results or server_results:
        save_results(offline_results or {}, server_results or {}, args.size)

if __name__ == '__main__':
    main()

