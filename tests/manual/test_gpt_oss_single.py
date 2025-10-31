#!/usr/bin/env python3
"""
GPT-OSS 20B - Single Candidate Test (Absolute Minimum)

From first principles:
- Model: 11.6 GB (Q4_K_M quantization)
- KV Cache: ~500 MB (2K context)
- Overhead: ~1 GB
- Total: ~13.1 GB (fits in 16 GB with 2.9 GB headroom)

Goal: Load model ONCE and process 1 candidate
"""

import json
import subprocess
import sys
import time


def get_gpu_memory():
    """Get current GPU memory usage in MB."""
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
        capture_output=True,
        text=True
    )
    return int(result.stdout.strip())

def main():
    print("=" * 80)
    print("GPT-OSS 20B - SINGLE CANDIDATE TEST (MINIMAL)")
    print("=" * 80)
    print("Strategy: Load model ONCE, process 1 candidate, measure memory")
    print("=" * 80)

    # Initial memory
    initial_mem = get_gpu_memory()
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    print(f"📊 Available: {16376 - initial_mem} MB")

    # Load candidate
    print("\n📄 Loading candidate from batch_5k.jsonl...")
    with open('batch_5k.jsonl') as f:
        candidate = json.loads(f.readline())

    print(f"✅ Loaded candidate: {candidate['custom_id'][:36]}")

    # Extract prompt
    messages = candidate['body']['messages']
    system_prompt = messages[0]['content']
    user_prompt = messages[1]['content']

    print(f"📝 System prompt: {len(system_prompt)} chars")
    print(f"📝 User prompt: {len(user_prompt)} chars")

    # Load model with MINIMAL settings
    print("\n🚀 Loading GPT-OSS 20B with MINIMAL settings...")
    print("Settings:")
    print("  - Model: openai/gpt-oss-20b (native, not GGUF)")
    print("  - Quantization: auto (will use mxfp4 if available)")
    print("  - GPU Memory: 0.80 (conservative)")
    print("  - Max Context: 2048 (minimal)")
    print("  - Eager Mode: True (no CUDA graphs)")
    print("  - Max Sequences: 1 (only 1 at a time)")
    print()

    start_load = time.time()

    try:
        from vllm import LLM, SamplingParams

        # MINIMAL configuration
        llm = LLM(
            model="openai/gpt-oss-20b",
            gpu_memory_utilization=0.80,  # Conservative
            max_model_len=2048,  # Minimal context
            enforce_eager=True,  # No CUDA graphs
            max_num_seqs=1,  # Only 1 sequence
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
            max_tokens=500,  # Reasonable for candidate evaluation
        )

        # Combine prompts
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        start_gen = time.time()
        outputs = llm.generate([full_prompt], sampling_params)
        gen_time = time.time() - start_gen

        response = outputs[0].outputs[0].text
        tokens = len(outputs[0].outputs[0].token_ids)

        after_gen_mem = get_gpu_memory()

        print(f"\n✅ Generation complete in {gen_time:.1f}s")
        print(f"📊 Tokens generated: {tokens}")
        print(f"📊 Throughput: {tokens/gen_time:.1f} tok/s")
        print(f"📊 GPU Memory after gen: {after_gen_mem} MB")

        # Parse response
        print("\n📄 Response:")
        print("-" * 80)
        print(response[:500])
        if len(response) > 500:
            print(f"... ({len(response) - 500} more chars)")
        print("-" * 80)

        # Try to parse as JSON
        try:
            result = json.loads(response)
            print("\n✅ Valid JSON response!")
            print(f"Recommendation: {result.get('recommendation', 'N/A')}")
            print(f"Reasoning: {result.get('reasoning', 'N/A')[:200]}...")
        except:
            print("\n⚠️  Response is not valid JSON (may need prompt tuning)")

        print("\n" + "=" * 80)
        print("SUCCESS - GPT-OSS 20B CAN PROCESS 1 CANDIDATE!")
        print("=" * 80)
        print(f"Memory used: {mem_used} MB")
        print(f"Peak memory: {after_gen_mem} MB")
        print(f"Headroom: {16376 - after_gen_mem} MB")
        print()
        print("Next steps:")
        print("1. Try batch of 10 candidates")
        print("2. Try batch of 100 candidates")
        print("3. Optimize memory settings if needed")

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")

        current_mem = get_gpu_memory()
        print(f"\n📊 GPU Memory at error: {current_mem} MB")

        print("\n" + "=" * 80)
        print("TROUBLESHOOTING")
        print("=" * 80)

        if "out of memory" in error_msg.lower() or "oom" in error_msg.lower():
            print("⚠️  Out of Memory Error")
            print("\nOptions to try:")
            print("1. Lower gpu_memory_utilization to 0.70")
            print("2. Reduce max_model_len to 1024")
            print("3. Try GGUF quantized version instead:")
            print("   model='unsloth/gpt-oss-20b-GGUF'")

        elif "quantization" in error_msg.lower() or "mxfp4" in error_msg.lower():
            print("⚠️  Quantization Error")
            print("\nThe model uses mxfp4 quantization which may need:")
            print("1. triton >= 3.4.0")
            print("2. triton_kernels package")
            print("\nOr try GGUF version:")
            print("   model='unsloth/gpt-oss-20b-GGUF'")

        else:
            print("⚠️  Unknown Error")
            print("\nFull error:")
            import traceback
            traceback.print_exc()

        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

