#!/usr/bin/env python3
"""
Benchmark OLMo 2 7B Q4_0 GGUF on 5K candidate dataset.

This uses the quantized GGUF version which should fit on RTX 4080 WITHOUT CPU offload.
Expected: ~700 tok/s (70x faster than FP16 with offload)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vllm import LLM, SamplingParams

# Configuration
MODEL_ID = "bartowski/OLMo-2-1124-7B-Instruct-GGUF"
DATASET_PATH = project_root / "batch_5k.jsonl"
OUTPUT_DIR = project_root / "benchmarks" / "raw"
LOG_DIR = project_root / "logs"

# vLLM configuration - NO CPU OFFLOAD!
VLLM_CONFIG = {
    "model": MODEL_ID,
    "max_model_len": 8192,
    "gpu_memory_utilization": 0.95,
    "enable_prefix_caching": True,
    "enable_chunked_prefill": True,
    "tensor_parallel_size": 1,
    "trust_remote_code": True,
}

# Sampling parameters
SAMPLING_PARAMS = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=1024,
    stop=["<|endoftext|>"]
)

# Batch size
BATCH_SIZE = 100


def load_dataset():
    """Load the 5K candidate evaluation dataset."""
    print(f"Loading dataset from {DATASET_PATH}...")
    
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
    
    requests = []
    with open(DATASET_PATH, 'r') as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))
    
    print(f"✅ Loaded {len(requests)} requests")
    return requests


def format_prompt(request_body):
    """Format request into OLMo 2 prompt format."""
    messages = request_body.get('messages', [])
    
    # OLMo 2 format: <|endoftext|><|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n
    prompt = "<|endoftext|>"
    
    for msg in messages:
        role = msg['role']
        content = msg['content']
        
        if role == 'system':
            prompt += f"<|system|>\n{content}\n"
        elif role == 'user':
            prompt += f"<|user|>\n{content}\n"
        elif role == 'assistant':
            prompt += f"<|assistant|>\n{content}\n"
    
    # Add assistant tag for generation
    if messages and messages[-1]['role'] != 'assistant':
        prompt += "<|assistant|>\n"
    
    return prompt


def run_benchmark():
    """Run the benchmark."""
    print("=" * 80)
    print("OLMo 2 7B Q4_0 GGUF Benchmark - 5K Candidates")
    print("=" * 80)
    print(f"Model: {MODEL_ID}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"CPU offload: 0 GB (fits on GPU!)")
    print("=" * 80)
    
    # Load dataset
    requests = load_dataset()
    total_requests = len(requests)
    
    # Initialize vLLM
    print("\n🔄 Initializing vLLM...")
    print(f"Config: {VLLM_CONFIG}")
    
    start_init = time.time()
    llm = LLM(**VLLM_CONFIG)
    init_time = time.time() - start_init
    
    print(f"✅ vLLM initialized in {init_time:.1f}s")
    
    # Prepare output file
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_file = OUTPUT_DIR / f"olmo2-7b-q4-5k-{timestamp}.jsonl"
    log_file = LOG_DIR / f"olmo2_7b_q4_5k_benchmark.log"
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📝 Output: {output_file}")
    print(f"📝 Log: {log_file}")
    
    # Process in batches
    total_batches = (total_requests + BATCH_SIZE - 1) // BATCH_SIZE
    completed = 0
    
    start_time = time.time()
    
    with open(output_file, 'w') as out_f, open(log_file, 'a') as log_f:
        log_f.write(f"\n{'=' * 80}\n")
        log_f.write(f"Benchmark started: {datetime.now().isoformat()}\n")
        log_f.write(f"Model: {MODEL_ID}\n")
        log_f.write(f"Total requests: {total_requests}\n")
        log_f.write(f"Batch size: {BATCH_SIZE}\n")
        log_f.write(f"{'=' * 80}\n\n")
        
        for batch_idx in range(total_batches):
            batch_start = batch_idx * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, total_requests)
            batch_requests = requests[batch_start:batch_end]
            
            print(f"\n🔄 Processing batch {batch_idx + 1}/{total_batches} ({batch_start}-{batch_end})...")
            log_f.write(f"Processing batch {batch_idx + 1}/{total_batches} ({batch_start}-{batch_end})...\n")
            log_f.flush()
            
            # Format prompts
            prompts = [format_prompt(req['body']) for req in batch_requests]
            
            # Generate
            batch_start_time = time.time()
            outputs = llm.generate(prompts, SAMPLING_PARAMS)
            batch_time = time.time() - batch_start_time
            
            # Save results
            for req, output in zip(batch_requests, outputs):
                result = {
                    "custom_id": req['custom_id'],
                    "response": {
                        "status_code": 200,
                        "request_id": f"req_{datetime.now().timestamp()}",
                        "body": {
                            "id": f"chatcmpl-{datetime.now().timestamp()}",
                            "object": "chat.completion",
                            "created": int(datetime.now().timestamp()),
                            "model": MODEL_ID,
                            "choices": [{
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": output.outputs[0].text
                                },
                                "finish_reason": output.outputs[0].finish_reason
                            }],
                            "usage": {
                                "prompt_tokens": len(output.prompt_token_ids),
                                "completion_tokens": len(output.outputs[0].token_ids),
                                "total_tokens": len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
                            }
                        }
                    },
                    "error": None
                }
                out_f.write(json.dumps(result) + '\n')
                out_f.flush()
            
            completed += len(batch_requests)
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total_requests - completed) / rate if rate > 0 else 0
            
            log_msg = f"Batch {batch_idx + 1} complete: {completed}/{total_requests} ({completed/total_requests*100:.1f}%) | {batch_time:.1f}s | {rate:.1f} req/s | ETA: {eta/60:.1f}min\n"
            print(log_msg.strip())
            log_f.write(log_msg)
            log_f.flush()
    
    # Final stats
    total_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("✅ Benchmark Complete!")
    print("=" * 80)
    print(f"Total requests: {total_requests}")
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"Throughput: {total_requests/total_time:.1f} req/s")
    print(f"Output file: {output_file}")
    print("=" * 80)
    
    with open(log_file, 'a') as log_f:
        log_f.write(f"\n{'=' * 80}\n")
        log_f.write(f"Benchmark complete: {datetime.now().isoformat()}\n")
        log_f.write(f"Total requests: {total_requests}\n")
        log_f.write(f"Total time: {total_time:.1f}s ({total_time/60:.1f}min)\n")
        log_f.write(f"Throughput: {total_requests/total_time:.1f} req/s\n")
        log_f.write(f"{'=' * 80}\n\n")


if __name__ == "__main__":
    run_benchmark()

