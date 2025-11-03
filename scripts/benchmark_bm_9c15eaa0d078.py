"""
Benchmark: Gemma 3 4B on test_dataset.jsonl
Generated: 2025-11-03T03:13:23.218642+00:00
"""

import json
import time
from datetime import datetime
from pathlib import Path
from vllm import LLM, SamplingParams

# Load dataset
dataset_path = Path("data/datasets/ds_2b16c1d98c9f_test_dataset.jsonl")
requests = []
with open(dataset_path, "r") as f:
    for line in f:
        if line.strip():
            requests.append(json.loads(line))

print(f"Loaded {len(requests)} requests from {dataset_path}")

# Initialize model
print(f"Loading model: google/gemma-3-4b-it")
llm = LLM(
    model="google/gemma-3-4b-it",
    max_model_len=4096,
    gpu_memory_utilization=0.9,
    
    enable_prefix_caching=True,
    enable_chunked_prefill=True,
)

# Sampling params
sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=1024
)

# Process in batches
batch_size = 100
results_file = Path("benchmarks/raw/bm_9c15eaa0d078.jsonl")
total_batches = (len(requests) + batch_size - 1) // batch_size

print(f"Processing {len(requests)} requests in {total_batches} batches of {batch_size}")

start_time = time.time()
completed = 0

for batch_idx in range(total_batches):
    batch_start = batch_idx * batch_size
    batch_end = min(batch_start + batch_size, len(requests))
    batch = requests[batch_start:batch_end]

    print(f"Processing batch {batch_idx + 1}/{total_batches} ({batch_start + 1}-{batch_end})...")

    # Extract prompts
    prompts = []
    for req in batch:
        messages = req["body"]["messages"]
        # Simple prompt construction - can be improved
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompts.append(prompt)

    # Generate
    batch_start_time = time.time()
    outputs = llm.generate(prompts, sampling_params)
    batch_time = time.time() - batch_start_time

    # Save results
    with open(results_file, "a") as f:
        for req, output in zip(batch, outputs):
            result = {
                "custom_id": req["custom_id"],
                "request": req,
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": output.outputs[0].text
                            }
                        }]
                    }
                }
            }
            f.write(json.dumps(result) + "\n")

    completed += len(batch)
    elapsed = time.time() - start_time
    throughput = completed / elapsed if elapsed > 0 else 0

    print(f"Batch complete: {completed}/{len(requests)} ({completed/len(requests)*100:.1f}%) - {throughput:.1f} req/s")

total_time = time.time() - start_time
print(f"\nBenchmark complete!")
print(f"Total time: {total_time:.1f}s")
print(f"Throughput: {len(requests)/total_time:.1f} req/s")
print(f"Results: {results_file}")
