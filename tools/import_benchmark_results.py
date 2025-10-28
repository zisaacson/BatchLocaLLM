#!/usr/bin/env python3
"""
Import benchmark results from our gemma3 test into the database

This saves the results from gemma3_benchmark_results.txt to the database
so they're available via API.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.benchmark_storage import BenchmarkStorage, BenchmarkResult


async def main():
    """Import the Gemma 3 benchmark results"""
    
    storage = BenchmarkStorage()
    await storage.init_db()
    
    # Results from gemma3_benchmark_results.txt
    # Context window sizes from https://ai.google.dev/gemma/docs/core
    # gemma3:1b = 32K, gemma3:4b/12b = 128K
    benchmarks = [
        BenchmarkResult(
            model_name="gemma3:1b",
            model_size_params="1b",
            model_size_bytes=815 * 1024 * 1024,
            context_window=32768,  # 32K context window
            num_workers=4,
            num_requests=100,
            total_time_seconds=108.6,
            successful_requests=100,
            failed_requests=0,
            sample_responses=[
                "Okay, let's analyze Candidate 0 and assess their potential fit for the role. Here's a breakdown of my assessment, broken down into strengths, areas for potential concern, and overall fit assessment:\n\n**Overall Assessment - Preliminary:**\n\nThis candidate presents a solid foundation for a Software Eng",
                "collaboratingOkay, let's break down this candidate's background and assess their potential fit for the role. Here's a brief assessment, focusing on strengths and potential areas for further exploration:\n\n**Overall Assessment:** This candidate appears to be a strong candidate with a solid foundation",
                "workedOkay, let's analyze this candidate's background and assess their potential fit for the role. Here's a breakdown of my assessment, focusing on key areas and potential strengths and areas for further exploration:\n\n**Overall Assessment: Strong Foundation, but Requires Context & Specificity**\n\nTh",
            ],
            benchmark_type="model_comparison",
            notes="Gemma 3 1B model - fastest but lower quality responses, 32K context window (text-only)",
        ),
        BenchmarkResult(
            model_name="gemma3:4b",
            model_size_params="4b",
            model_size_bytes=3300 * 1024 * 1024,
            context_window=131072,  # 128K context window
            num_workers=4,
            num_requests=100,
            total_time_seconds=191.3,
            successful_requests=100,
            failed_requests=0,
            sample_responses=[
                "startupOkay, let's analyze Candidate 0.\n\n**Overall Assessment: Strong Potential – Likely a Good Fit**\n\n**Strengths:**\n\n* **Solid Experience:** 5 years in software engineering is a good foundation and demonstrates they've spent a reasonable amount of time in the field.\n* **Relevant Technical Skills:",
                "usOkay, let's analyze this candidate. Based on the information provided, here's my assessment:\n\n**Overall Assessment: Strong Potential – Likely a Good Fit**\n\n**Strengths:**\n\n* **Solid Experience:** 6 years in software engineering is a respectable amount of experience and demonstrates a sustained ca",
                "stackOkay, let's break down Candidate 2's qualifications and assess their potential fit.\n\n**Overall Assessment: Strong Potential - A Solid Contender**\n\n**Strengths & Positive Indicators:**\n\n* **Significant Experience:** 7 years in software engineering is a very respectable amount of experience. This",
            ],
            benchmark_type="model_comparison",
            notes="Gemma 3 4B model - balanced speed and quality, 128K context window (multimodal)",
        ),
        BenchmarkResult(
            model_name="gemma3:12b",
            model_size_params="12b",
            model_size_bytes=8100 * 1024 * 1024,
            context_window=131072,  # 128K context window
            num_workers=4,
            num_requests=100,
            total_time_seconds=442.1,
            successful_requests=100,
            failed_requests=0,
            sample_responses=[
                "EngineerOkay, let's analyze Candidate 0. Here's a brief assessment based on the provided information:\n\n**Overall Assessment: Strong Potential - Likely a Good Fit with Further Exploration**\n\nThis candidate presents a very promising profile. Let's break down the strengths and areas for further invest",
                "CorpOkay, let's assess Candidate 1. Here's a breakdown of their qualifications and a potential fit assessment, considering common software engineering roles.  I'll structure this into Strengths, Potential Concerns, and Overall Fit/Recommendations.\n\n**Strengths:**\n\n* **Solid Experience:** 6 years in",
                "SpecificOkay, let's break down Candidate 2's profile and assess their fit. Here's my analysis, structured for clarity:\n\n**Overall Assessment: Strong Potential - Likely a Solid Hire with Potential for Leadership**\n\nThis candidate presents a very promising profile. The combination of experience, skil",
            ],
            benchmark_type="model_comparison",
            notes="Gemma 3 12B model - current baseline, best quality but slowest, 128K context window (multimodal)",
        ),
    ]
    
    print("Importing benchmark results...")
    
    for benchmark in benchmarks:
        benchmark_id = await storage.save_benchmark(benchmark)
        print(f"✅ Saved {benchmark.model_name}: {benchmark.requests_per_second:.2f} req/s (ID: {benchmark_id})")
    
    print(f"\n✅ Imported {len(benchmarks)} benchmark results")
    
    # Verify
    print("\nVerifying import...")
    models = await storage.get_all_models()
    print(f"Models in database: {models}")
    
    for model in models:
        benchmarks = await storage.get_benchmarks_for_model(model, limit=1)
        if benchmarks:
            latest = benchmarks[0]
            print(f"  {model}: {latest.requests_per_second:.2f} req/s")


if __name__ == "__main__":
    asyncio.run(main())

