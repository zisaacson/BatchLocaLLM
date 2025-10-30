# Unified Benchmarking System

**One format. One location. One source of truth.**

## The Problem We Solved

Before:
- ❌ Multiple benchmark scripts with different output formats
- ❌ Data scattered across `benchmark_results/`, `benchmarks/metadata/`, `benchmarks/raw/`
- ❌ Web UI couldn't display half the data
- ❌ Lost data from incomplete runs
- ❌ No way to compare results

Now:
- ✅ **One unified format** for all benchmarks
- ✅ **One location** (`benchmark_results/`) for all results
- ✅ **One script** (`benchmark_unified.py`) for all tests
- ✅ **Web UI** that displays everything correctly
- ✅ **Automatic saving** - never lose data again

---

## Quick Start

### 1. Migrate Old Data (One Time)

```bash
python migrate_benchmarks.py
```

This converts all your old benchmark data to the new unified format.

### 2. Run New Benchmarks

**Test offline batch mode (recommended):**
```bash
python benchmark_unified.py \
  --name gemma3_4b_5k \
  --model google/gemma-3-4b-it \
  --batch-file batch_5k.jsonl \
  --mode offline
```

**Test server mode:**
```bash
# First, start vLLM server
vllm serve google/gemma-3-4b-it --port 4080

# Then run benchmark
python benchmark_unified.py \
  --name gemma3_4b_5k_server \
  --model google/gemma-3-4b-it \
  --batch-file batch_5k.jsonl \
  --mode server
```

**Compare both modes:**
```bash
python benchmark_unified.py \
  --name gemma3_4b_comparison \
  --model google/gemma-3-4b-it \
  --batch-file batch_5k.jsonl \
  --mode both
```

**Limit test size:**
```bash
python benchmark_unified.py \
  --name gemma3_4b_100 \
  --model google/gemma-3-4b-it \
  --batch-file batch_5k.jsonl \
  --size 100 \
  --mode offline
```

### 3. View Results

**Web UI (recommended):**
```bash
# Make sure server is running
python serve_results.py

# Open browser
http://localhost:8001/benchmarks.html
```

**Command line:**
```bash
cat benchmark_results/gemma3_4b_5k_*.json | jq .
```

---

## Unified Data Format

Every benchmark result has this structure:

```json
{
  "test_name": "gemma3_4b_5k",
  "model": "google/gemma-3-4b-it",
  "mode": "offline_batch",
  "timestamp": "2025-10-29T23:45:00",
  
  "model_load_time_seconds": 26.08,
  "inference_time_seconds": 2183.03,
  "total_time_seconds": 2209.11,
  
  "num_requests": 5000,
  "successful_requests": 5000,
  "failed_requests": 0,
  "success_rate_pct": 100.0,
  
  "prompt_tokens": 3942154,
  "completion_tokens": 1540218,
  "total_tokens": 5482372,
  "avg_prompt_tokens": 788.4,
  "avg_completion_tokens": 308.0,
  
  "throughput_req_per_sec": 2.29,
  "throughput_tokens_per_sec": 2511,
  
  "latency_p50_ms": 436.61,
  "latency_p95_ms": 436.61,
  "latency_p99_ms": 436.61,
  "latency_min_ms": 436.61,
  "latency_max_ms": 436.61,
  
  "config": {
    "max_model_len": 4096,
    "gpu_memory_utilization": 0.9,
    "enable_prefix_caching": true
  },
  
  "notes": "Production test with 5k candidates"
}
```

**All fields are always present.** No more missing data. No more incompatible formats.

---

## Common Workflows

### Benchmark a New Model

```bash
python benchmark_unified.py \
  --name llama32_3b_5k \
  --model meta-llama/Llama-3.2-3B-Instruct \
  --batch-file batch_5k.jsonl \
  --mode offline
```

### Quick Quality Test (100 requests)

```bash
python benchmark_unified.py \
  --name qwen3_4b_quick \
  --model Qwen/Qwen2.5-3B-Instruct \
  --batch-file batch_5k.jsonl \
  --size 100 \
  --mode offline
```

### Compare Offline vs Server Performance

```bash
# Start server first
vllm serve google/gemma-3-4b-it --port 4080 --enable-prefix-caching

# Run comparison
python benchmark_unified.py \
  --name gemma3_offline_vs_server \
  --model google/gemma-3-4b-it \
  --batch-file batch_5k.jsonl \
  --size 1000 \
  --mode both
```

This will:
1. Run offline batch test
2. Run server test
3. Save both results
4. Print comparison showing which is faster

---

## Understanding the Results

### Key Metrics

**Throughput (req/s)**: How many requests per second
- Higher is better
- Offline batch is usually faster for large batches

**Throughput (tok/s)**: How many tokens per second
- Higher is better
- Indicates raw generation speed

**Latency P50/P95**: Response time percentiles
- Lower is better
- P50 = median response time
- P95 = 95% of requests faster than this
- Only accurate for server mode (offline batch estimates)

**Success Rate**: Percentage of successful requests
- Should be 100%
- Lower means errors occurred

### Comparing Results

The web UI shows all results in a table. Look for:
- **Time**: Total time to complete (lower is better)
- **Throughput**: Requests/tokens per second (higher is better)
- **Success Rate**: Should be 100%

---

## File Locations

```
benchmark_results/          # ALL benchmark results go here
  ├── gemma3_4b_5k_20251029_234500.json
  ├── llama32_3b_5k_20251029_120000.json
  └── ...

benchmarks/metadata/        # OLD FORMAT (migrated)
benchmarks/raw/             # OLD FORMAT (migrated)
```

**Only use `benchmark_results/` going forward.**

---

## Troubleshooting

### "Server not responding"

Start the vLLM server:
```bash
vllm serve google/gemma-3-4b-it --port 4080
```

### "No benchmark data available"

Run a benchmark first:
```bash
python benchmark_unified.py --name test --size 10 --mode offline
```

### "Results not showing in web UI"

1. Check file exists: `ls -lh benchmark_results/`
2. Restart web server: `python serve_results.py`
3. Refresh browser: http://localhost:8001/benchmarks.html

### "Old data not showing"

Run migration:
```bash
python migrate_benchmarks.py
```

---

## What Changed

### Old Way (DON'T USE)
```bash
# Multiple scripts, different formats
python benchmark_vllm_native.py batch_5k.jsonl output.jsonl
python benchmark_vllm_modes.py
python benchmark_batch_vs_server.py --size 5000
./test_gemma3_4b_5k_offline.sh
```

### New Way (USE THIS)
```bash
# One script, unified format
python benchmark_unified.py --name test_name --mode offline
```

---

## Next Steps

1. ✅ Run `python migrate_benchmarks.py` to convert old data
2. ✅ Use `python benchmark_unified.py` for all new benchmarks
3. ✅ View results at http://localhost:8001/benchmarks.html
4. ✅ Never lose benchmark data again

---

## Questions?

- **Where do results go?** → `benchmark_results/`
- **What script do I use?** → `benchmark_unified.py`
- **How do I view results?** → http://localhost:8001/benchmarks.html
- **What about old data?** → Run `migrate_benchmarks.py` once

**That's it. Simple.**

