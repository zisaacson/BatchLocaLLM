#!/usr/bin/env python3
"""
Test OLMo 2 7B (Nov 2024) with 100 samples to check quality
"""

import json
import time
from vllm import LLM, SamplingParams

def main():
    # Model configuration
    model_id = "allenai/OLMo-2-1124-7B-Instruct"
    output_file = "olmo2_7b_100_results.jsonl"
    
    print("=" * 80)
    print(f"🧪 Testing OLMo 2 7B (Nov 2024) - 100 samples")
    print(f"Model: {model_id}")
    print(f"Output: {output_file}")
    print("=" * 80)
    print()
    
    # Load requests
    print("📂 Loading batch requests...")
    with open('batch_5k.jsonl', 'r') as f:
        requests = [json.loads(line) for line in f]
    
    # Take first 100
    requests = requests[:100]
    print(f"✅ Loaded {len(requests):,} requests")
    print()
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req["body"]["messages"]
        # Format as chat template (OLMo 2 uses standard chat format)
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"<|system|>\n{content}\n"
            elif role == "user":
                prompt += f"<|user|>\n{content}\n"
            elif role == "assistant":
                prompt += f"<|assistant|>\n{content}\n"
        prompt += "<|assistant|>\n"
        prompts.append(prompt)
    
    # Initialize vLLM
    print("🔧 Initializing vLLM...")
    print(f"   Model: {model_id}")
    print(f"   GPU Memory Utilization: 0.85")
    print(f"   Max Model Length: 4096")
    print(f"   Enforce Eager: True")
    print()
    
    start_load = time.time()
    llm = LLM(
        model=model_id,
        gpu_memory_utilization=0.85,
        max_model_len=4096,
        enforce_eager=True,
        trust_remote_code=True
    )
    end_load = time.time()
    load_time = end_load - start_load
    
    print(f"✅ Model loaded in {load_time:.1f} seconds")
    print()
    
    # Sampling parameters
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=2048,
        stop=["<|endoftext|>", "<|end|>"]
    )
    
    # Run inference - BATCH MODE
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
    
    # Print summary
    print()
    print("=" * 80)
    print("📈 BENCHMARK RESULTS")
    print("=" * 80)
    print()
    print(f"Model: {model_id}")
    print(f"Total Requests: {len(requests):,}")
    print(f"Successful: {successful:,}")
    print(f"Failed: {failed:,}")
    print()
    print(f"Total Time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"Model Load Time: {load_time:.1f} seconds")
    print()
    print(f"Prompt Tokens: {prompt_tokens:,}")
    print(f"Completion Tokens: {completion_tokens:,}")
    print(f"Total Tokens: {prompt_tokens + completion_tokens:,}")
    print()
    print(f"Avg Prompt Tokens: {prompt_tokens // len(requests):,}")
    print(f"Avg Completion Tokens: {completion_tokens // len(requests):,}")
    print()
    
    total_tokens = prompt_tokens + completion_tokens
    throughput = total_tokens / total_time
    req_per_sec = len(requests) / total_time
    
    print(f"Throughput: {throughput:,.0f} tokens/second")
    print(f"Requests/second: {req_per_sec:.2f}")
    print()
    print("=" * 80)
    print(f"✅ Results saved to {output_file}")
    print()

if __name__ == "__main__":
    main()

