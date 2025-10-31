#!/usr/bin/env python3
"""
Test batch optimization with identical system prompts.

This simulates the 170k candidate scoring use case:
- Same system prompt (scoring rubric)
- Different candidate data each time
"""

import json
import time

import requests

BASE_URL = "http://localhost:4080"

# Simulated scoring rubric (same for all candidates)
SYSTEM_PROMPT = """You are an expert candidate evaluator. Score candidates on a scale of 1-10 based on:
- Technical skills
- Communication ability
- Cultural fit
- Leadership potential

Provide only a numeric score (1-10) as your response."""

def create_batch_file(num_requests: int = 20):
    """Create a batch file with identical system prompts"""
    requests_data = []

    for i in range(1, num_requests + 1):
        # Each candidate has different data
        candidate_data = f"Candidate #{i}: 5 years experience, strong Python skills, good communicator"

        request = {
            "custom_id": f"candidate-{i}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gemma3:12b",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": candidate_data}
                ],
                "max_tokens": 10
            }
        }
        requests_data.append(request)

    filename = "test_optimization_batch.jsonl"
    with open(filename, "w") as f:
        for req in requests_data:
            f.write(json.dumps(req) + "\n")

    print(f"✅ Created batch file: {filename} ({num_requests} requests)")
    print(f"   System prompt: {len(SYSTEM_PROMPT)} chars")
    print("   All requests share IDENTICAL system prompt")
    return filename

def upload_file(filename: str) -> str:
    """Upload batch file"""
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "application/jsonl")}
        data = {"purpose": "batch"}
        response = requests.post(f"{BASE_URL}/v1/files", files=files, data=data)
        response.raise_for_status()
        file_id = response.json()["id"]
        print(f"✅ File uploaded: {file_id}")
        return file_id

def create_batch(input_file_id: str) -> str:
    """Create batch job"""
    data = {
        "input_file_id": input_file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
    response = requests.post(f"{BASE_URL}/v1/batches", json=data)
    response.raise_for_status()
    batch_id = response.json()["id"]
    print(f"✅ Batch created: {batch_id}")
    return batch_id

def wait_for_batch(batch_id: str, max_wait: int = 300):
    """Poll batch status until complete"""
    print(f"\n⏳ Waiting for batch to complete (max {max_wait}s)...")
    start_time = time.time()
    poll_count = 0

    while time.time() - start_time < max_wait:
        poll_count += 1
        response = requests.get(f"{BASE_URL}/v1/batches/{batch_id}")
        response.raise_for_status()
        batch = response.json()

        status = batch["status"]
        completed = batch["request_counts"]["completed"]
        failed = batch["request_counts"]["failed"]
        total = batch["request_counts"]["total"]

        elapsed = int(time.time() - start_time)
        print(f"   [{elapsed}s] Poll #{poll_count}: {status} - {completed}/{total} completed, {failed} failed")

        if status == "completed":
            print(f"✅ Batch completed in {elapsed}s!")
            return batch
        elif status == "failed":
            print("❌ Batch failed!")
            return batch

        time.sleep(2)

    print(f"⏰ Timeout after {max_wait}s")
    return None

def download_results(output_file_id: str):
    """Download batch results"""
    response = requests.get(f"{BASE_URL}/v1/files/{output_file_id}/content")
    response.raise_for_status()

    results = []
    for line in response.text.strip().split("\n"):
        if line:
            results.append(json.loads(line))

    print(f"✅ Downloaded {len(results)} results")
    return results

def analyze_results(results):
    """Analyze token usage and optimization"""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for result in results:
        if result.get("response"):
            usage = result["response"]["body"]["usage"]
            total_prompt_tokens += usage["prompt_tokens"]
            total_completion_tokens += usage["completion_tokens"]
            total_tokens += usage["total_tokens"]

    num_requests = len(results)
    avg_prompt_tokens = total_prompt_tokens / num_requests if num_requests > 0 else 0

    # Calculate baseline (no optimization)
    baseline_prompt_tokens = num_requests * avg_prompt_tokens

    # Calculate savings
    savings_pct = 0
    if baseline_prompt_tokens > 0:
        savings_pct = ((baseline_prompt_tokens - total_prompt_tokens) / baseline_prompt_tokens) * 100

    print("\n📊 Token Usage Analysis:")
    print(f"   Requests: {num_requests}")
    print(f"   Total prompt tokens: {total_prompt_tokens:,}")
    print(f"   Total completion tokens: {total_completion_tokens:,}")
    print(f"   Total tokens: {total_tokens:,}")
    print(f"   Avg prompt tokens/request: {avg_prompt_tokens:.1f}")
    print("\n💡 Optimization Impact:")
    print(f"   Baseline (no optimization): {baseline_prompt_tokens:,.0f} prompt tokens")
    print(f"   Actual (with optimization): {total_prompt_tokens:,} prompt tokens")
    print(f"   Token savings: {savings_pct:.1f}%")

def main():
    print("="*80)
    print("Batch Optimization Test - Identical System Prompts")
    print("="*80)

    # Create batch with 20 requests (all same system prompt)
    batch_file = create_batch_file(num_requests=20)

    try:
        # Upload and process
        file_id = upload_file(batch_file)
        batch_id = create_batch(file_id)
        batch = wait_for_batch(batch_id)

        if batch and batch["status"] == "completed":
            # Download and analyze results
            output_file_id = batch["output_file_id"]
            results = download_results(output_file_id)
            analyze_results(results)

            print("\n✅ TEST PASSED!")
        else:
            print("\n❌ TEST FAILED!")

    finally:
        # Cleanup
        import os
        if os.path.exists(batch_file):
            os.remove(batch_file)
            print(f"\n🧹 Cleaned up: {batch_file}")

if __name__ == "__main__":
    main()

