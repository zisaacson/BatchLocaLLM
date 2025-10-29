#!/usr/bin/env python3
"""
Test smaller model (llama3.2:3b) for speed vs quality

Compare:
- gemma3:12b (current) - 1.3 req/s
- llama3.2:3b - ??? req/s

Goal: See if we can get 3-4x speedup with acceptable quality
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.models import BatchRequestLine, ChatCompletionBody, ChatMessage


async def create_test_batch(size: int, model: str):
    """Create test batch"""
    requests = []
    
    # Use realistic Aris-style prompts
    system_prompt = """You are an expert AI assistant helping evaluate job candidates. 
Analyze the candidate's background and provide a brief assessment of their fit for the role."""
    
    for i in range(size):
        user_prompt = f"""Candidate {i}:
- Experience: {5 + (i % 10)} years in software engineering
- Skills: Python, JavaScript, React, Node.js
- Education: BS Computer Science
- Previous roles: Senior Engineer at Tech Corp

Assess this candidate's qualifications and potential fit."""
        
        req = BatchRequestLine(
            custom_id=f"test-{i}",
            method="POST",
            url="/v1/chat/completions",
            body=ChatCompletionBody(
                model=model,
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt)
                ],
                temperature=0.7,
                max_tokens=300,
            )
        )
        requests.append(req)
    return requests


async def benchmark_model(model: str, num_requests: int = 100):
    """Benchmark a specific model"""
    print(f"\n{'='*80}")
    print(f"BENCHMARKING: {model}")
    print(f"{'='*80}")
    
    # Initialize backend
    backend = OllamaBackend(base_url="http://localhost:11434")
    
    # Load model
    print(f"Loading model: {model}...")
    await backend.load_model(model)
    print(f"✅ Model loaded")
    
    # Create test batch
    print(f"Creating {num_requests} test requests...")
    requests = await create_test_batch(num_requests, model)
    
    # Test with 4 workers (optimal from previous tests)
    processor = ParallelBatchProcessor(
        backend=backend,
        config=WorkerConfig(num_workers=4, retry_attempts=2)
    )
    
    # Benchmark
    print(f"\nProcessing {num_requests} requests with 4 workers...")
    start = time.time()
    results = await processor.process_batch(requests)
    elapsed = time.time() - start
    
    # Analyze
    success_count = sum(1 for r in results if r.error is None)
    rate = len(results) / elapsed if elapsed > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"RESULTS FOR {model}:")
    print(f"{'='*80}")
    print(f"Requests:     {num_requests}")
    print(f"Success:      {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
    print(f"Time:         {elapsed:.1f}s ({elapsed/60:.2f} min)")
    print(f"Rate:         {rate:.2f} req/s")
    print(f"Time/request: {elapsed/num_requests:.2f}s")
    
    # Show sample responses
    print(f"\nSAMPLE RESPONSES:")
    for i, result in enumerate(results[:3]):
        if result.error is None and result.response:
            response_dict = result.response if isinstance(result.response, dict) else result.response.model_dump()
            response_body = response_dict.get('body', {})
            choices = response_body.get('choices', [])
            if choices:
                content = choices[0].get('message', {}).get('content', 'N/A')
                print(f"\n--- Response {i} ---")
                print(content[:300])
    
    return {
        'model': model,
        'requests': num_requests,
        'success': success_count,
        'time': elapsed,
        'rate': rate,
        'time_per_request': elapsed / num_requests,
    }


async def main():
    print("=" * 80)
    print("GEMMA 3 MODEL SPEED COMPARISON")
    print("=" * 80)
    print("\nGoal: Find fastest Gemma 3 model with acceptable quality")
    print("Testing: gemma3:1b vs gemma3:4b vs gemma3:12b")
    print("\nWhy Gemma 3 family? Same architecture, same training, only size differs!")

    num_requests = 100

    # Test all Gemma 3 models (same family for apples-to-apples comparison)
    results = []

    # Test gemma3:1b (smallest, should be fastest)
    print("\n🔬 Testing gemma3:1b (1B params, 815MB)...")
    result_1b = await benchmark_model("gemma3:1b", num_requests)
    results.append(result_1b)

    # Short pause
    await asyncio.sleep(5)

    # Test gemma3:4b (medium)
    print("\n🔬 Testing gemma3:4b (4B params, 3.3GB)...")
    result_4b = await benchmark_model("gemma3:4b", num_requests)
    results.append(result_4b)

    # Short pause
    await asyncio.sleep(5)

    # Test gemma3:12b (current, largest)
    print("\n🔬 Testing gemma3:12b (12B params, 8.1GB)...")
    result_12b = await benchmark_model("gemma3:12b", num_requests)
    results.append(result_12b)
    
    # Comparison
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")
    print(f"{'Model':<20} {'Rate (req/s)':<15} {'Time/req (s)':<15} {'100 req time':<15}")
    print("-" * 80)

    for r in results:
        print(f"{r['model']:<20} {r['rate']:<15.2f} {r['time_per_request']:<15.2f} {r['time']/60:<15.1f} min")

    # Calculate speedups
    speedup_1b = result_1b['rate'] / result_12b['rate']
    speedup_4b = result_4b['rate'] / result_12b['rate']

    print(f"\n🚀 SPEEDUPS (vs gemma3:12b baseline):")
    print(f"gemma3:1b:  {speedup_1b:.2f}x faster")
    print(f"gemma3:4b:  {speedup_4b:.2f}x faster")

    # Extrapolate to 200K
    print(f"\n📊 EXTRAPOLATION TO 200K CANDIDATES:")
    for r in results:
        time_200k = 200000 / r['rate']
        print(f"{r['model']:<15} {time_200k/3600:.1f} hours ({time_200k/3600/24:.2f} days)")

    time_saved_1b = (200000 / result_12b['rate']) - (200000 / result_1b['rate'])
    time_saved_4b = (200000 / result_12b['rate']) - (200000 / result_4b['rate'])

    print(f"\n⏱️  TIME SAVED (vs gemma3:12b):")
    print(f"gemma3:1b:  {time_saved_1b/3600:.1f} hours saved")
    print(f"gemma3:4b:  {time_saved_4b/3600:.1f} hours saved")
    
    print(f"\n{'='*80}")
    print("✅ BENCHMARK COMPLETE")
    print(f"{'='*80}")
    print("\nNext step: Review sample responses above to assess quality trade-off")


if __name__ == "__main__":
    asyncio.run(main())

