#!/usr/bin/env python3
"""
Test parallel batch processing

Quick test to validate parallel processing works correctly.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.models import BatchRequestLine, ChatCompletionBody, ChatMessage
from src.config import settings


async def main():
    print("=" * 80)
    print("PARALLEL PROCESSING TEST")
    print("=" * 80)
    
    # Initialize backend
    print("\n1. Initializing Ollama backend...")
    backend = OllamaBackend(base_url=settings.ollama_base_url)
    
    # Health check
    healthy = await backend.health_check()
    if not healthy:
        print("❌ Ollama server not running!")
        sys.exit(1)
    
    print("✅ Ollama server healthy")
    
    # Load model
    print(f"\n2. Loading model: {settings.model_name}...")
    await backend.load_model(settings.model_name)
    print("✅ Model loaded")
    
    # Create test requests
    num_requests = 20  # Start small
    print(f"\n3. Creating {num_requests} test requests...")
    
    requests = []
    for i in range(num_requests):
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
    
    print(f"✅ Created {len(requests)} requests")
    
    # Test with different worker counts
    for num_workers in [1, 2, 4, 8]:
        print(f"\n{'='*80}")
        print(f"TEST: {num_workers} workers")
        print(f"{'='*80}")
        
        # Create processor
        processor = ParallelBatchProcessor(
            backend=backend,
            config=WorkerConfig(
                num_workers=num_workers,
                retry_attempts=2,
            )
        )
        
        # Process batch
        import time
        start = time.time()
        results = await processor.process_batch(requests)
        elapsed = time.time() - start
        
        # Analyze results
        success_count = sum(1 for r in results if r.error is None)
        fail_count = sum(1 for r in results if r.error is not None)
        rate = len(results) / elapsed if elapsed > 0 else 0
        
        print(f"\nRESULTS:")
        print(f"  Total: {len(results)}")
        print(f"  Success: {success_count}")
        print(f"  Failed: {fail_count}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Rate: {rate:.2f} req/s")
        print(f"  Speedup: {rate/0.20:.1f}x vs baseline (0.20 req/s)")
        
        # Show sample responses
        print(f"\nSAMPLE RESPONSES:")
        for i, result in enumerate(results[:3]):
            if result.error is None:
                response_body = result.response.get('body', {})
                choices = response_body.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', 'N/A')
                    print(f"  Request {i}: {content[:100]}")
            else:
                print(f"  Request {i}: ERROR - {result.error.message}")
    
    print(f"\n{'='*80}")
    print("✅ PARALLEL PROCESSING TEST COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

