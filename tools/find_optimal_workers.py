#!/usr/bin/env python3
"""
Find optimal worker count for large batches

Tests different worker counts on 1K, 5K, 10K batches to find the sweet spot.
"""

import asyncio
import json
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.models import BatchRequestLine, ChatCompletionBody, ChatMessage
from src.config import settings


def get_vram_usage():
    """Get current VRAM usage in GB"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True
        )
        vram_mb = float(result.stdout.strip())
        return vram_mb / 1024  # Convert to GB
    except:
        return 0.0


async def create_test_batch(size: int):
    """Create test batch"""
    requests = []
    for i in range(size):
        req = BatchRequestLine(
            custom_id=f"test-{i}",
            method="POST",
            url="/v1/chat/completions",
            body=ChatCompletionBody(
                model=settings.model_name,
                messages=[
                    ChatMessage(
                        role="system",
                        content="You are a helpful assistant. Give very brief responses (1-2 sentences)."
                    ),
                    ChatMessage(
                        role="user",
                        content=f"What is {i % 100}? Just give a brief answer."
                    )
                ],
                temperature=0.7,
                max_tokens=50,
            )
        )
        requests.append(req)
    return requests


async def benchmark_config(backend, batch_size, num_workers):
    """Benchmark a specific configuration"""
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {batch_size} requests, {num_workers} workers")
    print(f"{'='*80}")
    
    # Create test batch
    requests = await create_test_batch(batch_size)
    
    # Create processor
    processor = ParallelBatchProcessor(
        backend=backend,
        config=WorkerConfig(
            num_workers=num_workers,
            retry_attempts=2,
        )
    )
    
    # Measure VRAM before
    vram_before = get_vram_usage()
    
    # Process batch
    start = time.time()
    results = await processor.process_batch(requests)
    elapsed = time.time() - start
    
    # Measure VRAM after
    vram_after = get_vram_usage()
    
    # Analyze
    success_count = sum(1 for r in results if r.error is None)
    fail_count = sum(1 for r in results if r.error is not None)
    rate = len(results) / elapsed if elapsed > 0 else 0
    
    result = {
        'batch_size': batch_size,
        'num_workers': num_workers,
        'success': success_count,
        'failed': fail_count,
        'time_seconds': elapsed,
        'time_minutes': elapsed / 60,
        'rate': rate,
        'vram_before_gb': vram_before,
        'vram_after_gb': vram_after,
        'vram_delta_gb': vram_after - vram_before,
    }
    
    print(f"\nRESULTS:")
    print(f"  Success:      {success_count}/{batch_size} ({success_count/batch_size*100:.1f}%)")
    print(f"  Time:         {elapsed:.1f}s ({elapsed/60:.2f} min)")
    print(f"  Rate:         {rate:.2f} req/s")
    print(f"  VRAM:         {vram_after:.2f} GB (Δ {vram_after - vram_before:+.2f} GB)")
    
    return result


async def main():
    print("=" * 80)
    print("WORKER OPTIMIZATION BENCHMARK")
    print("=" * 80)
    print("\nGoal: Find optimal worker count for 50K batches")
    print("Strategy: Test 1K, 5K, 10K with different worker counts")
    
    # Initialize backend
    print("\nInitializing Ollama backend...")
    backend = OllamaBackend(base_url=settings.ollama_base_url)
    
    healthy = await backend.health_check()
    if not healthy:
        print("❌ Ollama server not running!")
        sys.exit(1)
    
    print("✅ Ollama server healthy")
    await backend.load_model(settings.model_name)
    print(f"✅ Model loaded: {settings.model_name}")
    
    # Test configurations
    batch_sizes = [1000, 5000, 10000]
    worker_counts = [2, 4, 8, 16, 32]
    
    all_results = []
    
    for batch_size in batch_sizes:
        print(f"\n{'#'*80}")
        print(f"# TESTING BATCH SIZE: {batch_size}")
        print(f"{'#'*80}")
        
        batch_results = []
        
        for num_workers in worker_counts:
            result = await benchmark_config(backend, batch_size, num_workers)
            batch_results.append(result)
            all_results.append(result)
            
            # Short pause between tests
            await asyncio.sleep(2)
        
        # Summary for this batch size
        print(f"\n{'='*80}")
        print(f"SUMMARY FOR {batch_size} REQUESTS:")
        print(f"{'='*80}")
        print(f"{'Workers':<10} {'Time (min)':<12} {'Rate (req/s)':<15} {'VRAM (GB)':<12}")
        print("-" * 80)
        
        best_rate = 0
        best_workers = 0
        
        for r in batch_results:
            print(f"{r['num_workers']:<10} {r['time_minutes']:<12.2f} {r['rate']:<15.2f} {r['vram_after_gb']:<12.2f}")
            if r['rate'] > best_rate:
                best_rate = r['rate']
                best_workers = r['num_workers']
        
        print(f"\n✅ BEST for {batch_size}: {best_workers} workers @ {best_rate:.2f} req/s")
    
    # Final analysis
    print(f"\n{'#'*80}")
    print("# FINAL ANALYSIS")
    print(f"{'#'*80}")
    
    # Find overall best configuration
    best_overall = max(all_results, key=lambda x: x['rate'])
    
    print(f"\n🏆 OPTIMAL CONFIGURATION:")
    print(f"   Workers:      {best_overall['num_workers']}")
    print(f"   Rate:         {best_overall['rate']:.2f} req/s")
    print(f"   Tested on:    {best_overall['batch_size']} requests")
    
    # Extrapolate to 50K and 170K
    rate = best_overall['rate']
    
    time_50k_seconds = 50000 / rate
    time_50k_minutes = time_50k_seconds / 60
    time_50k_hours = time_50k_minutes / 60
    
    time_170k_seconds = 170000 / rate
    time_170k_minutes = time_170k_seconds / 60
    time_170k_hours = time_170k_minutes / 60
    
    print(f"\n📊 EXTRAPOLATIONS:")
    print(f"   50K batch:    {time_50k_minutes:.1f} minutes ({time_50k_hours:.2f} hours)")
    print(f"   170K batch:   {time_170k_minutes:.1f} minutes ({time_170k_hours:.2f} hours)")
    
    # Compare to old estimate
    old_time_170k_hours = 236
    speedup = old_time_170k_hours / time_170k_hours
    
    print(f"\n🚀 IMPROVEMENT:")
    print(f"   Old estimate: {old_time_170k_hours} hours (10 days)")
    print(f"   New estimate: {time_170k_hours:.1f} hours ({time_170k_hours/24:.2f} days)")
    print(f"   Speedup:      {speedup:.1f}x faster!")
    
    # Save results
    output_file = Path("worker_optimization_results.json")
    with open(output_file, 'w') as f:
        json.dump({
            'all_results': all_results,
            'optimal_config': {
                'workers': best_overall['num_workers'],
                'rate': best_overall['rate'],
                'batch_size_tested': best_overall['batch_size'],
            },
            'extrapolations': {
                '50k_minutes': time_50k_minutes,
                '50k_hours': time_50k_hours,
                '170k_minutes': time_170k_minutes,
                '170k_hours': time_170k_hours,
                'speedup_vs_old': speedup,
            }
        }, f, indent=2)
    
    print(f"\n✅ Results saved to {output_file}")
    print(f"\n{'='*80}")
    print("BENCHMARK COMPLETE!")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

