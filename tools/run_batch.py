#!/usr/bin/env python3
"""
End-to-end batch processing workflow

Usage:
    python run_batch.py candidates.csv

This script:
1. Converts CSV to batch JSONL
2. Uploads batch file
3. Creates batch job
4. Monitors progress
5. Downloads results
6. Analyzes results
7. Exports to CSV
"""

import sys
import time
import json
import httpx
from pathlib import Path

# Server configuration
SERVER_URL = "http://localhost:4080"

def convert_csv_to_batch(csv_file: str, jsonl_file: str):
    """Convert CSV to batch JSONL"""
    print(f"\n{'='*80}")
    print("STEP 1: Convert CSV to Batch JSONL")
    print(f"{'='*80}")
    
    import subprocess
    result = subprocess.run([
        'python', 'tools/csv_to_batch.py',
        csv_file, jsonl_file
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)

def upload_file(jsonl_file: str) -> str:
    """Upload batch file to server"""
    print(f"\n{'='*80}")
    print("STEP 2: Upload Batch File")
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
    print("STEP 3: Create Batch Job")
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
    
    if response.status_code != 201:
        print(f"❌ Batch creation failed: {response.text}")
        sys.exit(1)
    
    batch_data = response.json()
    batch_id = batch_data['id']
    
    print(f"✅ Batch job created successfully")
    print(f"   Batch ID: {batch_id}")
    print(f"   Status: {batch_data['status']}")
    print(f"   Total requests: {batch_data['request_counts']['total']:,}")
    
    return batch_id

def monitor_progress(batch_id: str) -> dict:
    """Monitor batch progress until completion"""
    print(f"\n{'='*80}")
    print("STEP 4: Monitor Progress")
    print(f"{'='*80}")
    
    start_time = time.time()
    last_completed = 0
    
    while True:
        response = httpx.get(
            f"{SERVER_URL}/v1/batches/{batch_id}",
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ Status check failed: {response.text}")
            time.sleep(5)
            continue
        
        batch_data = response.json()
        status = batch_data['status']
        counts = batch_data['request_counts']
        
        # Calculate progress
        total = counts['total']
        completed = counts['completed']
        failed = counts['failed']
        progress_pct = (completed / total * 100) if total > 0 else 0
        
        # Calculate throughput
        elapsed = time.time() - start_time
        throughput = completed / elapsed if elapsed > 0 else 0
        
        # Calculate ETA
        remaining = total - completed
        eta_sec = remaining / throughput if throughput > 0 else 0
        eta_min = eta_sec / 60
        eta_hours = eta_min / 60
        
        # Print progress
        print(f"\r   Status: {status:12} | "
              f"Progress: {completed:,}/{total:,} ({progress_pct:5.1f}%) | "
              f"Failed: {failed:,} | "
              f"Throughput: {throughput:5.2f} req/s | "
              f"ETA: {eta_min:5.1f}m", end='', flush=True)
        
        # Check if completed
        if status in ['completed', 'failed', 'cancelled']:
            print()  # New line after progress
            break
        
        # Log milestone updates
        if completed > 0 and completed % 1000 == 0 and completed != last_completed:
            print()  # New line for milestone
            print(f"   ✅ Milestone: {completed:,} requests completed")
            last_completed = completed
        
        time.sleep(2)  # Poll every 2 seconds
    
    # Final summary
    elapsed_min = elapsed / 60
    elapsed_hours = elapsed_min / 60
    
    print(f"\n✅ Batch processing complete!")
    print(f"   Status: {status}")
    print(f"   Completed: {completed:,}/{total:,}")
    print(f"   Failed: {failed:,}")
    print(f"   Success rate: {(completed/total*100):.2f}%")
    print(f"   Total time: {elapsed_min:.1f} minutes ({elapsed_hours:.2f} hours)")
    print(f"   Avg throughput: {throughput:.2f} req/s")
    
    return batch_data

def download_results(batch_data: dict, output_file: str):
    """Download batch results"""
    print(f"\n{'='*80}")
    print("STEP 5: Download Results")
    print(f"{'='*80}")
    
    output_file_id = batch_data.get('output_file_id')
    if not output_file_id:
        print(f"❌ No output file available")
        sys.exit(1)
    
    response = httpx.get(
        f"{SERVER_URL}/v1/files/{output_file_id}/content",
        timeout=60.0
    )
    
    if response.status_code != 200:
        print(f"❌ Download failed: {response.text}")
        sys.exit(1)
    
    # Save results
    with open(output_file, 'w') as f:
        f.write(response.text)
    
    # Count lines
    num_results = len(response.text.strip().split('\n'))
    
    print(f"✅ Results downloaded successfully")
    print(f"   Output file: {output_file}")
    print(f"   Results: {num_results:,}")

def analyze_results(results_file: str, csv_file: str):
    """Analyze batch results"""
    print(f"\n{'='*80}")
    print("STEP 6: Analyze Results")
    print(f"{'='*80}")
    
    import subprocess
    result = subprocess.run([
        'python', 'tools/analyze_results.py',
        results_file, csv_file
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_batch.py candidates.csv")
        print()
        print("This script will:")
        print("  1. Convert CSV to batch JSONL")
        print("  2. Upload batch file")
        print("  3. Create batch job")
        print("  4. Monitor progress")
        print("  5. Download results")
        print("  6. Analyze results")
        print("  7. Export to CSV")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Generate filenames
    base_name = Path(csv_file).stem
    jsonl_file = f"{base_name}_batch.jsonl"
    results_file = f"{base_name}_results.jsonl"
    output_csv = f"{base_name}_scores.csv"
    
    print(f"{'='*80}")
    print("BATCH PROCESSING WORKFLOW")
    print(f"{'='*80}")
    print(f"Input CSV: {csv_file}")
    print(f"Batch JSONL: {jsonl_file}")
    print(f"Results JSONL: {results_file}")
    print(f"Output CSV: {output_csv}")
    
    try:
        # Step 1: Convert CSV to batch JSONL
        convert_csv_to_batch(csv_file, jsonl_file)
        
        # Step 2: Upload file
        file_id = upload_file(jsonl_file)
        
        # Step 3: Create batch
        batch_id = create_batch(file_id)
        
        # Step 4: Monitor progress
        batch_data = monitor_progress(batch_id)
        
        # Step 5: Download results
        download_results(batch_data, results_file)
        
        # Step 6: Analyze results
        analyze_results(results_file, output_csv)
        
        print(f"\n{'='*80}")
        print("✅ WORKFLOW COMPLETE!")
        print(f"{'='*80}")
        print(f"Results saved to: {output_csv}")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Workflow interrupted by user")
        print(f"   Batch ID: {batch_id if 'batch_id' in locals() else 'N/A'}")
        print(f"   You can check status with:")
        print(f"   curl {SERVER_URL}/v1/batches/{batch_id if 'batch_id' in locals() else '<batch_id>'}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

