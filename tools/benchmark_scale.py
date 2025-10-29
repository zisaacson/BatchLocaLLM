#!/usr/bin/env python3
"""
Scalability benchmark - test with increasing batch sizes

Tests: 100, 500, 1000 requests to validate performance at scale
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.models import BatchRequestLine, ChatCompletionBody, ChatMessage
from src.config import settings


async def create_test_batch(size: int):
    """Create test batch of given size"""
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
                        content=f"What is {i} + {i}? Just give the number."
                    )
                ],
                temperature=0.7,
                max_tokens=50,
            )
        )
        requests.append(req)
    return requests


async def main():
    print("=" * 80)
    print("SCALABILITY BENCHMARK")
    print("=" * 80)
    
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
    
    # Test with optimal worker count (4 workers based on previous benchmark)
    num_workers = 4
    
    # Test sizes
    test_sizes = [100, 500, 1000]
    
    results_summary = []
    
    for size in test_sizes:
        print(f"\n{'='*80}")
        print(f"BENCHMARK: {size} requests with {num_workers} workers")
        print(f"{'='*80}")
        
        # Create test batch
        print(f"Creating {size} test requests...")
        requests = await create_test_batch(size)
        print(f"✅ Created {size} requests")
        
        # Create processor
        processor = ParallelBatchProcessor(
            backend=backend,
            config=WorkerConfig(
                num_workers=num_workers,
                retry_attempts=3,
            )
        )
        
        # Process batch
        start = time.time()
        results = await processor.process_batch(requests)
        elapsed = time.time() - start
        
        # Analyze
        success_count = sum(1 for r in results if r.error is None)
        fail_count = sum(1 for r in results if r.error is not None)
        rate = len(results) / elapsed if elapsed > 0 else 0
        
        result_data = {
            'size': size,
            'workers': num_workers,
            'success': success_count,
            'failed': fail_count,
            'time_seconds': elapsed,
            'time_minutes': elapsed / 60,
            'rate': rate,
            'speedup': rate / 0.20,
        }
        results_summary.append(result_data)
        
        print(f"\n{'='*80}")
        print(f"RESULTS FOR {size} REQUESTS:")
        print(f"{'='*80}")
        print(f"Success:  {success_count}/{size} ({success_count/size*100:.1f}%)")
        print(f"Failed:   {fail_count}")
        print(f"Time:     {elapsed:.1f}s ({elapsed/60:.2f} minutes)")
        print(f"Rate:     {rate:.2f} req/s")
        print(f"Speedup:  {rate/0.20:.1f}x vs baseline")
    
    # Final summary
    print(f"\n{'='*80}")
    print("SCALABILITY SUMMARY")
    print(f"{'='*80}")
    print(f"{'Size':<10} {'Time':<15} {'Rate':<15} {'Speedup':<10}")
    print("-" * 80)
    for r in results_summary:
        print(f"{r['size']:<10} {r['time_minutes']:<15.2f} {r['rate']:<15.2f} {r['speedup']:<10.1f}x")
    
    # Extrapolate to 170K
    avg_rate = sum(r['rate'] for r in results_summary) / len(results_summary)
    time_170k_seconds = 170000 / avg_rate
    time_170k_hours = time_170k_seconds / 3600
    
    print(f"\n{'='*80}")
    print("EXTRAPOLATION TO 170K REQUESTS")
    print(f"{'='*80}")
    print(f"Average rate:     {avg_rate:.2f} req/s")
    print(f"Estimated time:   {time_170k_hours:.1f} hours ({time_170k_hours/24:.2f} days)")
    print(f"Old estimate:     236 hours (10 days)")
    print(f"Improvement:      {236/time_170k_hours:.1f}x faster!")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

