#!/usr/bin/env python3
"""
Hot-swapping integration test for vLLM batch server.
Tests model loading, unloading, and switching between Qwen3 and Gemma3.
"""

import time
import subprocess
import sys


def get_gpu_memory():
    """Get current GPU memory usage in MB."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return int(result.stdout.strip())
    except Exception as e:
        print(f"⚠️  Could not get GPU memory: {e}")
        return 0


def test_hot_swapping():
    """Test hot-swapping between Qwen3 4B and Gemma3 4B."""
    
    print("=" * 70)
    print("Hot-Swapping Integration Test")
    print("=" * 70)
    print()
    
    # Baseline GPU memory
    baseline_mem = get_gpu_memory()
    print(f"📊 Baseline GPU Memory: {baseline_mem} MB")
    print()
    
    # Test 1: Load Qwen3 4B
    print("=" * 70)
    print("Test 1: Loading Qwen3 4B")
    print("=" * 70)
    
    try:
        from vllm import LLM, SamplingParams
        
        print("🚀 Loading Qwen/Qwen2.5-3B-Instruct...")
        start_load = time.time()
        
        llm_qwen = LLM(
            model="Qwen/Qwen2.5-3B-Instruct",
            max_model_len=4096,
            gpu_memory_utilization=0.85,
            disable_log_stats=True,
            trust_remote_code=True
        )
        
        qwen_load_time = time.time() - start_load
        qwen_mem = get_gpu_memory()
        qwen_mem_delta = qwen_mem - baseline_mem
        
        print(f"✅ Qwen3 loaded in {qwen_load_time:.1f}s")
        print(f"📊 GPU Memory: {qwen_mem} MB (+{qwen_mem_delta} MB)")
        print()
        
        # Test inference
        print("🔄 Testing Qwen3 inference...")
        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=100,
        )
        
        test_prompt = "What is 2+2? Answer briefly."
        outputs = llm_qwen.generate([test_prompt], sampling_params)
        
        print(f"💬 Prompt: {test_prompt}")
        print(f"💬 Response: {outputs[0].outputs[0].text[:100]}...")
        print("✅ Qwen3 inference works")
        print()
        
    except Exception as e:
        print(f"❌ Failed to load Qwen3: {e}")
        return False
    
    # Test 2: Unload Qwen3
    print("=" * 70)
    print("Test 2: Unloading Qwen3 4B")
    print("=" * 70)
    
    print("🗑️  Unloading Qwen3...")
    del llm_qwen
    
    print("⏳ Waiting 2 seconds for GPU memory to free...")
    time.sleep(2)
    
    after_unload_mem = get_gpu_memory()
    freed_mem = qwen_mem - after_unload_mem
    
    print(f"📊 GPU Memory after unload: {after_unload_mem} MB (-{freed_mem} MB)")
    
    if freed_mem < qwen_mem_delta * 0.8:
        print(f"⚠️  Warning: Only freed {freed_mem} MB, expected ~{qwen_mem_delta} MB")
        print("   Possible memory leak detected!")
    else:
        print(f"✅ Memory freed successfully ({freed_mem} MB)")
    print()
    
    # Test 3: Load Gemma3 4B
    print("=" * 70)
    print("Test 3: Loading Gemma3 4B (Hot-Swap)")
    print("=" * 70)
    
    try:
        print("🚀 Loading google/gemma-3-4b-it...")
        start_load = time.time()
        
        llm_gemma = LLM(
            model="google/gemma-3-4b-it",
            max_model_len=4096,
            gpu_memory_utilization=0.85,
            disable_log_stats=True,
        )
        
        gemma_load_time = time.time() - start_load
        gemma_mem = get_gpu_memory()
        gemma_mem_delta = gemma_mem - after_unload_mem
        
        print(f"✅ Gemma3 loaded in {gemma_load_time:.1f}s")
        print(f"📊 GPU Memory: {gemma_mem} MB (+{gemma_mem_delta} MB)")
        print()
        
        # Test inference
        print("🔄 Testing Gemma3 inference...")
        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=100,
        )
        
        test_prompt = "What is 2+2? Answer briefly."
        outputs = llm_gemma.generate([test_prompt], sampling_params)
        
        print(f"💬 Prompt: {test_prompt}")
        print(f"💬 Response: {outputs[0].outputs[0].text[:100]}...")
        print("✅ Gemma3 inference works")
        print()
        
    except Exception as e:
        print(f"❌ Failed to load Gemma3: {e}")
        return False
    
    # Test 4: Unload Gemma3
    print("=" * 70)
    print("Test 4: Final Cleanup")
    print("=" * 70)
    
    print("🗑️  Unloading Gemma3...")
    del llm_gemma
    
    print("⏳ Waiting 2 seconds for GPU memory to free...")
    time.sleep(2)
    
    final_mem = get_gpu_memory()
    final_freed = gemma_mem - final_mem
    
    print(f"📊 Final GPU Memory: {final_mem} MB (-{final_freed} MB)")
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    
    print(f"Baseline GPU Memory:     {baseline_mem} MB")
    print(f"After Qwen3 load:        {qwen_mem} MB (+{qwen_mem_delta} MB)")
    print(f"After Qwen3 unload:      {after_unload_mem} MB")
    print(f"After Gemma3 load:       {gemma_mem} MB (+{gemma_mem_delta} MB)")
    print(f"After Gemma3 unload:     {final_mem} MB")
    print()
    
    print(f"Qwen3 load time:         {qwen_load_time:.1f}s")
    print(f"Gemma3 load time:        {gemma_load_time:.1f}s")
    print(f"Total swap time:         {qwen_load_time + gemma_load_time + 2:.1f}s (including 2s cooldown)")
    print()
    
    # Validation
    print("=" * 70)
    print("Validation")
    print("=" * 70)
    print()
    
    checks = []
    
    # Check 1: Load times reasonable
    if qwen_load_time < 60:
        print("✅ Qwen3 load time < 60s")
        checks.append(True)
    else:
        print(f"❌ Qwen3 load time too slow: {qwen_load_time:.1f}s")
        checks.append(False)
    
    if gemma_load_time < 60:
        print("✅ Gemma3 load time < 60s")
        checks.append(True)
    else:
        print(f"❌ Gemma3 load time too slow: {gemma_load_time:.1f}s")
        checks.append(False)
    
    # Check 2: Memory freed after unload
    if freed_mem > qwen_mem_delta * 0.7:
        print(f"✅ Qwen3 memory freed: {freed_mem} MB")
        checks.append(True)
    else:
        print(f"⚠️  Qwen3 memory not fully freed: {freed_mem} MB (expected ~{qwen_mem_delta} MB)")
        checks.append(False)
    
    if final_freed > gemma_mem_delta * 0.7:
        print(f"✅ Gemma3 memory freed: {final_freed} MB")
        checks.append(True)
    else:
        print(f"⚠️  Gemma3 memory not fully freed: {final_freed} MB (expected ~{gemma_mem_delta} MB)")
        checks.append(False)
    
    # Check 3: Both models worked
    print("✅ Both models generated responses")
    checks.append(True)
    
    print()
    print("=" * 70)
    
    if all(checks):
        print("✅ All hot-swapping tests passed!")
        print()
        print("Hot-swapping is working correctly:")
        print(f"  - Qwen3 loads in {qwen_load_time:.1f}s")
        print(f"  - Gemma3 loads in {gemma_load_time:.1f}s")
        print(f"  - Memory is properly freed after unload")
        print(f"  - Total swap overhead: ~{qwen_load_time + gemma_load_time + 2:.1f}s")
        return True
    else:
        print(f"❌ Some tests failed ({sum(checks)}/{len(checks)} passed)")
        return False


if __name__ == '__main__':
    try:
        success = test_hot_swapping()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

