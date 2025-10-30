# 🎯 Benchmark Execution Plan

**Goal:** Complete 5K batch tests for all viable models + quality comparison

---

## ✅ Completed Tests

| Model | Status | Time | Throughput | File |
|-------|--------|------|------------|------|
| **Gemma 3 4B** | ✅ DONE | 37 min | 2,511 tok/s | `gemma3_4b_5k_results.jsonl` |
| **Llama 3.2 1B** | ✅ DONE | 1.8 min | 19,813 tok/s | `llama32_1b_5k_results.jsonl` |
| **Qwen 3 4B** | 🔄 RUNNING | ~2 hrs (est) | ~740 tok/s | `qwen3_4b_5k_results.jsonl` |

---

## 🔄 In Progress

### **Qwen 3 4B - 5K Batch**
- **Status:** Running (Terminal 3)
- **Config:** gpu_util=0.8, enforce_eager=True (memory optimized)
- **Progress:** 42/5000 requests (~1% complete)
- **Est. Completion:** ~2 hours
- **Throughput:** 740 tok/s output

---

## ⏳ Pending Tests

### **Priority 1: Core Models**

1. **Gemma 3 12B QAT (Quantized)** 🔥
   - Model: `google/gemma-3-12b-it-qat-q4_0-gguf`
   - Size: 8.07 GB (Q4_0 quantized)
   - Script: `test_gemma3_12b_qat.py`
   - Expected: Should work! vLLM supports GGUF
   - **This is the big one - 12B model on 16GB GPU!**

2. **Llama 3.2 3B**
   - Model: `meta-llama/Llama-3.2-3B-Instruct`
   - Size: ~6 GB
   - Script: `test_llama32_3b.py`
   - Expected: 2-3x faster than Gemma 3 4B (~5,000-7,500 tok/s)
   - Est. Time: 10-15 minutes

3. **OLMo 1B**
   - Model: `allenai/OLMo-1B-0724-hf`
   - Size: ~2 GB
   - Script: `test_olmo_1b.py`
   - Expected: Similar or faster than Llama 3.2 1B (~15,000-20,000 tok/s)
   - Est. Time: 2-5 minutes

---

## 🎯 Quality Comparison

After all tests complete, run quality comparison on 5 same candidates:

```bash
python compare_quality.py
```

This will:
- Select 5 random candidates (or specify custom_ids)
- Show prompt + all model responses side-by-side
- Calculate token usage statistics
- Help evaluate which model produces best quality

**Models to compare:**
- Gemma 3 4B
- Gemma 3 12B QAT (if successful)
- Llama 3.2 1B
- Llama 3.2 3B
- Qwen 3 4B
- OLMo 1B

---

## 📋 Execution Order

### **Today's Plan:**

1. ✅ **Wait for Qwen 3 4B to finish** (~2 hours)
   - Currently running in Terminal 3
   - Using optimized memory settings

2. 🔥 **Test Gemma 3 12B QAT** (HIGH PRIORITY!)
   ```bash
   chmod +x test_gemma3_12b_qat.py
   source venv/bin/activate
   python test_gemma3_12b_qat.py
   ```
   - This is the most important test
   - Proves we can run 12B model on 16GB GPU
   - Uses official Google QAT quantization

3. **Test Llama 3.2 3B**
   ```bash
   chmod +x test_llama32_3b.py
   source venv/bin/activate
   python test_llama32_3b.py
   ```
   - Should be fast (~10-15 min)
   - Good middle ground between 1B and 4B

4. **Test OLMo 1B**
   ```bash
   chmod +x test_olmo_1b.py
   source venv/bin/activate
   python test_olmo_1b.py
   ```
   - Should be very fast (~2-5 min)
   - Alternative to Llama 3.2 1B

5. **Run Quality Comparison**
   ```bash
   python compare_quality.py
   ```
   - Compare all models on same 5 candidates
   - Evaluate output quality
   - Make production recommendations

---

## 🧠 Memory Management

All test scripts now use the **Memory Optimizer**:

```python
from memory_optimizer import MemoryOptimizer

optimizer = MemoryOptimizer()
config = optimizer.optimize_config(model_id, max_model_len=4096)

llm = LLM(
    model=model_id,
    gpu_memory_utilization=config.gpu_memory_utilization,
    enforce_eager=config.enforce_eager,
    ...
)
```

**Benefits:**
- Automatically detects optimal settings
- Learns from previous failures
- Prevents OOM errors
- Saves time on trial & error

**Check settings before running:**
```bash
python memory_optimizer.py "model-name"
```

---

## 📊 Expected Results Summary

| Model | Size | Est. Time | Est. Throughput | Production Use |
|-------|------|-----------|-----------------|----------------|
| **Llama 3.2 1B** | 2.5 GB | 2 min | 19,813 tok/s | ✅ High-volume screening |
| **OLMo 1B** | 2 GB | 2-5 min | 15,000-20,000 tok/s | ✅ Alternative to Llama 1B |
| **Llama 3.2 3B** | 6 GB | 10-15 min | 5,000-7,500 tok/s | ✅ Balanced speed/quality |
| **Gemma 3 4B** | 8.6 GB | 37 min | 2,511 tok/s | ✅ Detailed evaluation |
| **Qwen 3 4B** | 7.6 GB | 2 hrs | 740 tok/s | ⚠️  Slower, needs testing |
| **Gemma 3 12B QAT** | 8.07 GB | 30-60 min | 2,000-4,000 tok/s | 🔥 Best quality (if works!) |

---

## 💰 Production Cost Estimates (Parasail GPT-OSS 20B)

Based on current token usage (~1,105 tokens/request):

| Model | Tokens/Req | Cost per 100K | Monthly (1M) |
|-------|------------|---------------|--------------|
| **Llama 3.2 1B** | ~900 | $4.05 | $40.50 |
| **Llama 3.2 3B** | ~1,000 | $5.00 | $50.00 |
| **Gemma 3 4B** | ~1,105 | $9.31 | $93.10 |
| **Qwen 3 4B** | ~1,105 | $9.40 | $94.00 |
| **Gemma 3 12B** | ~1,200 | $12.00 | $120.00 |

**Hybrid Strategy (Best ROI):**
- Screen 100K with Llama 3.2 1B: $4.05
- Evaluate top 20K with Gemma 3 4B: $1.86
- **Total: $5.91** (vs $9.31 for Gemma only)
- **Savings: 37%**

---

## 🎯 Success Criteria

**For each model:**
- ✅ 100% success rate (5,000/5,000)
- ✅ Consistent throughput
- ✅ No OOM errors
- ✅ Token counts tracked
- ✅ Metadata saved

**For quality comparison:**
- ✅ 5 candidates compared across all models
- ✅ Output quality evaluated
- ✅ Production recommendations made

---

## 📁 Output Files

**Result Files:**
- `gemma3_4b_5k_results.jsonl` ✅
- `llama32_1b_5k_results.jsonl` ✅
- `qwen3_4b_5k_results.jsonl` 🔄
- `gemma3_12b_qat_5k_results.jsonl` ⏳
- `llama32_3b_5k_results.jsonl` ⏳
- `olmo_1b_5k_results.jsonl` ⏳

**Metadata Files:**
- `benchmarks/metadata/vllm-native-gemma3-4b-5000-2025-10-28.json` ✅
- `benchmarks/metadata/llama32-1b-5k-2025-10-28.json` ✅
- `benchmarks/metadata/qwen3-4b-5k-2025-10-28.json` 🔄
- `benchmarks/metadata/gemma3-12b-qat-5k-2025-10-28.json` ⏳
- `benchmarks/metadata/llama32-3b-5k-2025-10-28.json` ⏳
- `benchmarks/metadata/olmo-1b-5k-2025-10-28.json` ⏳

**Analysis Files:**
- `BENCHMARK_SUMMARY.md` - Overall comparison
- `PRODUCTION_COST_ESTIMATES.md` - Cost analysis
- `MEMORY_MANAGEMENT_GUIDE.md` - Memory optimization guide

---

## 🚀 Next Steps After Benchmarks

1. **Update BENCHMARKING_JOURNEY.md** with all results
2. **Run cost_analysis.py** to update production estimates
3. **Create quality comparison report**
4. **Make production recommendations**
5. **Test with real Aris data** (if needed)
6. **Implement hybrid pipeline** (if beneficial)

---

**Bottom Line:** We're systematically testing all viable models, tracking costs, and will compare quality to make informed production decisions! 🎉

