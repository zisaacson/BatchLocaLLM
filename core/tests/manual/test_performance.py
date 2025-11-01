#!/usr/bin/env python3
"""
Quick performance test - submit 100 requests and measure throughput
"""
import json
import time
import requests
from pathlib import Path

API_URL = "http://localhost:4080"

# Create test batch with 100 candidate evaluation requests
print("Creating test batch with 100 requests...")

requests_data = []
for i in range(100):
    requests_data.append({
        "custom_id": f"test-{i}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "google/gemma-3-4b-it",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert technical recruiter evaluating software engineering candidates."
                },
                {
                    "role": "user",
                    "content": f"""Evaluate this candidate:

Name: Test Candidate {i}
Current Role: Senior Software Engineer at Tech Corp
Education: BS Computer Science, Stanford University
Experience: 5 years at Google, 3 years at Meta

Rate on these criteria:
1. Trajectory (Exceptional/Strong/Good/Average/Weak)
2. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
3. Educational Pedigree (Exceptional/Strong/Good/Average/Weak)
4. Overall Recommendation (Strong Yes/Yes/Maybe/No/Strong No)

Provide your evaluation in JSON format."""
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
    })

# Save to JSONL file
batch_file = Path("test_batch_100.jsonl")
with open(batch_file, "w") as f:
    for req in requests_data:
        f.write(json.dumps(req) + "\n")

print(f"✅ Created {batch_file} with {len(requests_data)} requests")

# Submit batch
print("\n📤 Submitting batch...")
start_time = time.time()

with open(batch_file, "rb") as f:
    response = requests.post(
        f"{API_URL}/v1/batches",
        files={"file": ("batch.jsonl", f, "application/jsonl")},
        data={
            "model": "google/gemma-3-4b-it",
            "metadata": json.dumps({
                "conquest_type": "candidate_evaluation",
                "source": "performance_test"
            })
        }
    )

if response.status_code != 200:
    print(f"❌ Failed to submit batch: {response.status_code}")
    print(response.text)
    exit(1)

batch = response.json()
batch_id = batch["id"]
print(f"✅ Batch submitted: {batch_id}")
print(f"   Status: {batch['status']}")

# Poll for completion
print("\n⏳ Waiting for completion...")
last_status = None
last_completed = 0

while True:
    response = requests.get(f"{API_URL}/v1/batches/{batch_id}")
    batch = response.json()
    
    status = batch["status"]
    completed = batch["request_counts"]["completed"]
    total = batch["request_counts"]["total"]
    
    if status != last_status or completed != last_completed:
        elapsed = time.time() - start_time
        print(f"   [{elapsed:.1f}s] Status: {status}, Progress: {completed}/{total}")
        last_status = status
        last_completed = completed
    
    if status in ["completed", "failed", "cancelled"]:
        break
    
    time.sleep(1)

# Calculate metrics
end_time = time.time()
total_time = end_time - start_time

print("\n" + "="*60)
print("📊 PERFORMANCE RESULTS")
print("="*60)
print(f"Total requests: {total}")
print(f"Completed: {batch['request_counts']['completed']}")
print(f"Failed: {batch['request_counts']['failed']}")
print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
print(f"Throughput: {total/total_time:.1f} requests/sec")
print(f"Avg latency: {total_time/total:.3f}s per request")
print("="*60)

# Cleanup
batch_file.unlink()
print(f"\n🧹 Cleaned up {batch_file}")

