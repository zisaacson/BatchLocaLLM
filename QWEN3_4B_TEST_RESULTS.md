# ✅ Qwen 3 4B Test Results

**Date:** 2025-10-28  
**Model:** Qwen/Qwen3-4B-Instruct-2507  
**Test Size:** 10 requests  

---

## 📊 Results Summary

| Metric | Value |
|--------|-------|
| **Success Rate** | ✅ 10/10 (100%) |
| **Throughput** | 1,533 tokens/sec |
| **Requests/sec** | 1.39 |
| **Inference Time** | 7.2 seconds |
| **Model Load Time** | 678 seconds (first time only) |
| **Model Size** | 7.6 GB |
| **Memory Usage** | ~11 GB total |

---

## 📈 Comparison to Gemma 3 4B

| Model | Throughput | Difference |
|-------|------------|------------|
| **Gemma 3 4B** | 2,511 tok/s | Baseline |
| **Qwen 3 4B** | 1,533 tok/s | **-39%** slower |

**Analysis:**
- Qwen 3 4B is **39% slower** than Gemma 3 4B
- Both models are similar size (~8 GB)
- Both models work well on RTX 4080 16GB
- **Gemma 3 4B is the better choice for performance**

---

## 🔍 Detailed Metrics

**Token Statistics:**
- Prompt tokens: 7,946
- Completion tokens: 3,112
- Total tokens: 11,058

**Timing:**
- Model download: ~10 minutes (first time only)
- Model load: 678 seconds (~11 minutes)
- Inference: 7.2 seconds
- Total: 685.7 seconds

**Memory:**
- Model weights: 7.6 GB
- KV cache: ~2 GB
- CUDA graphs: ~0.7 GB
- Total: ~11 GB

---

## 🎯 Estimated Performance for Larger Batches

Based on 1,533 tok/s throughput:

| Batch Size | Estimated Time |
|------------|----------------|
| 100 | ~1.5 minutes |
| 5,000 | ~60 minutes (1 hour) |
| 50,000 | ~10 hours |
| 200,000 | ~40 hours |

**Note:** These are rough estimates. Actual performance may vary.

---

## ✅ Conclusions

1. ✅ **Qwen 3 4B works on RTX 4080 16GB**
2. ✅ **100% success rate** on test batch
3. ⚠️ **39% slower than Gemma 3 4B**
4. ✅ **Good alternative if you need Qwen-specific features**
5. 🎯 **Gemma 3 4B recommended for best performance**

---

## 📁 Files Generated

- **Results:** `qwen3_4b_test_results.jsonl`
- **Metadata:** `benchmarks/metadata/qwen3-4b-10-2025-10-28.json`
- **Test Script:** `test_qwen3_4b.py`

---

## 🚀 Next Steps

1. ✅ Qwen 3 4B tested successfully
2. ⏳ Test Llama 3.2 1B next?
3. ⏳ Test Llama 3.2 3B?
4. ⏳ Run larger batch (5K) with Qwen 3 4B?

---

**Updated:** BENCHMARKING_JOURNEY.md with Qwen 3 4B results

