#!/usr/bin/env python3
"""
vLLM Native Batch Inference Benchmark

Uses vLLM's native LLM.generate() - NO custom batching, NO wrappers.
Just pure vLLM as the experts designed it.

Usage:
    python benchmark_vllm_native.py batch_5k.jsonl output.jsonl
"""

import json
import sys
import time
from pathlib import Path
from vllm import LLM, SamplingParams

def main():
    if len(sys.argv) != 3:
        print("Usage: python benchmark_vllm_native.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print("=" * 80)
    print("vLLM NATIVE BATCH INFERENCE BENCHMARK")
    print("=" * 80)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print("=" * 80)
    
    # Load requests
    print("\n📥 Loading requests...")
    requests = []
    with open(input_file) as f:
        for line in f:
            req = json.loads(line)
            requests.append(req)
    
    print(f"✅ Loaded {len(requests)} requests")
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req['body']['messages']
        # Simple prompt formatting (adjust based on model)
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompts.append(prompt)
    
    # Initialize vLLM
    print("\n🚀 Initializing vLLM...")
    print("Config:")
    print("  - Model: google/gemma-3-4b-it")
    print("  - max_model_len: 4096")
    print("  - gpu_memory_utilization: 0.90")
    print("  - enable_prefix_caching: True (default)")
    print("  - chunked_prefill_enabled: True (default)")
    
    start_load = time.time()
    llm = LLM(
        model="google/gemma-3-4b-it",
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        disable_log_stats=True,
    )
    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f}s")
    
    # Sampling params
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )
    
    # Run inference (vLLM handles batching internally)
    print(f"\n⚡ Running inference on {len(prompts)} prompts...")
    print("vLLM will handle batching automatically - we just call generate()!")
    
    start_inference = time.time()
    outputs = llm.generate(prompts, sampling_params)
    inference_time = time.time() - start_inference
    
    print(f"✅ Inference complete in {inference_time:.1f}s")
    
    # Save results
    print(f"\n💾 Saving results to {output_file}...")
    results = []
    for i, output in enumerate(outputs):
        result = {
            "custom_id": requests[i]['custom_id'],
            "response": {
                "status_code": 200,
                "body": {
                    "id": f"chatcmpl-{i}",
                    "object": "chat.completion",
                    "model": "google/gemma-3-4b-it",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": output.outputs[0].text
                        },
                        "finish_reason": output.outputs[0].finish_reason
                    }],
                    "usage": {
                        "prompt_tokens": len(output.prompt_token_ids),
                        "completion_tokens": len(output.outputs[0].token_ids),
                        "total_tokens": len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
                    }
                }
            }
        }
        results.append(result)
    
    with open(output_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    print(f"✅ Saved {len(results)} results")
    
    # Calculate metrics
    total_tokens = sum(
        len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
        for output in outputs
    )
    prompt_tokens = sum(len(output.prompt_token_ids) for output in outputs)
    completion_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
    
    throughput = total_tokens / inference_time
    requests_per_sec = len(requests) / inference_time
    
    print("\n" + "=" * 80)
    print("📊 BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Requests:              {len(requests)}")
    print(f"Success:               {len(results)} ({len(results)/len(requests)*100:.1f}%)")
    print(f"Model load time:       {load_time:.1f}s")
    print(f"Inference time:        {inference_time:.1f}s")
    print(f"Total time:            {load_time + inference_time:.1f}s")
    print(f"Prompt tokens:         {prompt_tokens:,}")
    print(f"Completion tokens:     {completion_tokens:,}")
    print(f"Total tokens:          {total_tokens:,}")
    print(f"Throughput:            {throughput:.0f} tokens/sec")
    print(f"Requests/sec:          {requests_per_sec:.2f}")
    print("=" * 80)
    
    # Save metadata
    metadata = {
        "test_id": f"vllm-native-gemma3-4b-{len(requests)}-{time.strftime('%Y-%m-%d')}",
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "platform": "vllm-native",
        "model": "google/gemma-3-4b-it",
        "config": {
            "max_model_len": 4096,
            "gpu_memory_utilization": 0.90,
            "enable_prefix_caching": True,
            "chunked_prefill_enabled": True
        },
        "test": {
            "num_requests": len(requests),
            "input_file": input_file,
            "output_file": output_file
        },
        "results": {
            "success_count": len(results),
            "failure_count": 0,
            "model_load_time_seconds": load_time,
            "inference_time_seconds": inference_time,
            "total_time_seconds": load_time + inference_time,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "throughput_tokens_per_sec": int(throughput),
            "throughput_requests_per_sec": round(requests_per_sec, 2)
        },
        "status": "completed"
    }
    
    metadata_file = f"benchmarks/metadata/{metadata['test_id']}.json"
    Path(metadata_file).parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Metadata saved: {metadata_file}")
    print("\n🎉 Benchmark complete!")

if __name__ == '__main__':
    main()

