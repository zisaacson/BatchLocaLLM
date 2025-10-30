# 📊 Current Benchmark Results

**Last Updated:** 2025-10-28 11:15 AM

---

## ✅ Completed Tests

### **1. Gemma 3 4B** 🏆 **BEST QUALITY**

**Model:** `google/gemma-3-4b-it`  
**Status:** ✅ COMPLETE  
**File:** `benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl`

| Metric | Value |
|--------|-------|
| **Batch Size** | 5,000 requests |
| **Success Rate** | 100% (5,000/5,000) |
| **Total Time** | 36.8 minutes |
| **Throughput** | **2,511 tokens/second** |
| **Avg Prompt Tokens** | 788 |
| **Avg Completion Tokens** | 308 |
| **Avg Total Tokens** | 1,096 |

**Sample Response:**
```json
{
  "recommendation": "Strong Yes",
  "reasoning": "Min Thet K has a strong pedigree due to their MIT Computer 
               Science degrees and experience at both Microsoft and Bloomberg. 
               They also demonstrate a consistent trajectory with rapid 
               promotions and a clear focus on software engineering.",
  "analysis": {
    "educational_pedigree": {
      "rating": "Great",
      "reasoning": "The candidate holds a BS and MEng in Computer Science 
                   from MIT, a top-tier institution..."
    }
  }
}
```

**Quality:** ✅ Excellent - Structured JSON, detailed reasoning, coherent analysis

---

### **2. Llama 3.2 1B** 🚀 **FASTEST**

**Model:** `meta-llama/Llama-3.2-1B-Instruct`  
**Status:** ✅ COMPLETE  
**File:** `llama32_1b_5k_results.jsonl`

| Metric | Value |
|--------|-------|
| **Batch Size** | 5,000 requests |
| **Success Rate** | 100% (5,000/5,000) |
| **Total Time** | 1.8 minutes |
| **Throughput** | **19,813 tokens/second** |
| **Avg Prompt Tokens** | 308 |
| **Avg Completion Tokens** | 121 |
| **Avg Total Tokens** | 429 |

**Sample Response:**
```
Be clear and concise.

**Your Turn!**

Please fill in the fields with your evaluation and rationale. Remember to 
address the key areas of evaluation, such as Educational Pedigree, Company 
Pedigree, Trajectory, and Software Engineer. Use evidence from the candidate 
profile to support your recommendations. This is a high-stakes decision, and 
your evaluation will impact the candidate's future opportunities.
```

**Quality:** ⚠️ Poor - Doesn't follow instructions, asks user to fill in fields instead of evaluating

**Speed vs Quality Tradeoff:**
- ✅ **7.9x faster** than Gemma 3 4B
- ✅ **56% cheaper** on Parasail ($4.05 vs $9.31 per 100K)
- ❌ **Much shorter outputs** (121 vs 308 tokens)
- ❌ **Lower quality** - doesn't complete the task properly

---

### **3. Qwen 3 4B** 🔄 **RUNNING**

**Model:** `Qwen/Qwen3-4B-Instruct-2507`  
**Status:** 🔄 IN PROGRESS (Terminal 3)  
**File:** `qwen3_4b_5k_results.jsonl` (being written)

| Metric | Value |
|--------|-------|
| **Batch Size** | 5,000 requests |
| **Progress** | 42/5,000 (~1%) |
| **Est. Completion** | ~2 hours |
| **Throughput** | ~740 tokens/second (output) |
| **Memory Config** | gpu_util=0.8, enforce_eager=True |

**Notes:**
- Using optimized memory settings to avoid OOM
- Memory optimizer prevented OOM error!
- Slower than Gemma 3 4B (740 vs 2,511 tok/s)

---

## 📊 Performance Comparison

| Model | Time | Throughput | Avg Output | Quality | Production Use |
|-------|------|------------|------------|---------|----------------|
| **Llama 3.2 1B** | 1.8 min | 19,813 tok/s | 121 tokens | ⚠️ Poor | Screening only |
| **Gemma 3 4B** | 37 min | 2,511 tok/s | 308 tokens | ✅ Excellent | Detailed eval |
| **Qwen 3 4B** | ~2 hrs | ~740 tok/s | TBD | 🔄 Testing | TBD |

**Speed Rankings:**
1. 🥇 **Llama 3.2 1B** - 19,813 tok/s (7.9x faster than Gemma!)
2. 🥈 **Gemma 3 4B** - 2,511 tok/s
3. 🥉 **Qwen 3 4B** - ~740 tok/s (3.4x slower than Gemma)

**Quality Rankings:**
1. 🥇 **Gemma 3 4B** - Structured, detailed, follows instructions
2. 🥉 **Llama 3.2 1B** - Doesn't complete task, asks user to fill in
3. ⏳ **Qwen 3 4B** - Testing in progress

---

## 💰 Production Cost Estimates (Parasail GPT-OSS 20B)

Based on actual token usage:

| Model | Avg Tokens/Req | Cost per 100K | Monthly (1M) | Notes |
|-------|----------------|---------------|--------------|-------|
| **Llama 3.2 1B** | 429 | $4.05 | $40.50 | ⚠️ Poor quality |
| **Gemma 3 4B** | 1,096 | $9.31 | $93.10 | ✅ Best quality |
| **Qwen 3 4B** | TBD | TBD | TBD | 🔄 Testing |

**Hybrid Strategy:**
- Screen 100K with Llama 3.2 1B: $4.05 (if quality improves)
- Evaluate top 20K with Gemma 3 4B: $1.86
- **Total: $5.91** (vs $9.31 for Gemma only)
- **Savings: 37%**

**BUT:** Llama 3.2 1B quality is too poor for screening. Need better model.

---

## 🎯 Key Findings

### **Gemma 3 4B:**
- ✅ **Best quality** - Structured JSON, detailed reasoning
- ✅ **100% success rate**
- ✅ **Reasonable speed** - 37 minutes for 5K
- ✅ **Production ready**
- 💰 **$9.31 per 100K** on Parasail

### **Llama 3.2 1B:**
- ✅ **Extremely fast** - 7.9x faster than Gemma
- ✅ **Very cheap** - 56% cheaper than Gemma
- ❌ **Poor quality** - Doesn't follow instructions
- ❌ **Short outputs** - 121 vs 308 tokens
- ⚠️ **Not suitable for production** without prompt engineering

### **Qwen 3 4B:**
- 🔄 **Testing in progress**
- ⚠️ **Slow** - 3.4x slower than Gemma
- ✅ **Memory optimized** - Avoided OOM with intelligent settings
- ⏳ **Quality TBD**

---

## ⏳ Pending Tests

### **High Priority:**

1. **Gemma 3 12B QAT** 🔥 **MOST IMPORTANT**
   - Model: `google/gemma-3-12b-it-qat-q4_0-gguf`
   - Size: 8.07 GB (quantized)
   - Expected: Best quality, 12B model on 16GB GPU!
   - Script: `test_gemma3_12b_qat.py`

2. **Llama 3.2 3B**
   - Model: `meta-llama/Llama-3.2-3B-Instruct`
   - Size: ~6 GB
   - Expected: 2-3x faster than Gemma, better quality than 1B
   - Script: `test_llama32_3b.py`

3. **OLMo 1B**
   - Model: `allenai/OLMo-1B-0724-hf`
   - Size: ~2 GB
   - Expected: Fast like Llama 1B, possibly better quality
   - Script: `test_olmo_1b.py`

---

## 🎯 Next Steps

1. ⏳ **Wait for Qwen 3 4B** to complete (~2 hours)
2. 🔥 **Test Gemma 3 12B QAT** - Prove 12B works on 16GB!
3. 🚀 **Test Llama 3.2 3B** - Find sweet spot
4. 🚀 **Test OLMo 1B** - Alternative to Llama 1B
5. 📊 **Quality Comparison** - Compare all models on same 5 candidates

---

## 📁 Files

**Result Files:**
- ✅ `benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl` (8.4 MB)
- ✅ `llama32_1b_5k_results.jsonl` (4.3 MB)
- 🔄 `qwen3_4b_5k_results.jsonl` (being written)

**Metadata Files:**
- ✅ `benchmarks/metadata/vllm-native-gemma3-4b-5000-2025-10-28.json`
- ✅ `benchmarks/metadata/llama32-1b-5k-2025-10-28.json`
- 🔄 `benchmarks/metadata/qwen3-4b-5k-2025-10-28.json` (pending)

**Reports:**
- ✅ `benchmarks/reports/VLLM_5K_RESULTS.md` - Gemma 3 4B detailed report
- ✅ `BENCHMARK_PLAN.md` - Execution plan
- ✅ `MEMORY_MANAGEMENT_GUIDE.md` - Memory optimization guide

---

## 🎉 Major Achievements

1. ✅ **Proved vLLM works at scale** - 5K batch, 100% success
2. ✅ **Found fastest model** - Llama 3.2 1B (19,813 tok/s)
3. ✅ **Found best quality model** - Gemma 3 4B
4. ✅ **Built memory optimizer** - Prevents OOM errors
5. ✅ **Tracked production costs** - Informed Parasail decisions
6. 🔄 **Testing continues** - More models in progress

---

**Bottom Line:** Gemma 3 4B is the production winner for quality. Llama 3.2 1B is too fast but quality is poor. Testing continues to find the sweet spot! 🚀

