#!/usr/bin/env python3
"""
OLMo 2 7B - 5K Candidates Benchmark with CPU Offload

This tests OLMo 2 7B on the same 5K dataset used for Gemma 3 4B benchmarking.
Uses CPU offload to fit the 7B model on RTX 4080 16GB.

Expected performance:
- Load time: ~80 seconds
- Throughput: ~15-25 tok/s (slower than 4B models due to CPU offload)
- Total time: ~2-3 hours for 5K requests
"""

import json
import time
from pathlib import Path
from vllm import LLM, SamplingParams
from datetime import datetime

def main():
    print("=" * 80)
    print("OLMO 2 7B - 5K CANDIDATES BENCHMARK (WITH CPU OFFLOAD)")
    print("=" * 80)
    print(f"Model: allenai/OLMo-2-1124-7B-Instruct")
    print(f"Dataset: batch_5k.jsonl (5,000 candidate evaluations)")
    print(f"CPU Offload: 8 GB")
    print(f"GPU Memory Util: 0.85")
    print("=" * 80)
    print()
    
    # Paths
    input_file = Path("batch_5k.jsonl")
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_file = Path(f"benchmarks/raw/olmo2-7b-5k-{timestamp}.jsonl")
    metadata_file = Path(f"benchmarks/metadata/olmo2-7b-5k-{timestamp}.json")
    
    # Create output directories
    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Validate input file
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Load requests
    print(f"📄 Loading requests from {input_file}...")
    requests = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))
    
    print(f"✅ Loaded {len(requests)} requests")
    print()
    
    # Load model with CPU offload
    print("🚀 Loading OLMo 2 7B with CPU offload...")
    print("   This will take ~80 seconds...")
    start_load = time.time()
    
    llm = LLM(
        model="allenai/OLMo-2-1124-7B-Instruct",
        max_model_len=4096,
        gpu_memory_utilization=0.85,
        cpu_offload_gb=8,  # Offload 8GB to CPU RAM
        swap_space=4,      # 4GB swap for KV cache
        max_num_seqs=16,   # Fewer concurrent sequences for 7B model
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        disable_log_stats=True
    )
    
    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f}s")
    print()
    
    # Prepare prompts
    print("🧪 Preparing prompts...")
    prompts = []
    custom_ids = []
    
    for req in requests:
        custom_ids.append(req['custom_id'])
        
        # Extract messages from request body
        messages = req['body']['messages']
        
        # Format as chat template (OLMo uses ChatML format)
        prompt = ""
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == 'user':
                prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        
        prompts.append(prompt)
    
    print(f"✅ Prepared {len(prompts)} prompts")
    print()
    
    # Run inference
    print(f"🔥 Running inference on {len(prompts)} requests...")
    print(f"   Expected time: ~2-3 hours")
    print(f"   Output will be saved incrementally to: {output_file}")
    print()
    
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000
    )
    
    start_inference = time.time()
    
    # Process in batches of 100 to save incrementally
    batch_size = 100
    all_results = []
    
    for i in range(0, len(prompts), batch_size):
        batch_prompts = prompts[i:i+batch_size]
        batch_ids = custom_ids[i:i+batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(prompts) + batch_size - 1)//batch_size} ({i+1}-{min(i+batch_size, len(prompts))})...")
        
        batch_start = time.time()
        outputs = llm.generate(batch_prompts, sampling_params)
        batch_time = time.time() - batch_start
        
        # Save results for this batch
        batch_results = []
        for custom_id, output in zip(batch_ids, outputs):
            result = {
                "custom_id": custom_id,
                "response": {
                    "status_code": 200,
                    "body": {
                        "id": f"chatcmpl-{custom_id}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": "allenai/OLMo-2-1124-7B-Instruct",
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
            batch_results.append(result)
            all_results.append(result)
        
        # Save incrementally
        with open(output_file, 'a') as f:
            for result in batch_results:
                f.write(json.dumps(result) + '\n')
        
        # Calculate batch metrics
        batch_tokens = sum(
            len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
            for output in outputs
        )
        batch_throughput = batch_tokens / batch_time
        
        print(f"  ✅ Batch complete in {batch_time:.1f}s ({batch_throughput:.1f} tok/s)")
        print(f"  📁 Saved {len(batch_results)} results to {output_file}")
        print()
    
    inference_time = time.time() - start_inference
    total_time = load_time + inference_time
    
    # Calculate final metrics
    total_tokens = sum(
        result['response']['body']['usage']['total_tokens']
        for result in all_results
    )
    throughput = total_tokens / inference_time
    
    print()
    print("=" * 80)
    print("📊 BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Model: allenai/OLMo-2-1124-7B-Instruct")
    print(f"Requests: {len(all_results)}")
    print(f"Load Time: {load_time:.1f}s")
    print(f"Inference Time: {inference_time:.1f}s ({inference_time/60:.1f} minutes)")
    print(f"Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Throughput: {throughput:.1f} tok/s")
    print(f"Requests/sec: {len(all_results)/inference_time:.2f}")
    print()
    print(f"📁 Results saved to: {output_file}")
    print("=" * 80)
    
    # Save metadata
    metadata = {
        "test_id": f"olmo2-7b-5k-{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "model": "allenai/OLMo-2-1124-7B-Instruct",
        "config": {
            "max_model_len": 4096,
            "gpu_memory_utilization": 0.85,
            "cpu_offload_gb": 8.0,
            "swap_space": 4,
            "max_num_seqs": 16,
            "enable_prefix_caching": True,
            "enable_chunked_prefill": True
        },
        "test": {
            "num_requests": len(all_results),
            "input_file": str(input_file),
            "output_file": str(output_file)
        },
        "results": {
            "load_time_sec": round(load_time, 2),
            "inference_time_sec": round(inference_time, 2),
            "total_time_sec": round(total_time, 2),
            "total_tokens": total_tokens,
            "throughput_tokens_per_sec": round(throughput, 2),
            "throughput_requests_per_sec": round(len(all_results)/inference_time, 2)
        },
        "status": "completed"
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"📁 Metadata saved to: {metadata_file}")
    print()
    print("✅ Benchmark complete!")

if __name__ == "__main__":
    main()

