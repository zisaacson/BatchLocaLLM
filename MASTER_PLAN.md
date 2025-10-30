# MASTER PLAN: vLLM vs Ollama Batch Processing Benchmarking

**Date:** October 28, 2024  
**Hardware:** RTX 4080 16GB (15.57 GB VRAM)  
**Goal:** Comprehensive benchmarking of vLLM vs Ollama for batch LLM inference

---

## 🎯 PROJECT GOALS

### Primary Goal
**Determine the best platform for batch processing 5K-200K candidate evaluation requests on consumer GPU hardware (RTX 4080 16GB).**

### Success Criteria
1. ✅ **Performance:** Measure throughput (tokens/sec, requests/sec) for both platforms
2. ✅ **Reliability:** Validate 100% success rate at scale (5K, 10K, 50K requests)
3. ✅ **Model Support:** Test with 4B and 12B parameter models
4. ✅ **Resource Efficiency:** Measure GPU memory usage, CPU usage, batch processing time
5. ✅ **Simplicity:** Evaluate ease of implementation and maintenance

---

## 📊 CURRENT STATUS AUDIT

### What We Have Accomplished

#### ✅ vLLM Offline (Native Batching) - **TESTED**
- **100 requests:** 2,491 tok/s, 100% success, 45s processing time
- **5,000 requests:** 🔄 **RUNNING NOW** (25% complete, ~1,800 tok/s, ETA 30 min)
- **Model:** Gemma 3 4B (8.6 GB)
- **Implementation:** Native `LLM.generate(prompts)` - NO custom code!
- **Status:** ✅ **VALIDATED** - This is the correct approach for vLLM

#### ✅ vLLM Serve (API Mode) - **TESTED**
- **100 requests:** 2,472 tok/s, 100% success, 46s processing time
- **5,000 requests:** ❌ Server crashed, 0% success
- **Model:** Gemma 3 4B (8.6 GB)
- **Implementation:** Custom async scripts hitting OpenAI-compatible API
- **Status:** ❌ **NOT RECOMMENDED** - Wrong tool for batch processing

#### ⚠️ Ollama + Custom Batch Wrapper - **PARTIALLY TESTED**
- **9 requests:** 100% success (no throughput data)
- **99 requests:** 100% success (no throughput data)
- **5,000 requests:** ❓ Not tested yet
- **Model:** Gemma 3 12B (3.3 GB quantized)
- **Implementation:** Custom Python wrapper with SQLite queue
- **Status:** ⚠️ **NEEDS BENCHMARKING** - Unknown throughput

---

## 🔬 BENCHMARK DATA INVENTORY

### On `vllm-serve-only` Branch
```
batch_10_vllm_results.jsonl          - 10 requests, vLLM Serve, 983 tok/s
batch_100_vllm_results.jsonl         - 100 requests, vLLM Serve, 2,472 tok/s
batch_100_offline_results.jsonl      - 100 requests, vLLM Offline, 2,491 tok/s ✅
batch_5k_offline_results.jsonl       - 5K requests, vLLM Offline, 🔄 RUNNING
batch_5k_optimized_results.jsonl     - 5K requests, vLLM Serve, ALL FAILED ❌
```

### On `ollama` Branch
```
test_batch_10_results.jsonl          - 9 requests, Gemma 3 12B, 100% success
sample_candidates_results.jsonl      - 99 requests, Gemma 3 12B, 100% success
data/vllm_batch.db                   - SQLite database with metrics
batch_1000_output.log                - 1K batch logs
batch_100_output.log                 - 100 batch logs
batch_5k_run.log                     - 5K batch logs
```

### On `master` Branch
```
BENCHMARKS.md                        - Benchmark documentation
FINAL_REPORT.md                      - vLLM vs Ollama comparison
TROUBLESHOOTING_CHECKLIST.md         - Debugging guide
```

---

## 🎯 COMPREHENSIVE TESTING PLAN

### Phase 1: vLLM Offline Validation ✅ IN PROGRESS

**Goal:** Validate vLLM Offline (native batching) at scale

**Tests:**
- [x] 10 requests - ✅ DONE (not saved, but tested)
- [x] 100 requests - ✅ DONE (2,491 tok/s, 100% success)
- [ ] 5,000 requests - 🔄 **RUNNING NOW** (ETA 30 min)
- [ ] 10,000 requests - ❓ TODO
- [ ] 50,000 requests - ❓ TODO (stretch goal)

**Metrics to Collect:**
- ✅ Throughput (tokens/sec, requests/sec)
- ✅ Success rate (%)
- ✅ Processing time (seconds)
- ✅ Model load time (one-time cost)
- ✅ GPU memory usage (GB)
- ⚠️ GPU utilization (%) - observed 96%, need to log
- ⚠️ CPU usage (%) - not measured yet
- ⚠️ Token statistics (prompt vs completion) - collected but not analyzed

---

### Phase 2: Ollama Benchmarking ❌ NOT STARTED

**Goal:** Measure Ollama throughput and validate at scale

**Tests:**
- [x] 9 requests - ✅ DONE (100% success, no throughput)
- [x] 99 requests - ✅ DONE (100% success, no throughput)
- [ ] 100 requests - ❓ TODO (for fair comparison with vLLM)
- [ ] 5,000 requests - ❓ TODO
- [ ] 10,000 requests - ❓ TODO

**Metrics to Collect:**
- ❌ Throughput (tokens/sec, requests/sec) - **CRITICAL MISSING DATA**
- ✅ Success rate (%) - 100% so far
- ❌ Processing time (seconds) - not measured
- ❌ Model load time - not measured
- ❌ GPU memory usage - not measured
- ❌ GPU utilization - not measured
- ❌ CPU usage - not measured

**Action Items:**
1. Switch to `ollama` branch
2. Run 100 request benchmark with timing
3. Run 5K request benchmark
4. Collect all metrics listed above

---

### Phase 3: Model-by-Model Comparison ❌ NOT STARTED

**Goal:** Compare same model across both platforms

#### Test 1: Gemma 3 4B (vLLM) vs Gemma 3 12B (Ollama)

**Current Status:**
- vLLM: ✅ Gemma 3 4B tested (2,491 tok/s)
- Ollama: ⚠️ Gemma 3 12B tested (no throughput data)

**Problem:** Different model sizes - not apples-to-apples!

**Solution Options:**
1. **Option A:** Test Gemma 3 4B on Ollama (fair comparison)
2. **Option B:** Accept different models, compare quality vs speed tradeoff
3. **Option C:** Test both 4B and 12B on both platforms

**Recommendation:** Option A - Test Gemma 3 4B on Ollama for fair comparison

#### Test 2: Same Prompts, Same Model, Both Platforms

**Test Matrix:**

| Platform | Model | Batch Size | Status |
|----------|-------|------------|--------|
| vLLM Offline | Gemma 3 4B | 100 | ✅ DONE (2,491 tok/s) |
| vLLM Offline | Gemma 3 4B | 5,000 | 🔄 RUNNING |
| Ollama | Gemma 3 4B | 100 | ❌ TODO |
| Ollama | Gemma 3 4B | 5,000 | ❌ TODO |
| Ollama | Gemma 3 12B | 100 | ⚠️ PARTIAL (no throughput) |
| Ollama | Gemma 3 12B | 5,000 | ❌ TODO |

---

## 📋 DETAILED ACTION PLAN

### Immediate Actions (Next 2 Hours)

#### Action 1: Wait for vLLM 5K Test to Complete 🔄
- **Status:** 25% complete (1,255/5,000)
- **ETA:** ~30 minutes
- **Next:** Analyze results, document findings

#### Action 2: Run Ollama Benchmarks with Gemma 3 4B
```bash
# Switch to ollama branch
git checkout ollama

# Download Gemma 3 4B for Ollama
ollama pull gemma3:4b

# Run 100 request benchmark
python src/batch_processor.py --model gemma3:4b --input batch_100_real.jsonl --output ollama_gemma3_4b_100_results.jsonl

# Measure throughput, time, GPU usage
```

#### Action 3: Run Ollama Benchmarks with Gemma 3 12B
```bash
# Run 100 request benchmark
python src/batch_processor.py --model gemma3:12b --input batch_100_real.jsonl --output ollama_gemma3_12b_100_results.jsonl

# Run 5K benchmark
python src/batch_processor.py --model gemma3:12b --input batch_5k.jsonl --output ollama_gemma3_12b_5k_results.jsonl
```

#### Action 4: Create Comprehensive Comparison Table
- Collect all metrics from both platforms
- Create side-by-side comparison
- Document findings in `FINAL_COMPARISON.md`

---

### Short Term Actions (This Week)

#### Action 5: Test vLLM Offline at 10K Scale
```bash
git checkout vllm-serve-only
python test_vllm_offline.py batch_10k.jsonl batch_10k_offline_results.jsonl
```

#### Action 6: Test Ollama at 10K Scale
```bash
git checkout ollama
python src/batch_processor.py --model gemma3:12b --input batch_10k.jsonl --output ollama_10k_results.jsonl
```

#### Action 7: Quality Comparison
- Run same 100 prompts through both platforms
- Compare output quality (Gemma 3 4B vs 12B)
- Determine if 12B quality improvement justifies slower speed

---

### Medium Term Actions (This Month)

#### Action 8: Stress Test at 50K Scale
- Test vLLM Offline with 50K requests
- Test Ollama with 50K requests
- Validate reliability at production scale

#### Action 9: Resource Optimization
- Test different vLLM configurations (context length, GPU memory)
- Test different Ollama configurations (concurrent requests, batch size)
- Find optimal settings for RTX 4080 16GB

#### Action 10: Documentation
- Create final recommendation document
- Document optimal configurations
- Create deployment guide for chosen platform

---

## 🎯 DECISION CRITERIA

### Performance Metrics (40%)
- **Throughput:** tokens/sec, requests/sec
- **Latency:** time per request
- **Scalability:** performance at 5K, 10K, 50K

### Reliability Metrics (30%)
- **Success Rate:** % of requests completed successfully
- **Error Handling:** graceful degradation, retry logic
- **Stability:** no crashes, memory leaks

### Resource Efficiency (20%)
- **GPU Memory:** fits in 16GB VRAM
- **GPU Utilization:** efficient use of GPU
- **CPU Usage:** minimal CPU overhead

### Simplicity (10%)
- **Implementation:** lines of code, complexity
- **Maintenance:** ease of updates, debugging
- **Dependencies:** number of external dependencies

---

## 📊 EXPECTED OUTCOMES

### Scenario 1: vLLM Offline Wins
**If:** vLLM Offline has higher throughput, 100% success rate, simpler implementation

**Recommendation:** Use vLLM Offline for all batch processing
- ✅ Native batching - no custom code
- ✅ Highest throughput
- ✅ Simplest implementation
- ⚠️ Limited to 4B models on RTX 4080

### Scenario 2: Ollama Wins
**If:** Ollama has acceptable throughput, 100% success rate, runs 12B model

**Recommendation:** Use Ollama for batch processing
- ✅ Runs larger model (12B vs 4B)
- ✅ Production-ready architecture
- ✅ Better resource efficiency (quantization)
- ⚠️ More complex implementation

### Scenario 3: Hybrid Approach
**If:** Both have strengths and weaknesses

**Recommendation:** Use both platforms for different use cases
- vLLM Offline: Fast batch processing with 4B model
- Ollama: High-quality inference with 12B model
- Choose based on speed vs quality requirements

---

## 🚀 NEXT STEPS

### Right Now (Next 30 Minutes)
1. ✅ Wait for vLLM 5K test to complete
2. ✅ Analyze vLLM 5K results
3. ✅ Document findings

### Today (Next 2 Hours)
4. ❌ Switch to Ollama branch
5. ❌ Run Ollama 100 request benchmark (Gemma 3 4B)
6. ❌ Run Ollama 100 request benchmark (Gemma 3 12B)
7. ❌ Measure throughput for both

### This Week
8. ❌ Run Ollama 5K benchmark
9. ❌ Run vLLM 10K benchmark
10. ❌ Create comprehensive comparison table
11. ❌ Make final recommendation

---

## 📝 CRITICAL MISSING DATA

### vLLM Offline
- ⚠️ 5K benchmark results (running now)
- ❌ 10K benchmark results
- ❌ 50K benchmark results
- ⚠️ GPU utilization logs (observed but not saved)
- ❌ CPU usage metrics

### Ollama
- ❌ **Throughput data** (tokens/sec, requests/sec) - **CRITICAL!**
- ❌ 100 request benchmark with timing
- ❌ 5K benchmark results
- ❌ 10K benchmark results
- ❌ GPU memory usage
- ❌ GPU utilization
- ❌ CPU usage

### Comparison
- ❌ Same model (Gemma 3 4B) on both platforms
- ❌ Same prompts on both platforms
- ❌ Quality comparison (4B vs 12B outputs)
- ❌ Resource usage comparison

---

## 🎓 LESSONS LEARNED

### What We Discovered

1. **vLLM Has Native Batching!**
   - I was writing custom async scripts when vLLM has `LLM.generate(prompts)`
   - Native batching is simpler and faster than API mode
   - This is the official vLLM recommendation for batch processing

2. **vLLM Serve is Wrong Tool**
   - Designed for online serving, not batch processing
   - Crashes on large batches (5K failed)
   - Requires custom async code

3. **Ollama Needs Throughput Data**
   - We have success rates but no performance metrics
   - Can't make informed decision without throughput data
   - Need to run proper benchmarks

4. **Model Size Matters**
   - vLLM: 4B model (8.6 GB)
   - Ollama: 12B model (3.3 GB quantized)
   - Not apples-to-apples comparison!

---

## 🎯 SUCCESS CRITERIA CHECKLIST

### Minimum Viable Benchmarking (MVP)
- [x] vLLM Offline 100 requests - ✅ DONE
- [ ] vLLM Offline 5,000 requests - 🔄 RUNNING
- [ ] Ollama 100 requests with throughput - ❌ TODO
- [ ] Ollama 5,000 requests - ❌ TODO
- [ ] Comparison table - ❌ TODO

### Production Ready Benchmarking
- [ ] vLLM Offline 10,000 requests
- [ ] Ollama 10,000 requests
- [ ] Same model on both platforms
- [ ] Quality comparison
- [ ] Resource usage comparison
- [ ] Final recommendation document

### Stretch Goals
- [ ] 50,000 request batches
- [ ] Multiple model comparison
- [ ] Optimization guide
- [ ] Deployment automation

---

**Current Status:** Phase 1 (vLLM Offline) 50% complete, Phase 2 (Ollama) not started  
**Next Milestone:** Complete vLLM 5K test, start Ollama benchmarking  
**ETA to Decision:** 2-3 days with comprehensive testing

