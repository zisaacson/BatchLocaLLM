#!/usr/bin/env python3
"""
Benchmark Gemma 3 12B on 5K candidates
Strategy: Use vLLM batch processing with incremental result saving
"""

import sys
import time
import json
import subprocess
from datetime import datetime
from pathlib import Path

def get_gpu_memory():
    """Get current GPU memory usage in MB"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            check=True
        )
        return int(result.stdout.strip())
    except:
        return 0

def save_result(result, output_file):
    """Save a single result incrementally"""
    with open(output_file, "a") as f:
        f.write(json.dumps(result) + "\n")

def main():
    print("=" * 80)
    print("GEMMA 3 12B QUANTIZED (Q4_0) - 5K CANDIDATES BENCHMARK")
    print("=" * 80)
    print("Model: google/gemma-3-12b-it-qat-q4_0-gguf")
    print("Candidates: 5,000")
    print("Strategy: Batch processing with incremental saves")
    print("=" * 80)
    
    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    available = 16376 - initial_mem
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    print(f"📊 Available: {available} MB")
    
    # Load all 5K candidates
    print(f"\n📄 Loading 5K candidates from batch_5k.jsonl...")
    requests = []
    with open("batch_5k.jsonl") as f:
        for line in f:
            requests.append(json.loads(line))
    
    total_requests = len(requests)
    print(f"✅ Loaded {total_requests} candidates")
    
    # Prepare output file
    output_file = f"gemma3_12b_5k_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
    print(f"📝 Results will be saved to: {output_file}")
    
    # Load model
    print("\n🚀 Loading Gemma 3 12B Quantized (Q4_0 GGUF)...")
    print("Settings:")
    print("  - Model: google/gemma-3-12b-it-qat-q4_0-gguf")
    print("  - GPU Memory: 0.90")
    print("  - Max Context: 8192")
    print("  - Batch Size: All 5K at once")
    print("\nLoading model...")

    start_load = time.time()

    try:
        from vllm import LLM, SamplingParams

        # Load Gemma 3 12B Quantized GGUF
        llm = LLM(
            model="google/gemma-3-12b-it-qat-q4_0-gguf",
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            disable_log_stats=False,
        )
        
        load_time = time.time() - start_load
        loaded_mem = get_gpu_memory()
        mem_used = loaded_mem - initial_mem
        
        print(f"\n✅ Model loaded in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {loaded_mem} MB (+{mem_used} MB)")
        print(f"📊 Available: {16376 - loaded_mem} MB")
        
        # Prepare prompts
        print(f"\n⚡ Preparing {total_requests} prompts...")
        prompts = []
        custom_ids = []
        
        for request in requests:
            custom_id = request["custom_id"]
            messages = request["body"]["messages"]
            system_prompt = messages[0]["content"]
            user_prompt = messages[1]["content"]
            
            # Format prompt for Gemma
            prompt = f"{system_prompt}\n\n{user_prompt}"
            prompts.append(prompt)
            custom_ids.append(custom_id)
        
        print(f"✅ Prepared {len(prompts)} prompts")
        
        # Set sampling parameters
        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=2000,
        )
        
        # Process all candidates in one batch
        print(f"\n⚡ Processing {total_requests} candidates in batch...")
        print("This will take several minutes...")
        
        start_gen = time.time()
        outputs = llm.generate(prompts, sampling_params)
        gen_time = time.time() - start_gen
        
        print(f"\n✅ Batch generation complete in {gen_time:.1f}s ({gen_time/60:.1f} minutes)")
        
        # Save results incrementally
        print(f"\n💾 Saving results to {output_file}...")
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        
        for i, output in enumerate(outputs):
            custom_id = custom_ids[i]
            response = output.outputs[0].text
            
            prompt_tokens = len(output.prompt_token_ids)
            completion_tokens = len(output.outputs[0].token_ids)
            tokens = prompt_tokens + completion_tokens
            
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            total_tokens += tokens
            
            result = {
                "custom_id": custom_id,
                "response": {
                    "body": {
                        "choices": [{
                            "message": {
                                "content": response
                            }
                        }]
                    }
                },
                "metadata": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": tokens,
                }
            }
            
            save_result(result, output_file)
            
            # Progress update every 500 candidates
            if (i + 1) % 500 == 0:
                print(f"  Saved {i + 1}/{total_requests} results...")
        
        print(f"✅ All {total_requests} results saved")
        
        # Calculate statistics
        avg_prompt_tokens = total_prompt_tokens / total_requests
        avg_completion_tokens = total_completion_tokens / total_requests
        avg_total_tokens = total_tokens / total_requests
        throughput = total_tokens / gen_time
        
        # Final memory check
        final_mem = get_gpu_memory()
        
        # Print summary
        print("\n" + "=" * 80)
        print("✅ BENCHMARK COMPLETE")
        print("=" * 80)
        print(f"Model: google/gemma-3-12b-it-qat-q4_0-gguf")
        print(f"Candidates: {total_requests}")
        print(f"Model Load Time: {load_time:.1f}s")
        print(f"Generation Time: {gen_time:.1f}s ({gen_time/60:.1f} minutes)")
        print(f"Total Time: {(load_time + gen_time):.1f}s ({(load_time + gen_time)/60:.1f} minutes)")
        print("-" * 80)
        print(f"Total Prompt Tokens: {total_prompt_tokens:,}")
        print(f"Total Completion Tokens: {total_completion_tokens:,}")
        print(f"Total Tokens: {total_tokens:,}")
        print("-" * 80)
        print(f"Avg Prompt Tokens/Candidate: {avg_prompt_tokens:.1f}")
        print(f"Avg Completion Tokens/Candidate: {avg_completion_tokens:.1f}")
        print(f"Avg Total Tokens/Candidate: {avg_total_tokens:.1f}")
        print("-" * 80)
        print(f"Throughput: {throughput:.1f} tokens/s")
        print(f"Time per Candidate: {gen_time / total_requests:.2f}s")
        print("-" * 80)
        print(f"GPU Memory Used: {mem_used} MB")
        print(f"Final GPU Memory: {final_mem} MB")
        print("=" * 80)
        print(f"\n📁 Results saved to: {output_file}")
        
        # Save benchmark summary
        summary = {
            "model": "google/gemma-2-2b-it",
            "total_candidates": total_requests,
            "load_time_seconds": load_time,
            "generation_time_seconds": gen_time,
            "total_time_seconds": load_time + gen_time,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "avg_prompt_tokens_per_candidate": avg_prompt_tokens,
            "avg_completion_tokens_per_candidate": avg_completion_tokens,
            "avg_total_tokens_per_candidate": avg_total_tokens,
            "throughput_tokens_per_second": throughput,
            "time_per_candidate_seconds": gen_time / total_requests,
            "gpu_memory_used_mb": mem_used,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        summary_file = f"gemma3_12b_5k_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Summary saved to: {summary_file}")
        
        return 0
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")
        
        # Check memory at error
        error_mem = get_gpu_memory()
        print(f"\n📊 GPU Memory at error: {error_mem} MB")
        
        print("\n" + "=" * 80)
        print("TROUBLESHOOTING")
        print("=" * 80)
        
        if "out of memory" in error_msg.lower() or "oom" in error_msg.lower():
            print("⚠️  Out of Memory Error")
            print("\nTry:")
            print("1. Reduce gpu_memory_utilization to 0.85")
            print("2. Reduce max_model_len to 4096")
            print("3. Process in smaller batches (1000 at a time)")
            
        else:
            print("⚠️  Unknown Error")
            print("\nFull error:")
            import traceback
            traceback.print_exc()
        
        print("=" * 80)
        
        return 1

if __name__ == "__main__":
    sys.exit(main())

