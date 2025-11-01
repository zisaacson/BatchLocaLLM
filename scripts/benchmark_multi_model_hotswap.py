#!/usr/bin/env python3
"""
Multi-Model Hot-Swap Benchmark

Submits batch jobs for multiple models and lets the worker
automatically hot-swap between them.

This demonstrates:
1. Queue-based model switching
2. Automatic model loading/unloading
3. Sequential processing of different models
4. No manual intervention needed

Usage:
    python scripts/benchmark_multi_model_hotswap.py
"""

import json
import time
from pathlib import Path
import requests
from datetime import datetime

# Models to benchmark
MODELS = [
    {
        "model_id": "bartowski/OLMo-2-1124-7B-Instruct-GGUF",
        "local_path": "./models/olmo2-7b-q4/OLMo-2-1124-7B-Instruct-Q4_0.gguf",
        "name": "OLMo 2 7B Q4_0"
    },
    {
        "model_id": "bartowski/openai_gpt-oss-20b-GGUF",
        "local_path": "./models/gpt-oss-20b-q4/openai_gpt-oss-20b-Q4_0.gguf",
        "name": "GPT-OSS 20B Q4_0"
    }
]

DATASET_PATH = Path("batch_5k.jsonl")
API_URL = "http://localhost:4080"


def wait_for_download(local_path: str, model_name: str):
    """Wait for model download to complete."""
    path = Path(local_path)
    print(f"⏳ Waiting for {model_name} download to complete...")
    print(f"   Checking: {path}")
    
    while not path.exists():
        print(f"   Still downloading... (checking every 30s)")
        time.sleep(30)
    
    print(f"✅ {model_name} download complete!")
    return True


def submit_batch_job(model_id: str, model_name: str) -> str:
    """Submit a batch job to the API."""
    
    # Read dataset
    with open(DATASET_PATH) as f:
        requests_data = [json.loads(line) for line in f]
    
    print(f"\n📤 Submitting batch job for {model_name}")
    print(f"   Model: {model_id}")
    print(f"   Requests: {len(requests_data)}")
    
    # Create batch file
    batch_content = "\n".join(json.dumps(req) for req in requests_data)
    
    # Submit via API
    response = requests.post(
        f"{API_URL}/v1/batches",
        files={
            "file": ("batch.jsonl", batch_content, "application/jsonl")
        },
        data={
            "model": model_id,
            "endpoint": "/v1/chat/completions"
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit batch: {response.text}")
        return None
    
    batch = response.json()
    batch_id = batch["id"]
    
    print(f"✅ Batch submitted: {batch_id}")
    print(f"   Status: {batch['status']}")
    
    return batch_id


def monitor_batch(batch_id: str, model_name: str):
    """Monitor batch progress."""
    print(f"\n📊 Monitoring {model_name} batch: {batch_id}")
    
    last_status = None
    start_time = time.time()
    
    while True:
        response = requests.get(f"{API_URL}/v1/batches/{batch_id}")
        if response.status_code != 200:
            print(f"❌ Failed to get batch status: {response.text}")
            break
        
        batch = response.json()
        status = batch["status"]
        
        if status != last_status:
            elapsed = time.time() - start_time
            print(f"   [{elapsed:.0f}s] Status: {status}")
            
            if "request_counts" in batch:
                counts = batch["request_counts"]
                total = counts.get("total", 0)
                completed = counts.get("completed", 0)
                failed = counts.get("failed", 0)
                
                if total > 0:
                    pct = (completed / total) * 100
                    print(f"   Progress: {completed}/{total} ({pct:.1f}%) | Failed: {failed}")
            
            last_status = status
        
        if status in ["completed", "failed", "cancelled"]:
            break
        
        time.sleep(10)
    
    elapsed = time.time() - start_time
    print(f"\n✅ {model_name} batch {status} in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    
    return batch


def main():
    """Main execution."""
    print("=" * 80)
    print("🔥 Multi-Model Hot-Swap Benchmark")
    print("=" * 80)
    print()
    print("This will:")
    print("1. Wait for model downloads to complete")
    print("2. Submit batch jobs for each model")
    print("3. Worker will automatically hot-swap between models")
    print("4. Process all batches sequentially")
    print()
    
    # Wait for downloads
    print("📥 Checking model downloads...")
    for model in MODELS:
        wait_for_download(model["local_path"], model["name"])
    
    print("\n✅ All models downloaded!")
    
    # Submit all batch jobs
    print("\n" + "=" * 80)
    print("📤 Submitting Batch Jobs")
    print("=" * 80)
    
    batch_ids = []
    for model in MODELS:
        batch_id = submit_batch_job(model["model_id"], model["name"])
        if batch_id:
            batch_ids.append({
                "id": batch_id,
                "model": model["name"],
                "model_id": model["model_id"]
            })
            time.sleep(2)  # Brief pause between submissions
    
    if not batch_ids:
        print("❌ No batches submitted!")
        return
    
    print(f"\n✅ Submitted {len(batch_ids)} batch jobs")
    print("\n🔄 Worker will now hot-swap between models automatically:")
    for i, batch in enumerate(batch_ids, 1):
        print(f"   {i}. {batch['model']} (batch {batch['id']})")
    
    # Monitor all batches
    print("\n" + "=" * 80)
    print("📊 Monitoring Progress")
    print("=" * 80)
    
    results = []
    for batch_info in batch_ids:
        result = monitor_batch(batch_info["id"], batch_info["model"])
        results.append({
            "model": batch_info["model"],
            "model_id": batch_info["model_id"],
            "batch_id": batch_info["id"],
            "result": result
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Final Summary")
    print("=" * 80)
    
    for r in results:
        print(f"\n{r['model']}:")
        print(f"  Batch ID: {r['batch_id']}")
        print(f"  Status: {r['result']['status']}")
        
        if "request_counts" in r["result"]:
            counts = r["result"]["request_counts"]
            print(f"  Completed: {counts.get('completed', 0)}/{counts.get('total', 0)}")
            print(f"  Failed: {counts.get('failed', 0)}")
        
        if "output_file_id" in r["result"]:
            print(f"  Output: {r['result']['output_file_id']}")
    
    print("\n✅ All batches complete!")
    print("\nNext steps:")
    print("1. View results in workbench: http://localhost:4080/workbench.html")
    print("2. Compare model outputs side-by-side")
    print("3. Analyze quality vs speed tradeoffs")


if __name__ == "__main__":
    main()

