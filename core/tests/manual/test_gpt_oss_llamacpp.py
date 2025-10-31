#!/usr/bin/env python3
"""
Test GPT-OSS 20B with llama-cpp-python - Single Candidate
Strategy: Use llama.cpp (proven to work from Reddit) with GGUF quantization
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
    except Exception:
        return 0

def main():
    print("=" * 80)
    print("GPT-OSS 20B - LLAMA.CPP SINGLE CANDIDATE TEST")
    print("=" * 80)
    print("Strategy: Use llama-cpp-python with GGUF Q4_K_M quantization")
    print("Based on Reddit success story: RTX 4080 16GB can run GPT-OSS 120B!")
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

    # Load model with llama.cpp
    print("\n🚀 Loading GPT-OSS 20B with llama.cpp...")
    print("Settings:")
    print("  - Model: unsloth/gpt-oss-20b-GGUF (Q4_K_M)")
    print("  - GPU Layers: 999 (offload all to GPU)")
    print("  - Context: 4096")
    print("  - Flash Attention: Enabled")
    print("\nThis will download ~11.6 GB GGUF model...")

    start_load = time.time()

    try:
        from llama_cpp import Llama

        # Load with llama.cpp - proven to work from Reddit
        llm = Llama(
            model_path="hf://unsloth/gpt-oss-20b-GGUF/gpt-oss-20b-Q4_K_M.gguf",
            n_gpu_layers=-1,  # Offload all layers to GPU
            n_ctx=4096,  # Context window
            flash_attn=True,  # Flash attention for speed
            verbose=True,  # Show loading progress
        )

        load_time = time.time() - start_load
        loaded_mem = get_gpu_memory()
        mem_used = loaded_mem - initial_mem

        print(f"\n✅ Model loaded in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {loaded_mem} MB (+{mem_used} MB)")
        print(f"📊 Available: {16376 - loaded_mem} MB")

        # Process 1 candidate
        print("\n⚡ Processing 1 candidate...")

        # Format prompt
        prompt = f"{system_prompt}\n\n{user_prompt}"

        start_gen = time.time()

        # Generate with llama.cpp
        output = llm(
            prompt,
            max_tokens=2000,
            temperature=0.7,
            top_p=0.9,
            echo=False,
        )

        gen_time = time.time() - start_gen

        # Extract result
        response = output["choices"][0]["text"]
        prompt_tokens = output["usage"]["prompt_tokens"]
        completion_tokens = output["usage"]["completion_tokens"]
        total_tokens = output["usage"]["total_tokens"]

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
                "model": "unsloth/gpt-oss-20b-GGUF",
                "quantization": "Q4_K_M",
                "backend": "llama.cpp",
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

        output_file = "gpt_oss_llamacpp_single_result.jsonl"
        with open(output_file, "w") as f:
            f.write(json.dumps(result) + "\n")

        print(f"\n✅ Result saved to {output_file}")

        # Final memory check
        final_mem = get_gpu_memory()
        print(f"\n📊 Final GPU Memory: {final_mem} MB")

        print("\n" + "=" * 80)
        print("✅ SUCCESS - GPT-OSS 20B works with llama.cpp!")
        print("=" * 80)
        print(f"Model Size: ~{mem_used} MB")
        print(f"Load Time: {load_time:.1f}s")
        print(f"Generation Time: {gen_time:.1f}s")
        print(f"Throughput: {total_tokens / gen_time:.1f} tokens/s")
        print("=" * 80)

        return 0

    except ImportError:
        print("\n❌ ERROR: llama-cpp-python not installed")
        print("\nInstall with:")
        print("  pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121")
        return 1

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
            print("1. Use Q2_K quantization (smaller)")
            print("2. Reduce context: n_ctx=2048")
            print("3. Offload some layers to CPU: n_gpu_layers=30")

        else:
            print("⚠️  Unknown Error")
            print("\nFull error:")
            import traceback
            traceback.print_exc()

        print("=" * 80)

        return 1

if __name__ == "__main__":
    sys.exit(main())

