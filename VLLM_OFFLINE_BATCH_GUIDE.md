# vLLM Offline Batch Processing Guide

## Overview

You're building a **vLLM batch processing server** to score 170K+ candidates efficiently. This guide documents the correct approach using vLLM's built-in offline batch mode.

---

## Architecture

```
Your Main App (Aris)
    ↓ (sends batch job request)
FastAPI Server (job queue)
    ↓ (queues jobs)
vLLM Offline Batch Processor
    ↓ (processes in batches)
Results Storage (JSONL files)
    ↓ (serves results)
Your Main App (polls for completion)
```

---

## Key Discovery: vLLM Offline Batch Mode

vLLM has a **built-in offline batch processor** that's MUCH more efficient than using `llm.generate()`:

```bash
python -m vllm.entrypoints.openai.run_batch \
    -i input.jsonl \
    -o output.jsonl \
    --model "Qwen/Qwen3-4B-Instruct-2507" \
    --gpu-memory-utilization 0.8 \
    --enforce-eager \
    --max-model-len 8192 \
    --max-num-seqs 256 \
    --enable-prefix-caching
```

### Advantages:
- ✅ **Processes requests incrementally** - doesn't wait for all to complete
- ✅ **Saves results as it goes** - no data loss if it crashes
- ✅ **Optimized for batch processing** - better memory management
- ✅ **OpenAI-compatible format** - works with standard batch JSONL files

---

## Critical Issue: Model Names

**PROBLEM:** Your `batch_5k.jsonl` file has Ollama model names (`gemma3:12b`), but vLLM expects HuggingFace model names (`Qwen/Qwen3-4B-Instruct-2507`).

**SOLUTION:** Use `fix_batch_model_names.py` to convert:

```bash
python3 fix_batch_model_names.py \
    batch_5k.jsonl \
    batch_5k_qwen.jsonl \
    "Qwen/Qwen3-4B-Instruct-2507"
```

This replaces the `"model"` field in each request's `body` with the correct HuggingFace model name.

---

## Batch File Format

Each line in the JSONL file must be:

```json
{
  "custom_id": "unique-id",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "Qwen/Qwen3-4B-Instruct-2507",  // ← MUST be HuggingFace format
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "temperature": 0.7,
    "max_tokens": 2000
  }
}
```

---

## Performance Benchmarks

### Qwen 3-4B (5K batch, offline mode)
- **Speed**: ~2.45 req/s
- **Estimated time**: ~33 minutes for 5000 requests
- **Throughput**: ~147 requests/minute
- **For 170K candidates**: ~19 hours

### Comparison to Previous Approach
- **Old approach** (`llm.generate()`): Got stuck at 777/5000 after 24 hours
- **New approach** (offline batch): Processes incrementally, saves as it goes

---

## Why the Old Approach Failed

The previous `test_qwen3_4b_5k.py` script used:

```python
outputs = llm.generate(prompts, sampling_params)  # Waits for ALL to complete
```

**Problems:**
1. **No incremental saving** - only saves when ALL 5000 complete
2. **Memory issues** - holds all results in memory
3. **No progress tracking** - can't tell if it's stuck or working
4. **Data loss** - if it crashes, you lose everything

---

## Recommended Workflow

### 1. Prepare Batch Files

For each model you want to test, create a model-specific batch file:

```bash
# Qwen 3-4B
python3 fix_batch_model_names.py batch_5k.jsonl batch_5k_qwen.jsonl "Qwen/Qwen3-4B-Instruct-2507"

# Gemma 3-4B
python3 fix_batch_model_names.py batch_5k.jsonl batch_5k_gemma.jsonl "google/gemma-3-4b-it"

# Llama 3.2-3B
python3 fix_batch_model_names.py batch_5k.jsonl batch_5k_llama.jsonl "meta-llama/Llama-3.2-3B-Instruct"
```

### 2. Run Benchmarks

```bash
# Qwen 3-4B
./test_qwen3_4b_5k_offline.sh

# Monitor progress
tail -f qwen3_4b_5k_offline.log
```

### 3. Analyze Results

Use the web viewer at `http://localhost:8001/` to:
- Compare model responses side-by-side
- Filter for disagreements
- Find good/bad examples for in-context learning

---

## Next Steps

### Immediate:
1. ✅ Complete Qwen 3-4B benchmark (running now)
2. ⏳ Test other models (Gemma 3-4B, Llama 3.2-3B)
3. ⏳ Find the fastest + highest quality model

### Production:
1. Build FastAPI server to accept batch job requests
2. Implement job queue (Redis/Celery or simple file-based)
3. Add monitoring (Grafana + GPU metrics)
4. Scale to 170K+ candidates

---

## Monitoring & Logging

**TODO:** Set up proper monitoring to prevent the "stuck at 777/5000" issue:

1. **Grafana Dashboard**:
   - GPU utilization over time
   - Requests processed per minute
   - Memory usage
   - Temperature

2. **Alerting**:
   - Alert if GPU utilization drops below 50% for >5 minutes
   - Alert if no progress for >10 minutes
   - Alert if memory usage >95%

3. **Structured Logging**:
   - Log every 100 requests processed
   - Log checkpoint saves
   - Log errors with full context

---

## Files Created

- `test_qwen3_4b_5k_offline.sh` - Bash script to run offline batch mode
- `fix_batch_model_names.py` - Python script to fix model names in batch files
- `batch_5k_qwen.jsonl` - Fixed batch file for Qwen 3-4B
- `VLLM_OFFLINE_BATCH_GUIDE.md` - This guide

---

## Key Takeaways

1. **Use vLLM's offline batch mode** - don't reinvent the wheel
2. **Fix model names** - Ollama format ≠ HuggingFace format
3. **Monitor everything** - GPU, memory, progress
4. **Save incrementally** - never lose 24 hours of work again
5. **Keep it simple** - vLLM already has what you need

