"""
Benchmark Gemma 3 12B Q4_0 GGUF on 5K dataset.

This model should run WITHOUT CPU offload on RTX 4080 16GB!
Expected throughput: ~100 tok/s
"""

import json
import time
from pathlib import Path
from datetime import datetime
from vllm import LLM, SamplingParams

# Configuration
MODEL_ID = "google/gemma-3-12b-it-qat-q4_0-gguf"
INPUT_FILE = Path("batch_5k.jsonl")
OUTPUT_FILE = Path(f"benchmarks/raw/gemma3-12b-5k-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jsonl")
LOG_FILE = Path("logs/gemma3_12b_5k_benchmark.log")
BATCH_SIZE = 100

# Create output directories
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(message):
    """Log to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")

def load_requests(input_file: Path):
    """Load requests from JSONL file."""
    requests = []
    with open(input_file, "r") as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))
    return requests

def save_result(result, output_file: Path):
    """Save a single result to JSONL file."""
    with open(output_file, "a") as f:
        f.write(json.dumps(result) + "\n")

def main():
    log("="*70)
    log("GEMMA 3 12B Q4_0 GGUF - 5K BENCHMARK")
    log("="*70)
    log(f"Model: {MODEL_ID}")
    log(f"Input: {INPUT_FILE}")
    log(f"Output: {OUTPUT_FILE}")
    log(f"Batch size: {BATCH_SIZE}")
    log("")
    
    # Load requests
    log("Loading requests...")
    requests = load_requests(INPUT_FILE)
    total_requests = len(requests)
    log(f"Loaded {total_requests} requests")
    log("")
    
    # Initialize vLLM
    log("Initializing vLLM...")
    log("Configuration:")
    log("  - NO CPU offload (fits on GPU!)")
    log("  - max_model_len: 4096")
    log("  - gpu_memory_utilization: 0.90")
    log("  - enable_prefix_caching: True")
    log("  - enable_chunked_prefill: True")
    log("")
    
    llm = LLM(
        model=MODEL_ID,
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        # NO cpu_offload_gb - model fits on GPU!
    )
    
    sampling_params = SamplingParams(
        temperature=0.0,
        max_tokens=512,
        stop=["</response>", "\n\n\n"]
    )
    
    log("✅ vLLM initialized successfully!")
    log("")
    
    # Process in batches
    num_batches = (total_requests + BATCH_SIZE - 1) // BATCH_SIZE
    total_processed = 0
    start_time = time.time()
    
    for batch_idx in range(num_batches):
        batch_start = batch_idx * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, total_requests)
        batch_requests = requests[batch_start:batch_end]
        
        log(f"Processing batch {batch_idx + 1}/{num_batches} ({batch_start + 1}-{batch_end})...")
        batch_start_time = time.time()
        
        # Extract prompts
        prompts = []
        for req in batch_requests:
            messages = req["body"]["messages"]
            # Convert to prompt format
            prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt += f"<system>{content}</system>\n"
                elif role == "user":
                    prompt += f"<user>{content}</user>\n"
            prompt += "<assistant>"
            prompts.append(prompt)
        
        # Generate
        outputs = llm.generate(prompts, sampling_params)
        
        # Save results
        for req, output in zip(batch_requests, outputs):
            result = {
                "custom_id": req["custom_id"],
                "response": {
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
            save_result(result, OUTPUT_FILE)
        
        total_processed += len(batch_requests)
        batch_time = time.time() - batch_start_time
        elapsed_time = time.time() - start_time
        
        # Calculate metrics
        throughput = total_processed / elapsed_time
        eta_seconds = (total_requests - total_processed) / throughput if throughput > 0 else 0
        
        log(f"Batch complete: {total_processed}/{total_requests} ({total_processed/total_requests*100:.1f}%)")
        log(f"  Batch time: {batch_time:.1f}s")
        log(f"  Throughput: {throughput:.2f} req/s")
        log(f"  ETA: {eta_seconds/60:.1f} minutes")
        log("")
    
    # Final stats
    total_time = time.time() - start_time
    final_throughput = total_requests / total_time
    
    log("="*70)
    log("BENCHMARK COMPLETE!")
    log("="*70)
    log(f"Total requests: {total_requests}")
    log(f"Total time: {total_time/60:.1f} minutes")
    log(f"Average throughput: {final_throughput:.2f} req/s")
    log(f"Output file: {OUTPUT_FILE}")
    log("="*70)

if __name__ == "__main__":
    main()

