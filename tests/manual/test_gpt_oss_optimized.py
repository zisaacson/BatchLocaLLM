#!/usr/bin/env python3
"""
Test GPT-OSS 20B with optimized settings - Single Candidate
Strategy: Minimal memory footprint, let model use native quantization
"""

import json
import subprocess
import sys
import time
from datetime import datetime


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

def main():
    print("=" * 80)
    print("GPT-OSS 20B - OPTIMIZED SINGLE CANDIDATE TEST")
    print("=" * 80)
    print("Strategy: Minimal memory settings, native model quantization")
    print("=" * 80)

    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    available = 16376 - initial_mem
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    print(f"📊 Available: {available} MB")

    # Load 1 candidate from batch file
    print("\n📄 Loading candidate from batch_5k.jsonl...")
    with open("batch_5k.jsonl") as f:
        request = json.loads(f.readline())

    custom_id = request["custom_id"]
    messages = request["body"]["messages"]
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    print(f"✅ Loaded candidate: {custom_id}")
    print(f"📝 System prompt: {len(system_prompt)} chars")
    print(f"📝 User prompt: {len(user_prompt)} chars")

    # Load model with optimized settings
    print("\n🚀 Loading GPT-OSS 20B with optimized settings...")
    print("Settings:")
    print("  - Model: openai/gpt-oss-20b")
    print("  - Quantization: None (use model's native MXFP4)")
    print("  - GPU Memory: 0.75 (conservative)")
    print("  - Max Context: 2048 (minimal)")
    print("  - Eager Mode: True")
    print("  - Max Sequences: 1")
    print("  - Swap Space: 4GB CPU offload")
    print("\nLoading model...")

    start_load = time.time()

    try:
        from vllm import LLM, SamplingParams

        # Optimized settings for RTX 4080 16GB
        llm = LLM(
            model="openai/gpt-oss-20b",
            # Don't specify quantization - let model use native MXFP4
            gpu_memory_utilization=0.75,  # More conservative
            max_model_len=2048,  # Smaller context to save memory
            enforce_eager=True,  # No CUDA graphs
            max_num_seqs=1,  # Only 1 at a time
            swap_space=4,  # 4GB CPU swap space for overflow
            disable_log_stats=False,
            trust_remote_code=True,  # May be needed for custom model
        )

        load_time = time.time() - start_load
        loaded_mem = get_gpu_memory()
        mem_used = loaded_mem - initial_mem

        print(f"\n✅ Model loaded in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {loaded_mem} MB (+{mem_used} MB)")
        print(f"📊 Available: {16376 - loaded_mem} MB")

        # Process 1 candidate
        print("\n⚡ Processing 1 candidate...")

        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=2000,
        )

        # Format prompt
        prompt = f"{system_prompt}\n\n{user_prompt}"

        start_gen = time.time()
        outputs = llm.generate([prompt], sampling_params)
        gen_time = time.time() - start_gen

        # Extract result
        output = outputs[0]
        response = output.outputs[0].text

        # Count tokens
        prompt_tokens = len(output.prompt_token_ids)
        completion_tokens = len(output.outputs[0].token_ids)
        total_tokens = prompt_tokens + completion_tokens

        print(f"\n✅ Generation complete in {gen_time:.1f}s")
        print(f"📊 Prompt tokens: {prompt_tokens}")
        print(f"📊 Completion tokens: {completion_tokens}")
        print(f"📊 Total tokens: {total_tokens}")
        print(f"📊 Throughput: {total_tokens / gen_time:.1f} tokens/s")

        # Show response preview
        print("\n💬 Response preview (first 500 chars):")
        print("-" * 80)
        print(response[:500])
        if len(response) > 500:
            print("...")
        print("-" * 80)

        # Save result
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
                "model": "openai/gpt-oss-20b",
                "quantization": "native_mxfp4",
                "load_time_seconds": load_time,
                "generation_time_seconds": gen_time,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "throughput_tokens_per_second": total_tokens / gen_time,
                "gpu_memory_used_mb": mem_used,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        output_file = "gpt_oss_optimized_single_result.jsonl"
        with open(output_file, "w") as f:
            f.write(json.dumps(result) + "\n")

        print(f"\n✅ Result saved to {output_file}")

        # Final memory check
        final_mem = get_gpu_memory()
        print(f"\n📊 Final GPU Memory: {final_mem} MB")

        print("\n" + "=" * 80)
        print("✅ SUCCESS - GPT-OSS 20B works on RTX 4080 16GB!")
        print("=" * 80)
        print(f"Model Size: ~{mem_used} MB")
        print(f"Load Time: {load_time:.1f}s")
        print(f"Generation Time: {gen_time:.1f}s")
        print(f"Throughput: {total_tokens / gen_time:.1f} tokens/s")
        print("=" * 80)

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
            print("\nThe 20B model is too large for RTX 4080 16GB with vLLM.")
            print("\nNext steps:")
            print("1. Try llama.cpp instead (proven to work from Reddit)")
            print("2. Use GGUF Q4_K_M quantization")
            print("3. Consider using a smaller model (13B or 7B)")

        elif "triton" in error_msg.lower():
            print("⚠️  Triton Kernel Error")
            print("\nMissing triton_kernels.swiglu module.")
            print("\nNext steps:")
            print("1. Try llama.cpp instead of vLLM")
            print("2. Install missing package: pip install triton-kernels")

        else:
            print("⚠️  Unknown Error")
            print("\nFull error:")
            import traceback
            traceback.print_exc()

        print("=" * 80)

        return 1

if __name__ == "__main__":
    sys.exit(main())

