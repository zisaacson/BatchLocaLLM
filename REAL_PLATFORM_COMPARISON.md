# REAL Platform Comparison: vLLM vs Ollama Batch Processing

**Date:** October 28, 2024  
**Hardware:** RTX 4080 16GB  
**Test Data:** Real Aris candidate evaluation prompts

---

## 🎯 Executive Summary

We tested **THREE** different approaches for batch LLM inference:

1. **vLLM Offline (Native Batching)** - `LLM.generate(prompts)` ← **NATIVE BATCHING!**
2. **vLLM Serve (API mode)** - Custom async scripts hitting OpenAI-compatible API
3. **Ollama + Custom Batch Wrapper** - SQLite queue + custom Python wrapper

**KEY FINDING:** I was writing custom async scripts for vLLM Serve when vLLM **ALREADY HAS NATIVE BATCH PROCESSING** via the offline `LLM.generate()` API!

---

## 📊 Results Summary (100 Requests)

| Approach | Model | Throughput | Time | Success | Architecture |
|----------|-------|------------|------|---------|--------------|
| **vLLM Offline** | Gemma 3 4B | **2,491 tok/s** | 45s | 100% | ✅ **NATIVE** |
| vLLM Serve | Gemma 3 4B | 2,472 tok/s | 46s | 100% | ❌ Custom scripts |
| Ollama | Gemma 3 12B | ❓ Unknown | ❓ | 100% | ❌ Custom wrapper |

**Winner:** vLLM Offline - Native batching, no custom code needed!

---

## 🔬 Detailed Comparison

### 1. vLLM Offline (Native Batching) ✅ RECOMMENDED

**How it works:**
```python
from vllm import LLM, SamplingParams

# Load model once
llm = LLM(model="google/gemma-3-4b-it")

# Process ALL prompts in one batch - NATIVE!
outputs = llm.generate(prompts, sampling_params)
```

**Results (100 requests):**
```
Model load time:     26.54s (one-time cost)
Processing time:     45.03s
Total time:          71.57s
Throughput:          2.22 req/s
Tokens/sec:          2,491 tok/s
Success rate:        100%
```

**Pros:**
- ✅ **NATIVE batching** - no custom code!
- ✅ Highest throughput (2,491 tok/s)
- ✅ Simple API - just `llm.generate(prompts)`
- ✅ 100% success rate
- ✅ One-time model load cost
- ✅ Automatic continuous batching
- ✅ Optimal GPU utilization

**Cons:**
- ⚠️ Model stays in memory (11.5 GB)
- ⚠️ One-time load cost (26s)
- ⚠️ Limited to 4B models on RTX 4080 16GB

**Use case:** Perfect for batch processing where you load model once and process many batches

---

### 2. vLLM Serve (API Mode) ⚠️ NOT RECOMMENDED

**How it works:**
```python
# Start server
vllm serve google/gemma-3-4b-it --port 8000

# Custom async script to hit API
async def process_batch():
    async with aiohttp.ClientSession() as session:
        tasks = [call_api(session, req) for req in requests]
        await asyncio.gather(*tasks)
```

**Results (100 requests):**
```
Processing time:     46s
Throughput:          2.17 req/s
Tokens/sec:          2,472 tok/s
Success rate:        100%
```

**Pros:**
- ✅ OpenAI-compatible API
- ✅ Can serve multiple clients
- ✅ Good throughput

**Cons:**
- ❌ **Requires custom async scripts** - unnecessary!
- ❌ Server overhead
- ❌ Network latency
- ❌ More complex setup
- ❌ Crashes on large batches (5K failed)

**Use case:** Only if you need OpenAI-compatible API for multiple clients

---

### 3. Ollama + Custom Batch Wrapper

**How it works:**
```python
# Custom Python wrapper with SQLite queue
# Full production system with metrics, monitoring, etc.
```

**Results:**
```
9 requests:   100% success (no throughput data)
99 requests:  100% success (no throughput data)
Model:        Gemma 3 12B (3x larger!)
```

**Pros:**
- ✅ Runs larger model (12B vs 4B)
- ✅ Production-ready architecture
- ✅ SQLite persistence
- ✅ Built-in metrics
- ✅ Quantization (3.3 GB vs 8.6 GB)

**Cons:**
- ❌ **Custom wrapper needed** - complex!
- ❌ Unknown throughput
- ❌ Not tested at scale (5K)
- ❌ More moving parts

**Use case:** If you need 12B model and production features

---

## 💡 Key Insights

### I Fucked Up!

I was writing **custom async scripts** for vLLM Serve when vLLM **ALREADY HAS NATIVE BATCH PROCESSING**!

The vLLM docs clearly show:
```python
# Offline Batched Inference
llm = LLM(model="facebook/opt-125m")
outputs = llm.generate(prompts, sampling_params)  # ← NATIVE BATCHING!
```

This is the **official, recommended way** to do batch processing with vLLM!

### Why vLLM Offline is Better:

1. **Native batching** - vLLM handles everything internally
2. **Continuous batching** - optimal GPU utilization
3. **No network overhead** - direct Python API
4. **Simpler code** - no async/await complexity
5. **Better performance** - 2,491 tok/s vs 2,472 tok/s

### When to Use Each:

| Use Case | Recommended Approach |
|----------|---------------------|
| Batch processing (5K-200K requests) | **vLLM Offline** |
| Multiple concurrent clients | vLLM Serve |
| Need 12B+ model | Ollama (with quantization) |
| Production monitoring/metrics | Ollama wrapper |
| OpenAI API compatibility | vLLM Serve |

---

## 🚀 Recommended Architecture

### For Your Use Case (5K-200K batches):

**Use vLLM Offline with Native Batching:**

```python
#!/usr/bin/env python3
from vllm import LLM, SamplingParams
import json

# Load model once
llm = LLM(
    model="google/gemma-3-4b-it",
    max_model_len=4096,
    gpu_memory_utilization=0.90,
)

# Read all requests
with open("batch_5k.jsonl") as f:
    requests = [json.loads(line) for line in f]

# Prepare prompts
prompts = [format_prompt(req) for req in requests]

# Process ALL in one batch - NATIVE!
sampling_params = SamplingParams(temperature=0.7, max_tokens=2000)
outputs = llm.generate(prompts, sampling_params)

# Save results
with open("results.jsonl", "w") as f:
    for req, output in zip(requests, outputs):
        result = {
            "custom_id": req["custom_id"],
            "response": output.outputs[0].text
        }
        f.write(json.dumps(result) + "\n")
```

**That's it!** No custom async code, no server, no complexity!

---

## 📈 Performance Projections

Based on vLLM Offline results (2,491 tok/s, 2.22 req/s):

| Batch Size | Estimated Time | Tokens Processed |
|------------|----------------|------------------|
| 1,000 | ~7.5 minutes | ~1.1M tokens |
| 5,000 | **~37 minutes** | ~5.6M tokens |
| 10,000 | ~1.2 hours | ~11M tokens |
| 50,000 | ~6.3 hours | ~56M tokens |
| 200,000 | **~25 hours** | ~224M tokens |

**Note:** Model load time (26s) is one-time cost, amortized across all batches.

---

## ✅ Action Items

### Immediate:
1. ✅ **Use vLLM Offline for all batch processing**
2. ❌ **Stop using custom async scripts** - unnecessary!
3. ✅ **Test vLLM Offline with 5K batch**
4. ✅ **Simplify codebase** - remove custom batching code

### Future:
1. Test Ollama throughput for comparison
2. Consider Ollama if 12B model quality is significantly better
3. Add simple progress tracking to vLLM Offline script
4. Test with 10K, 50K batches

---

## 🎓 Lessons Learned

1. **RTFM!** - vLLM docs clearly show native batching
2. **Don't over-engineer** - native solution is often best
3. **Test all approaches** - offline mode was fastest
4. **Simplicity wins** - less code = fewer bugs

---

## 📝 Final Recommendation

**Use vLLM Offline (Native Batching) for your batch processing needs.**

**Why:**
- ✅ Highest throughput (2,491 tok/s)
- ✅ Native batching - no custom code
- ✅ Simplest implementation
- ✅ 100% success rate
- ✅ Official vLLM recommendation

**Only use alternatives if:**
- Need 12B+ model → Ollama (quantization)
- Need OpenAI API → vLLM Serve
- Need production metrics → Add to vLLM Offline script

---

**Status:** vLLM Offline is the clear winner!  
**Next:** Test with 5K batch to validate scaling

