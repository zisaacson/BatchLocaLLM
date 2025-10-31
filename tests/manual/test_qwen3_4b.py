#!/usr/bin/env python3
"""
Test Qwen 3 4B model with vLLM native batch processing.
"""

import json
import time
from pathlib import Path
from vllm import LLM, SamplingParams

def main():
    print("=" * 80)
    print("QWEN 3 4B BENCHMARK TEST")
    print("=" * 80)
    print()
    
    # Model configuration
    model_id = "Qwen/Qwen3-4B-Instruct-2507"
    input_file = "batch_10_test.jsonl"
    output_file = "qwen3_4b_test_results.jsonl"
    
    print(f"Model: {model_id}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()
    
    # Load requests
    print("📥 Loading requests...")
    requests = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))
    
    print(f"✅ Loaded {len(requests)} requests")
    print()
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req['body']['messages']
        # Format for Qwen (similar to Gemma)
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompts.append(prompt)
    
    # Initialize vLLM
    print(f"🚀 Loading model: {model_id}")
    print("This may take 20-30 seconds...")
    print()
    
    start_load = time.time()
    llm = LLM(
        model=model_id,
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        disable_log_stats=True,
    )
    load_time = time.time() - start_load
    
    print(f"✅ Model loaded in {load_time:.1f}s")
    print()
    
    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )
    
    # Run inference
    print(f"⚡ Running inference on {len(prompts)} prompts...")
    print("vLLM will handle batching automatically")
    print()
    
    start_inference = time.time()
    outputs = llm.generate(prompts, sampling_params)
    inference_time = time.time() - start_inference
    
    print(f"✅ Inference complete in {inference_time:.1f}s ({inference_time/60:.1f} minutes)")
    print()
    
    # Save results
    print(f"💾 Saving results to {output_file}")
    results = []
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    for i, output in enumerate(outputs):
        prompt_tok = len(output.prompt_token_ids)
        completion_tok = len(output.outputs[0].token_ids)
        
        prompt_tokens += prompt_tok
        completion_tokens += completion_tok
        total_tokens += prompt_tok + completion_tok
        
        result = {
            "custom_id": requests[i]['custom_id'],
            "response": {
                "status_code": 200,
                "body": {
                    "id": f"chatcmpl-{i}",
                    "object": "chat.completion",
                    "model": model_id,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": output.outputs[0].text
                        },
                        "finish_reason": output.outputs[0].finish_reason
                    }],
                    "usage": {
                        "prompt_tokens": prompt_tok,
                        "completion_tokens": completion_tok,
                        "total_tokens": prompt_tok + completion_tok
                    }
                }
            }
        }
        results.append(result)
    
    # Write results
    with open(output_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    print(f"✅ Saved {len(results)} results")
    print()
    
    # Calculate metrics
    throughput = total_tokens / inference_time
    requests_per_sec = len(requests) / inference_time
    
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print(f"Model:                 {model_id}")
    print(f"Requests:              {len(requests)}")
    print(f"Success:               {len(results)} ({len(results)/len(requests)*100:.1f}%)")
    print(f"Model load time:       {load_time:.1f}s")
    print(f"Inference time:        {inference_time:.1f}s ({inference_time/60:.1f} minutes)")
    print(f"Total time:            {load_time + inference_time:.1f}s")
    print(f"Prompt tokens:         {prompt_tokens:,}")
    print(f"Completion tokens:     {completion_tokens:,}")
    print(f"Total tokens:          {total_tokens:,}")
    print(f"Throughput:            {throughput:.0f} tokens/sec")
    print(f"Requests/sec:          {requests_per_sec:.2f}")
    print("=" * 80)
    print()
    
    # Save benchmark metadata
    metadata = {
        "test_id": f"qwen3-4b-test-{len(requests)}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": "vllm-native",
        "model": model_id,
        "config": {
            "max_model_len": 4096,
            "gpu_memory_utilization": 0.9,
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
            "failure_count": len(requests) - len(results),
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
    
    metadata_file = f"benchmarks/metadata/qwen3-4b-{len(requests)}-{time.strftime('%Y-%m-%d')}.json"
    Path(metadata_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Saved benchmark metadata: {metadata_file}")
    print()
    
    # Compare to Gemma 3 4B
    print("=" * 80)
    print("📊 COMPARISON TO GEMMA 3 4B")
    print("=" * 80)
    print(f"Qwen 3 4B:             {throughput:.0f} tokens/sec")
    print(f"Gemma 3 4B:            2,511 tokens/sec (from 5K benchmark)")
    print(f"Difference:            {throughput - 2511:+.0f} tokens/sec ({(throughput/2511 - 1)*100:+.1f}%)")
    print("=" * 80)
    print()
    
    print("🎉 Qwen 3 4B test complete!")
    print()

if __name__ == "__main__":
    main()

