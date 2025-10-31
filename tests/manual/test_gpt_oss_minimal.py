#!/usr/bin/env python3
"""
Minimal GPT-OSS 20B test - lowest possible settings
"""

import sys

print("Starting minimal GPT-OSS test...", file=sys.stderr, flush=True)

try:
    from vllm import LLM, SamplingParams
    print("✅ vLLM imported", file=sys.stderr, flush=True)

    print("\n🚀 Loading GPT-OSS 20B GGUF (Q2_K - smallest quantization)", file=sys.stderr, flush=True)
    print("Settings: Minimal everything to just test if it loads", file=sys.stderr, flush=True)

    # Try with absolute minimal settings
    llm = LLM(
        model="unsloth/gpt-oss-20b-GGUF",
        # Specify the Q2_K quantization file explicitly
        # tokenizer="openai/gpt-oss-20b",  # Use base model tokenizer
        gpu_memory_utilization=0.85,  # Lower than default
        max_model_len=512,  # Very small context
        disable_log_stats=False,  # Enable logs to see what's happening
        enforce_eager=True,  # Disable CUDA graphs to save memory
        max_num_seqs=1,  # Only 1 sequence at a time
    )

    print("\n✅ Model loaded!", file=sys.stderr, flush=True)

    # Try simplest possible generation
    print("\n⚡ Testing generation...", file=sys.stderr, flush=True)
    sampling_params = SamplingParams(
        temperature=1.0,
        top_p=1.0,
        top_k=0,
        max_tokens=10,  # Very short
    )

    outputs = llm.generate(["Hello"], sampling_params)

    print("\n✅ SUCCESS!", file=sys.stderr, flush=True)
    print(f"Output: {outputs[0].outputs[0].text}", file=sys.stderr, flush=True)

except Exception as e:
    print(f"\n❌ ERROR: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

