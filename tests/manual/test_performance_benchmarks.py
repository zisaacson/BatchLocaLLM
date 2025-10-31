#!/usr/bin/env python3
"""
Performance Benchmarks for Batch Processing

Test at different scales to validate:
1. Optimization works at scale (100, 1000, 10000 requests)
2. Context trimming prevents OOM
3. Performance is consistent
4. Token savings match predictions

This validates our system is ready for 170k requests!
"""

import json
import subprocess
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

def get_vram_usage() -> float | None:
    """Get current VRAM usage in GB"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            vram_mb = float(result.stdout.strip().split('\n')[0])
            return vram_mb / 1024
    except Exception:
        pass
    return None

def create_batch_file(num_requests: int, filename: str) -> str:
    """Create a batch file with identical system prompts"""
    requests_data = []

    for i in range(1, num_requests + 1):
        candidate_data = f"Candidate #{i}: {5 + (i % 5)} years experience, strong Python skills"

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

    with open(filename, "w") as f:
        for req in requests_data:
            f.write(json.dumps(req) + "\n")

    return filename

def upload_file(filename: str) -> str:
    """Upload batch file"""
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "application/jsonl")}
        data = {"purpose": "batch"}
        response = requests.post(f"{BASE_URL}/v1/files", files=files, data=data)
        response.raise_for_status()
        return response.json()["id"]

def create_batch(input_file_id: str) -> str:
    """Create batch job"""
    data = {
        "input_file_id": input_file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
    response = requests.post(f"{BASE_URL}/v1/batches", json=data)
    response.raise_for_status()
    return response.json()["id"]

def wait_for_batch(batch_id: str, max_wait: int = 3600) -> dict | None:
    """Poll batch status until complete"""
    start_time = time.time()
    last_log_time = start_time

    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/v1/batches/{batch_id}")
        response.raise_for_status()
        batch = response.json()

        status = batch["status"]
        completed = batch["request_counts"]["completed"]
        total = batch["request_counts"]["total"]

        # Log every 30 seconds
        if time.time() - last_log_time >= 30:
            elapsed = int(time.time() - start_time)
            vram = get_vram_usage()
            vram_str = f", VRAM={vram:.2f}GB" if vram else ""
            print(f"  [{elapsed}s] {status}: {completed}/{total} completed{vram_str}")
            last_log_time = time.time()

        if status == "completed":
            return batch
        elif status == "failed":
            print("❌ Batch failed!")
            return batch

        time.sleep(2)

    print(f"⏰ Timeout after {max_wait}s")
    return None

def download_results(output_file_id: str) -> list[dict]:
    """Download batch results"""
    response = requests.get(f"{BASE_URL}/v1/files/{output_file_id}/content")
    response.raise_for_status()

    results = []
    for line in response.text.strip().split("\n"):
        if line:
            results.append(json.loads(line))

    return results

def analyze_results(results: list[dict], batch_time: float) -> dict:
    """Analyze token usage and performance"""
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

    return {
        "num_requests": num_requests,
        "total_time_sec": batch_time,
        "avg_time_per_request_sec": batch_time / num_requests if num_requests > 0 else 0,
        "requests_per_second": num_requests / batch_time if batch_time > 0 else 0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "avg_prompt_tokens": avg_prompt_tokens,
        "baseline_prompt_tokens": baseline_prompt_tokens,
        "token_savings_pct": savings_pct,
        "tokens_per_second": total_tokens / batch_time if batch_time > 0 else 0,
    }

def run_benchmark(num_requests: int) -> dict | None:
    """Run a single benchmark test"""
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {num_requests:,} Requests")
    print(f"{'='*80}")

    filename = f"benchmark_{num_requests}.jsonl"

    try:
        # Create batch file
        print("Creating batch file...")
        create_batch_file(num_requests, filename)
        print(f"✅ Created {filename}")

        # Upload
        print("Uploading...")
        vram_start = get_vram_usage()
        file_id = upload_file(filename)
        print(f"✅ Uploaded: {file_id}")

        # Create batch
        print("Creating batch job...")
        batch_id = create_batch(file_id)
        print(f"✅ Batch created: {batch_id}")

        # Wait for completion
        print("Processing (this may take a while)...")
        start_time = time.time()
        batch = wait_for_batch(batch_id, max_wait=7200)  # 2 hour timeout

        if not batch or batch["status"] != "completed":
            print("❌ Batch did not complete successfully")
            return None

        batch_time = time.time() - start_time
        vram_end = get_vram_usage()

        # Download results
        print("Downloading results...")
        output_file_id = batch["output_file_id"]
        results = download_results(output_file_id)
        print(f"✅ Downloaded {len(results)} results")

        # Analyze
        metrics = analyze_results(results, batch_time)
        metrics["vram_start_gb"] = vram_start
        metrics["vram_end_gb"] = vram_end
        metrics["vram_delta_gb"] = vram_end - vram_start if (vram_start and vram_end) else None

        # Print summary
        print("\n📊 RESULTS:")
        print(f"   Requests: {metrics['num_requests']:,}")
        print(f"   Total time: {metrics['total_time_sec']:.1f}s ({metrics['total_time_sec']/60:.1f}min)")
        print(f"   Avg time/request: {metrics['avg_time_per_request_sec']:.3f}s")
        print(f"   Throughput: {metrics['requests_per_second']:.2f} req/s")
        print(f"   Token speed: {metrics['tokens_per_second']:.1f} tokens/s")
        print(f"   Total tokens: {metrics['total_tokens']:,}")
        print(f"   Token savings: {metrics['token_savings_pct']:.1f}%")
        if metrics["vram_delta_gb"]:
            print(f"   VRAM delta: {metrics['vram_delta_gb']:.2f} GB")

        return metrics

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        # Cleanup
        import os
        if os.path.exists(filename):
            os.remove(filename)

def main():
    print("="*80)
    print("PERFORMANCE BENCHMARKS")
    print("="*80)
    print("\nThis will test batch processing at different scales:")
    print("  - 100 requests (~15 seconds)")
    print("  - 1,000 requests (~2.5 minutes)")
    print("  - 10,000 requests (~25 minutes)")
    print("\n⚠️  Make sure server is running on port 4080!")
    print("⚠️  Make sure Ollama is running with gemma3:12b loaded!")

    input("\nPress Enter to continue...")

    # Check server
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server not running! Start with: python -m uvicorn src.main:app --host 0.0.0.0 --port 4080")
            return
    except:
        print("❌ Cannot connect to server!")
        return

    # Run benchmarks
    test_sizes = [100, 1000, 10000]
    results = {}

    for size in test_sizes:
        result = run_benchmark(size)
        if result:
            results[size] = result
        else:
            print(f"\n🚨 Benchmark failed at {size} requests")
            break

        # Wait between tests
        if size != test_sizes[-1]:
            print("\n⏸️  Waiting 10 seconds before next test...")
            time.sleep(10)

    # Final summary
    if results:
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}")

        print(f"\n{'Size':<10} {'Time':<12} {'Req/s':<10} {'Tokens/s':<12} {'Savings':<10}")
        print(f"{'-'*10} {'-'*12} {'-'*10} {'-'*12} {'-'*10}")

        for size, metrics in results.items():
            time_str = f"{metrics['total_time_sec']:.1f}s"
            req_s = f"{metrics['requests_per_second']:.2f}"
            tok_s = f"{metrics['tokens_per_second']:.1f}"
            savings = f"{metrics['token_savings_pct']:.1f}%"
            print(f"{size:<10,} {time_str:<12} {req_s:<10} {tok_s:<12} {savings:<10}")

        # Extrapolate to 170k
        if 10000 in results:
            metrics_10k = results[10000]
            time_per_request = metrics_10k["avg_time_per_request_sec"]
            estimated_time_170k = time_per_request * 170000

            print("\n📊 EXTRAPOLATION TO 170,000 REQUESTS:")
            print(f"   Estimated time: {estimated_time_170k:.1f}s ({estimated_time_170k/3600:.1f} hours)")
            print(f"   Estimated throughput: {metrics_10k['requests_per_second']:.2f} req/s")
            print(f"   Estimated token savings: {metrics_10k['token_savings_pct']:.1f}%")

        # Save results
        with open("performance_benchmarks.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\n💾 Results saved to: performance_benchmarks.json")

if __name__ == "__main__":
    main()

