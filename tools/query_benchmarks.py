#!/usr/bin/env python3
"""
Query benchmark database to help users choose models

Shows expected timing for different models based on historical benchmarks.

Usage:
    # Show all available models
    python tools/query_benchmarks.py --list
    
    # Get timing estimate for specific model and workload
    python tools/query_benchmarks.py --model gemma3:4b --requests 50000
    
    # Compare all models for a specific workload
    python tools/query_benchmarks.py --compare --requests 200000
    
    # Show detailed stats for a model
    python tools/query_benchmarks.py --model gemma3:4b --details
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.benchmark_storage import BenchmarkStorage, BenchmarkResult
import time


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    else:
        return f"{seconds/86400:.1f}d ({seconds/3600:.1f}h)"


async def list_models():
    """List all benchmarked models"""
    storage = BenchmarkStorage()
    await storage.init_db()
    
    models = await storage.get_all_models()
    
    print(f"\n{'='*80}")
    print("AVAILABLE MODELS (with benchmark data)")
    print(f"{'='*80}\n")
    
    if not models:
        print("No benchmarks found. Run benchmark_models.py first!")
        return
    
    for model in sorted(models):
        benchmarks = await storage.get_benchmarks_for_model(model, limit=1)
        if benchmarks:
            latest = benchmarks[0]
            ctx_window = f"{latest.context_window//1024}K" if latest.context_window else "N/A"
            print(f"  {model:<20} {latest.requests_per_second:>8.2f} req/s  {ctx_window:>6} ctx  ({latest.num_requests} requests, {latest.num_workers} workers)")
    
    print(f"\nTotal models: {len(models)}")


async def get_model_estimate(model: str, num_requests: int):
    """Get timing estimate for a specific model and workload"""
    storage = BenchmarkStorage()
    await storage.init_db()
    
    benchmarks = await storage.get_benchmarks_for_model(model, limit=5)
    
    if not benchmarks:
        print(f"❌ No benchmark data found for {model}")
        print(f"Run: python tools/benchmark_models.py --models {model}")
        return
    
    # Use most recent benchmark
    latest = benchmarks[0]
    
    # Calculate estimates
    estimated_time = num_requests / latest.requests_per_second
    
    print(f"\n{'='*80}")
    print(f"ESTIMATE FOR {model}")
    print(f"{'='*80}")
    print(f"\nWorkload: {num_requests:,} requests")
    print(f"\nBased on benchmark:")
    print(f"  Date:           {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest.created_at))}")
    print(f"  Test size:      {latest.num_requests} requests")
    print(f"  Workers:        {latest.num_workers}")
    print(f"  Context window: {latest.context_window//1024}K tokens" if latest.context_window else "  Context window: N/A")
    print(f"  Rate:           {latest.requests_per_second:.2f} req/s")
    print(f"  Success rate:   {latest.success_rate:.1f}%")
    
    print(f"\n📊 ESTIMATED TIME:")
    print(f"  Total time:   {format_time(estimated_time)}")
    print(f"  Per request:  {latest.time_per_request_seconds:.2f}s")
    
    if latest.avg_prompt_tokens:
        print(f"\n💬 TOKEN USAGE (per request):")
        print(f"  Prompt:       {latest.avg_prompt_tokens} tokens")
        print(f"  Completion:   {latest.avg_completion_tokens} tokens")
        print(f"  Total:        {latest.avg_prompt_tokens + latest.avg_completion_tokens} tokens")
        
        total_tokens = num_requests * (latest.avg_prompt_tokens + latest.avg_completion_tokens)
        print(f"\n  Total for {num_requests:,} requests: {total_tokens:,} tokens")
    
    # Show quality samples if available
    if latest.sample_responses:
        print(f"\n📝 SAMPLE RESPONSES:")
        for i, sample in enumerate(latest.sample_responses[:2]):
            print(f"\n--- Sample {i+1} ---")
            print(sample[:200] + "..." if len(sample) > 200 else sample)


async def compare_all_models(num_requests: int):
    """Compare all available models for a specific workload"""
    storage = BenchmarkStorage()
    await storage.init_db()
    
    models = await storage.get_all_models()
    
    if not models:
        print("❌ No benchmark data found. Run benchmark_models.py first!")
        return
    
    print(f"\n{'='*80}")
    print(f"MODEL COMPARISON FOR {num_requests:,} REQUESTS")
    print(f"{'='*80}\n")
    
    results = []
    for model in sorted(models):
        benchmarks = await storage.get_benchmarks_for_model(model, limit=1)
        if benchmarks:
            latest = benchmarks[0]
            estimated_time = num_requests / latest.requests_per_second
            results.append({
                'model': model,
                'context_window': latest.context_window,
                'rate': latest.requests_per_second,
                'time': estimated_time,
                'success_rate': latest.success_rate,
                'workers': latest.num_workers,
            })
    
    # Sort by speed (fastest first)
    results.sort(key=lambda x: x['time'])

    print(f"{'Model':<20} {'Ctx':<8} {'Rate':<12} {'Est. Time':<15} {'Success':<10} {'Workers':<8}")
    print("-" * 90)

    for r in results:
        ctx = f"{r['context_window']//1024}K" if r.get('context_window') else "N/A"
        print(f"{r['model']:<20} {ctx:<8} {r['rate']:>8.2f}/s  {format_time(r['time']):<15} {r['success_rate']:>6.1f}%  {r['workers']:>8}")
    
    # Show speedups
    if len(results) > 1:
        slowest = results[-1]
        print(f"\n🚀 SPEEDUPS (vs {slowest['model']}):")
        for r in results:
            if r['model'] != slowest['model']:
                speedup = slowest['time'] / r['time']
                time_saved = slowest['time'] - r['time']
                print(f"  {r['model']:<20} {speedup:>5.2f}x faster  (saves {format_time(time_saved)})")


async def show_model_details(model: str):
    """Show detailed statistics for a model"""
    storage = BenchmarkStorage()
    await storage.init_db()
    
    benchmarks = await storage.get_benchmarks_for_model(model, limit=10)
    
    if not benchmarks:
        print(f"❌ No benchmark data found for {model}")
        return
    
    print(f"\n{'='*80}")
    print(f"DETAILED STATS FOR {model}")
    print(f"{'='*80}")
    print(f"\nTotal benchmarks: {len(benchmarks)}\n")
    
    print(f"{'Date':<20} {'Requests':<10} {'Workers':<8} {'Rate':<12} {'Success':<10}")
    print("-" * 80)
    
    for b in benchmarks:
        date_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(b.created_at))
        print(f"{date_str:<20} {b.num_requests:<10} {b.num_workers:<8} {b.requests_per_second:>8.2f}/s  {b.success_rate:>6.1f}%")
    
    # Calculate averages
    avg_rate = sum(b.requests_per_second for b in benchmarks) / len(benchmarks)
    avg_success = sum(b.success_rate for b in benchmarks) / len(benchmarks)
    
    print(f"\n📊 AVERAGES:")
    print(f"  Rate:         {avg_rate:.2f} req/s")
    print(f"  Success rate: {avg_success:.1f}%")
    
    # Show latest sample
    latest = benchmarks[0]
    if latest.sample_responses:
        print(f"\n📝 LATEST SAMPLE RESPONSE:")
        print(latest.sample_responses[0][:300])


async def main():
    parser = argparse.ArgumentParser(description="Query benchmark database for model selection")
    parser.add_argument("--list", action="store_true", help="List all available models")
    parser.add_argument("--model", type=str, help="Model to query")
    parser.add_argument("--requests", type=int, help="Number of requests for estimate")
    parser.add_argument("--compare", action="store_true", help="Compare all models")
    parser.add_argument("--details", action="store_true", help="Show detailed stats for model")
    
    args = parser.parse_args()
    
    if args.list:
        await list_models()
    elif args.compare:
        if not args.requests:
            print("❌ --requests required for comparison")
            parser.print_help()
            return
        await compare_all_models(args.requests)
    elif args.model:
        if args.details:
            await show_model_details(args.model)
        elif args.requests:
            await get_model_estimate(args.model, args.requests)
        else:
            print("❌ Specify --requests for estimate or --details for stats")
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

