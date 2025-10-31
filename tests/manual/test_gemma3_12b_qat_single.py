#!/usr/bin/env python3
"""
Test Gemma 3 12B Quantized (Q4_0 GGUF) with a single candidate
"""

import json
import subprocess
import time


def get_gpu_memory():
    """Get current GPU memory usage in MB"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, check=True
        )
        return int(result.stdout.strip())
    except Exception:
        return 0

def main():
    print("=" * 80)
    print("GEMMA 3 12B QUANTIZED (Q4_0) - SINGLE CANDIDATE TEST")
    print("=" * 80)
    print("Model: google/gemma-3-12b-it-qat-q4_0-gguf")
    print("=" * 80)

    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    print(f"📊 Available: {16376 - initial_mem} MB")

    # Load one candidate from batch file
    print("\n📄 Loading 1 candidate from batch_5k.jsonl...")
    with open("batch_5k.jsonl") as f:
        candidate = json.loads(f.readline())

    # Extract the prompt
    messages = candidate["body"]["messages"]
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

    print(f"✅ Loaded candidate: {candidate['custom_id']}")

    # Load model
    print("\n🚀 Loading Gemma 3 12B Quantized (Q4_0 GGUF)...")
    print("Settings:")
    print("  - Model: models/gemma-3-12b-qat-q4_0/gemma-3-12b-it-q4_0.gguf")
    print("  - GPU Memory: 0.90")
    print("  - Max Context: 8192")
    print("\nLoading model...")

    start_load = time.time()

    try:
        from vllm import LLM, SamplingParams

        # Load Gemma 3 12B Quantized GGUF from local file
        llm = LLM(
            model="models/gemma-3-12b-qat-q4_0/gemma-3-12b-it-q4_0.gguf",
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            disable_log_stats=False,
        )

        load_time = time.time() - start_load
        load_mem = get_gpu_memory()

        print(f"\n✅ Model loaded in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {load_mem} MB")
        print(f"📊 Model size: {load_mem - initial_mem} MB")

        # Generate
        print("\n🔄 Generating response...")

        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=2000,
        )

        start_gen = time.time()
        outputs = llm.generate([prompt], sampling_params)
        gen_time = time.time() - start_gen

        # Get result
        output = outputs[0]
        response = output.outputs[0].text
        prompt_tokens = len(output.prompt_token_ids)
        completion_tokens = len(output.outputs[0].token_ids)

        print(f"\n✅ Generation complete in {gen_time:.1f}s")
        print(f"📊 Prompt tokens: {prompt_tokens}")
        print(f"📊 Completion tokens: {completion_tokens}")
        print(f"📊 Total tokens: {prompt_tokens + completion_tokens}")
        print(f"📊 Throughput: {(prompt_tokens + completion_tokens) / gen_time:.1f} tok/s")

        final_mem = get_gpu_memory()
        print(f"📊 Final GPU Memory: {final_mem} MB")

        print("\n" + "=" * 80)
        print("RESPONSE:")
        print("=" * 80)
        print(response[:500] + "..." if len(response) > 500 else response)
        print("=" * 80)

        print("\n✅ SUCCESS - Model works!")
        print(f"Total time: {time.time() - start_load:.1f}s")

    except Exception as e:
        error_mem = get_gpu_memory()
        print(f"\n❌ ERROR: {e}")
        print(f"📊 GPU Memory at error: {error_mem} MB")
        raise

if __name__ == "__main__":
    main()

