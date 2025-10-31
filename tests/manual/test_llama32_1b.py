#!/usr/bin/env python3
"""
Test Llama 3.2 1B - smallest model, should be fastest.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from vllm import LLM, SamplingParams

def main():
    print("=" * 80)
    print("🧪 LLAMA 3.2 1B - 5K BATCH TEST")
    print("=" * 80)
    print()
    
    # Configuration
    model_id = "meta-llama/Llama-3.2-1B-Instruct"
    input_file = "batch_5k.jsonl"
    output_file = "llama32_1b_5k_results.jsonl"
    
    print(f"Model: {model_id}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()
    print("⚠️  Note: Requires HuggingFace authentication (huggingface-cli login)")
    print()
    
    # Load requests
    print("📂 Loading requests...")
    requests = []
    with open(input_file) as f:
        for line in f:
            requests.append(json.loads(line))
    
    print(f"✅ Loaded {len(requests)} requests")
    print()
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req["body"]["messages"]
        prompt = messages[0]["content"]
        prompts.append(prompt)
    
    # Initialize vLLM
    print("🚀 Initializing vLLM...")
    start_load = time.time()
    
    llm = LLM(
        model=model_id,
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        disable_log_stats=True,
    )
    
    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f} seconds")
    print()
    
    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )
    
    # Run inference
    print("⚡ Running inference...")
    print(f"Batch size: {len(prompts)}")
    print()
    
    start_inference = time.time()
    outputs = llm.generate(prompts, sampling_params)
    inference_time = time.time() - start_inference
    
    print(f"✅ Inference complete in {inference_time:.1f} seconds ({inference_time/60:.1f} minutes)")
    print()
    
    # Process results
    print("📊 Processing results...")
    
    results = []
    success_count = 0
    failure_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    
    for i, output in enumerate(outputs):
        custom_id = requests[i]["custom_id"]
        
        if output.outputs and len(output.outputs) > 0:
            success_count += 1
            text = output.outputs[0].text
            finish_reason = output.outputs[0].finish_reason
            
            prompt_tok = len(output.prompt_token_ids)
            completion_tok = len(output.outputs[0].token_ids)
            
            prompt_tokens += prompt_tok
            completion_tokens += completion_tok
            total_tokens += prompt_tok + completion_tok
            
            result = {
                "custom_id": custom_id,
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": text
                            },
                            "finish_reason": finish_reason
                        }],
                        "usage": {
                            "prompt_tokens": prompt_tok,
                            "completion_tokens": completion_tok,
                            "total_tokens": prompt_tok + completion_tok
                        }
                    }
                }
            }
        else:
            failure_count += 1
            result = {
                "custom_id": custom_id,
                "response": {
                    "status_code": 500,
                    "body": {"error": "No output generated"}
                }
            }
        
        results.append(result)
    
    # Save results
    print(f"💾 Saving results to {output_file}...")
    with open(output_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    print(f"✅ Saved {len(results)} results")
    print()
    
    # Calculate metrics
    total_time = load_time + inference_time
    throughput_tokens_per_sec = int(total_tokens / inference_time) if inference_time > 0 else 0
    throughput_requests_per_sec = round(len(requests) / inference_time, 2) if inference_time > 0 else 0
    
    # Print summary
    print("=" * 80)
    print("📊 RESULTS SUMMARY")
    print("=" * 80)
    print()
    print(f"Success: {success_count}/{len(requests)} ({success_count/len(requests)*100:.1f}%)")
    print(f"Failures: {failure_count}")
    print()
    print(f"Prompt tokens:     {prompt_tokens:,} ({prompt_tokens//len(requests)} avg)")
    print(f"Completion tokens: {completion_tokens:,} ({completion_tokens//len(requests)} avg)")
    print(f"Total tokens:      {total_tokens:,}")
    print()
    print(f"Model load time:   {load_time:.1f} seconds")
    print(f"Inference time:    {inference_time:.1f} seconds ({inference_time/60:.1f} minutes)")
    print(f"Total time:        {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print()
    print(f"Throughput:        {throughput_tokens_per_sec:,} tokens/sec")
    print(f"Throughput:        {throughput_requests_per_sec} requests/sec")
    print()
    print("=" * 80)
    
    # Save metadata
    metadata = {
        "test_id": "llama32-1b-5k",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "platform": "vllm-native",
        "model": model_id,
        "test": {
            "input_file": input_file,
            "output_file": output_file,
            "num_requests": len(requests)
        },
        "results": {
            "success_count": success_count,
            "failure_count": failure_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model_load_time_seconds": round(load_time, 2),
            "inference_time_seconds": round(inference_time, 2),
            "total_time_seconds": round(total_time, 2),
            "throughput_tokens_per_sec": throughput_tokens_per_sec,
            "throughput_requests_per_sec": throughput_requests_per_sec
        },
        "configuration": {
            "max_model_len": 4096,
            "gpu_memory_utilization": 0.90,
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2000
        }
    }
    
    metadata_file = f"benchmarks/metadata/llama32-1b-5k-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    Path("benchmarks/metadata").mkdir(parents=True, exist_ok=True)
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Saved metadata to {metadata_file}")
    print()
    
    # Comparison
    print("📊 COMPARISON TO OTHER MODELS (5K batch):")
    print()
    print("| Model | Throughput | Time | Success Rate |")
    print("|-------|------------|------|--------------|")
    print(f"| Gemma 3 4B  | 2,511 tok/s | 36.8 min | 100% |")
    print(f"| Qwen 3 4B   | 1,533 tok/s | ~60 min  | 100% (est) |")
    print(f"| Llama 3.2 1B | {throughput_tokens_per_sec:,} tok/s | {inference_time/60:.1f} min | {success_count/len(requests)*100:.1f}% |")
    print()
    
    if throughput_tokens_per_sec > 0:
        vs_gemma = ((throughput_tokens_per_sec - 2511) / 2511) * 100
        if vs_gemma > 0:
            print(f"✅ Llama 3.2 1B is {vs_gemma:.1f}% FASTER than Gemma 3 4B!")
        else:
            print(f"⚠️  Llama 3.2 1B is {abs(vs_gemma):.1f}% slower than Gemma 3 4B")
    
    print()
    print("✅ TEST COMPLETE!")

if __name__ == "__main__":
    main()

