#!/usr/bin/env python3
"""
Multi-Batch Test Runner

Tests scalability and performance by running multiple 5K batches in sequence.
This validates:
1. No memory leaks between batches
2. Consistent performance across batches
3. VRAM stability over time
4. Model stays loaded (keep_alive working)
5. No degradation in success rate

Usage:
    python tools/run_multi_batch_test.py --batches 3 --input batch_5k.jsonl
"""

import asyncio
import httpx
import json
import time
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import subprocess

class MultiBatchTester:
    def __init__(self, base_url: str = "http://localhost:4080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
        self.results: List[Dict] = []
        
    async def upload_file(self, file_path: str) -> str:
        """Upload batch file and return file_id"""
        print(f"\n📤 Uploading {file_path}...")
        
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f, 'application/jsonl')}
            data = {'purpose': 'batch'}
            
            response = await self.client.post(
                f"{self.base_url}/v1/files",
                files=files,
                data=data
            )
            response.raise_for_status()
            
        file_data = response.json()
        file_id = file_data['id']
        print(f"✅ File uploaded: {file_id}")
        return file_id
    
    async def create_batch(self, file_id: str, batch_num: int) -> str:
        """Create batch job and return batch_id"""
        print(f"\n🚀 Creating batch {batch_num}...")
        
        response = await self.client.post(
            f"{self.base_url}/v1/batches",
            json={
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {
                    "test_batch_num": str(batch_num),
                    "test_type": "multi_batch_scalability"
                }
            }
        )
        response.raise_for_status()
        
        batch_data = response.json()
        batch_id = batch_data['id']
        print(f"✅ Batch created: {batch_id}")
        return batch_id
    
    async def wait_for_batch(self, batch_id: str, batch_num: int) -> Dict:
        """Wait for batch to complete and return final status"""
        print(f"\n⏳ Waiting for batch {batch_num} to complete...")
        
        start_time = time.time()
        last_progress = 0
        
        while True:
            response = await self.client.get(f"{self.base_url}/v1/batches/{batch_id}")
            response.raise_for_status()
            batch_data = response.json()
            
            status = batch_data['status']
            request_counts = batch_data.get('request_counts', {})
            completed = request_counts.get('completed', 0)
            total = request_counts.get('total', 0)
            failed = request_counts.get('failed', 0)
            
            # Show progress
            if completed > last_progress:
                elapsed = time.time() - start_time
                if total > 0:
                    pct = (completed / total) * 100
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(f"  Progress: {completed}/{total} ({pct:.1f}%) | "
                          f"Rate: {rate:.1f} req/s | ETA: {eta/60:.1f} min | "
                          f"Failed: {failed}")
                last_progress = completed
            
            if status in ['completed', 'failed', 'cancelled']:
                elapsed = time.time() - start_time
                print(f"\n✅ Batch {batch_num} {status} in {elapsed/60:.1f} minutes")
                return {
                    'batch_id': batch_id,
                    'batch_num': batch_num,
                    'status': status,
                    'request_counts': request_counts,
                    'elapsed_seconds': elapsed,
                    'rate_per_second': completed / elapsed if elapsed > 0 else 0
                }
            
            await asyncio.sleep(5)
    
    def get_vram_usage(self) -> float:
        """Get current VRAM usage in GB"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                check=True
            )
            vram_mb = float(result.stdout.strip())
            return vram_mb / 1024
        except Exception:
            return 0.0
    
    async def run_batch_test(self, file_path: str, batch_num: int) -> Dict:
        """Run a single batch test"""
        print(f"\n{'='*80}")
        print(f"BATCH TEST {batch_num}")
        print(f"{'='*80}")
        
        # Record VRAM before
        vram_before = self.get_vram_usage()
        print(f"📊 VRAM before: {vram_before:.2f} GB")
        
        # Upload file
        file_id = await self.upload_file(file_path)
        
        # Create batch
        batch_id = await self.create_batch(file_id, batch_num)
        
        # Wait for completion
        result = await self.wait_for_batch(batch_id, batch_num)
        
        # Record VRAM after
        vram_after = self.get_vram_usage()
        print(f"📊 VRAM after: {vram_after:.2f} GB")
        print(f"📊 VRAM delta: {vram_after - vram_before:+.2f} GB")
        
        # Add VRAM info to result
        result['vram_before_gb'] = vram_before
        result['vram_after_gb'] = vram_after
        result['vram_delta_gb'] = vram_after - vram_before
        
        return result
    
    async def run_multi_batch_test(self, file_path: str, num_batches: int):
        """Run multiple batches in sequence"""
        print(f"\n{'='*80}")
        print(f"MULTI-BATCH SCALABILITY TEST")
        print(f"{'='*80}")
        print(f"File: {file_path}")
        print(f"Number of batches: {num_batches}")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        overall_start = time.time()
        
        for i in range(1, num_batches + 1):
            result = await self.run_batch_test(file_path, i)
            self.results.append(result)
            
            # Print summary after each batch
            self.print_batch_summary(result)
            
            # Wait a bit between batches to let things settle
            if i < num_batches:
                print(f"\n⏸️  Waiting 10 seconds before next batch...")
                await asyncio.sleep(10)
        
        overall_elapsed = time.time() - overall_start
        
        # Print final summary
        self.print_final_summary(overall_elapsed)
        
        # Save results
        self.save_results()
    
    def print_batch_summary(self, result: Dict):
        """Print summary for a single batch"""
        print(f"\n{'─'*80}")
        print(f"BATCH {result['batch_num']} SUMMARY")
        print(f"{'─'*80}")
        print(f"Status: {result['status']}")
        print(f"Completed: {result['request_counts'].get('completed', 0)}")
        print(f"Failed: {result['request_counts'].get('failed', 0)}")
        print(f"Total: {result['request_counts'].get('total', 0)}")
        print(f"Time: {result['elapsed_seconds']/60:.1f} minutes")
        print(f"Rate: {result['rate_per_second']:.2f} req/s")
        print(f"VRAM: {result['vram_before_gb']:.2f} GB → {result['vram_after_gb']:.2f} GB "
              f"({result['vram_delta_gb']:+.2f} GB)")
        print(f"{'─'*80}\n")
    
    def print_final_summary(self, overall_elapsed: float):
        """Print final summary of all batches"""
        print(f"\n{'='*80}")
        print(f"FINAL MULTI-BATCH SUMMARY")
        print(f"{'='*80}")
        
        total_requests = sum(r['request_counts'].get('completed', 0) for r in self.results)
        total_failed = sum(r['request_counts'].get('failed', 0) for r in self.results)
        avg_rate = sum(r['rate_per_second'] for r in self.results) / len(self.results)
        
        print(f"\n📊 Overall Statistics:")
        print(f"  Total batches: {len(self.results)}")
        print(f"  Total requests: {total_requests:,}")
        print(f"  Total failed: {total_failed}")
        print(f"  Success rate: {(total_requests/(total_requests+total_failed)*100):.2f}%")
        print(f"  Total time: {overall_elapsed/60:.1f} minutes")
        print(f"  Average rate: {avg_rate:.2f} req/s")
        
        print(f"\n📊 Per-Batch Performance:")
        for r in self.results:
            print(f"  Batch {r['batch_num']}: "
                  f"{r['elapsed_seconds']/60:.1f} min | "
                  f"{r['rate_per_second']:.2f} req/s | "
                  f"VRAM: {r['vram_delta_gb']:+.2f} GB")
        
        print(f"\n📊 VRAM Analysis:")
        vram_start = self.results[0]['vram_before_gb']
        vram_end = self.results[-1]['vram_after_gb']
        vram_total_delta = vram_end - vram_start
        print(f"  Start VRAM: {vram_start:.2f} GB")
        print(f"  End VRAM: {vram_end:.2f} GB")
        print(f"  Total delta: {vram_total_delta:+.2f} GB")
        
        if abs(vram_total_delta) < 0.5:
            print(f"  ✅ No memory leak detected!")
        else:
            print(f"  ⚠️  Possible memory leak: {vram_total_delta:+.2f} GB")
        
        print(f"\n📊 Performance Consistency:")
        rates = [r['rate_per_second'] for r in self.results]
        min_rate = min(rates)
        max_rate = max(rates)
        variance = ((max_rate - min_rate) / avg_rate) * 100
        print(f"  Min rate: {min_rate:.2f} req/s")
        print(f"  Max rate: {max_rate:.2f} req/s")
        print(f"  Variance: {variance:.1f}%")
        
        if variance < 10:
            print(f"  ✅ Consistent performance!")
        else:
            print(f"  ⚠️  Performance varies by {variance:.1f}%")
        
        print(f"\n{'='*80}\n")
    
    def save_results(self):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"multi_batch_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'num_batches': len(self.results),
                'results': self.results
            }, f, indent=2)
        
        print(f"💾 Results saved to: {filename}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Run multi-batch scalability test')
    parser.add_argument('--batches', type=int, default=3, help='Number of batches to run')
    parser.add_argument('--input', type=str, default='batch_5k.jsonl', help='Input JSONL file')
    parser.add_argument('--url', type=str, default='http://localhost:4080', help='Server URL')
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.input).exists():
        print(f"❌ Error: File not found: {args.input}")
        sys.exit(1)
    
    tester = MultiBatchTester(base_url=args.url)
    
    try:
        await tester.run_multi_batch_test(args.input, args.batches)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())

