# Benchmark Data & Analysis Tools Plan

**Goal:** Simple, reliable system to track vLLM vs Ollama performance without losing data

---

## 1. Benchmark Storage Structure

```
benchmarks/
├── raw/                                    # Raw JSONL results
│   ├── vllm-offline-gemma3-4b-100-2024-10-28.jsonl
│   ├── vllm-offline-gemma3-4b-5000-2024-10-28.jsonl
│   ├── ollama-gemma3-12b-100-2024-10-28.jsonl
│   └── ...
├── metadata/                               # Test metadata (config, timing, GPU)
│   ├── vllm-offline-gemma3-4b-100-2024-10-28.json
│   ├── vllm-offline-gemma3-4b-5000-2024-10-28.json
│   └── ...
├── analysis/                               # Analyzed results
│   └── summary.json                        # All benchmarks summarized
└── reports/                                # Human-readable reports
    └── COMPARISON.md                       # vLLM vs Ollama comparison
```

---

## 2. Metadata Schema

**File:** `benchmarks/metadata/{platform}-{model}-{num_requests}-{date}.json`

```json
{
  "test_id": "vllm-offline-gemma3-4b-5000-2024-10-28",
  "timestamp": "2024-10-28T07:38:12Z",
  "platform": "vllm-offline",
  "model": "google/gemma-3-4b-it",
  "gpu": {
    "name": "RTX 4080",
    "vram_total_gb": 16,
    "vram_used_gb": 14.4
  },
  "config": {
    "max_model_len": 4096,
    "gpu_memory_utilization": 0.90,
    "enable_prefix_caching": true,
    "chunked_prefill_enabled": true
  },
  "test": {
    "num_requests": 5000,
    "input_file": "batch_5k.jsonl",
    "output_file": "benchmarks/raw/vllm-offline-gemma3-4b-5000-2024-10-28.jsonl"
  },
  "results": {
    "success_count": 5000,
    "failure_count": 0,
    "total_time_seconds": 2400,
    "model_load_time_seconds": 25.8,
    "throughput_tokens_per_sec": 1809,
    "throughput_requests_per_sec": 2.08,
    "avg_prompt_tokens": 850,
    "avg_completion_tokens": 450,
    "gpu_utilization_percent": 96
  },
  "status": "completed"
}
```

---

## 3. Analysis Tool

**File:** `tools/analyze_benchmark.py`

**Purpose:** Parse JSONL results → extract metrics → save metadata

```python
#!/usr/bin/env python3
"""
Analyze benchmark results and generate metadata.

Usage:
    python tools/analyze_benchmark.py \
        --platform vllm-offline \
        --model gemma3-4b \
        --input batch_5k_offline_results.jsonl \
        --config '{"max_model_len": 4096, "gpu_memory_utilization": 0.90}'
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

def analyze_results(input_file):
    """Parse JSONL and extract metrics."""
    results = []
    with open(input_file) as f:
        for line in f:
            results.append(json.loads(line))
    
    success_count = sum(1 for r in results if 'choices' in r)
    failure_count = len(results) - success_count
    
    # Calculate token stats
    prompt_tokens = [r.get('usage', {}).get('prompt_tokens', 0) for r in results if 'usage' in r]
    completion_tokens = [r.get('usage', {}).get('completion_tokens', 0) for r in results if 'usage' in r]
    
    return {
        'success_count': success_count,
        'failure_count': failure_count,
        'avg_prompt_tokens': sum(prompt_tokens) // len(prompt_tokens) if prompt_tokens else 0,
        'avg_completion_tokens': sum(completion_tokens) // len(completion_tokens) if completion_tokens else 0,
        'total_tokens': sum(prompt_tokens) + sum(completion_tokens)
    }

def save_metadata(metadata, output_dir='benchmarks/metadata'):
    """Save metadata to JSON file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    test_id = metadata['test_id']
    output_file = Path(output_dir) / f"{test_id}.json"
    
    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Saved metadata: {output_file}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', required=True, help='vllm-offline, vllm-serve, ollama')
    parser.add_argument('--model', required=True, help='gemma3-4b, gemma3-12b')
    parser.add_argument('--input', required=True, help='Input JSONL file')
    parser.add_argument('--config', required=True, help='JSON config string')
    parser.add_argument('--total-time', type=float, required=True, help='Total processing time (seconds)')
    parser.add_argument('--model-load-time', type=float, default=0, help='Model load time (seconds)')
    args = parser.parse_args()
    
    # Analyze results
    results = analyze_results(args.input)
    
    # Build metadata
    date = datetime.now().strftime('%Y-%m-%d')
    test_id = f"{args.platform}-{args.model}-{results['success_count']}-{date}"
    
    metadata = {
        'test_id': test_id,
        'timestamp': datetime.now().isoformat(),
        'platform': args.platform,
        'model': args.model,
        'config': json.loads(args.config),
        'test': {
            'num_requests': results['success_count'] + results['failure_count'],
            'input_file': args.input
        },
        'results': {
            **results,
            'total_time_seconds': args.total_time,
            'model_load_time_seconds': args.model_load_time,
            'throughput_tokens_per_sec': int(results['total_tokens'] / args.total_time),
            'throughput_requests_per_sec': round(results['success_count'] / args.total_time, 2)
        },
        'status': 'completed' if results['failure_count'] == 0 else 'partial'
    }
    
    # Save metadata
    save_metadata(metadata)
    
    # Print summary
    print(f"\n📊 Benchmark Summary:")
    print(f"  Platform: {args.platform}")
    print(f"  Model: {args.model}")
    print(f"  Requests: {results['success_count']}/{results['success_count'] + results['failure_count']}")
    print(f"  Throughput: {metadata['results']['throughput_tokens_per_sec']} tok/s")
    print(f"  Time: {args.total_time:.1f}s")

if __name__ == '__main__':
    main()
```

---

## 4. Comparison Tool

**File:** `tools/compare_benchmarks.py`

**Purpose:** Load all metadata → generate comparison table

```python
#!/usr/bin/env python3
"""
Compare all benchmarks and generate report.

Usage:
    python tools/compare_benchmarks.py
"""

import json
from pathlib import Path
from tabulate import tabulate

def load_all_metadata(metadata_dir='benchmarks/metadata'):
    """Load all metadata files."""
    metadata_files = Path(metadata_dir).glob('*.json')
    benchmarks = []
    
    for file in metadata_files:
        with open(file) as f:
            benchmarks.append(json.load(f))
    
    return sorted(benchmarks, key=lambda x: x['timestamp'])

def generate_comparison_table(benchmarks):
    """Generate comparison table."""
    headers = ['Platform', 'Model', 'Requests', 'Success %', 'Throughput (tok/s)', 'Time (s)', 'Date']
    rows = []
    
    for b in benchmarks:
        r = b['results']
        total = r['success_count'] + r['failure_count']
        success_pct = (r['success_count'] / total * 100) if total > 0 else 0
        
        rows.append([
            b['platform'],
            b['model'],
            total,
            f"{success_pct:.1f}%",
            r['throughput_tokens_per_sec'],
            f"{r['total_time_seconds']:.1f}",
            b['timestamp'][:10]
        ])
    
    return tabulate(rows, headers=headers, tablefmt='github')

def main():
    benchmarks = load_all_metadata()
    
    if not benchmarks:
        print("❌ No benchmarks found in benchmarks/metadata/")
        return
    
    print("# Benchmark Comparison\n")
    print(generate_comparison_table(benchmarks))
    
    # Save to file
    report_path = Path('benchmarks/reports/COMPARISON.md')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write("# Benchmark Comparison\n\n")
        f.write(generate_comparison_table(benchmarks))
    
    print(f"\n✅ Report saved: {report_path}")

if __name__ == '__main__':
    main()
```

---

## 5. Implementation Steps

### Step 1: Create Directory Structure
```bash
mkdir -p benchmarks/{raw,metadata,analysis,reports}
mkdir -p tools
```

### Step 2: Create Analysis Tools
- `tools/analyze_benchmark.py` - Parse results → metadata
- `tools/compare_benchmarks.py` - Compare all benchmarks

### Step 3: Run vLLM Native Test (5K)
```bash
# Test vLLM Offline with 5K requests
time python test_vllm_offline.py batch_5k.jsonl benchmarks/raw/vllm-offline-gemma3-4b-5000-$(date +%Y-%m-%d).jsonl

# Analyze results
python tools/analyze_benchmark.py \
    --platform vllm-offline \
    --model gemma3-4b \
    --input benchmarks/raw/vllm-offline-gemma3-4b-5000-2024-10-28.jsonl \
    --config '{"max_model_len": 4096, "gpu_memory_utilization": 0.90}' \
    --total-time 2400 \
    --model-load-time 25.8
```

### Step 4: If OOM, Tune vLLM Settings (NOT wrapper code)
**Possible vLLM settings to adjust:**
- `--gpu-memory-utilization 0.85` (reduce from 0.90)
- `--max-model-len 2048` (reduce context window)
- `--max-num-batched-tokens 4096` (reduce batch size)
- `--disable-log-stats` (reduce overhead)
- `--kv-cache-dtype fp8` (use quantized KV cache)

### Step 5: Run Ollama Tests
```bash
# Test Ollama with same data
time python -c "
import ollama
import json
from pathlib import Path

with open('batch_5k.jsonl') as f:
    requests = [json.loads(line) for line in f]

results = []
for req in requests:
    response = ollama.chat(model='gemma3:12b', messages=req['body']['messages'])
    results.append(response)

with open('benchmarks/raw/ollama-gemma3-12b-5000-2024-10-28.jsonl', 'w') as f:
    for r in results:
        f.write(json.dumps(r) + '\n')
"

# Analyze
python tools/analyze_benchmark.py \
    --platform ollama \
    --model gemma3-12b \
    --input benchmarks/raw/ollama-gemma3-12b-5000-2024-10-28.jsonl \
    --config '{}' \
    --total-time <MEASURED_TIME>
```

### Step 6: Generate Comparison
```bash
python tools/compare_benchmarks.py
```

---

## 6. What NOT to Do

❌ **Don't build wrapper code** - vLLM handles batching natively  
❌ **Don't chunk requests** - trust vLLM's internal batching  
❌ **Don't add retry logic** - if it fails, it's a config issue  
❌ **Don't build custom queue systems** - use vLLM as-is  

✅ **Do adjust vLLM settings** - memory, context, batch size  
✅ **Do track results properly** - metadata + analysis  
✅ **Do report bugs to vLLM** - they want to know!  
✅ **Do focus on recruiting workflow** - that's our value-add  

---

## 7. Success Criteria

**We'll know the system works when:**
1. ✅ Every test automatically saves metadata
2. ✅ We can run `compare_benchmarks.py` and see all results
3. ✅ We never lose benchmark data again
4. ✅ We can answer "what was the throughput for X?" instantly
5. ✅ We have clean vLLM vs Ollama comparison

**Timeline:**
- **Today:** Build tools, test vLLM 5K natively
- **Tomorrow:** Run Ollama benchmarks, generate comparison
- **This week:** Make final platform decision based on data

---

## Next Actions

1. Create `tools/analyze_benchmark.py`
2. Create `tools/compare_benchmarks.py`
3. Test vLLM Offline with 5K requests (native, no wrappers)
4. If OOM → adjust vLLM settings (memory, context, batch)
5. Run Ollama benchmarks
6. Generate final comparison report

