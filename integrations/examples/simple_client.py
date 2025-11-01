#!/usr/bin/env python3
"""
Simple example of using the vLLM Batch Server API.

This demonstrates the basic workflow:
1. Upload a batch file
2. Create a batch job
3. Poll for completion
4. Download results
"""

import requests
import json
import time
from pathlib import Path

# Configuration
API_URL = "http://localhost:4080"
BATCH_FILE = "examples/datasets/demo_batch_10.jsonl"


def upload_file(file_path: str) -> str:
    """Upload a batch file and return the file ID."""
    print(f"📤 Uploading {file_path}...")
    
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/v1/files",
            files={"file": f},
            data={"purpose": "batch"}
        )
    
    response.raise_for_status()
    file_id = response.json()["id"]
    print(f"✅ File uploaded: {file_id}")
    return file_id


def create_batch(file_id: str) -> str:
    """Create a batch job and return the batch ID."""
    print(f"\n🚀 Creating batch job...")
    
    response = requests.post(
        f"{API_URL}/v1/batches",
        json={
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        }
    )
    
    response.raise_for_status()
    batch_id = response.json()["id"]
    print(f"✅ Batch created: {batch_id}")
    return batch_id


def poll_batch(batch_id: str, poll_interval: int = 5) -> dict:
    """Poll batch status until completion."""
    print(f"\n⏳ Polling batch status (every {poll_interval}s)...")
    
    while True:
        response = requests.get(f"{API_URL}/v1/batches/{batch_id}")
        response.raise_for_status()
        batch = response.json()
        
        status = batch["status"]
        request_counts = batch.get("request_counts", {})
        completed = request_counts.get("completed", 0)
        total = request_counts.get("total", 0)
        
        print(f"   Status: {status} | Progress: {completed}/{total}")
        
        if status in ["completed", "failed", "cancelled"]:
            print(f"\n{'✅' if status == 'completed' else '❌'} Batch {status}")
            return batch
        
        time.sleep(poll_interval)


def download_results(output_file_id: str, save_path: str = "results.jsonl"):
    """Download and save batch results."""
    print(f"\n📥 Downloading results...")
    
    response = requests.get(f"{API_URL}/v1/files/{output_file_id}/content")
    response.raise_for_status()
    
    with open(save_path, 'w') as f:
        f.write(response.text)
    
    print(f"✅ Results saved to: {save_path}")
    
    # Print first result as example
    lines = response.text.strip().split('\n')
    if lines:
        first_result = json.loads(lines[0])
        print(f"\n📊 Example result:")
        print(f"   Custom ID: {first_result.get('custom_id')}")
        if 'response' in first_result:
            resp = first_result['response']
            if 'body' in resp and 'choices' in resp['body']:
                content = resp['body']['choices'][0]['message']['content']
                print(f"   Response: {content[:100]}...")


def main():
    """Run the complete batch processing workflow."""
    print("=" * 60)
    print("vLLM Batch Server - Simple Client Example")
    print("=" * 60)
    
    try:
        # 1. Upload batch file
        file_id = upload_file(BATCH_FILE)
        
        # 2. Create batch job
        batch_id = create_batch(file_id)
        
        # 3. Poll for completion
        batch = poll_batch(batch_id)
        
        # 4. Download results if completed
        if batch["status"] == "completed":
            output_file_id = batch["output_file_id"]
            download_results(output_file_id, f"results_{batch_id}.jsonl")
        
        print("\n" + "=" * 60)
        print("✅ Workflow complete!")
        print("=" * 60)
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

