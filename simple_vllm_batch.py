#!/usr/bin/env python3
"""
Simple vLLM Batch Processing - The 80-line version
No PostgreSQL. No Grafana. No FastAPI. No webhooks.
Just batch inference that works.
"""

import json
import argparse
from pathlib import Path
from vllm import LLM, SamplingParams

def load_batch(input_file: str) -> list[dict]:
    """Load OpenAI-format batch file."""
    with open(input_file) as f:
        return [json.loads(line) for line in f]

def process_batch(
    input_file: str,
    output_file: str,
    model: str = "google/gemma-3-4b-it",
    gpu_memory: float = 0.9,
    max_tokens: int = 512,
):
    """Process batch with vLLM."""
    
    # Load requests
    print(f"Loading batch from {input_file}...")
    requests = load_batch(input_file)
    print(f"Loaded {len(requests)} requests")
    
    # Initialize vLLM
    print(f"Loading model {model}...")
    llm = LLM(
        model=model,
        gpu_memory_utilization=gpu_memory,
        max_model_len=4096,
    )
    
    # Extract prompts
    prompts = []
    for req in requests:
        messages = req["body"]["messages"]
        # Simple prompt formatting (adjust for your model)
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompts.append(prompt)
    
    # Run inference
    print(f"Running inference on {len(prompts)} prompts...")
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=max_tokens,
    )
    outputs = llm.generate(prompts, sampling_params)
    
    # Save results
    print(f"Saving results to {output_file}...")
    with open(output_file, "w") as f:
        for req, output in zip(requests, outputs):
            result = {
                "id": f"batch_req_{req['custom_id']}",
                "custom_id": req["custom_id"],
                "response": {
                    "status_code": 200,
                    "body": {
                        "id": f"chatcmpl-{req['custom_id']}",
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": output.outputs[0].text,
                            }
                        }]
                    }
                }
            }
            f.write(json.dumps(result) + "\n")
    
    print(f"✅ Done! Processed {len(requests)} requests")
    print(f"   Output: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple vLLM batch processing")
    parser.add_argument("input_file", help="Input JSONL file")
    parser.add_argument("output_file", help="Output JSONL file")
    parser.add_argument("--model", default="google/gemma-3-4b-it", help="Model name")
    parser.add_argument("--gpu-memory", type=float, default=0.9, help="GPU memory utilization")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max tokens per response")
    
    args = parser.parse_args()
    process_batch(
        args.input_file,
        args.output_file,
        args.model,
        args.gpu_memory,
        args.max_tokens,
    )

