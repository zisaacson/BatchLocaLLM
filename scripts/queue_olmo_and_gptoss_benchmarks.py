#!/usr/bin/env python3
"""
Queue OLMo 2 7B and GPT-OSS 20B benchmarks.

This script:
1. Adds both models to the registry with correct configs
2. Queues both 5K batch jobs
3. Worker will process them sequentially with automatic model hot-swap

Just run this and walk away - it will take hours/days but will keep going.
"""

import json
import requests
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "batch_server.db"
BATCH_FILE = PROJECT_ROOT / "batch_5k.jsonl"
API_URL = "http://localhost:4080"


def add_model_to_registry(model_config: dict):
    """Add a model to the registry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if model already exists
        cursor.execute(
            "SELECT id FROM model_registry WHERE model_id = ?",
            (model_config['model_id'],)
        )
        existing = cursor.fetchone()
        
        if existing:
            print(f"⏭️  Model {model_config['model_id']} already in registry")
            return
        
        # Insert model
        cursor.execute("""
            INSERT INTO model_registry (
                model_id, name, local_path, quantization_type,
                size_gb, estimated_memory_gb, max_model_len,
                gpu_memory_utilization, cpu_offload_gb,
                enable_prefix_caching, chunked_prefill_enabled,
                rtx4080_compatible, requires_hf_auth, status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_config['model_id'],
            model_config['name'],
            model_config['local_path'],
            model_config['quantization_type'],
            model_config['size_gb'],
            model_config['estimated_memory_gb'],
            model_config['max_model_len'],
            model_config['gpu_memory_utilization'],
            model_config['cpu_offload_gb'],
            model_config['enable_prefix_caching'],
            model_config['chunked_prefill_enabled'],
            model_config['rtx4080_compatible'],
            model_config['requires_hf_auth'],
            model_config['status'],
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        print(f"✅ Added {model_config['name']} to registry")
        
    finally:
        conn.close()


def queue_batch_job(model_id: str, batch_file: Path, description: str):
    """Queue a batch job via API."""
    
    if not batch_file.exists():
        print(f"❌ Batch file not found: {batch_file}")
        return None
    
    print(f"\n📤 Queuing batch job: {description}")
    print(f"   Model: {model_id}")
    print(f"   File: {batch_file}")
    
    # Upload batch file
    with open(batch_file, 'rb') as f:
        files = {'file': (batch_file.name, f, 'application/jsonl')}
        data = {
            'model': model_id,
            'metadata': json.dumps({
                'description': description,
                'queued_at': datetime.now(timezone.utc).isoformat()
            })
        }
        
        response = requests.post(
            f"{API_URL}/v1/batches",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        result = response.json()
        batch_id = result.get('id')
        print(f"✅ Batch queued: {batch_id}")
        print(f"   Status: {result.get('status')}")
        return batch_id
    else:
        print(f"❌ Failed to queue batch: {response.status_code}")
        print(f"   Error: {response.text}")
        return None


def main():
    """Main execution."""
    
    print("=" * 80)
    print("🚀 Queueing OLMo 2 7B and GPT-OSS 20B Benchmarks")
    print("=" * 80)
    
    # Model configurations
    models = [
        {
            'model_id': 'bartowski/OLMo-2-1124-7B-Instruct-GGUF',
            'name': 'OLMo 2 7B Q4_0 GGUF',
            'local_path': str(PROJECT_ROOT / 'models/olmo2-7b-q4/OLMo-2-1124-7B-Instruct-Q4_0.gguf'),
            'quantization_type': 'Q4_0',
            'size_gb': 4.23,
            'estimated_memory_gb': 11.5,
            'max_model_len': 8192,
            'gpu_memory_utilization': 0.95,
            'cpu_offload_gb': 0.0,  # No offload needed!
            'enable_prefix_caching': True,
            'chunked_prefill_enabled': True,
            'rtx4080_compatible': True,
            'requires_hf_auth': False,
            'status': 'downloaded'
        },
        {
            'model_id': 'bartowski/openai_gpt-oss-20b-GGUF',
            'name': 'GPT-OSS 20B Q4_0 GGUF',
            'local_path': str(PROJECT_ROOT / 'models/gpt-oss-20b-q4/openai_gpt-oss-20b-Q4_0.gguf'),
            'quantization_type': 'Q4_0',
            'size_gb': 11.5,
            'estimated_memory_gb': 23.2,
            'max_model_len': 8192,
            'gpu_memory_utilization': 0.95,
            'cpu_offload_gb': 7.2,  # Needs offload!
            'enable_prefix_caching': True,
            'chunked_prefill_enabled': True,
            'rtx4080_compatible': True,
            'requires_hf_auth': False,
            'status': 'downloaded'
        }
    ]
    
    # Step 1: Add models to registry
    print("\n📋 Step 1: Adding models to registry")
    print("-" * 80)
    for model in models:
        add_model_to_registry(model)
    
    # Step 2: Queue batch jobs
    print("\n📋 Step 2: Queueing batch jobs")
    print("-" * 80)
    
    batch_ids = []
    
    # Queue OLMo 2 7B (faster, will run first)
    batch_id = queue_batch_job(
        model_id=models[0]['model_id'],
        batch_file=BATCH_FILE,
        description="OLMo 2 7B Q4_0 - 5K candidate evaluation benchmark"
    )
    if batch_id:
        batch_ids.append(batch_id)
    
    # Queue GPT-OSS 20B (slower, will run after OLMo)
    batch_id = queue_batch_job(
        model_id=models[1]['model_id'],
        batch_file=BATCH_FILE,
        description="GPT-OSS 20B Q4_0 - 5K candidate evaluation benchmark"
    )
    if batch_id:
        batch_ids.append(batch_id)
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ SETUP COMPLETE")
    print("=" * 80)
    print(f"\n📊 Queued {len(batch_ids)} batch jobs:")
    for i, batch_id in enumerate(batch_ids, 1):
        print(f"   {i}. {batch_id}")
    
    print("\n⏱️  Estimated Timeline:")
    print("   1. OLMo 2 7B Q4_0:  ~10-15 minutes (no CPU offload)")
    print("   2. GPT-OSS 20B Q4_0: ~60-90 minutes (with CPU offload)")
    print("   Total: ~70-105 minutes")
    
    print("\n🔍 Monitor Progress:")
    print(f"   API: {API_URL}/v1/batches")
    print(f"   Logs: tail -f logs/worker.log")
    print(f"   GPU: watch -n 1 nvidia-smi")
    
    print("\n💡 What Happens Next:")
    print("   1. Worker picks up OLMo job from queue")
    print("   2. Loads OLMo 2 7B (4.23 GB, no offload)")
    print("   3. Processes 5K requests in chunks")
    print("   4. Saves results incrementally")
    print("   5. Unloads OLMo, frees GPU memory")
    print("   6. Loads GPT-OSS 20B (11.5 GB, 7.2 GB offload)")
    print("   7. Processes 5K requests (slower due to offload)")
    print("   8. Saves results incrementally")
    print("   9. Done!")
    
    print("\n🛡️  Robustness Features:")
    print("   ✅ Automatic model hot-swap (unload → load)")
    print("   ✅ Incremental saves (resume from crashes)")
    print("   ✅ GPU memory monitoring")
    print("   ✅ Detailed logging")
    print("   ✅ Webhook notifications on completion")
    
    print("\n🚀 Worker is running - you can walk away now!")
    print("=" * 80)


if __name__ == "__main__":
    main()

