#!/usr/bin/env python3
"""
Quality Comparison Tool

Compare outputs from different models for the same candidates.
Helps evaluate which model produces better quality responses.
"""

import json
import random
from pathlib import Path
from typing import List, Dict
import sys


def load_results(result_file: str) -> List[Dict]:
    """Load results from JSONL file"""
    results = []
    with open(result_file) as f:
        for line in f:
            results.append(json.loads(line))
    return results


def extract_response_text(result: Dict) -> str:
    """Extract response text from result"""
    try:
        return result["response"]["body"]["choices"][0]["message"]["content"]
    except (KeyError, TypeError, IndexError):
        return "[ERROR: No response]"


def extract_prompt(result: Dict, batch_file: str) -> str:
    """Extract original prompt from batch file"""
    custom_id = result["custom_id"]
    
    with open(batch_file) as f:
        for line in f:
            req = json.loads(line)
            if req["custom_id"] == custom_id:
                messages = req["body"]["messages"]
                # Find user message
                for msg in messages:
                    if msg["role"] == "user":
                        return msg["content"]
    
    return "[ERROR: Prompt not found]"


def compare_models(
    model_results: Dict[str, str],  # model_name -> result_file
    batch_file: str,
    num_samples: int = 5,
    sample_ids: List[str] = None
):
    """
    Compare outputs from multiple models for the same candidates.
    
    Args:
        model_results: Dict mapping model name to result file path
        batch_file: Path to original batch file
        num_samples: Number of samples to compare (default: 5)
        sample_ids: Specific custom_ids to compare (optional)
    """
    
    print("=" * 100)
    print("🔍 MODEL QUALITY COMPARISON")
    print("=" * 100)
    print()
    
    # Load all results
    all_results = {}
    for model_name, result_file in model_results.items():
        if not Path(result_file).exists():
            print(f"⚠️  Warning: {result_file} not found, skipping {model_name}")
            continue
        
        results = load_results(result_file)
        all_results[model_name] = {r["custom_id"]: r for r in results}
        print(f"✅ Loaded {len(results):,} results from {model_name}")
    
    print()
    
    if not all_results:
        print("❌ No results loaded!")
        return
    
    # Get common custom_ids across all models
    common_ids = set(list(all_results.values())[0].keys())
    for results in all_results.values():
        common_ids &= set(results.keys())
    
    print(f"📊 Found {len(common_ids):,} common candidates across all models")
    print()
    
    # Select samples
    if sample_ids:
        selected_ids = [sid for sid in sample_ids if sid in common_ids]
        if len(selected_ids) < len(sample_ids):
            print(f"⚠️  Warning: Only {len(selected_ids)}/{len(sample_ids)} requested IDs found")
    else:
        selected_ids = random.sample(list(common_ids), min(num_samples, len(common_ids)))
    
    print(f"🎯 Comparing {len(selected_ids)} samples:")
    for sid in selected_ids:
        print(f"   - {sid}")
    print()
    
    # Compare each sample
    for i, custom_id in enumerate(selected_ids, 1):
        print("=" * 100)
        print(f"SAMPLE {i}/{len(selected_ids)}: {custom_id}")
        print("=" * 100)
        print()
        
        # Get prompt
        first_result = list(all_results.values())[0][custom_id]
        prompt = extract_prompt(first_result, batch_file)
        
        print("📝 PROMPT:")
        print("-" * 100)
        print(prompt[:500] + ("..." if len(prompt) > 500 else ""))
        print("-" * 100)
        print()
        
        # Compare responses
        for model_name in sorted(all_results.keys()):
            result = all_results[model_name][custom_id]
            response = extract_response_text(result)
            
            # Get token counts
            try:
                usage = result["response"]["body"]["usage"]
                prompt_tokens = usage["prompt_tokens"]
                completion_tokens = usage["completion_tokens"]
                token_info = f"({prompt_tokens} → {completion_tokens} tokens)"
            except (KeyError, TypeError):
                token_info = ""
            
            print(f"🤖 {model_name.upper()} {token_info}")
            print("-" * 100)
            print(response)
            print("-" * 100)
            print()
        
        print()
    
    # Summary statistics
    print("=" * 100)
    print("📊 SUMMARY STATISTICS")
    print("=" * 100)
    print()
    
    for model_name in sorted(all_results.keys()):
        results = list(all_results[model_name].values())
        
        # Calculate average tokens
        prompt_tokens = []
        completion_tokens = []
        
        for result in results:
            try:
                usage = result["response"]["body"]["usage"]
                prompt_tokens.append(usage["prompt_tokens"])
                completion_tokens.append(usage["completion_tokens"])
            except (KeyError, TypeError):
                pass
        
        if prompt_tokens and completion_tokens:
            avg_prompt = sum(prompt_tokens) / len(prompt_tokens)
            avg_completion = sum(completion_tokens) / len(completion_tokens)
            
            print(f"{model_name}:")
            print(f"  Avg Prompt Tokens: {avg_prompt:.0f}")
            print(f"  Avg Completion Tokens: {avg_completion:.0f}")
            print(f"  Avg Total Tokens: {avg_prompt + avg_completion:.0f}")
            print()


def main():
    """CLI interface"""
    
    # Example usage
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python compare_quality.py")
        print()
        print("This script compares outputs from different models for the same candidates.")
        print("Edit the script to specify which models and result files to compare.")
        return
    
    # Define models to compare
    model_results = {
        "Gemma 3 4B": "gemma3_4b_5k_results.jsonl",
        "Llama 3.2 1B": "llama32_1b_5k_results.jsonl",
        "Qwen 3 4B": "qwen3_4b_5k_results.jsonl",
    }
    
    batch_file = "batch_5k.jsonl"
    
    # Check which files exist
    existing_models = {}
    for model_name, result_file in model_results.items():
        if Path(result_file).exists():
            existing_models[model_name] = result_file
    
    if not existing_models:
        print("❌ No result files found!")
        print()
        print("Available result files should be:")
        for model_name, result_file in model_results.items():
            print(f"  - {result_file} ({model_name})")
        print()
        print("Run benchmarks first to generate result files.")
        return
    
    # Run comparison
    compare_models(
        model_results=existing_models,
        batch_file=batch_file,
        num_samples=5
    )


if __name__ == "__main__":
    main()

