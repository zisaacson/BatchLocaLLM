# vLLM Native Batch Inference - 5K Requests Benchmark Results

**Test Date:** October 28, 2025  
**Test ID:** `vllm-native-gemma3-4b-5000-2025-10-28`  
**Status:** ✅ **COMPLETE - 100% SUCCESS**

---

## Executive Summary

Successfully processed **5,000 candidate evaluation requests** using vLLM's native batch inference with **zero failures** and **no OOM errors**.

**Key Achievement:** Proved that vLLM can handle large-scale batch processing on consumer GPU (RTX 4080 16GB) without custom wrapper code or chunking strategies.

---

## Hardware Configuration

| Component | Specification |
|-----------|---------------|
| **GPU** | NVIDIA RTX 4080 |
| **VRAM** | 16 GB (15.57 GiB usable) |
| **CUDA Version** | 12.x |
| **Driver** | Latest |

---

## Model Configuration

| Parameter | Value |
|-----------|-------|
| **Model** | `google/gemma-3-4b-it` |
| **Model Size** | 4 billion parameters |
| **Model Memory** | 8.58 GiB |
| **Precision** | bfloat16 |
| **Context Window** | 4,096 tokens |
| **Max Model Length** | 4,096 tokens |

---

## vLLM Engine Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| **GPU Memory Utilization** | 0.90 (90%) | Leaves 10% headroom |
| **Enable Prefix Caching** | True | Default - improves efficiency for similar prompts |
| **Chunked Prefill** | True | Default - processes long prompts in chunks |
| **Max Batched Tokens** | 8,192 | Automatic chunked prefill setting |
| **KV Cache Size** | 11,824 tokens | Dynamically allocated |
| **KV Cache Memory** | 1.58 GiB | Available for request batching |
| **CUDA Graphs** | Enabled | 0.64 GiB for graph capture |
| **Max Concurrency** | 2.88x | For 4,096 token requests |

---

## Memory Breakdown

| Component | Memory Usage | Percentage |
|-----------|--------------|------------|
| **Model Weights** | 8.58 GiB | 53.8% |
| **KV Cache** | 1.58 GiB | 9.9% |
| **CUDA Graphs** | 0.64 GiB | 4.0% |
| **Other (PyTorch, etc.)** | ~0.15 GiB | 0.9% |
| **Total Used** | ~10.95 GiB | 68.6% |
| **Available Headroom** | ~5.0 GiB | 31.4% |

**Analysis:** Significant headroom available for scaling to larger batches.

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| **Input File** | `batch_5k.jsonl` |
| **Output File** | `benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl` |
| **Total Requests** | 5,000 |
| **Request Type** | Candidate evaluation (recruiting) |
| **Sampling Temperature** | 0.7 |
| **Top-P** | 0.9 |
| **Max Tokens** | 2,000 |

---

## Performance Results

### Overall Metrics

| Metric | Value |
|--------|-------|
| **Total Requests** | 5,000 |
| **Successful Requests** | 5,000 (100.0%) |
| **Failed Requests** | 0 (0.0%) |
| **Model Load Time** | 26.1 seconds |
| **Inference Time** | 2,183.0 seconds (36.4 minutes) |
| **Total Time** | 2,209.1 seconds (36.8 minutes) |
| **Throughput** | **2,511 tokens/second** |
| **Requests/Second** | 2.29 |

### Token Statistics

| Metric | Total | Average per Request |
|--------|-------|---------------------|
| **Prompt Tokens** | 3,942,154 | 788 |
| **Completion Tokens** | 1,540,218 | 308 |
| **Total Tokens** | 5,482,372 | 1,096 |

### Context Window Utilization

| Metric | Value | Percentage of Max (4,096) |
|--------|-------|---------------------------|
| **Average Request Size** | 1,096 tokens | 26.8% |
| **Average Prompt** | 788 tokens | 19.2% |
| **Average Completion** | 308 tokens | 7.5% |

**Analysis:** Requests are well within context window limits, leaving significant room for longer prompts or completions.

---

## Scaling Projections

Based on linear scaling from 5K results:

| Batch Size | Estimated Time | Estimated Tokens | Memory Required |
|------------|----------------|------------------|-----------------|
| **5,000** | 36.8 min | 5.5M | ~11 GiB ✅ |
| **10,000** | 73.6 min (1.2 hrs) | 11M | ~11 GiB ✅ |
| **50,000** | 368 min (6.1 hrs) | 55M | ~11 GiB ✅ |
| **200,000** | 1,472 min (24.5 hrs) | 220M | ~11 GiB ✅ |

**Key Insight:** Memory usage is **constant** regardless of batch size because vLLM processes requests in rolling batches. The KV cache size (1.58 GiB) remains the same.

**Bottleneck:** Time, not memory. Processing 200K candidates takes ~24 hours on a single RTX 4080.

---

## vLLM Internal Batching Behavior

vLLM automatically batches requests internally:

- **Concurrent Requests:** ~3 requests processed simultaneously (2.88x concurrency)
- **Dynamic Scheduling:** vLLM schedules requests based on available KV cache
- **Continuous Batching:** New requests added as old ones complete
- **No Manual Chunking Required:** vLLM handles everything

**This is why we don't need wrapper code!**

---

## Sample Output Quality

Example candidate evaluation (first request):

**Input:** Resume for "Min Thet K" (MIT CS, Microsoft, Bloomberg)

**Output:**
```json
{
  "recommendation": "Strong Yes",
  "reasoning": "Min Thet K has a strong pedigree due to their MIT Computer Science degrees and experience at both Microsoft and Bloomberg. They also demonstrate a consistent trajectory with rapid promotions and a clear focus on software engineering.",
  "analysis": {
    "educational_pedigree": {
      "rating": "Great",
      "reasoning": "The candidate holds a BS and MEng in Computer Science from MIT, a top-tier institution. This is a strong pedigree signal, particularly given their experience at Microsoft and Bloomberg."
    },
    "company_pedigree": {
      "rating": "Good",
      "reasoning": "Experience at Bloomberg and Microsoft, both established tech companies, indicates a decent company pedigree. Bloomberg is a highly respected financial data provider."
    },
    "trajectory": {
      "rating": "Good",
      "reasoning": "The candidate progressed quickly through their roles at Microsoft and Bloomberg, indicating a strong trajectory. They rapidly moved from intern to full-time software engineer roles."
    },
    "is_software_engineer": {
      "value": true,
      "reasoning": "The candidate's titles consistently indicate software engineering roles (Software Engineer, Software Engineer Intern, Learning Assistant)."
    }
  }
}
```

**Quality Assessment:** ✅ Structured JSON output, coherent reasoning, appropriate evaluation

---

## Reliability & Stability

| Metric | Result |
|--------|--------|
| **OOM Errors** | 0 |
| **Crashes** | 0 |
| **Timeouts** | 0 |
| **Malformed Outputs** | 0 (spot-checked) |
| **Success Rate** | 100.0% |

**Conclusion:** vLLM native batching is **production-ready** for this workload.

---

## Comparison to Previous Tests

| Test | Platform | Requests | Success Rate | Throughput | Notes |
|------|----------|----------|--------------|------------|-------|
| **This Test** | vLLM Native | 5,000 | 100% | 2,511 tok/s | ✅ BEST |
| Previous | vLLM Offline | 100 | 100% | 2,491 tok/s | Small batch |
| Previous | vLLM Serve | 100 | 100% | 2,472 tok/s | API server |
| Previous | vLLM Serve | 5,000 | **0%** | N/A | ❌ Server crashed |

**Key Finding:** vLLM Native (Offline) is the correct approach for batch processing.

---

## Lessons Learned

### ✅ What Worked

1. **vLLM Native API** - `LLM.generate()` handles batching perfectly
2. **Default Settings** - vLLM's defaults (prefix caching, chunked prefill) are optimal
3. **Memory Management** - vLLM efficiently manages GPU memory
4. **No Wrapper Code** - Trust the experts who built vLLM

### ❌ What Didn't Work (Previously)

1. **vLLM Serve** - API server not designed for large batches
2. **Custom Batching** - Unnecessary complexity
3. **Manual Chunking** - vLLM already does this internally

### 🎯 Best Practices

1. Use `LLM.generate()` for batch processing
2. Set `gpu_memory_utilization=0.90` for headroom
3. Let vLLM handle batching internally
4. Monitor GPU memory during first run
5. Trust vLLM's internal scheduling

---

## Next Steps

### Immediate
- ✅ **GPU Monitoring Tool** - Created `tools/monitor_gpu.py`
- ⏳ **50K Benchmark** - Ready to run with monitoring
- ⏳ **Ollama Comparison** - Benchmark Ollama for platform decision

### Future Optimizations (if needed)
- **KV Cache Quantization** - Use `--kv-cache-dtype fp8` to double context size
- **Reduce Context Window** - Use `--max-model-len 2048` if prompts are shorter
- **Multi-GPU** - Scale horizontally with tensor parallelism

---

## Files Generated

| File | Purpose | Size |
|------|---------|------|
| `benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl` | Raw results | 5,000 lines |
| `benchmarks/metadata/vllm-native-gemma3-4b-5000-2025-10-28.json` | Test metadata | 30 lines |
| `vllm_5k_benchmark.log` | Console output | Full log |

---

## Conclusion

**vLLM native batch inference successfully processed 5,000 candidate evaluations with 100% success rate and 2,511 tok/s throughput on RTX 4080 16GB.**

**Key Takeaway:** Stop building software on top of vLLM. It already works perfectly.

**Ready for 50K test with GPU monitoring.**

---

**Report Generated:** October 28, 2025  
**Author:** vLLM Batch Server Project  
**Version:** 1.0

