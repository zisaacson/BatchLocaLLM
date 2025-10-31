#!/usr/bin/env python3
"""
Test Llama 3.2 3B with 5K batch.
Should be 2-3x faster than Gemma 3 4B.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from memory_optimizer import MemoryOptimizer
from vllm import LLM, SamplingParams


def main():
    print("=" * 80)
    print("🧪 LLAMA 3.2 3B - 5K BATCH TEST")
    print("=" * 80)
    print()

    # Configuration
    model_id = "meta-llama/Llama-3.2-3B-Instruct"
    input_file = "batch_5k.jsonl"
    output_file = "llama32_3b_5k_results.jsonl"

    print(f"Model: {model_id}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()

    # Get optimized configuration
    print("🧠 Optimizing memory configuration...")
    optimizer = MemoryOptimizer()
    config = optimizer.optimize_config(model_id, max_model_len=4096)
    print(f"✅ Using gpu_memory_utilization={config.gpu_memory_utilization}")
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
        # Convert to Llama format
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>"
            elif role == "user":
                prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        prompts.append(prompt)

    # Initialize vLLM
    print("🚀 Initializing vLLM...")
    start_load = time.time()

    llm = LLM(
        model=model_id,
        max_model_len=config.max_model_len,
        gpu_memory_utilization=config.gpu_memory_utilization,
        disable_log_stats=True,
        enforce_eager=True,  # Avoid engine core issues
    )

    load_time = time.time() - start_load
    print(f"✅ Model loaded in {load_time:.1f} seconds")
    print()

    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2000,
    )

    # Run inference - BATCH MODE like Gemma 3 4B
    print(f"🚀 Running inference on {len(prompts):,} requests...")
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

    for i, (req, output) in enumerate(zip(requests, outputs)):
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
    print("📊 BENCHMARK RESULTS - LLAMA 3.2 3B")
    print("=" * 80)
    print()
    print(f"Model: {model_id}")
    print()
    print(f"Total Requests: {len(requests):,}")
    print(f"Successful: {successful:,}")
    print(f"Failed: {failed:,}")
    print(f"Success Rate: {successful/len(requests)*100:.1f}%")
    print()
    print(f"Total Time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"Model Load Time: {load_time:.1f} seconds")
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
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2000
        }
    }

    metadata_file = f"benchmarks/metadata/llama32-3b-5k-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    Path("benchmarks/metadata").mkdir(parents=True, exist_ok=True)

    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Metadata saved to {metadata_file}")
    print()

if __name__ == "__main__":
    main()

