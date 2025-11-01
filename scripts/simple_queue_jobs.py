#!/usr/bin/env python3
"""
Simple script to queue both benchmark jobs using OpenAI-compatible API.
"""

import requests
from pathlib import Path
import json

API_URL = "http://localhost:4080"

def queue_batch(batch_file: Path, model_id: str, description: str):
    """Upload file and create batch job."""

    # Step 1: Upload file
    print(f"Uploading {batch_file.name} for {description}...")
    with open(batch_file, 'rb') as f:
        response = requests.post(
            f"{API_URL}/v1/files",
            files={'file': (batch_file.name, f, 'application/jsonl')},
            data={'purpose': 'batch'}
        )

    if response.status_code != 200:
        print(f"❌ File upload failed: {response.status_code} - {response.text[:200]}")
        return None

    file_id = response.json()['id']
    print(f"✅ File uploaded: {file_id}")

    # Step 2: Create batch job
    print(f"Creating batch job...")
    response = requests.post(
        f"{API_URL}/v1/batches",
        json={
            'input_file_id': file_id,
            'endpoint': '/v1/chat/completions',
            'completion_window': '24h',
            'metadata': {
                'description': description,
                'model': model_id
            }
        }
    )

    if response.status_code != 200:
        print(f"❌ Batch creation failed: {response.status_code} - {response.text[:200]}")
        return None

    batch_id = response.json()['id']
    print(f"✅ Batch created: {batch_id}")
    return batch_id

# Queue OLMo 2 7B
print("=" * 60)
print("QUEUING OLMO 2 7B Q4_0")
print("=" * 60)
olmo_batch = queue_batch(
    Path("batch_5k_olmo2_7b.jsonl"),
    'bartowski/OLMo-2-1124-7B-Instruct-GGUF',
    'OLMo 2 7B Q4_0 - 5K benchmark'
)

# Queue GPT-OSS 20B
print("\n" + "=" * 60)
print("QUEUING GPT-OSS 20B Q4_0")
print("=" * 60)
gptoss_batch = queue_batch(
    Path("batch_5k_gptoss_20b.jsonl"),
    'bartowski/openai_gpt-oss-20b-GGUF',
    'GPT-OSS 20B Q4_0 - 5K benchmark'
)

print("\n" + "=" * 60)
if olmo_batch and gptoss_batch:
    print("✅ BOTH JOBS QUEUED SUCCESSFULLY!")
    print(f"   OLMo 2 7B: {olmo_batch}")
    print(f"   GPT-OSS 20B: {gptoss_batch}")
    print("\nWorker will process them sequentially:")
    print("  1. Load OLMo 2 7B → Process 5K → Unload")
    print("  2. Load GPT-OSS 20B → Process 5K → Unload")
    print("\nMonitor progress:")
    print("  tail -f logs/worker.log")
    print("  ./scripts/monitor_benchmark.sh")
else:
    print("❌ FAILED TO QUEUE JOBS")
print("=" * 60)

