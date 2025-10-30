#!/usr/bin/env python3
"""
Proper vLLM Serve Test

Tests vLLM's OpenAI-compatible API server for batch processing.
This is the CORRECT way to test vLLM Serve.

Usage:
    # Terminal 1: Start server
    vllm serve google/gemma-3-4b-it --max-model-len 4096 --gpu-memory-utilization 0.90
    
    # Terminal 2: Run test
    python test_vllm_serve_proper.py batch_100.jsonl results.jsonl
"""

import json
import sys
import time
import asyncio
import aiohttp
from pathlib import Path

async def send_request(session, url, request_data, semaphore):
    """Send a single request with rate limiting."""
    async with semaphore:
        try:
            async with session.post(url, json=request_data, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status == 200:
                    result = await response.json()
                    return {"success": True, "data": result}
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

async def process_batch(requests, url, max_concurrent=10):
    """Process batch with controlled concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for req in requests:
            # Convert to OpenAI format
            request_data = {
                "model": "google/gemma-3-4b-it",
                "messages": req['body']['messages'],
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2000,
            }
            task = send_request(session, url, request_data, semaphore)
            tasks.append((req['custom_id'], task))
        
        # Process all requests
        results = []
        for custom_id, task in tasks:
            result = await task
            results.append({
                "custom_id": custom_id,
                "result": result
            })
        
        return results

def main():
    if len(sys.argv) != 3:
        print("Usage: python test_vllm_serve_proper.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print("=" * 80)
    print("vLLM SERVE BATCH TEST (OpenAI-Compatible API)")
    print("=" * 80)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print("=" * 80)
    
    # Check if server is running
    print("\n🔍 Checking if vLLM server is running...")
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ vLLM server is running")
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
    except Exception as e:
        print(f"❌ ERROR: Cannot connect to vLLM server at http://localhost:8000")
        print(f"   {e}")
        print("\nPlease start the server first:")
        print("   vllm serve google/gemma-3-4b-it --max-model-len 4096 --gpu-memory-utilization 0.90")
        sys.exit(1)
    
    # Load requests
    print("\n📥 Loading requests...")
    requests_data = []
    with open(input_file) as f:
        for line in f:
            req = json.loads(line)
            requests_data.append(req)
    
    print(f"✅ Loaded {len(requests_data)} requests")
    
    # Process batch
    print(f"\n⚡ Processing {len(requests_data)} requests...")
    print("Using OpenAI-compatible API with controlled concurrency (max 10 concurrent)")
    
    start_time = time.time()
    results = asyncio.run(process_batch(
        requests_data,
        "http://localhost:8000/v1/chat/completions",
        max_concurrent=10
    ))
    total_time = time.time() - start_time
    
    print(f"✅ Processing complete in {total_time:.1f}s")
    
    # Analyze results
    successful = sum(1 for r in results if r['result']['success'])
    failed = len(results) - successful
    
    # Save results
    print(f"\n💾 Saving results to {output_file}...")
    output_data = []
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    for r in results:
        if r['result']['success']:
            data = r['result']['data']
            output_data.append({
                "custom_id": r['custom_id'],
                "response": {
                    "status_code": 200,
                    "body": data
                }
            })
            if 'usage' in data:
                total_tokens += data['usage'].get('total_tokens', 0)
                prompt_tokens += data['usage'].get('prompt_tokens', 0)
                completion_tokens += data['usage'].get('completion_tokens', 0)
        else:
            output_data.append({
                "custom_id": r['custom_id'],
                "error": r['result']['error'],
                "status": "error"
            })
    
    with open(output_file, 'w') as f:
        for item in output_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"✅ Saved {len(output_data)} results")
    
    # Print summary
    throughput = total_tokens / total_time if total_time > 0 else 0
    requests_per_sec = len(requests_data) / total_time if total_time > 0 else 0
    
    print("\n" + "=" * 80)
    print("📊 BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Requests:              {len(requests_data)}")
    print(f"Successful:            {successful} ({successful/len(requests_data)*100:.1f}%)")
    print(f"Failed:                {failed} ({failed/len(requests_data)*100:.1f}%)")
    print(f"Total time:            {total_time:.1f}s")
    print(f"Prompt tokens:         {prompt_tokens:,}")
    print(f"Completion tokens:     {completion_tokens:,}")
    print(f"Total tokens:          {total_tokens:,}")
    print(f"Throughput:            {throughput:.0f} tokens/sec")
    print(f"Requests/sec:          {requests_per_sec:.2f}")
    print("=" * 80)
    
    if failed > 0:
        print(f"\n⚠️  {failed} requests failed. Check {output_file} for errors.")
    
    print("\n🎉 Test complete!")

if __name__ == '__main__':
    main()

