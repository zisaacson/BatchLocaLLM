"""
Test OpenAI SDK compatibility with our vLLM batch server.

This script verifies that the OpenAI Python SDK works with our API
as a drop-in replacement for OpenAI/Parasail.
"""

import json
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("❌ OpenAI SDK not installed. Installing...")
    import subprocess
    subprocess.run(["pip", "install", "openai"], check=True)
    from openai import OpenAI

print("=" * 80)
print("🧪 TESTING OPENAI SDK COMPATIBILITY")
print("=" * 80)

# Initialize client pointing to our local server
client = OpenAI(
    base_url="http://localhost:4080/v1",
    api_key="dummy-key"  # We don't have auth yet, but SDK requires something
)

print("\n1️⃣  Creating test input file...")

# Create test JSONL file
test_requests = [
    {
        "custom_id": "request-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "Qwen/Qwen2.5-3B-Instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "temperature": 0.7,
            "max_completion_tokens": 100
        }
    },
    {
        "custom_id": "request-2",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "Qwen/Qwen2.5-3B-Instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "temperature": 0.7,
            "max_completion_tokens": 100
        }
    },
    {
        "custom_id": "request-3",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "Qwen/Qwen2.5-3B-Instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Write a haiku about coding."}
            ],
            "temperature": 0.7,
            "max_completion_tokens": 100
        }
    }
]

test_file = Path("test_openai_sdk_input.jsonl")
with open(test_file, "w") as f:
    for req in test_requests:
        f.write(json.dumps(req) + "\n")

print(f"✅ Created test file: {test_file}")
print(f"   Requests: {len(test_requests)}")

# Step 1: Upload file
print("\n2️⃣  Uploading file to Files API...")
try:
    with open(test_file, "rb") as f:
        file = client.files.create(
            file=f,
            purpose="batch"
        )

    print("✅ File uploaded successfully!")
    print(f"   File ID: {file.id}")
    print(f"   Filename: {file.filename}")
    print(f"   Bytes: {file.bytes}")
    print(f"   Purpose: {file.purpose}")
    print(f"   Created at: {file.created_at}")
except Exception as e:
    print(f"❌ File upload failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 2: Create batch
print("\n3️⃣  Creating batch job...")
try:
    batch = client.batches.create(
        input_file_id=file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    print("✅ Batch created successfully!")
    print(f"   Batch ID: {batch.id}")
    print(f"   Status: {batch.status}")
    print(f"   Endpoint: {batch.endpoint}")
    print(f"   Input file ID: {batch.input_file_id}")
    print(f"   Completion window: {batch.completion_window}")
    print(f"   Created at: {batch.created_at}")
    print(f"   Expires at: {batch.expires_at}")
except Exception as e:
    print(f"❌ Batch creation failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 3: Poll for completion
print("\n4️⃣  Polling for completion...")
print("   (This will take a few minutes - worker needs to load model and process)")

max_wait = 600  # 10 minutes
start_time = time.time()
last_status = None

while time.time() - start_time < max_wait:
    try:
        batch = client.batches.retrieve(batch.id)

        if batch.status != last_status:
            print(f"   Status: {batch.status}")
            if batch.request_counts:
                print(f"   Progress: {batch.request_counts.completed}/{batch.request_counts.total}")
            last_status = batch.status

        if batch.status in ["completed", "failed", "expired", "cancelled"]:
            break

        time.sleep(5)
    except Exception as e:
        print(f"   ⚠️  Polling error: {e}")
        time.sleep(5)

elapsed = time.time() - start_time

if batch.status == "completed":
    print(f"\n✅ Batch completed in {elapsed:.1f}s!")
    print(f"   Output file ID: {batch.output_file_id}")
    print("   Request counts:")
    print(f"     Total: {batch.request_counts.total}")
    print(f"     Completed: {batch.request_counts.completed}")
    print(f"     Failed: {batch.request_counts.failed}")

    # Step 4: Download results
    print("\n5️⃣  Downloading results...")
    try:
        content = client.files.content(batch.output_file_id)

        results_file = Path("test_openai_sdk_results.jsonl")
        results_file.write_bytes(content.read())

        print(f"✅ Results downloaded: {results_file}")

        # Parse and display results
        print("\n📊 Results:")
        with open(results_file) as f:
            for i, line in enumerate(f, 1):
                result = json.loads(line)
                custom_id = result.get("custom_id")
                response = result.get("response", {})
                body = response.get("body", {})
                choices = body.get("choices", [])

                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    print(f"\n   Request {i} ({custom_id}):")
                    print(f"   {content[:200]}...")

        print("\n" + "=" * 80)
        print("✅ OPENAI SDK COMPATIBILITY TEST PASSED!")
        print("=" * 80)
        print("\nThe OpenAI Python SDK works perfectly with our vLLM batch server!")
        print("You can now switch between local and Parasail by just changing base_url.")

    except Exception as e:
        print(f"❌ Results download failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

elif batch.status == "failed":
    print("\n❌ Batch failed!")
    print(f"   Errors: {batch.errors}")
    exit(1)
elif batch.status == "expired":
    print("\n❌ Batch expired (took longer than 24h)")
    exit(1)
elif batch.status == "cancelled":
    print("\n❌ Batch was cancelled")
    exit(1)
else:
    print(f"\n⏱️  Batch still processing after {elapsed:.1f}s")
    print(f"   Current status: {batch.status}")
    print(f"   You can check status later with: client.batches.retrieve('{batch.id}')")

