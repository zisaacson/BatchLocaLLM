#!/usr/bin/env python3
"""
Comprehensive model benchmarking tool

Benchmarks different models and saves results to database for user reference.
Users can then query the database to see expected timing for their workload.

Usage:
    # Benchmark specific models
    python tools/benchmark_models.py --models gemma3:1b gemma3:4b gemma3:12b
    
    # Benchmark with different request counts
    python tools/benchmark_models.py --models gemma3:4b --requests 100 500 1000
    
    # Benchmark with different worker counts
    python tools/benchmark_models.py --models gemma3:4b --workers 2 4 8
    
    # View existing benchmarks
    python tools/benchmark_models.py --list
    
    # Export benchmarks to JSON
    python tools/benchmark_models.py --export benchmarks.json
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.parallel_processor import ParallelBatchProcessor, WorkerConfig
from src.models import BatchRequestLine, ChatCompletionBody, ChatMessage
from src.benchmark_storage import BenchmarkStorage, BenchmarkResult
from src.logger import logger


# Model size mapping (for reference)
MODEL_SIZES = {
    "gemma3:1b": {"params": "1b", "bytes": 815 * 1024 * 1024, "context_window": 32768},
    "gemma3:4b": {"params": "4b", "bytes": 3300 * 1024 * 1024, "context_window": 131072},
    "gemma3:12b": {"params": "12b", "bytes": 8100 * 1024 * 1024, "context_window": 131072},
    "gemma2:2b": {"params": "2b", "bytes": 1600 * 1024 * 1024, "context_window": 8192},
    "gemma2:9b": {"params": "9b", "bytes": 5400 * 1024 * 1024, "context_window": 8192},
}


def generate_prompt_with_target_tokens(target_tokens: int) -> str:
    """Generate a prompt with approximately target_tokens tokens.

    Rough estimate: 1 token ≈ 4 characters for English text.
    """
    # Base prompt structure
    base_system = "You are an expert AI assistant helping evaluate job candidates."
    base_user_prefix = "Candidate Profile:\n\n"
    base_user_suffix = "\n\nProvide a detailed assessment of this candidate's qualifications."

    # Calculate overhead
    overhead_chars = len(base_system) + len(base_user_prefix) + len(base_user_suffix)
    overhead_tokens = overhead_chars // 4

    # Calculate how many tokens we need to fill
    remaining_tokens = max(0, target_tokens - overhead_tokens)
    remaining_chars = remaining_tokens * 4

    # Generate filler content (realistic candidate info)
    filler_sections = []

    # Add experience section
    filler_sections.append("PROFESSIONAL EXPERIENCE:\n")
    num_jobs = max(1, remaining_chars // 500)  # Each job ~500 chars
    for i in range(min(num_jobs, 10)):
        filler_sections.append(f"""
Position {i+1}: Senior Software Engineer at TechCorp Inc.
Duration: {2020 - i*2} - {2022 - i*2}
Responsibilities:
- Designed and implemented scalable microservices architecture serving 10M+ users
- Led team of 5 engineers in developing real-time data processing pipeline
- Optimized database queries reducing latency by 40%
- Implemented CI/CD pipelines improving deployment frequency by 3x
- Mentored junior developers and conducted code reviews
Technologies: Python, JavaScript, React, Node.js, PostgreSQL, Redis, Docker, Kubernetes
""")

    # Add skills section
    filler_sections.append("\nTECHNICAL SKILLS:\n")
    filler_sections.append("""
Languages: Python, JavaScript, TypeScript, Java, Go, Rust, C++
Frameworks: React, Vue.js, Angular, Django, Flask, FastAPI, Express.js, Spring Boot
Databases: PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Cassandra
Cloud: AWS (EC2, S3, Lambda, RDS), GCP, Azure
DevOps: Docker, Kubernetes, Jenkins, GitLab CI, Terraform, Ansible
""")

    # Add education section
    filler_sections.append("\nEDUCATION:\n")
    filler_sections.append("""
Master of Science in Computer Science - Stanford University (2018)
Bachelor of Science in Computer Engineering - MIT (2016)
Relevant Coursework: Machine Learning, Distributed Systems, Algorithms, Database Systems
""")

    # Add projects section if we need more content
    filler_sections.append("\nNOTABLE PROJECTS:\n")
    filler_sections.append("""
1. Real-time Analytics Platform
   - Built distributed system processing 1M events/second
   - Reduced data processing latency from minutes to seconds
   - Technologies: Kafka, Spark, Cassandra, Python

2. Machine Learning Recommendation Engine
   - Developed collaborative filtering system improving user engagement by 25%
   - Implemented A/B testing framework for model evaluation
   - Technologies: TensorFlow, Python, Redis, PostgreSQL

3. Microservices Migration
   - Led migration from monolith to microservices architecture
   - Improved system reliability from 99.5% to 99.95% uptime
   - Technologies: Docker, Kubernetes, gRPC, Go
""")

    # Combine and truncate to target size
    full_content = "".join(filler_sections)
    if len(full_content) > remaining_chars:
        full_content = full_content[:remaining_chars]

    user_prompt = base_user_prefix + full_content + base_user_suffix

    return base_system, user_prompt


async def create_test_batch(size: int, model: str, target_context_tokens: Optional[int] = None):
    """Create test batch with realistic prompts

    Args:
        size: Number of requests to create
        model: Model name
        target_context_tokens: If specified, generate prompts with approximately this many tokens
    """
    requests = []

    if target_context_tokens:
        # Generate prompts with specific token count
        system_prompt, user_prompt_template = generate_prompt_with_target_tokens(target_context_tokens)
        print(f"  Generated prompts with ~{target_context_tokens} tokens (estimated)")
    else:
        # Use realistic Aris-style prompts (default)
        system_prompt = """You are an expert AI assistant helping evaluate job candidates.
Analyze the candidate's background and provide a brief assessment of their fit for the role."""
        user_prompt_template = None

    for i in range(size):
        if user_prompt_template:
            # Use the generated template (same for all requests in this batch)
            user_prompt = user_prompt_template
        else:
            # Use default short prompts
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


async def benchmark_model(
    model: str,
    num_requests: int = 100,
    num_workers: int = 4,
    target_context_tokens: Optional[int] = None,
    save_to_db: bool = True,
    benchmark_type: str = "model_comparison"
) -> BenchmarkResult:
    """Benchmark a specific model and optionally save to database

    Args:
        model: Model name to benchmark
        num_requests: Number of requests to process
        num_workers: Number of parallel workers
        target_context_tokens: If specified, generate prompts with this many tokens
        save_to_db: Whether to save results to database
        benchmark_type: Type of benchmark (for categorization)
    """
    print(f"\n{'='*80}")
    print(f"BENCHMARKING: {model}")
    print(f"{'='*80}")
    print(f"Requests: {num_requests} | Workers: {num_workers}")
    if target_context_tokens:
        print(f"Context size: ~{target_context_tokens} tokens")

    # Initialize backend
    backend = OllamaBackend(base_url="http://localhost:11434")

    # Load model
    print(f"Loading model: {model}...")
    await backend.load_model(model)
    print(f"✅ Model loaded")

    # Create test batch
    print(f"Creating {num_requests} test requests...")
    requests = await create_test_batch(num_requests, model, target_context_tokens)
    
    # Initialize processor
    processor = ParallelBatchProcessor(
        backend=backend,
        config=WorkerConfig(num_workers=num_workers, retry_attempts=2)
    )
    
    # Benchmark
    print(f"\nProcessing {num_requests} requests with {num_workers} workers...")
    start = time.time()
    results = await processor.process_batch(requests)
    elapsed = time.time() - start
    
    # Analyze results
    success_count = sum(1 for r in results if r.error is None)
    fail_count = sum(1 for r in results if r.error is not None)
    
    # Extract sample responses
    sample_responses = []
    for i, result in enumerate(results[:3]):
        if result.error is None and result.response:
            response_dict = result.response if isinstance(result.response, dict) else result.response.model_dump()
            response_body = response_dict.get('body', {})
            choices = response_body.get('choices', [])
            if choices:
                content = choices[0].get('message', {}).get('content', 'N/A')
                sample_responses.append(content[:300])
    
    # Calculate token stats (if available)
    total_prompt_tokens = 0
    total_completion_tokens = 0
    token_count = 0
    
    for result in results:
        if result.error is None and result.response:
            response_dict = result.response if isinstance(result.response, dict) else result.response.model_dump()
            response_body = response_dict.get('body', {})
            usage = response_body.get('usage', {})
            if usage:
                total_prompt_tokens += usage.get('prompt_tokens', 0)
                total_completion_tokens += usage.get('completion_tokens', 0)
                token_count += 1
    
    avg_prompt_tokens = int(total_prompt_tokens / token_count) if token_count > 0 else None
    avg_completion_tokens = int(total_completion_tokens / token_count) if token_count > 0 else None
    
    # Create benchmark result
    model_info = MODEL_SIZES.get(model, {})
    benchmark_result = BenchmarkResult(
        model_name=model,
        model_size_params=model_info.get("params"),
        model_size_bytes=model_info.get("bytes"),
        context_window=model_info.get("context_window"),
        num_workers=num_workers,
        num_requests=num_requests,
        avg_prompt_tokens=avg_prompt_tokens,
        avg_completion_tokens=avg_completion_tokens,
        total_time_seconds=elapsed,
        successful_requests=success_count,
        failed_requests=fail_count,
        sample_responses=sample_responses,
        benchmark_type=benchmark_type,
        notes=f"Context size: ~{target_context_tokens} tokens" if target_context_tokens else None,
    )
    
    # Print results
    print(f"\n{'='*80}")
    print(f"RESULTS FOR {model}:")
    print(f"{'='*80}")
    print(f"Requests:     {num_requests}")
    print(f"Success:      {success_count}/{num_requests} ({benchmark_result.success_rate:.1f}%)")
    print(f"Time:         {elapsed:.1f}s ({elapsed/60:.2f} min)")
    print(f"Rate:         {benchmark_result.requests_per_second:.2f} req/s")
    print(f"Time/request: {benchmark_result.time_per_request_seconds:.2f}s")
    
    if avg_prompt_tokens:
        print(f"Avg tokens:   {avg_prompt_tokens} prompt + {avg_completion_tokens} completion")
    
    print(f"\nSAMPLE RESPONSES:")
    for i, sample in enumerate(sample_responses):
        print(f"\n--- Response {i} ---")
        print(sample)
    
    # Save to database
    if save_to_db:
        storage = BenchmarkStorage()
        await storage.init_db()
        benchmark_id = await storage.save_benchmark(benchmark_result)
        print(f"\n✅ Benchmark saved to database (ID: {benchmark_id})")
    
    return benchmark_result


async def list_benchmarks():
    """List all benchmarks in the database"""
    storage = BenchmarkStorage()
    await storage.init_db()
    
    models = await storage.get_all_models()
    
    print(f"\n{'='*80}")
    print("BENCHMARKED MODELS")
    print(f"{'='*80}")
    
    for model in models:
        benchmarks = await storage.get_benchmarks_for_model(model, limit=5)
        print(f"\n{model}:")
        print(f"  Total benchmarks: {len(benchmarks)}")
        
        if benchmarks:
            latest = benchmarks[0]
            print(f"  Latest: {latest.requests_per_second:.2f} req/s ({latest.num_requests} requests, {latest.num_workers} workers)")
            print(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest.created_at))}")


async def export_benchmarks(output_path: str):
    """Export all benchmarks to JSON"""
    storage = BenchmarkStorage()
    await storage.init_db()
    await storage.export_benchmarks_json(output_path)
    print(f"✅ Benchmarks exported to {output_path}")


async def compare_models(models: List[str], num_requests: int = 100):
    """Compare multiple models side-by-side"""
    results = []
    
    for model in models:
        result = await benchmark_model(model, num_requests=num_requests, save_to_db=True)
        results.append(result)
        
        # Short pause between models
        await asyncio.sleep(5)
    
    # Print comparison
    print(f"\n{'='*80}")
    print("MODEL COMPARISON")
    print(f"{'='*80}")
    print(f"{'Model':<20} {'Rate (req/s)':<15} {'Time/req (s)':<15} {f'{num_requests} req time':<15}")
    print("-" * 80)
    
    for r in results:
        print(f"{r.model_name:<20} {r.requests_per_second:<15.2f} {r.time_per_request_seconds:<15.2f} {r.total_time_seconds/60:<15.1f} min")
    
    # Calculate speedups vs slowest
    slowest = min(results, key=lambda r: r.requests_per_second)
    
    print(f"\n🚀 SPEEDUPS (vs {slowest.model_name} baseline):")
    for r in results:
        speedup = r.requests_per_second / slowest.requests_per_second
        print(f"{r.model_name:<20} {speedup:.2f}x faster")
    
    # Extrapolate to 200K
    print(f"\n📊 EXTRAPOLATION TO 200K CANDIDATES:")
    for r in results:
        time_200k = 200000 / r.requests_per_second
        print(f"{r.model_name:<20} {time_200k/3600:.1f} hours ({time_200k/3600/24:.2f} days)")
    
    print(f"\n⏱️  TIME SAVED (vs {slowest.model_name}):")
    for r in results:
        if r.model_name != slowest.model_name:
            time_saved = (200000 / slowest.requests_per_second) - (200000 / r.requests_per_second)
            print(f"{r.model_name:<20} {time_saved/3600:.1f} hours saved")


async def main():
    parser = argparse.ArgumentParser(description="Benchmark LLM models for batch processing")
    parser.add_argument("--models", nargs="+", help="Models to benchmark (e.g., gemma3:1b gemma3:4b)")
    parser.add_argument("--requests", type=int, nargs="+", default=[100], help="Number of requests to test")
    parser.add_argument("--workers", type=int, nargs="+", default=[4], help="Number of workers to test")
    parser.add_argument("--context-sizes", type=int, nargs="+", help="Context sizes to test (in tokens, e.g., 1000 8000 32000)")
    parser.add_argument("--list", action="store_true", help="List existing benchmarks")
    parser.add_argument("--export", type=str, help="Export benchmarks to JSON file")
    parser.add_argument("--compare", action="store_true", help="Compare models side-by-side")

    args = parser.parse_args()
    
    if args.list:
        await list_benchmarks()
        return
    
    if args.export:
        await export_benchmarks(args.export)
        return
    
    if not args.models:
        parser.print_help()
        return
    
    if args.compare:
        # Compare models with same config
        await compare_models(args.models, num_requests=args.requests[0])
    else:
        # Benchmark each combination
        context_sizes = args.context_sizes if args.context_sizes else [None]

        for model in args.models:
            for num_requests in args.requests:
                for num_workers in args.workers:
                    for context_size in context_sizes:
                        benchmark_type = "context_size_test" if context_size else "comprehensive"

                        await benchmark_model(
                            model,
                            num_requests=num_requests,
                            num_workers=num_workers,
                            target_context_tokens=context_size,
                            save_to_db=True,
                            benchmark_type=benchmark_type
                        )

                        # Short pause
                        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

