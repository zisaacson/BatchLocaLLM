#!/usr/bin/env python3
"""
GPT-OSS 20B - 5K Candidates Benchmark with llama.cpp

This tests GPT-OSS 20B on the same 5K dataset using llama.cpp instead of vLLM.
Uses --cpu-moe flag to offload expert layers to CPU for RTX 4080 16GB.

GPT-OSS is a Mixture of Experts (MoE) model:
- 20B total parameters
- 8 expert layers (only 2 active per token)
- Effective compute: ~2.5B per token
- Native MXFP4 quantization (no need for Q4/Q8)

Expected performance (based on Reddit reports):
- 7-10 tok/s on 3060ti 8GB for 120B model
- 20B should run much faster on RTX 4080 16GB
- Target: 20-40 tok/s with CPU MoE offload
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 80)
    print("GPT-OSS 20B - 5K CANDIDATES BENCHMARK (LLAMA.CPP + CPU MOE OFFLOAD)")
    print("=" * 80)
    print(f"Model: gpt-oss/gpt-oss-20b-gguf")
    print(f"Dataset: batch_5k.jsonl (5,000 candidate evaluations)")
    print(f"Engine: llama.cpp")
    print(f"Strategy: --cpu-moe to offload expert layers to CPU")
    print("=" * 80)
    print()
    
    # Check if llama.cpp is installed
    llamacpp_path = Path.home() / "llama.cpp" / "llama-cli"
    if not llamacpp_path.exists():
        print("❌ llama.cpp not found!")
        print(f"   Expected: {llamacpp_path}")
        print()
        print("To install llama.cpp:")
        print("  cd ~")
        print("  git clone https://github.com/ggerganov/llama.cpp")
        print("  cd llama.cpp")
        print("  make GGML_CUDA=1")
        print()
        return
    
    print(f"✅ Found llama.cpp at {llamacpp_path}")
    print()
    
    # Paths
    input_file = Path("batch_5k.jsonl")
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_file = Path(f"benchmarks/raw/gptoss-20b-5k-{timestamp}.jsonl")
    metadata_file = Path(f"benchmarks/metadata/gptoss-20b-5k-{timestamp}.json")
    
    # Create output directories
    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Validate input file
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Load requests
    print(f"📄 Loading requests from {input_file}...")
    requests = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))
    
    print(f"✅ Loaded {len(requests)} requests")
    print()
    
    # Check if model is downloaded
    model_path = Path.home() / ".cache" / "huggingface" / "hub" / "models--gpt-oss--gpt-oss-20b-gguf"
    print(f"🔍 Checking for GPT-OSS 20B model...")
    if not model_path.exists():
        print("⚠️  Model not found in cache. Will download on first run.")
        print(f"   This may take 10-15 minutes (model is ~12GB)")
        print()
    else:
        print(f"✅ Model found in cache")
        print()
    
    # Run inference using llama.cpp
    print(f"🔥 Running inference on {len(requests)} requests...")
    print(f"   Using llama.cpp with --cpu-moe flag")
    print(f"   Expected time: ~2-4 hours (depends on CPU/GPU balance)")
    print(f"   Output will be saved incrementally to: {output_file}")
    print()
    
    start_time = time.time()
    results = []
    
    # Process requests one by one (llama.cpp doesn't have batch API)
    for i, req in enumerate(requests):
        custom_id = req['custom_id']
        messages = req['body']['messages']
        
        # Format prompt
        prompt = ""
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == 'user':
                prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        
        # Save prompt to temp file
        temp_prompt = Path(f"/tmp/gptoss_prompt_{i}.txt")
        with open(temp_prompt, 'w') as f:
            f.write(prompt)
        
        # Run llama.cpp
        cmd = [
            str(llamacpp_path),
            "--model", "gpt-oss/gpt-oss-20b-gguf",
            "--file", str(temp_prompt),
            "--n-gpu-layers", "999",  # Offload as many layers as possible to GPU
            "--cpu-moe", "8",  # Offload all 8 expert layers to CPU
            "--ctx-size", "4096",
            "--temp", "0.7",
            "--top-p", "0.9",
            "--n-predict", "2000",
            "--no-display-prompt"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per request
            )
            
            response_text = result.stdout.strip()
            
            # Create result in OpenAI format
            result_obj = {
                "custom_id": custom_id,
                "response": {
                    "status_code": 200,
                    "body": {
                        "id": f"chatcmpl-{custom_id}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": "gpt-oss/gpt-oss-20b-gguf",
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": response_text
                            },
                            "finish_reason": "stop"
                        }],
                        "usage": {
                            "prompt_tokens": len(prompt.split()),  # Rough estimate
                            "completion_tokens": len(response_text.split()),
                            "total_tokens": len(prompt.split()) + len(response_text.split())
                        }
                    }
                }
            }
            
            results.append(result_obj)
            
            # Save incrementally
            with open(output_file, 'a') as f:
                f.write(json.dumps(result_obj) + '\n')
            
            # Clean up temp file
            temp_prompt.unlink()
            
            # Progress update every 10 requests
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / (i + 1)
                remaining = avg_time * (len(requests) - i - 1)
                print(f"  Progress: {i+1}/{len(requests)} ({(i+1)/len(requests)*100:.1f}%) - "
                      f"Elapsed: {elapsed/60:.1f}m - ETA: {remaining/60:.1f}m")
        
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Request {i+1} timed out, skipping...")
            temp_prompt.unlink()
            continue
        except Exception as e:
            print(f"  ❌ Request {i+1} failed: {e}")
            temp_prompt.unlink()
            continue
    
    total_time = time.time() - start_time
    
    print()
    print("=" * 80)
    print("📊 BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Model: gpt-oss/gpt-oss-20b-gguf")
    print(f"Requests: {len(results)}")
    print(f"Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Requests/sec: {len(results)/total_time:.2f}")
    print()
    print(f"📁 Results saved to: {output_file}")
    print("=" * 80)
    
    # Save metadata
    metadata = {
        "test_id": f"gptoss-20b-5k-{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "model": "gpt-oss/gpt-oss-20b-gguf",
        "engine": "llama.cpp",
        "config": {
            "n_gpu_layers": 999,
            "cpu_moe": 8,
            "ctx_size": 4096,
            "temperature": 0.7,
            "top_p": 0.9,
            "n_predict": 2000
        },
        "test": {
            "num_requests": len(results),
            "input_file": str(input_file),
            "output_file": str(output_file)
        },
        "results": {
            "total_time_sec": round(total_time, 2),
            "throughput_requests_per_sec": round(len(results)/total_time, 2)
        },
        "status": "completed"
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"📁 Metadata saved to: {metadata_file}")
    print()
    print("✅ Benchmark complete!")

if __name__ == "__main__":
    main()

