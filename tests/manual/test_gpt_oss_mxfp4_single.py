#!/usr/bin/env python3
"""
Test GPT-OSS 20B with native MXFP4 quantization - Single Candidate
Strategy: Use model's built-in MXFP4 quantization (4-bit microscaling floating point)
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
    print("GPT-OSS 20B - SINGLE CANDIDATE TEST (MXFP4 QUANTIZATION)")
    print("=" * 80)
    print("Strategy: Use model's native MXFP4 quantization")
    print("MXFP4 = 4-bit microscaling floating point, ~75% memory reduction vs FP16")
    print("=" * 80)

    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    available = 16376 - initial_mem
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    print(f"📊 Available: {available} MB")

    if available < 8000:
        print(f"\n⚠️  WARNING: Only {available} MB available!")
        print("This may not be enough for GPT-OSS 20B even with MXFP4.")
        print("Proceeding anyway...")

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

    # Load model with native MXFP4 quantization
    print("\n🚀 Loading GPT-OSS 20B with native MXFP4 quantization...")
    print("Settings:")
    print("  - Model: openai/gpt-oss-20b")
    print("  - Quantization: mxfp4 (model's native quantization)")
    print("  - GPU Memory: 0.85 (conservative)")
    print("  - Max Context: 4096")
    print("  - Eager Mode: True (no CUDA graphs)")
    print("  - Max Sequences: 1 (only 1 at a time)")
    print("\nThis will take 1-2 minutes to download and load...")

    start_load = time.time()

    try:
        from vllm import LLM, SamplingParams

        # Load with native MXFP4 quantization
        llm = LLM(
            model="openai/gpt-oss-20b",
            quantization="mxfp4",  # Use model's native quantization
            gpu_memory_utilization=0.85,  # Conservative
            max_model_len=4096,  # Reasonable context
            enforce_eager=True,  # No CUDA graphs to save memory
            max_num_seqs=1,  # Only 1 sequence at a time
            disable_log_stats=False,  # Show logs
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
            max_tokens=2000,  # Match batch settings
        )

        # Format prompt
        prompt = f"{system_prompt}\n\n{user_prompt}"

        start_gen = time.time()
        outputs = llm.generate([prompt], sampling_params)
        gen_time = time.time() - start_gen

        # Extract result
        output = outputs[0]
        response = output.outputs[0].text

        # Count tokens (approximate)
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
                "quantization": "mxfp4",
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

        output_file = "gpt_oss_mxfp4_single_result.jsonl"
        with open(output_file, "w") as f:
            f.write(json.dumps(result) + "\n")

        print(f"\n✅ Result saved to {output_file}")

        # Final memory check
        final_mem = get_gpu_memory()
        print(f"\n📊 Final GPU Memory: {final_mem} MB")

        print("\n" + "=" * 80)
        print("✅ SUCCESS - GPT-OSS 20B with MXFP4 works!")
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
            print("\nThe model is too large even with MXFP4 quantization.")
            print("\nOptions:")
            print("1. Try GGUF quantization (Q4_K_M or Q2_K)")
            print("2. Use a smaller model (13B or 7B)")
            print("3. Reduce max_model_len to 2048")
            print("4. Reduce gpu_memory_utilization to 0.75")

        elif "triton" in error_msg.lower():
            print("⚠️  Triton Kernel Error")
            print("\nMissing or incompatible Triton kernels for MXFP4.")
            print("\nOptions:")
            print("1. Install triton_kernels: pip install triton-kernels")
            print("2. Try GGUF version: unsloth/gpt-oss-20b-GGUF")
            print("3. Use llama.cpp instead of vLLM")

        else:
            print("⚠️  Unknown Error")
            print("\nFull error:")
            import traceback
            traceback.print_exc()

        print("=" * 80)

        return 1

if __name__ == "__main__":
    sys.exit(main())

