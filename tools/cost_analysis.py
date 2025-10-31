#!/usr/bin/env python3
"""
Cost analysis tool for comparing self-hosted vs Parasail production costs.
"""

import json
from pathlib import Path
from typing import Dict, List

# Parasail pricing (per million tokens)
PARASAIL_PRICING = {
    "parasail-cydonia-24-v41": {"input": 0.30, "output": 0.50},
    "parasail-deepseek-31": {"input": 0.45, "output": 1.70},
    "parasail-deepseek-r1-0528": {"input": 1.00, "output": 4.50},
    "parasail-drummer-anubis-70b-1-1": {"input": 0.65, "output": 1.00},
    "parasail-gemma3-27b-it": {"input": 0.20, "output": 0.50},
    "parasail-glm-45v": {"input": 0.70, "output": 2.00},
    "parasail-glm-46": {"input": 0.45, "output": 2.10},
    "parasail-gpt-oss-120b": {"input": 0.14, "output": 0.50},
    "parasail-gpt-oss-20b": {"input": 0.04, "output": 0.20},
    "parasail-kimi-k2-instruct": {"input": 0.55, "output": 2.99},
    "parasail-kimi-k2-instruct-0905": {"input": 0.99, "output": 2.99},
    "parasail-llama-33-70b-fp8": {"input": 0.15, "output": 0.50},
    "parasail-llama-4-maverick-instruct-fp8": {"input": 0.35, "output": 0.85},
    "parasail-mistral-small-32-24b": {"input": 0.20, "output": 0.50},
    "parasail-olmo-2-32b-instruct": {"input": 0.20, "output": 0.35},
    "parasail-olmocr-7b-1025-fp8": {"input": 0.10, "output": 0.20},
    "parasail-qwen-3-next-80b-instruct": {"input": 0.10, "output": 1.10},
    "parasail-qwen-3-vl-30b-instruct": {"input": 0.25, "output": 1.00},
    "parasail-qwen25-vl-72b-instruct": {"input": 0.80, "output": 1.00},
    "parasail-qwen3-235b-a22b-instruct-2507": {"input": 0.18, "output": 0.85},
    "parasail-qwen3-30b-a3b": {"input": 0.15, "output": 0.65},
    "parasail-qwen3-vl-235b-a22b-instruct": {"input": 0.50, "output": 2.50},
    "parasail-qwen3vl-32b": {"input": 0.35, "output": 1.10},
    "parasail-qwen3vl-8b-instruct": {"input": 0.15, "output": 0.70},
    "parasail-skyfall-36b-v2-fp8": {"input": 0.50, "output": 0.80},
    "parasail-ui-tars-1p5-7b": {"input": 0.10, "output": 0.20},
    "parasail-qwen3-14b": {"input": 0.15, "output": 0.30},
}

# Self-hosted costs (RTX 4080 16GB)
# Assumptions:
# - GPU cost: $1,200 (RTX 4080 16GB)
# - Lifespan: 3 years
# - Power: 320W @ $0.12/kWh
# - Uptime: 24/7
SELF_HOSTED_COSTS = {
    "gpu_cost": 1200,
    "lifespan_years": 3,
    "power_watts": 320,
    "electricity_cost_per_kwh": 0.12,
    "hours_per_year": 8760,
}

def calculate_parasail_cost(prompt_tokens: int, completion_tokens: int, model: str) -> Dict:
    """Calculate cost for Parasail API."""
    if model not in PARASAIL_PRICING:
        return {"error": f"Model {model} not found in pricing"}
    
    pricing = PARASAIL_PRICING[model]
    
    # Convert to millions
    prompt_mtok = prompt_tokens / 1_000_000
    completion_mtok = completion_tokens / 1_000_000
    
    input_cost = prompt_mtok * pricing["input"]
    output_cost = completion_mtok * pricing["output"]
    total_cost = input_cost + output_cost
    
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "input_cost": round(input_cost, 4),
        "output_cost": round(output_cost, 4),
        "total_cost": round(total_cost, 4),
        "pricing": pricing
    }

def calculate_self_hosted_cost(hours_used: float) -> Dict:
    """Calculate cost for self-hosted RTX 4080."""
    # Amortized GPU cost
    gpu_cost_per_hour = SELF_HOSTED_COSTS["gpu_cost"] / (
        SELF_HOSTED_COSTS["lifespan_years"] * SELF_HOSTED_COSTS["hours_per_year"]
    )
    
    # Electricity cost
    kwh_per_hour = SELF_HOSTED_COSTS["power_watts"] / 1000
    electricity_cost_per_hour = kwh_per_hour * SELF_HOSTED_COSTS["electricity_cost_per_kwh"]
    
    # Total cost per hour
    total_cost_per_hour = gpu_cost_per_hour + electricity_cost_per_hour
    
    # Total cost for usage
    total_cost = hours_used * total_cost_per_hour
    
    return {
        "hours_used": hours_used,
        "gpu_cost_per_hour": round(gpu_cost_per_hour, 4),
        "electricity_cost_per_hour": round(electricity_cost_per_hour, 4),
        "total_cost_per_hour": round(total_cost_per_hour, 4),
        "total_cost": round(total_cost, 4),
        "assumptions": SELF_HOSTED_COSTS
    }

def analyze_benchmark(benchmark_file: str) -> Dict:
    """Analyze a benchmark file and calculate costs."""
    with open(benchmark_file) as f:
        data = json.load(f)
    
    results = data.get("results", {})
    prompt_tokens = results.get("prompt_tokens", 0)
    completion_tokens = results.get("completion_tokens", 0)
    total_tokens = results.get("total_tokens", 0)
    inference_time_seconds = results.get("inference_time_seconds", 0)
    
    # Self-hosted cost
    hours_used = inference_time_seconds / 3600
    self_hosted = calculate_self_hosted_cost(hours_used)
    
    # Find comparable Parasail models
    comparisons = []
    
    # Add specific comparisons based on model
    model = data.get("model", "")
    
    if "gemma" in model.lower():
        comparisons.append(calculate_parasail_cost(prompt_tokens, completion_tokens, "parasail-gemma3-27b-it"))
    
    if "qwen" in model.lower():
        comparisons.append(calculate_parasail_cost(prompt_tokens, completion_tokens, "parasail-qwen3-14b"))
        comparisons.append(calculate_parasail_cost(prompt_tokens, completion_tokens, "parasail-qwen3-30b-a3b"))
    
    # Always add GPT-OSS 20B as baseline
    comparisons.append(calculate_parasail_cost(prompt_tokens, completion_tokens, "parasail-gpt-oss-20b"))
    
    # Add OLMo as alternative
    comparisons.append(calculate_parasail_cost(prompt_tokens, completion_tokens, "parasail-olmo-2-32b-instruct"))
    
    # Calculate cost per 1K, 10K, 100K, 1M requests
    num_requests = data.get("test", {}).get("num_requests", 1)
    if num_requests > 0:
        avg_prompt_tokens = prompt_tokens / num_requests
        avg_completion_tokens = completion_tokens / num_requests

        scale_projections = []
        for scale in [1_000, 10_000, 100_000, 1_000_000]:
            scale_prompt = int(avg_prompt_tokens * scale)
            scale_completion = int(avg_completion_tokens * scale)

            scale_costs = []
            for comp in comparisons:
                model_name = comp["model"]
                pricing = PARASAIL_PRICING[model_name]

                input_cost = (scale_prompt / 1_000_000) * pricing["input"]
                output_cost = (scale_completion / 1_000_000) * pricing["output"]
                total_cost = input_cost + output_cost

                scale_costs.append({
                    "model": model_name,
                    "total_cost": round(total_cost, 2)
                })

            scale_projections.append({
                "num_requests": scale,
                "prompt_tokens": scale_prompt,
                "completion_tokens": scale_completion,
                "total_tokens": scale_prompt + scale_completion,
                "costs": scale_costs
            })
    else:
        scale_projections = []

    return {
        "benchmark": benchmark_file,
        "model": model,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "avg_prompt_per_request": round(prompt_tokens / num_requests, 1) if num_requests > 0 else 0,
            "avg_completion_per_request": round(completion_tokens / num_requests, 1) if num_requests > 0 else 0
        },
        "parasail_comparisons": comparisons,
        "scale_projections": scale_projections
    }

def print_cost_analysis(analysis: Dict):
    """Print cost analysis in a readable format."""
    print("=" * 80)
    print("💰 PRODUCTION COST ESTIMATE (Parasail)")
    print("=" * 80)
    print(f"Benchmark: {analysis['benchmark']}")
    print(f"Model: {analysis['model']}")
    print()

    print("📊 Token Usage:")
    tokens = analysis['tokens']
    print(f"  Prompt tokens:     {tokens['prompt']:,}")
    print(f"  Completion tokens: {tokens['completion']:,}")
    print(f"  Total tokens:      {tokens['total']:,}")
    if tokens['total'] > 0:
        input_ratio = (tokens['prompt'] / tokens['total']) * 100
        output_ratio = (tokens['completion'] / tokens['total']) * 100
        print(f"  Input/Output ratio: {input_ratio:.1f}% / {output_ratio:.1f}%")
    print()

    print("☁️  Parasail Production Costs:")
    for comp in analysis['parasail_comparisons']:
        print(f"\n  {comp['model']}:")
        print(f"    Input:  ${comp['input_cost']:.4f} @ ${comp['pricing']['input']}/MTok")
        print(f"    Output: ${comp['output_cost']:.4f} @ ${comp['pricing']['output']}/MTok")
        print(f"    TOTAL:  ${comp['total_cost']:.4f}")
    print()

    # Find cheapest option
    cheapest = min(analysis['parasail_comparisons'], key=lambda x: x['total_cost'])
    print(f"💡 Cheapest Option: {cheapest['model']} at ${cheapest['total_cost']:.4f}")
    print()

    # Production scale projections
    if analysis.get('scale_projections'):
        print("📈 PRODUCTION SCALE PROJECTIONS:")
        print()

        for projection in analysis['scale_projections']:
            print(f"  {projection['num_requests']:,} requests:")
            print(f"    Tokens: {projection['total_tokens']:,} ({projection['prompt_tokens']:,} in / {projection['completion_tokens']:,} out)")

            # Show costs for each model
            for cost in projection['costs']:
                print(f"    {cost['model']}: ${cost['total_cost']:,.2f}")

            # Highlight cheapest
            cheapest_at_scale = min(projection['costs'], key=lambda x: x['total_cost'])
            print(f"    💡 Cheapest: {cheapest_at_scale['model']} at ${cheapest_at_scale['total_cost']:,.2f}")
            print()

    print("=" * 80)

def main():
    """Analyze all benchmarks."""
    benchmark_dir = Path("benchmarks/metadata")
    
    if not benchmark_dir.exists():
        print(f"Error: {benchmark_dir} not found")
        return
    
    benchmark_files = sorted(benchmark_dir.glob("*.json"))
    
    if not benchmark_files:
        print(f"No benchmark files found in {benchmark_dir}")
        return
    
    print(f"Found {len(benchmark_files)} benchmark files\n")
    
    all_analyses = []
    
    for benchmark_file in benchmark_files:
        try:
            analysis = analyze_benchmark(str(benchmark_file))
            all_analyses.append(analysis)
            print_cost_analysis(analysis)
            print()
        except Exception as e:
            print(f"Error analyzing {benchmark_file}: {e}")
    
    # Save summary
    summary_file = "benchmarks/cost_analysis_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(all_analyses, f, indent=2)
    
    print(f"✅ Saved cost analysis summary to {summary_file}")

if __name__ == "__main__":
    main()

