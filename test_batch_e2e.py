#!/usr/bin/env python3
"""
End-to-End Batch Processing Test

Tests the complete batch processing workflow:
1. Create batch JSONL file
2. Upload file
3. Create batch job
4. Poll for completion
5. Download and verify results
"""

import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, Any, List

BASE_URL = "http://localhost:4080"

def create_batch_file(num_requests: int = 5) -> str:
    """Create a test batch JSONL file"""
    batch_file = "test_batch_requests.jsonl"
    
    requests_data = [
        {
            "custom_id": f"request-{i+1}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gemma3:12b",
                "messages": [
                    {"role": "user", "content": f"What is {i+1} + {i+1}? Answer with just the number."}
                ],
                "temperature": 0.1,
                "max_tokens": 10
            }
        }
        for i in range(num_requests)
    ]
    
    with open(batch_file, 'w') as f:
        for req in requests_data:
            f.write(json.dumps(req) + '\n')
    
    print(f"✅ Created batch file: {batch_file} ({num_requests} requests)")
    return batch_file

def upload_file(file_path: str) -> str:
    """Upload batch file to server"""
    print(f"\n📤 Uploading file: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f, 'application/jsonl')}
        data = {'purpose': 'batch'}
        
        response = requests.post(f"{BASE_URL}/v1/files", files=files, data=data)
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    file_id = result['id']
    print(f"✅ File uploaded: {file_id}")
    print(f"   Filename: {result['filename']}")
    print(f"   Bytes: {result['bytes']}")
    return file_id

def create_batch(file_id: str) -> str:
    """Create batch job"""
    print(f"\n🚀 Creating batch job...")
    
    payload = {
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
    
    response = requests.post(
        f"{BASE_URL}/v1/batches",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 201:
        print(f"❌ Batch creation failed: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    batch_id = result['id']
    print(f"✅ Batch created: {batch_id}")
    print(f"   Status: {result['status']}")
    print(f"   Input file: {result['input_file_id']}")
    return batch_id

def poll_batch_status(batch_id: str, max_wait_seconds: int = 300) -> Dict[str, Any]:
    """Poll batch status until completion or timeout"""
    print(f"\n⏳ Polling batch status (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    poll_count = 0
    
    while True:
        poll_count += 1
        elapsed = int(time.time() - start_time)
        
        response = requests.get(f"{BASE_URL}/v1/batches/{batch_id}")
        
        if response.status_code != 200:
            print(f"❌ Failed to get batch status: {response.status_code}")
            return None
        
        batch = response.json()
        status = batch['status']
        
        # Print progress
        request_counts = batch.get('request_counts', {})
        total = request_counts.get('total', 0)
        completed = request_counts.get('completed', 0)
        failed = request_counts.get('failed', 0)
        
        print(f"   [{elapsed}s] Poll #{poll_count}: {status} - {completed}/{total} completed, {failed} failed")
        
        # Check terminal states
        if status == 'completed':
            print(f"✅ Batch completed in {elapsed}s!")
            return batch
        elif status == 'failed':
            print(f"❌ Batch failed!")
            return batch
        elif status == 'cancelled':
            print(f"⚠️  Batch cancelled!")
            return batch
        
        # Check timeout
        if elapsed >= max_wait_seconds:
            print(f"⏱️  Timeout after {max_wait_seconds}s")
            return batch
        
        # Wait before next poll
        time.sleep(2)

def download_results(file_id: str) -> List[Dict[str, Any]]:
    """Download and parse batch results"""
    print(f"\n📥 Downloading results: {file_id}")
    
    response = requests.get(f"{BASE_URL}/v1/files/{file_id}/content")
    
    if response.status_code != 200:
        print(f"❌ Download failed: {response.status_code}")
        return None
    
    # Parse JSONL
    results = []
    for line in response.text.strip().split('\n'):
        if line:
            results.append(json.loads(line))
    
    print(f"✅ Downloaded {len(results)} results")
    return results

def verify_results(results: List[Dict[str, Any]]) -> bool:
    """Verify batch results"""
    print(f"\n🔍 Verifying results...")
    
    all_passed = True
    
    for i, result in enumerate(results, 1):
        custom_id = result.get('custom_id')
        error = result.get('error')
        response = result.get('response')
        
        if error:
            print(f"❌ Request {i} ({custom_id}): ERROR - {error.get('message')}")
            all_passed = False
            continue
        
        if not response or response.get('status_code') != 200:
            print(f"❌ Request {i} ({custom_id}): Bad response")
            all_passed = False
            continue
        
        body = response.get('body', {})
        choices = body.get('choices', [])
        
        if not choices:
            print(f"❌ Request {i} ({custom_id}): No choices in response")
            all_passed = False
            continue
        
        content = choices[0].get('message', {}).get('content', '')
        usage = body.get('usage', {})
        
        print(f"✅ Request {i} ({custom_id}):")
        print(f"   Response: {content[:100]}")
        print(f"   Tokens: {usage.get('prompt_tokens')} prompt + {usage.get('completion_tokens')} completion = {usage.get('total_tokens')} total")
    
    return all_passed

def main():
    print("=" * 80)
    print("Ollama Batch Server - End-to-End Test")
    print("=" * 80)
    
    try:
        # Step 1: Create batch file
        batch_file = create_batch_file(num_requests=5)
        
        # Step 2: Upload file
        file_id = upload_file(batch_file)
        if not file_id:
            return 1
        
        # Step 3: Create batch
        batch_id = create_batch(file_id)
        if not batch_id:
            return 1
        
        # Step 4: Poll for completion
        batch = poll_batch_status(batch_id, max_wait_seconds=300)
        if not batch:
            return 1
        
        # Step 5: Download results
        if batch['status'] != 'completed':
            print(f"\n❌ Batch did not complete successfully: {batch['status']}")
            return 1
        
        output_file_id = batch.get('output_file_id')
        if not output_file_id:
            print(f"\n❌ No output file ID in batch response")
            return 1
        
        results = download_results(output_file_id)
        if not results:
            return 1
        
        # Step 6: Verify results
        all_passed = verify_results(results)
        
        # Summary
        print("\n" + "=" * 80)
        if all_passed:
            print("✅ END-TO-END TEST PASSED!")
            print()
            print("📊 Summary:")
            print(f"   Batch ID: {batch_id}")
            print(f"   Total requests: {batch['request_counts']['total']}")
            print(f"   Completed: {batch['request_counts']['completed']}")
            print(f"   Failed: {batch['request_counts']['failed']}")
            print(f"   Output file: {output_file_id}")
            print()
            return 0
        else:
            print("❌ SOME RESULTS FAILED VERIFICATION")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if Path(batch_file).exists():
            Path(batch_file).unlink()
            print(f"\n🧹 Cleaned up: {batch_file}")

if __name__ == "__main__":
    sys.exit(main())

