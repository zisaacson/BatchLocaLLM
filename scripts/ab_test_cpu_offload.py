#!/usr/bin/env python3
"""
A/B Test: CPU Offload Performance Impact

Test Gemma 3 4B with and without CPU offload to measure:
1. Load time
2. Throughput (tokens/sec)
3. Latency
4. GPU memory usage

This will show us the performance cost of CPU offload.
"""

import time
import json
from vllm import LLM, SamplingParams

def test_model(model_id: str, cpu_offload_gb: float, num_requests: int = 100):
    """Test a model with specific CPU offload setting."""
    print("=" * 80)
    print(f"Testing: {model_id}")
    print(f"CPU Offload: {cpu_offload_gb} GB")
    print(f"Requests: {num_requests}")
    print("=" * 80)
    print()
    
    # Load model
    print("🚀 Loading model...")
    start_load = time.time()
    
    vllm_kwargs = {
        "model": model_id,
        "max_model_len": 4096,
        "gpu_memory_utilization": 0.90,
        "max_num_seqs": 64,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "disable_log_stats": True
    }
    
    if cpu_offload_gb > 0:
        vllm_kwargs["cpu_offload_gb"] = cpu_offload_gb
        vllm_kwargs["swap_space"] = 4
    
    llm = LLM(**vllm_kwargs)
    
    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f}s")
    print()
    
    # Create test prompts
    prompts = [f"Write a short story about {i}" for i in range(num_requests)]
    
    # Run inference
    print(f"🧪 Running {num_requests} requests...")
    sampling_params = SamplingParams(temperature=0.7, max_tokens=100)
    
    start_inference = time.time()
    outputs = llm.generate(prompts, sampling_params)
    inference_time = time.time() - start_inference
    
    # Calculate metrics
    total_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
    throughput = total_tokens / inference_time
    avg_latency = (inference_time / num_requests) * 1000  # ms
    
    print(f"✅ Completed in {inference_time:.1f}s")
    print()
    
    # Results
    results = {
        "model": model_id,
        "cpu_offload_gb": cpu_offload_gb,
        "num_requests": num_requests,
        "load_time_sec": round(load_time, 2),
        "inference_time_sec": round(inference_time, 2),
        "total_tokens": total_tokens,
        "throughput_tokens_per_sec": round(throughput, 2),
        "avg_latency_ms": round(avg_latency, 2)
    }
    
    print("📊 Results:")
    print(f"  Load Time: {results['load_time_sec']}s")
    print(f"  Inference Time: {results['inference_time_sec']}s")
    print(f"  Throughput: {results['throughput_tokens_per_sec']} tok/s")
    print(f"  Avg Latency: {results['avg_latency_ms']} ms")
    print()
    
    return results


def main():
    print("=" * 80)
    print("A/B TEST: CPU Offload Performance Impact")
    print("=" * 80)
    print()
    
    model_id = "google/gemma-3-4b-it"
    num_requests = 100
    
    # Test A: No CPU offload (baseline)
    print("\n🅰️  TEST A: No CPU Offload (Baseline)")
    print("-" * 80)
    results_a = test_model(model_id, cpu_offload_gb=0, num_requests=num_requests)
    
    # Test B: With CPU offload
    print("\n🅱️  TEST B: With CPU Offload (4 GB)")
    print("-" * 80)
    results_b = test_model(model_id, cpu_offload_gb=4, num_requests=num_requests)
    
    # Compare results
    print("\n" + "=" * 80)
    print("📊 COMPARISON")
    print("=" * 80)
    print()
    
    print(f"{'Metric':<30} {'No Offload':<20} {'4GB Offload':<20} {'Impact':<20}")
    print("-" * 90)
    
    # Load time
    load_diff = results_b['load_time_sec'] - results_a['load_time_sec']
    load_pct = (load_diff / results_a['load_time_sec']) * 100
    print(f"{'Load Time (s)':<30} {results_a['load_time_sec']:<20} {results_b['load_time_sec']:<20} {load_pct:+.1f}%")
    
    # Throughput
    throughput_diff = results_b['throughput_tokens_per_sec'] - results_a['throughput_tokens_per_sec']
    throughput_pct = (throughput_diff / results_a['throughput_tokens_per_sec']) * 100
    print(f"{'Throughput (tok/s)':<30} {results_a['throughput_tokens_per_sec']:<20} {results_b['throughput_tokens_per_sec']:<20} {throughput_pct:+.1f}%")
    
    # Latency
    latency_diff = results_b['avg_latency_ms'] - results_a['avg_latency_ms']
    latency_pct = (latency_diff / results_a['avg_latency_ms']) * 100
    print(f"{'Avg Latency (ms)':<30} {results_a['avg_latency_ms']:<20} {results_b['avg_latency_ms']:<20} {latency_pct:+.1f}%")
    
    # Inference time
    inference_diff = results_b['inference_time_sec'] - results_a['inference_time_sec']
    inference_pct = (inference_diff / results_a['inference_time_sec']) * 100
    print(f"{'Total Inference Time (s)':<30} {results_a['inference_time_sec']:<20} {results_b['inference_time_sec']:<20} {inference_pct:+.1f}%")
    
    print()
    print("=" * 80)
    print("💡 CONCLUSION")
    print("=" * 80)
    
    if throughput_pct < -10:
        print(f"⚠️  CPU offload causes {abs(throughput_pct):.1f}% throughput degradation")
        print("   Recommendation: Only use CPU offload for models that don't fit in VRAM")
    elif throughput_pct < -5:
        print(f"⚠️  CPU offload causes {abs(throughput_pct):.1f}% throughput degradation")
        print("   Recommendation: Acceptable for 7B+ models that need it")
    else:
        print(f"✅ CPU offload has minimal impact ({throughput_pct:+.1f}%)")
        print("   Recommendation: Safe to use when needed")
    
    # Save results
    output_file = "ab_test_cpu_offload_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "test_a_no_offload": results_a,
            "test_b_with_offload": results_b,
            "comparison": {
                "load_time_impact_pct": round(load_pct, 2),
                "throughput_impact_pct": round(throughput_pct, 2),
                "latency_impact_pct": round(latency_pct, 2),
                "inference_time_impact_pct": round(inference_pct, 2)
            }
        }, f, indent=2)
    
    print(f"\n📁 Results saved to: {output_file}")


if __name__ == "__main__":
    main()

