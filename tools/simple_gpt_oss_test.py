#!/usr/bin/env python3
"""Simple GPT-OSS 20B test with vLLM + GGUF"""

print("Starting GPT-OSS 20B test...")
print("Model: unsloth/gpt-oss-20b-GGUF")
print("")

try:
    from vllm import LLM, SamplingParams
    print("✅ vLLM imported successfully")
    
    print("\n🚀 Loading model (this will download ~11.6 GB)...")
    print("This may take 2-5 minutes...")
    
    llm = LLM(
        model="unsloth/gpt-oss-20b-GGUF",
        gpu_memory_utilization=0.90,
        max_model_len=4096,
        disable_log_stats=True,
    )
    
    print("\n✅ Model loaded successfully!")
    
    print("\n⚡ Testing generation...")
    sampling_params = SamplingParams(
        temperature=1.0,
        top_p=1.0,
        top_k=0,
        max_tokens=100,
    )
    
    prompt = "What is 2+2? Think step by step."
    outputs = llm.generate([prompt], sampling_params)
    
    print(f"\n💬 Prompt: {prompt}")
    print(f"💬 Response: {outputs[0].outputs[0].text}")
    
    print("\n✅ SUCCESS - GPT-OSS 20B works with vLLM!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

