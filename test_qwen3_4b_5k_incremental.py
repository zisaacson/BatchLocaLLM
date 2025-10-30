#!/usr/bin/env python3
"""
Test Qwen 3 4B with 5K batch - INCREMENTAL SAVING VERSION
Saves results after every batch to prevent data loss.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from vllm import LLM, SamplingParams
from memory_optimizer import MemoryOptimizer

def main():
    print("=" * 80)
    print("🧪 QWEN 3 4B - 5K BATCH TEST (INCREMENTAL SAVE)")
    print("=" * 80)
    print()

    # Configuration
    model_id = "Qwen/Qwen3-4B-Instruct-2507"
    input_file = "batch_5k.jsonl"
    output_file = "qwen3_4b_5k_results.jsonl"
    checkpoint_file = "qwen3_4b_5k_checkpoint.txt"
    
    # Batch size for incremental processing
    BATCH_SIZE = 100  # Process 100 at a time, save after each batch

    print(f"Model: {model_id}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print(f"Batch size: {BATCH_SIZE} (incremental)")
    print()

    # Check for existing checkpoint
    start_idx = 0
    if Path(checkpoint_file).exists():
        with open(checkpoint_file) as f:
            start_idx = int(f.read().strip())
        print(f"📍 Resuming from checkpoint: {start_idx}")
        print()

    # Get optimized configuration
    print("🧠 Optimizing memory configuration...")
    optimizer = MemoryOptimizer()
    config = optimizer.optimize_config(model_id, max_model_len=4096)
    print(f"✅ Using gpu_memory_utilization={config.gpu_memory_utilization}")
    if config.enforce_eager:
        print(f"✅ Using enforce_eager={config.enforce_eager}")
    print()
    
    # Load requests
    print("📂 Loading requests...")
    requests = []
    with open(input_file) as f:
        for line in f:
            requests.append(json.loads(line))
    
    total_requests = len(requests)
    print(f"✅ Loaded {total_requests} requests")
    print(f"✅ Starting from index {start_idx}")
    print()
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req["body"]["messages"]
        # Format as chat prompt
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n\n"
        prompt += "Assistant:"
        prompts.append(prompt)
    
    # Initialize model
    print("🔧 Initializing model...")
    start_load = time.time()
    
    vllm_kwargs = {
        "model": model_id,
        "gpu_memory_utilization": config.gpu_memory_utilization,
        "max_model_len": 4096,
        "trust_remote_code": True,
    }
    
    if config.enforce_eager:
        vllm_kwargs["enforce_eager"] = config.enforce_eager
    if config.max_num_seqs:
        vllm_kwargs["max_num_seqs"] = config.max_num_seqs
    if config.kv_cache_dtype:
        vllm_kwargs["kv_cache_dtype"] = config.kv_cache_dtype

    llm = LLM(**vllm_kwargs)
    
    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f} seconds")
    print()
    
    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )
    
    # Process in batches
    print("⚡ Running inference in batches...")
    print()
    
    total_start = time.time()
    success_count = 0
    failure_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    # Open output file in append mode
    output_mode = 'a' if start_idx > 0 else 'w'
    
    for batch_start in range(start_idx, total_requests, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_requests)
        batch_prompts = prompts[batch_start:batch_end]
        batch_requests = requests[batch_start:batch_end]
        
        print(f"📦 Processing batch {batch_start}-{batch_end} ({len(batch_prompts)} requests)...")
        batch_start_time = time.time()
        
        # Generate for this batch
        outputs = llm.generate(batch_prompts, sampling_params)
        
        batch_time = time.time() - batch_start_time
        print(f"   ✅ Batch complete in {batch_time:.1f}s ({batch_time/len(batch_prompts):.2f}s per request)")
        
        # Save results immediately
        with open(output_file, output_mode) as f:
            for i, output in enumerate(outputs):
                custom_id = batch_requests[i]["custom_id"]
                
                if output.outputs and len(output.outputs) > 0:
                    success_count += 1
                    text = output.outputs[0].text
                    finish_reason = output.outputs[0].finish_reason
                    
                    # Count tokens
                    prompt_tok = len(output.prompt_token_ids)
                    completion_tok = len(output.outputs[0].token_ids)
                    
                    prompt_tokens += prompt_tok
                    completion_tokens += completion_tok
                    
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
                
                f.write(json.dumps(result) + '\n')
        
        # Update checkpoint
        with open(checkpoint_file, 'w') as f:
            f.write(str(batch_end))
        
        # Switch to append mode after first batch
        output_mode = 'a'
        
        # Progress update
        elapsed = time.time() - total_start
        processed = batch_end - start_idx
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = total_requests - batch_end
        eta = remaining / rate if rate > 0 else 0
        
        print(f"   📊 Progress: {batch_end}/{total_requests} ({100*batch_end/total_requests:.1f}%)")
        print(f"   ⏱️  Rate: {rate:.1f} req/s | ETA: {eta/60:.1f} min")
        print()
    
    total_time = time.time() - total_start
    
    # Final statistics
    print("=" * 80)
    print("✅ BENCHMARK COMPLETE")
    print("=" * 80)
    print()
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"Total tokens: {prompt_tokens + completion_tokens:,}")
    print(f"  - Prompt tokens: {prompt_tokens:,}")
    print(f"  - Completion tokens: {completion_tokens:,}")
    print(f"Throughput: {(prompt_tokens + completion_tokens) / total_time:.1f} tokens/sec")
    print()
    print(f"Results saved to: {output_file}")
    
    # Clean up checkpoint
    if Path(checkpoint_file).exists():
        Path(checkpoint_file).unlink()
        print(f"Checkpoint file removed")

if __name__ == "__main__":
    main()

