#!/usr/bin/env python3
"""
GPT-OSS 20B Load Test

Tests if we can load OpenAI's GPT-OSS 20B model (quantized) on RTX 4080 16GB.

Usage:
    python test_gpt_oss_load.py
"""

import time
import subprocess

def get_gpu_memory():
    """Get current GPU memory usage."""
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
        capture_output=True,
        text=True
    )
    return int(result.stdout.strip())

def main():
    print("=" * 80)
    print("GPT-OSS 20B LOAD TEST - vLLM Native + GGUF")
    print("=" * 80)
    print("Model: unsloth/gpt-oss-20b-GGUF (Q4_K_M quantization)")
    print("GPU: RTX 4080 16GB")
    print("Note: Q4_K_M = 11.6 GB (fits with 4.4 GB headroom)")
    print("=" * 80)
    
    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    print(f"\n📊 Initial GPU Memory: {initial_mem} MB")
    
    print("\n🚀 Loading model with vLLM...")
    print("This may take 30-60 seconds...\n")
    
    start_time = time.time()
    
    try:
        from vllm import LLM, SamplingParams
        
        # Load GGUF model with vLLM
        # Using Unsloth's fixed GGUF version (Q4_K_M = 11.6 GB)
        # vLLM docs: "You can use GGUF model directly through the LLM entrypoint"
        llm = LLM(
            model="unsloth/gpt-oss-20b-GGUF",
            # vLLM will auto-detect GGUF format
            gpu_memory_utilization=0.90,
            max_model_len=4096,  # GPT-OSS supports up to 128K
            disable_log_stats=True,
        )
        
        load_time = time.time() - start_time
        loaded_mem = get_gpu_memory()
        mem_used = loaded_mem - initial_mem
        
        print(f"✅ Model loaded successfully in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {loaded_mem} MB (+{mem_used} MB)")
        print(f"📊 Total VRAM: 16,376 MB")
        print(f"📊 Available: {16376 - loaded_mem} MB")
        
        # Try a simple generation
        print("\n⚡ Testing generation...")
        
        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=100,
        )
        
        prompt = "What is the capital of France?"
        
        gen_start = time.time()
        outputs = llm.generate([prompt], sampling_params)
        gen_time = time.time() - gen_start
        
        output_text = outputs[0].outputs[0].text
        output_tokens = len(outputs[0].outputs[0].token_ids)
        
        print(f"✅ Generation successful in {gen_time:.1f}s")
        print(f"📊 Tokens generated: {output_tokens}")
        print(f"📊 Throughput: {output_tokens / gen_time:.1f} tok/s")
        print(f"\n💬 Output: {output_text[:200]}...")
        
        final_mem = get_gpu_memory()
        print(f"\n📊 Final GPU Memory: {final_mem} MB")
        
        print("\n" + "=" * 80)
        print("✅ SUCCESS - GPT-OSS 20B works on RTX 4080!")
        print("=" * 80)
        print(f"Model load time: {load_time:.1f}s")
        print(f"Memory used: {mem_used} MB")
        print(f"Available headroom: {16376 - final_mem} MB")
        print(f"Generation throughput: {output_tokens / gen_time:.1f} tok/s")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n" + "=" * 80)
        print("TROUBLESHOOTING")
        print("=" * 80)
        
        if "GGUF" in str(e) or "quantization" in str(e):
            print("⚠️  vLLM may not support GGUF quantization directly")
            print("\nOptions:")
            print("1. Try the original OpenAI model: openai/gpt-oss-20b")
            print("2. Use llama.cpp instead of vLLM")
            print("3. Try a different quantization format (AWQ, GPTQ)")
            
        elif "out of memory" in str(e).lower() or "oom" in str(e).lower():
            print("⚠️  Out of memory error")
            print("\nOptions:")
            print("1. Try smaller quantization (Q2_K instead of Q4_K_M)")
            print("2. Reduce gpu_memory_utilization to 0.85")
            print("3. Reduce max_model_len to 2048")
            
        else:
            print(f"⚠️  Unexpected error: {e}")
            print("\nCheck:")
            print("1. Model name is correct")
            print("2. vLLM version supports this model")
            print("3. GPU drivers are up to date")
        
        print("=" * 80)
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

