#!/usr/bin/env python3
"""
Run batch processing from JSONL file (skip CSV conversion)

Usage:
    python run_batch_jsonl.py batch_requests.jsonl

This script:
1. Uploads batch JSONL file
2. Creates batch job
3. Monitors progress
4. Downloads results
5. Analyzes results
"""

import sys
import time
import json
import httpx
from pathlib import Path

# Server configuration
SERVER_URL = "http://localhost:4080"

def upload_file(jsonl_file: str) -> str:
    """Upload batch file to server"""
    print(f"\n{'='*80}")
    print("STEP 1: Upload Batch File")
    print(f"{'='*80}")
    
    with open(jsonl_file, 'rb') as f:
        response = httpx.post(
            f"{SERVER_URL}/v1/files",
            files={"file": (Path(jsonl_file).name, f, "application/jsonl")},
            data={"purpose": "batch"},
            timeout=60.0
        )
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        sys.exit(1)
    
    file_data = response.json()
    file_id = file_data['id']
    
    print(f"✅ File uploaded successfully")
    print(f"   File ID: {file_id}")
    print(f"   Filename: {file_data['filename']}")
    print(f"   Size: {file_data['bytes']:,} bytes")
    
    return file_id

def create_batch(file_id: str) -> str:
    """Create batch processing job"""
    print(f"\n{'='*80}")
    print("STEP 2: Create Batch Job")
    print(f"{'='*80}")

    response = httpx.post(
        f"{SERVER_URL}/v1/batches",
        json={
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        },
        timeout=30.0
    )

    if response.status_code not in [200, 201]:
        print(f"❌ Batch creation failed (HTTP {response.status_code}): {response.text}")
        sys.exit(1)

    batch_data = response.json()
    batch_id = batch_data.get('id')

    if not batch_id:
        print(f"❌ No batch ID in response: {response.text}")
        sys.exit(1)

    print(f"✅ Batch job created successfully")
    print(f"   Batch ID: {batch_id}")
    print(f"   Status: {batch_data.get('status', 'unknown')}")

    return batch_id

def monitor_batch(batch_id: str) -> dict:
    """Monitor batch progress until completion"""
    print(f"\n{'='*80}")
    print("STEP 3: Monitor Batch Progress")
    print(f"{'='*80}")
    
    start_time = time.time()
    last_status = None
    
    while True:
        response = httpx.get(
            f"{SERVER_URL}/v1/batches/{batch_id}",
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ Status check failed: {response.text}")
            sys.exit(1)
        
        batch_data = response.json()
        status = batch_data['status']
        
        # Print status update if changed
        if status != last_status:
            elapsed = time.time() - start_time
            print(f"\n[{elapsed:.1f}s] Status: {status}")
            
            if status == 'in_progress':
                counts = batch_data.get('request_counts', {})
                total = counts.get('total', 0)
                completed = counts.get('completed', 0)
                failed = counts.get('failed', 0)
                
                if total > 0:
                    progress_pct = (completed + failed) / total * 100
                    print(f"   Progress: {completed + failed}/{total} ({progress_pct:.1f}%)")
                    print(f"   Completed: {completed}, Failed: {failed}")
            
            last_status = status
        
        # Check if done
        if status in ['completed', 'failed', 'cancelled']:
            elapsed = time.time() - start_time
            print(f"\n✅ Batch {status} in {elapsed:.1f}s")
            
            counts = batch_data.get('request_counts', {})
            print(f"   Total: {counts.get('total', 0)}")
            print(f"   Completed: {counts.get('completed', 0)}")
            print(f"   Failed: {counts.get('failed', 0)}")
            
            return batch_data
        
        # Wait before next check
        time.sleep(2)

def download_results(batch_data: dict, output_file: str):
    """Download batch results"""
    print(f"\n{'='*80}")
    print("STEP 4: Download Results")
    print(f"{'='*80}")
    
    output_file_id = batch_data.get('output_file_id')
    if not output_file_id:
        print("❌ No output file available")
        sys.exit(1)
    
    response = httpx.get(
        f"{SERVER_URL}/v1/files/{output_file_id}/content",
        timeout=60.0
    )
    
    if response.status_code != 200:
        print(f"❌ Download failed: {response.text}")
        sys.exit(1)
    
    # Save results
    with open(output_file, 'wb') as f:
        f.write(response.content)
    
    print(f"✅ Results downloaded")
    print(f"   Output file: {output_file}")
    print(f"   Size: {len(response.content):,} bytes")

def analyze_results(results_file: str):
    """Analyze batch results"""
    print(f"\n{'='*80}")
    print("STEP 5: Analyze Results")
    print(f"{'='*80}")
    
    # Read results
    results = []
    with open(results_file, 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    
    # Count successes and failures
    successes = sum(1 for r in results if r.get('error') is None)
    failures = sum(1 for r in results if r.get('error') is not None)
    
    print(f"\n📊 Results Summary:")
    print(f"   Total: {len(results)}")
    print(f"   Successes: {successes} ({successes/len(results)*100:.1f}%)")
    print(f"   Failures: {failures} ({failures/len(results)*100:.1f}%)")
    
    # Show sample results
    if successes > 0:
        print(f"\n✅ Sample Success:")
        for r in results:
            if r.get('error') is None:
                response_body = r.get('response', {}).get('body', {})
                content = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(content)
                    print(f"   Custom ID: {r.get('custom_id')}")
                    print(f"   Recommendation: {parsed.get('recommendation', 'N/A')}")
                    print(f"   Reasoning: {parsed.get('reasoning', 'N/A')[:100]}...")
                except:
                    print(f"   Custom ID: {r.get('custom_id')}")
                    print(f"   Content: {content[:200]}...")
                break
    
    if failures > 0:
        print(f"\n❌ Sample Failure:")
        for r in results:
            if r.get('error') is not None:
                error = r.get('error', {})
                print(f"   Custom ID: {r.get('custom_id')}")
                print(f"   Error: {error.get('message', 'Unknown error')}")
                break
    
    # Token usage
    total_prompt_tokens = 0
    total_completion_tokens = 0
    
    for r in results:
        if r.get('error') is None:
            usage = r.get('response', {}).get('body', {}).get('usage', {})
            total_prompt_tokens += usage.get('prompt_tokens', 0)
            total_completion_tokens += usage.get('completion_tokens', 0)
    
    if total_prompt_tokens > 0:
        print(f"\n📊 Token Usage:")
        print(f"   Prompt tokens: {total_prompt_tokens:,}")
        print(f"   Completion tokens: {total_completion_tokens:,}")
        print(f"   Total tokens: {total_prompt_tokens + total_completion_tokens:,}")
        print(f"   Avg per request: {(total_prompt_tokens + total_completion_tokens) / successes:.0f}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_batch_jsonl.py batch_requests.jsonl")
        print()
        print("Example:")
        print("  python run_batch_jsonl.py test_batch_10.jsonl")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    
    # Validate input file exists
    if not Path(jsonl_file).exists():
        print(f"❌ Error: Input file not found: {jsonl_file}")
        sys.exit(1)
    
    # Derive output filename
    base_name = Path(jsonl_file).stem
    results_file = f"{base_name}_results.jsonl"
    
    print(f"{'='*80}")
    print("BATCH PROCESSING WORKFLOW (JSONL)")
    print(f"{'='*80}")
    print(f"Input JSONL: {jsonl_file}")
    print(f"Results JSONL: {results_file}")
    
    # Run workflow
    file_id = upload_file(jsonl_file)
    batch_id = create_batch(file_id)
    batch_data = monitor_batch(batch_id)
    download_results(batch_data, results_file)
    analyze_results(results_file)
    
    print(f"\n{'='*80}")
    print("✅ WORKFLOW COMPLETE")
    print(f"{'='*80}")
    print(f"Results saved to: {results_file}")

if __name__ == "__main__":
    main()

