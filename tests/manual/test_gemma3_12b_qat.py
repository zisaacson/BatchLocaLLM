#!/usr/bin/env python3
"""
Test Gemma 3 12B QAT (Quantization-Aware Training) Q4_0 GGUF

This is the quantized version that should fit on RTX 4080 16GB.
Model size: 8.07 GB (vs 24 GB for full precision)
"""

import json
import time
from datetime import datetime
from pathlib import Path

from memory_optimizer import MemoryOptimizer
from vllm import LLM, SamplingParams


def main():
    print("=" * 80)
    print("🧪 GEMMA 3 12B QAT Q4_0 - QUANTIZED TEST")
    print("=" * 80)
    print()

    # Configuration
    model_id = "google/gemma-3-12b-it-qat-q4_0-gguf"
    gguf_file = "gemma-3-12b-it-q4_0.gguf"
    input_file = "batch_5k.jsonl"
    output_file = "gemma3_12b_qat_5k_results.jsonl"

    print(f"Model: {model_id}")
    print(f"GGUF File: {gguf_file}")
    print("Model Size: 8.07 GB (Q4_0 quantized)")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()

    # Get optimized configuration
    print("🧠 Optimizing memory configuration...")
    optimizer = MemoryOptimizer()
    # For 8GB model, should have plenty of room
    config = optimizer.optimize_config(model_id, max_model_len=4096)
    print(f"✅ Using gpu_memory_utilization={config.gpu_memory_utilization}")
    if config.enforce_eager:
        print(f"✅ Using enforce_eager={config.enforce_eager}")
    print()

    # Load requests
    print(f"📂 Loading requests from {input_file}...")
    with open(input_file) as f:
        requests = [json.loads(line) for line in f]

    print(f"✅ Loaded {len(requests):,} requests")
    print()

    # Extract prompts
    prompts = []
    for req in requests:
        messages = req["body"]["messages"]
        # Convert messages to prompt format
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"system\n{content}\n"
            elif role == "user":
                prompt += f"user\n{content}\n"
        prompt += "model\n"
        prompts.append(prompt)

    # Initialize vLLM with GGUF model
    print("🚀 Initializing vLLM with GGUF model...")
    print("⚠️  Note: vLLM GGUF support may require specific configuration")
    start_load = time.time()

    try:
        vllm_kwargs = {
            "model": model_id,
            "max_model_len": config.max_model_len,
            "gpu_memory_utilization": config.gpu_memory_utilization,
            "disable_log_stats": True,
        }

        if config.enforce_eager:
            vllm_kwargs["enforce_eager"] = True
        if config.max_num_seqs:
            vllm_kwargs["max_num_seqs"] = config.max_num_seqs

        llm = LLM(**vllm_kwargs)

        load_time = time.time() - start_load
        print(f"✅ Model loaded in {load_time:.1f} seconds")
        print()

    except Exception as e:
        print(f"❌ Failed to load GGUF model: {e}")
        print()
        print("💡 Trying alternative approach with explicit GGUF file...")

        # Try with explicit GGUF file path
        vllm_kwargs["model"] = gguf_file

        try:
            llm = LLM(**vllm_kwargs)
            load_time = time.time() - start_load
            print(f"✅ Model loaded in {load_time:.1f} seconds")
            print()
        except Exception as e2:
            print(f"❌ Still failed: {e2}")
            print()
            print("📝 vLLM may not support this GGUF format yet.")
            print("   Consider using llama.cpp or Ollama for GGUF models.")
            return

    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )

    # Run inference
    print(f"🚀 Running inference on {len(prompts):,} requests...")
    print("This will take a while...")
    print()

    start_time = time.time()
    outputs = llm.generate(prompts, sampling_params)
    end_time = time.time()

    total_time = end_time - start_time

    # Process results
    print("📊 Processing results...")
    results = []
    successful = 0
    failed = 0
    prompt_tokens = 0
    completion_tokens = 0

    for i, (req, output) in enumerate(zip(requests, outputs, strict=False)):
        try:
            response_text = output.outputs[0].text

            # Count tokens
            prompt_tok = len(output.prompt_token_ids)
            completion_tok = len(output.outputs[0].token_ids)

            prompt_tokens += prompt_tok
            completion_tokens += completion_tok

            result = {
                "id": req["custom_id"],
                "custom_id": req["custom_id"],
                "response": {
                    "status_code": 200,
                    "body": {
                        "id": f"chatcmpl-{i}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model_id,
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": response_text
                            },
                            "finish_reason": "stop"
                        }],
                        "usage": {
                            "prompt_tokens": prompt_tok,
                            "completion_tokens": completion_tok,
                            "total_tokens": prompt_tok + completion_tok
                        }
                    }
                },
                "error": None
            }
            results.append(result)
            successful += 1

        except Exception as e:
            result = {
                "id": req["custom_id"],
                "custom_id": req["custom_id"],
                "response": None,
                "error": {
                    "message": str(e),
                    "type": "processing_error"
                }
            }
            results.append(result)
            failed += 1

    # Save results
    print(f"💾 Saving results to {output_file}...")
    with open(output_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')

    # Calculate metrics
    total_tokens = prompt_tokens + completion_tokens
    throughput = total_tokens / total_time
    avg_prompt_tokens = prompt_tokens / len(requests)
    avg_completion_tokens = completion_tokens / len(requests)

    # Print summary
    print()
    print("=" * 80)
    print("📊 BENCHMARK RESULTS - GEMMA 3 12B QAT Q4_0")
    print("=" * 80)
    print()
    print(f"Model: {model_id}")
    print("Quantization: Q4_0 (4-bit)")
    print("Model Size: 8.07 GB")
    print()
    print(f"Total Requests: {len(requests):,}")
    print(f"Successful: {successful:,}")
    print(f"Failed: {failed:,}")
    print(f"Success Rate: {successful/len(requests)*100:.1f}%")
    print()
    print(f"Total Time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"Model Load Time: {load_time:.1f} seconds")
    print(f"Inference Time: {total_time - load_time:.1f} seconds")
    print()
    print(f"Prompt Tokens: {prompt_tokens:,}")
    print(f"Completion Tokens: {completion_tokens:,}")
    print(f"Total Tokens: {total_tokens:,}")
    print()
    print(f"Avg Prompt Tokens: {avg_prompt_tokens:.0f}")
    print(f"Avg Completion Tokens: {avg_completion_tokens:.0f}")
    print()
    print(f"Throughput: {throughput:,.0f} tokens/second")
    print(f"Requests/second: {len(requests)/total_time:.2f}")
    print()
    print("=" * 80)

    # Save metadata
    metadata = {
        "model": model_id,
        "quantization": "Q4_0",
        "model_size_gb": 8.07,
        "timestamp": datetime.utcnow().isoformat(),
        "batch_size": len(requests),
        "successful": successful,
        "failed": failed,
        "total_time_seconds": total_time,
        "load_time_seconds": load_time,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "throughput_tokens_per_second": throughput,
        "avg_prompt_tokens": avg_prompt_tokens,
        "avg_completion_tokens": avg_completion_tokens,
        "configuration": {
            "max_model_len": config.max_model_len,
            "gpu_memory_utilization": config.gpu_memory_utilization,
            "enforce_eager": config.enforce_eager,
            "max_num_seqs": config.max_num_seqs,
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2000
        }
    }

    metadata_file = f"benchmarks/metadata/gemma3-12b-qat-5k-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    Path("benchmarks/metadata").mkdir(parents=True, exist_ok=True)

    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Metadata saved to {metadata_file}")
    print()

if __name__ == "__main__":
    main()

