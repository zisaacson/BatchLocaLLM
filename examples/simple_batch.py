"""
Simple example of using vLLM Batch Server with OpenAI SDK

This example shows how to:
1. Create a batch input file
2. Upload it to the server
3. Create a batch job
4. Poll for completion
5. Download and parse results
"""

import json
import time
from openai import OpenAI

# =============================================================================
# Configuration
# =============================================================================

# Point to your vLLM Batch Server
# For local: http://localhost:8000/v1
# For remote: http://10.0.0.223:8000/v1
BASE_URL = "http://localhost:8000/v1"
API_KEY = "not-needed-for-local"  # vLLM doesn't require auth by default

# Model name (must match what's loaded in vLLM)
MODEL = "meta-llama/Llama-3.1-8B-Instruct"

# =============================================================================
# Example Batch Requests
# =============================================================================

batch_requests = [
    {
        "custom_id": "request-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
    },
    {
        "custom_id": "request-2",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "max_tokens": 50,
            "temperature": 0.7
        }
    },
    {
        "custom_id": "request-3",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Write a haiku about programming."}
            ],
            "max_tokens": 100,
            "temperature": 0.9
        }
    },
]

# =============================================================================
# Main Script
# =============================================================================

def main():
    print("=" * 80)
    print("vLLM Batch Server - Simple Example")
    print("=" * 80)
    print()

    # Initialize OpenAI client
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    # Step 1: Create batch input file
    print("Step 1: Creating batch input file...")
    batch_file_name = "batch_input.jsonl"
    with open(batch_file_name, "w") as f:
        for request in batch_requests:
            f.write(json.dumps(request) + "\n")
    print(f"✓ Created {batch_file_name} with {len(batch_requests)} requests")
    print()

    # Step 2: Upload file
    print("Step 2: Uploading batch file...")
    with open(batch_file_name, "rb") as f:
        file = client.files.create(file=f, purpose="batch")
    print(f"✓ File uploaded: {file.id}")
    print(f"  - Filename: {file.filename}")
    print(f"  - Size: {file.bytes} bytes")
    print()

    # Step 3: Create batch job
    print("Step 3: Creating batch job...")
    batch = client.batches.create(
        input_file_id=file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    print(f"✓ Batch created: {batch.id}")
    print(f"  - Status: {batch.status}")
    print(f"  - Input file: {batch.input_file_id}")
    print()

    # Step 4: Poll for completion
    print("Step 4: Waiting for batch to complete...")
    print("(This may take a few seconds to a few minutes depending on batch size)")
    print()

    start_time = time.time()
    while True:
        batch_status = client.batches.retrieve(batch.id)
        elapsed = time.time() - start_time
        
        print(f"  [{elapsed:.1f}s] Status: {batch_status.status}", end="")
        
        if batch_status.request_counts:
            counts = batch_status.request_counts
            print(f" | Completed: {counts.completed}/{counts.total}", end="")
            if counts.failed > 0:
                print(f" | Failed: {counts.failed}", end="")
        
        print()
        
        if batch_status.status == "completed":
            print()
            print("✓ Batch completed successfully!")
            break
        elif batch_status.status == "failed":
            print()
            print("✗ Batch failed!")
            return
        elif batch_status.status == "cancelled":
            print()
            print("✗ Batch was cancelled!")
            return
        
        time.sleep(2)  # Poll every 2 seconds

    print()

    # Step 5: Download results
    print("Step 5: Downloading results...")
    if batch_status.output_file_id:
        result_content = client.files.content(batch_status.output_file_id)
        results_text = result_content.text()
        
        # Save results to file
        results_file_name = "batch_results.jsonl"
        with open(results_file_name, "w") as f:
            f.write(results_text)
        
        print(f"✓ Results saved to {results_file_name}")
        print()
        
        # Parse and display results
        print("Step 6: Parsing results...")
        print("=" * 80)
        
        for line in results_text.strip().split("\n"):
            result = json.loads(line)
            custom_id = result["custom_id"]
            
            if result.get("error"):
                print(f"\n❌ {custom_id}: ERROR")
                print(f"   {result['error']['message']}")
            else:
                response = result["response"]["body"]
                message = response["choices"][0]["message"]["content"]
                usage = response["usage"]
                
                print(f"\n✓ {custom_id}:")
                print(f"   Response: {message}")
                print(f"   Tokens: {usage['prompt_tokens']} prompt + {usage['completion_tokens']} completion = {usage['total_tokens']} total")
        
        print()
        print("=" * 80)
        print()
        
        # Summary
        total_time = time.time() - start_time
        print("Summary:")
        print(f"  - Total requests: {batch_status.request_counts.total}")
        print(f"  - Completed: {batch_status.request_counts.completed}")
        print(f"  - Failed: {batch_status.request_counts.failed}")
        print(f"  - Total time: {total_time:.2f}s")
        print(f"  - Average time per request: {total_time / batch_status.request_counts.total:.2f}s")
        print()
        print("✓ Done!")
    else:
        print("✗ No output file available")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

