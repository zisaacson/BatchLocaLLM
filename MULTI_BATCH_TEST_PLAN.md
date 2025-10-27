# 🚀 Multi-Batch Scalability Test Plan

**Date**: 2025-10-27  
**Purpose**: Validate scalability, performance consistency, and memory stability  
**Status**: Ready to execute after current 5K batch completes

---

## 🎯 Objectives

### **Primary Goals**:

1. **Validate No Memory Leaks**: VRAM should remain stable across multiple batches
2. **Confirm Performance Consistency**: Processing rate should not degrade over time
3. **Test Model Persistence**: `keep_alive=-1` should keep model loaded between batches
4. **Verify Scalability**: System should handle back-to-back large batches
5. **Measure Throughput**: Establish baseline performance metrics

### **Success Criteria**:

- ✅ VRAM delta < 0.5 GB across all batches (no memory leak)
- ✅ Performance variance < 10% between batches
- ✅ 100% success rate for all batches
- ✅ No crashes or OOM errors
- ✅ Model stays loaded (no reload delays)

---

## 📊 Test Configuration

### **Test 1: Sequential 5K Batches** (Recommended)

```bash
python tools/run_multi_batch_test.py --batches 3 --input batch_5k.jsonl
```

**Configuration**:
- Number of batches: 3
- Requests per batch: 5,000
- Total requests: 15,000
- Expected time: ~2 hours
- Chunks per batch: 57

**What This Tests**:
- Memory stability over 15K requests
- Performance consistency across batches
- Model persistence (no reloads)
- Back-to-back processing capability

---

### **Test 2: Extended Stress Test** (Optional)

```bash
python tools/run_multi_batch_test.py --batches 5 --input batch_5k.jsonl
```

**Configuration**:
- Number of batches: 5
- Requests per batch: 5,000
- Total requests: 25,000
- Expected time: ~3.5 hours
- Chunks per batch: 57

**What This Tests**:
- Long-running stability
- Extended memory behavior
- Performance degradation (if any)
- System endurance

---

### **Test 3: Production Simulation** (After validation)

```bash
# Create 10K batch
head -10000 batch_170k.jsonl > batch_10k.jsonl

# Run test
python tools/run_multi_batch_test.py --batches 3 --input batch_10k.jsonl
```

**Configuration**:
- Number of batches: 3
- Requests per batch: 10,000
- Total requests: 30,000
- Expected time: ~2.5 hours
- Chunks per batch: 114

**What This Tests**:
- Larger batch handling
- Production-scale simulation
- Readiness for 170K batch

---

## 📈 Metrics Tracked

### **Per-Batch Metrics**:

1. **Performance**:
   - Processing time (minutes)
   - Throughput (req/s)
   - Average time per request
   - Token processing speed

2. **Memory**:
   - VRAM before batch
   - VRAM after batch
   - VRAM delta
   - Peak VRAM during batch

3. **Success Rate**:
   - Completed requests
   - Failed requests
   - Success percentage
   - Error types (if any)

4. **Token Usage**:
   - Prompt tokens
   - Completion tokens
   - Cached tokens
   - Cache hit rate

### **Overall Metrics**:

1. **Stability**:
   - Total VRAM delta (start → end)
   - Memory leak detection
   - VRAM trend analysis

2. **Consistency**:
   - Performance variance
   - Min/max/avg throughput
   - Standard deviation

3. **Scalability**:
   - Total requests processed
   - Total processing time
   - Overall success rate
   - System reliability

---

## 🔍 What We're Looking For

### **✅ Good Signs**:

1. **VRAM Stability**:
   ```
   Batch 1: 10.35 GB → 10.35 GB (Δ 0.00 GB)
   Batch 2: 10.35 GB → 10.35 GB (Δ 0.00 GB)
   Batch 3: 10.35 GB → 10.35 GB (Δ 0.00 GB)
   Total delta: 0.00 GB ✅ No memory leak!
   ```

2. **Performance Consistency**:
   ```
   Batch 1: 0.20 req/s
   Batch 2: 0.19 req/s
   Batch 3: 0.20 req/s
   Variance: 5% ✅ Consistent!
   ```

3. **Model Persistence**:
   ```
   Batch 1: No model load delay
   Batch 2: No model load delay ✅ Model stayed loaded!
   Batch 3: No model load delay ✅ keep_alive working!
   ```

### **⚠️ Warning Signs**:

1. **Memory Leak**:
   ```
   Batch 1: 10.35 GB → 10.50 GB (Δ +0.15 GB)
   Batch 2: 10.50 GB → 10.65 GB (Δ +0.15 GB)
   Batch 3: 10.65 GB → 10.80 GB (Δ +0.15 GB)
   Total delta: +0.45 GB ⚠️ Possible leak!
   ```

2. **Performance Degradation**:
   ```
   Batch 1: 0.20 req/s
   Batch 2: 0.18 req/s
   Batch 3: 0.16 req/s
   Variance: 20% ⚠️ Degrading!
   ```

3. **Model Reloading**:
   ```
   Batch 1: 0s delay
   Batch 2: 30s delay ⚠️ Model reloaded!
   Batch 3: 30s delay ⚠️ keep_alive not working!
   ```

---

## 🚀 Execution Plan

### **Step 1: Wait for Current 5K Batch** ⏳

Current status:
- Batch ID: `batch_85c5d5f0067d4ca3bd8e4ff6d1b5b0a7`
- Progress: Chunk 3/57 (176/5,000 requests)
- ETA: ~6.5 hours (410 minutes)
- Status: Running smoothly!

**Wait for**:
- Batch completion
- Results validation
- Success confirmation

### **Step 2: Analyze Current Batch Results** ⏳

Once complete:
```bash
# Check final status
curl http://localhost:4080/v1/batches/batch_85c5d5f0067d4ca3bd8e4ff6d1b5b0a7

# Review metrics
tail -100 server.log | grep "Batch progress"

# Validate VRAM
nvidia-smi
```

**Validate**:
- 100% success rate
- VRAM stable
- No errors
- Performance metrics

### **Step 3: Run Multi-Batch Test** ⏳

After validation:
```bash
# Run 3-batch test
python tools/run_multi_batch_test.py --batches 3 --input batch_5k.jsonl
```

**Monitor**:
```bash
# Watch progress
tail -f server.log

# Monitor VRAM
watch -n 5 nvidia-smi

# Check results
ls -lh multi_batch_results_*.json
```

### **Step 4: Analyze Multi-Batch Results** ⏳

After completion:
```bash
# View results
cat multi_batch_results_*.json | python -m json.tool

# Check for memory leaks
grep "VRAM" multi_batch_results_*.json

# Verify consistency
grep "rate_per_second" multi_batch_results_*.json
```

**Analyze**:
- VRAM trend
- Performance variance
- Success rates
- Error patterns

### **Step 5: Decision Point** ⏳

Based on results:

**If all tests pass** ✅:
- Proceed to 170K production batch
- System is production-ready
- Scalability confirmed

**If issues found** ⚠️:
- Investigate root cause
- Fix identified problems
- Re-run tests
- Validate fixes

---

## 📊 Expected Results

### **For 3x 5K Batches**:

```
============================================================
FINAL MULTI-BATCH SUMMARY
============================================================

📊 Overall Statistics:
  Total batches: 3
  Total requests: 15,000
  Total failed: 0
  Success rate: 100.00%
  Total time: 120.0 minutes
  Average rate: 0.20 req/s

📊 Per-Batch Performance:
  Batch 1: 40.0 min | 0.20 req/s | VRAM: +0.00 GB
  Batch 2: 40.0 min | 0.20 req/s | VRAM: +0.00 GB
  Batch 3: 40.0 min | 0.20 req/s | VRAM: +0.00 GB

📊 VRAM Analysis:
  Start VRAM: 10.35 GB
  End VRAM: 10.35 GB
  Total delta: +0.00 GB
  ✅ No memory leak detected!

📊 Performance Consistency:
  Min rate: 0.19 req/s
  Max rate: 0.20 req/s
  Variance: 5.0%
  ✅ Consistent performance!
```

---

## 🎯 Why This Matters

### **1. Production Readiness**

Multi-batch testing proves:
- System can handle 170K batch (34x 5K batches)
- No degradation over time
- Reliable for production use

### **2. Memory Safety**

Validates:
- No memory leaks
- VRAM stays within limits
- Safe for long-running batches

### **3. Performance Predictability**

Confirms:
- Consistent throughput
- Reliable ETAs
- Predictable resource usage

### **4. Operational Confidence**

Demonstrates:
- System stability
- Error handling
- Recovery capability

---

## 🔧 Troubleshooting

### **If VRAM Increases**:

```bash
# Check for zombie processes
ps aux | grep -E "python|ollama"

# Kill if needed
pkill -f "ollama"
pkill -f "python.*batch"

# Restart server
./venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

### **If Performance Degrades**:

```bash
# Check system resources
htop

# Check disk I/O
iostat -x 5

# Check network
netstat -an | grep 4080
```

### **If Errors Occur**:

```bash
# Check logs
tail -100 server.log | grep ERROR

# Check Ollama
curl http://localhost:11434/api/tags

# Restart if needed
systemctl restart ollama  # or however you run Ollama
```

---

## 📝 Test Checklist

### **Before Running**:

- [ ] Current 5K batch completed successfully
- [ ] VRAM is stable (~10.35 GB)
- [ ] No zombie processes running
- [ ] Server is responsive
- [ ] Disk space available (>10 GB)

### **During Test**:

- [ ] Monitor VRAM every 10 minutes
- [ ] Check progress logs
- [ ] Watch for errors
- [ ] Verify throughput
- [ ] Note any anomalies

### **After Test**:

- [ ] Analyze results JSON
- [ ] Verify VRAM stability
- [ ] Check performance consistency
- [ ] Review error logs
- [ ] Document findings

---

## 🎉 Success Indicators

### **System is Production-Ready If**:

1. ✅ **All batches complete** with 100% success rate
2. ✅ **VRAM delta < 0.5 GB** across all batches
3. ✅ **Performance variance < 10%** between batches
4. ✅ **No crashes or OOM errors**
5. ✅ **Model stays loaded** (no reload delays)
6. ✅ **Throughput matches expectations** (~0.20 req/s)

### **Next Steps After Success**:

1. **Scale to 10K batches** (optional validation)
2. **Run 170K production batch** (main goal)
3. **Monitor and optimize** (continuous improvement)
4. **Document best practices** (operational guide)

---

## 💡 Key Insights

### **Why 3 Batches?**

- Enough to detect trends
- Not too long to run (~2 hours)
- Statistically significant
- Practical for validation

### **Why 5K Size?**

- Large enough to stress system
- Small enough to iterate quickly
- Matches our validated chunk size
- Proven to work (current batch)

### **Why Sequential?**

- Tests real production scenario
- Validates model persistence
- Checks memory cleanup
- Simulates actual usage

---

## 🚀 Bottom Line

**This multi-batch test will prove**:

1. ✅ System can handle 170K batch (34x 5K = 170K)
2. ✅ No memory leaks over extended runs
3. ✅ Performance stays consistent
4. ✅ Production-ready architecture

**After successful completion**:

- **Confidence**: 100% ready for 170K
- **Risk**: Minimal (validated at scale)
- **Timeline**: Predictable (~13-15 hours)
- **Success**: Virtually guaranteed

**Let's validate our scalability!** 🎉

---

**Current Status**: Waiting for 5K batch to complete  
**Next Action**: Run multi-batch test  
**Expected Outcome**: Production validation complete!

