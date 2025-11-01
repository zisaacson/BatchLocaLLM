#!/usr/bin/env python3
"""
Test OLMo 2 7B with a single request to verify it loads and works.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models.olmo2_7b import OLMO2_7B


def get_gpu_memory():
    """Get current GPU memory usage in MB."""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def main():
    print("=" * 80)
    print("🧪 OLMo 2 7B - SINGLE REQUEST TEST")
    print("=" * 80)
    print()
    
    print(f"Model: {OLMO2_7B.model_id}")
    print(f"Expected memory: {OLMO2_7B.estimated_memory_gb} GB")
    print(f"GPU memory utilization: {OLMO2_7B.gpu_memory_utilization}")
    print()
    
    # Check initial GPU memory
    initial_mem = get_gpu_memory()
    print(f"📊 Initial GPU Memory: {initial_mem} MB")
    print()
    
    # Load model
    print("🚀 Loading model...")
    start_load = time.time()
    
    try:
        from vllm import LLM, SamplingParams
        
        # Load with model config settings
        llm = LLM(**OLMO2_7B.get_vllm_kwargs())
        
        load_time = time.time() - start_load
        load_mem = get_gpu_memory()
        
        print(f"\n✅ Model loaded in {load_time:.1f}s")
        print(f"📊 GPU Memory after load: {load_mem} MB")
        print(f"📊 Model size: {load_mem - initial_mem} MB ({(load_mem - initial_mem) / 1024:.2f} GB)")
        print()
        
        # Create test prompt
        print("🔄 Generating response...")
        
        prompt = """You are an expert technical recruiter evaluating a software engineer candidate.

Candidate Profile:
- Name: Jane Smith
- Current Role: Senior Software Engineer at Google
- Education: BS Computer Science, Stanford University
- Experience: 8 years in backend systems, distributed systems, and infrastructure
- Notable: Led migration of critical service to microservices, reduced latency by 40%

Please evaluate this candidate on the following criteria:
1. Recommendation (Strong Yes/Yes/Maybe/No/Strong No)
2. Trajectory (Exceptional/Strong/Good/Average/Weak)
3. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
4. Educational Pedigree (Exceptional/Strong/Good/Average/Weak)
5. Is this candidate a software engineer? (Yes/No)

Provide your evaluation in JSON format."""
        
        sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.9,
            max_tokens=2000,
        )
        
        start_gen = time.time()
        outputs = llm.generate([prompt], sampling_params)
        gen_time = time.time() - start_gen
        
        # Get response
        response = outputs[0].outputs[0].text
        prompt_tokens = len(outputs[0].prompt_token_ids)
        completion_tokens = len(outputs[0].outputs[0].token_ids)
        total_tokens = prompt_tokens + completion_tokens
        
        print(f"\n✅ Generated in {gen_time:.1f}s")
        print(f"📊 Prompt tokens: {prompt_tokens}")
        print(f"📊 Completion tokens: {completion_tokens}")
        print(f"📊 Total tokens: {total_tokens}")
        print(f"📊 Throughput: {total_tokens / gen_time:.1f} tok/s")
        print()
        
        print("=" * 80)
        print("RESPONSE:")
        print("=" * 80)
        print(response)
        print("=" * 80)
        print()
        
        # Check if response looks valid
        if len(response) > 50:
            print("✅ Response looks valid (length > 50 chars)")
        else:
            print("⚠️  Response seems short, may need investigation")
        
        # Try to parse as JSON
        try:
            # Look for JSON in response
            if '{' in response and '}' in response:
                json_start = response.index('{')
                json_end = response.rindex('}') + 1
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                print("✅ Response contains valid JSON")
                print(f"   Keys: {list(parsed.keys())}")
            else:
                print("⚠️  No JSON found in response")
        except Exception as e:
            print(f"⚠️  Could not parse JSON: {e}")
        
        print()
        print("=" * 80)
        print("✅ TEST PASSED - Model loads and generates responses")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Run 100 request test: python core/tests/manual/test_olmo2_7b_100.py")
        print("2. Run 5K batch test: bash scripts/test_olmo2_7b_5k_offline.sh")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

