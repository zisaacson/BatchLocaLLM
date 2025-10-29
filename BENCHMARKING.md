# Benchmarking System

This system stores and exposes benchmark data to help users (and AI agents) choose the right model for their workload.

## Overview

The benchmarking system:
1. **Stores** benchmark results in SQLite database
2. **Exposes** results via REST API
3. **Helps users** make informed decisions about model selection
4. **Provides estimates** for processing time based on historical data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Benchmark System                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   CLI Tools  │─────▶│   Database   │◀─────│  REST API │ │
│  └──────────────┘      │   (SQLite)   │      └───────────┘ │
│                        └──────────────┘                      │
│                                                               │
│  Tools:                 Schema:                API:          │
│  • benchmark_models.py  • model_name           • GET /v1/... │
│  • query_benchmarks.py  • num_workers          • benchmarks  │
│  • import_results.py    • rate (req/s)                       │
│                         • success_rate                       │
│                         • sample_responses                   │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

```sql
CREATE TABLE benchmark_results (
    id INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_size_params TEXT,        -- e.g., "1b", "4b", "12b"
    model_size_bytes INTEGER,
    num_workers INTEGER NOT NULL,
    context_window INTEGER,
    num_requests INTEGER NOT NULL,
    avg_prompt_tokens INTEGER,
    avg_completion_tokens INTEGER,
    total_time_seconds REAL NOT NULL,
    requests_per_second REAL NOT NULL,
    time_per_request_seconds REAL NOT NULL,
    successful_requests INTEGER NOT NULL,
    failed_requests INTEGER NOT NULL,
    success_rate REAL NOT NULL,
    sample_responses TEXT,          -- JSON array
    created_at INTEGER NOT NULL,
    benchmark_type TEXT NOT NULL,   -- "model_comparison", "worker_optimization", etc.
    notes TEXT,
    hardware_info TEXT              -- JSON
);
```

## CLI Tools

### 1. Benchmark Models

Run benchmarks and save to database:

```bash
# Benchmark specific models
python tools/benchmark_models.py --models gemma3:1b gemma3:4b gemma3:12b --compare

# Benchmark with different request counts
python tools/benchmark_models.py --models gemma3:4b --requests 100 500 1000

# Benchmark with different worker counts
python tools/benchmark_models.py --models gemma3:4b --workers 2 4 8 16

# List existing benchmarks
python tools/benchmark_models.py --list

# Export to JSON
python tools/benchmark_models.py --export benchmarks.json
```

### 2. Query Benchmarks

Query benchmark database for decision-making:

```bash
# List all benchmarked models
python tools/query_benchmarks.py --list

# Get estimate for specific workload
python tools/query_benchmarks.py --model gemma3:4b --requests 50000

# Compare all models for a workload
python tools/query_benchmarks.py --compare --requests 200000

# Show detailed stats for a model
python tools/query_benchmarks.py --model gemma3:4b --details
```

### 3. Import Results

Import existing benchmark results:

```bash
python tools/import_benchmark_results.py
```

## REST API Endpoints

### List All Models

```bash
GET /v1/benchmarks/models
```

**Response:**
```json
{
  "models": [
    {
      "model": "gemma3:1b",
      "rate_req_per_sec": 0.92,
      "success_rate_pct": 100.0,
      "workers": 4,
      "last_benchmarked": 1761594486
    },
    {
      "model": "gemma3:4b",
      "rate_req_per_sec": 0.52,
      "success_rate_pct": 100.0,
      "workers": 4,
      "last_benchmarked": 1761594486
    }
  ],
  "total": 2
}
```

### Get Model Benchmarks

```bash
GET /v1/benchmarks/models/{model_name}?limit=10
```

**Example:**
```bash
curl http://localhost:4080/v1/benchmarks/models/gemma3:4b
```

**Response:**
```json
{
  "model": "gemma3:4b",
  "benchmarks": [
    {
      "model": "gemma3:4b",
      "model_size_params": "4b",
      "num_requests": 100,
      "num_workers": 4,
      "rate_req_per_sec": 0.52,
      "time_per_request_sec": 1.91,
      "success_rate_pct": 100.0,
      "avg_prompt_tokens": null,
      "avg_completion_tokens": null,
      "benchmark_type": "model_comparison",
      "created_at": 1761594486
    }
  ],
  "total": 1
}
```

### Estimate Batch Time

```bash
GET /v1/benchmarks/estimate?model={model}&num_requests={count}
```

**Example:**
```bash
curl "http://localhost:4080/v1/benchmarks/estimate?model=gemma3:4b&num_requests=50000"
```

**Response:**
```json
{
  "model": "gemma3:4b",
  "num_requests": 50000,
  "estimate": {
    "total_time_seconds": 96153.8,
    "total_time_hours": 26.7,
    "total_time_days": 1.11,
    "rate_req_per_sec": 0.52,
    "time_per_request_sec": 1.91
  },
  "based_on_benchmark": {
    "test_size": 100,
    "workers": 4,
    "success_rate_pct": 100.0,
    "date": 1761594486
  }
}
```

### Compare Models

```bash
GET /v1/benchmarks/compare?num_requests={count}
```

**Example:**
```bash
curl "http://localhost:4080/v1/benchmarks/compare?num_requests=200000"
```

**Response:**
```json
{
  "num_requests": 200000,
  "models": [
    {
      "model": "gemma3:1b",
      "model_size_params": "1b",
      "rate_req_per_sec": 0.92,
      "estimated_time_hours": 60.4,
      "estimated_time_days": 2.52,
      "success_rate_pct": 100.0,
      "workers": 4,
      "speedup_vs_slowest": 4.07,
      "time_saved_hours": 185.2
    },
    {
      "model": "gemma3:4b",
      "model_size_params": "4b",
      "rate_req_per_sec": 0.52,
      "estimated_time_hours": 106.3,
      "estimated_time_days": 4.43,
      "success_rate_pct": 100.0,
      "workers": 4,
      "speedup_vs_slowest": 2.31,
      "time_saved_hours": 139.3
    },
    {
      "model": "gemma3:12b",
      "model_size_params": "12b",
      "rate_req_per_sec": 0.23,
      "estimated_time_hours": 245.6,
      "estimated_time_days": 10.23,
      "success_rate_pct": 100.0,
      "workers": 4,
      "speedup_vs_slowest": 1.0,
      "time_saved_hours": 0.0
    }
  ],
  "total_models": 3
}
```

## Usage in AI Agents

AI agents can query the benchmark API to make informed decisions:

```python
import httpx

# Get all available models
response = httpx.get("http://localhost:4080/v1/benchmarks/models")
models = response.json()["models"]

# Get estimate for specific workload
response = httpx.get(
    "http://localhost:4080/v1/benchmarks/estimate",
    params={"model": "gemma3:4b", "num_requests": 50000}
)
estimate = response.json()

print(f"Estimated time: {estimate['estimate']['total_time_hours']:.1f} hours")

# Compare all models
response = httpx.get(
    "http://localhost:4080/v1/benchmarks/compare",
    params={"num_requests": 200000}
)
comparison = response.json()

# Choose fastest model
fastest = comparison["models"][0]
print(f"Fastest model: {fastest['model']} ({fastest['estimated_time_hours']:.1f} hours)")
```

## Current Benchmark Data

As of the latest benchmark run:

| Model | Context Window | Rate (req/s) | 50K Time | 200K Time | Speedup vs 12B |
|-------|----------------|--------------|----------|-----------|----------------|
| gemma3:1b | **32K** | 0.92 | 15.1 hours | 60.4 hours (2.5 days) | 4.1x ⚡ |
| gemma3:4b | **128K** | 0.52 | 26.7 hours | 106.3 hours (4.4 days) | 2.3x 🔥 |
| gemma3:12b | **128K** | 0.23 | 60.4 hours | 245.6 hours (10.2 days) | 1.0x |

**Important Note**: The 1B model has a smaller 32K context window (vs 128K for 4B/12B models). This means:
- ✅ **Faster** for short prompts (< 32K tokens)
- ⚠️ **Cannot handle** long contexts that exceed 32K tokens
- 🎯 **Best for**: Short candidate evaluations, quick assessments
- 🎯 **Not suitable for**: Long documents, extensive context requirements

## Continuous Benchmarking

To keep benchmarks up-to-date:

1. **Run benchmarks regularly** with different configurations
2. **Track performance over time** to detect regressions
3. **Benchmark new models** as they become available
4. **Test different worker counts** to find optimal configuration

```bash
# Weekly benchmark run
python tools/benchmark_models.py \
  --models gemma3:1b gemma3:4b gemma3:12b \
  --requests 100 500 1000 \
  --workers 2 4 8
```

## Next Steps

1. ✅ Benchmark storage system implemented
2. ✅ REST API endpoints exposed
3. ✅ CLI tools for querying
4. ✅ Context window size tracking
5. ⏳ Add hardware info tracking (GPU model, VRAM, etc.)
6. ⏳ Add quality metrics (response length, coherence scores)
7. ⏳ Add cost estimates (if using cloud APIs)
8. ⏳ Benchmark with different context sizes (test impact of prompt length)

