# 🏗️ Production Queue Architecture for 50K+ Batches

**Date**: 2025-10-27  
**Goal**: Handle multiple 50K batches efficiently with optimal concurrency

---

## 🎯 The Problem

### **Current State**:
- ✅ Parallel processing works (14.65 req/s with 4 workers)
- ✅ Can handle single batches efficiently
- ❓ **What happens with multiple 50K batches?**
- ❓ **How do we queue them?**
- ❓ **What's the optimal worker count for 50K?**
- ❓ **Is the bottleneck Ollama or our code?**

### **Questions to Answer**:
1. **Concurrency limits**: How many parallel requests can Ollama handle?
2. **Worker optimization**: What's optimal for 50K batches?
3. **Queue management**: How do we handle multiple batches?
4. **Resource limits**: VRAM, CPU, memory constraints?

---

## 🔬 Concurrency Analysis

### **Benchmark Results (20 requests)**:
```
Workers | Rate       | Notes
--------|------------|---------------------------
1       | 7.21 req/s | Baseline
2       | 13.18 req/s| 1.83x improvement (good!)
4       | 14.65 req/s| 2.03x improvement (BEST!)
8       | 14.53 req/s| 2.02x improvement (diminishing returns)
```

### **Key Insight**:
**Optimal = 4 workers** (peak at 14.65 req/s)

### **Why diminishing returns after 4?**

**Possible bottlenecks**:
1. **Ollama concurrency limit** - Ollama may serialize requests internally
2. **GPU contention** - RTX 4080 can only process one inference at a time
3. **Memory bandwidth** - Loading model weights from VRAM
4. **CPU overhead** - Context processing, tokenization

**Most likely**: **GPU is the bottleneck** (single GPU = sequential inference)

---

## 🧪 Testing Strategy

### **Phase 1: Find Optimal Worker Count for 50K** ✅ NEXT

Test with 1K, 5K, 10K requests to find optimal workers:

```python
# Test different worker counts on larger batches
for batch_size in [1000, 5000, 10000]:
    for num_workers in [2, 4, 8, 16, 32]:
        rate = benchmark(batch_size, num_workers)
        print(f"{batch_size} requests, {num_workers} workers: {rate:.2f} req/s")
```

**Expected outcome**:
- Optimal workers: 4-8 (based on 20-request test)
- Rate: 12-15 req/s (sustained)
- 50K batch time: ~55-70 minutes

### **Phase 2: Test Multiple Batches** ✅ AFTER PHASE 1

Test queue behavior:
```python
# Submit 3 batches simultaneously
batch1 = submit_batch("batch_50k_1.jsonl")
batch2 = submit_batch("batch_50k_2.jsonl")
batch3 = submit_batch("batch_50k_3.jsonl")

# Monitor: Do they queue or conflict?
```

**Questions**:
- Do batches queue automatically?
- Do they interfere with each other?
- Is there resource contention?

---

## 🏗️ Queue Architecture Options

### **Option A: Single Batch at a Time (Current)**

```
┌─────────────────────────────────────┐
│         Batch Processor             │
│  - Processes ONE batch at a time    │
│  - 4 workers per batch              │
│  - Queue in database (status)       │
└─────────────────────────────────────┘
         │
         ▼
    ┌────────┐
    │ Ollama │ (single GPU)
    └────────┘
```

**Pros**:
- ✅ Simple (already implemented!)
- ✅ No resource contention
- ✅ Predictable performance

**Cons**:
- ❌ Batches wait in queue (sequential)
- ❌ Can't utilize idle resources

**Performance**:
- 50K batch: ~55-70 minutes
- 3 batches: ~165-210 minutes (sequential)

### **Option B: Multiple Batches with Shared Workers**

```
┌─────────────────────────────────────┐
│      Global Worker Pool (4)         │
│  - Shared across all batches        │
│  - Requests from all batches mixed  │
└─────────────────────────────────────┘
         │
         ▼
    ┌────────┐
    │ Ollama │ (single GPU)
    └────────┘
```

**Pros**:
- ✅ Better resource utilization
- ✅ Batches progress in parallel

**Cons**:
- ❌ Complex coordination
- ❌ Results harder to track
- ❌ No performance gain (same GPU!)

**Performance**:
- Same as Option A (GPU bottleneck)

### **Option C: Batch Queue with Priority**

```
┌─────────────────────────────────────┐
│         Batch Queue Manager         │
│  - Queues batches by priority       │
│  - Processes one at a time          │
│  - Tracks progress per batch        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│    Batch Processor (4 workers)      │
└─────────────────────────────────────┘
         │
         ▼
    ┌────────┐
    │ Ollama │ (single GPU)
    └────────┘
```

**Pros**:
- ✅ Simple and clean
- ✅ Priority support
- ✅ Easy to monitor
- ✅ Predictable performance

**Cons**:
- ❌ Batches wait in queue

**Performance**:
- Same as Option A

---

## 🎯 Recommendation: Option C (Batch Queue)

### **Why**:
1. **Single GPU = Sequential anyway** (no benefit from parallel batches)
2. **Simple and predictable** (easy to reason about)
3. **Already mostly implemented** (database tracks status)
4. **Priority support** (can add later)

### **Implementation**:

**Current state** (already works!):
```python
# Database tracks batch status
batch1 = create_batch(...)  # status: validating
batch2 = create_batch(...)  # status: validating
batch3 = create_batch(...)  # status: validating

# Processor picks next batch
while True:
    batch = get_next_pending_batch()
    if batch:
        process_batch(batch)  # status: in_progress → completed
```

**What we need to add**:
1. ✅ **Queue management** - Pick next batch from database
2. ✅ **Concurrency control** - Only process N batches at once (N=1 for single GPU)
3. ✅ **Progress tracking** - Update database during processing
4. ✅ **Checkpointing** - Resume on crash

---

## 📊 Expected Performance (50K Batches)

### **Assumptions**:
- Optimal workers: 4
- Sustained rate: 14 req/s (conservative)
- 50K requests per batch

### **Single 50K Batch**:
```
Time = 50,000 / 14 = 3,571 seconds = 59.5 minutes (~1 hour)
```

### **Multiple 50K Batches** (sequential):
```
3 batches: 3 × 59.5 = 178.5 minutes (~3 hours)
5 batches: 5 × 59.5 = 297.5 minutes (~5 hours)
10 batches: 10 × 59.5 = 595 minutes (~10 hours)
```

### **170K Batch** (single):
```
Time = 170,000 / 14 = 12,143 seconds = 202 minutes (~3.4 hours)
```

---

## 🚀 Optimization Opportunities

### **1. Increase Worker Count** (Test first!)

If Ollama can handle more concurrency:
```
8 workers @ 20 req/s → 50K in 42 minutes
16 workers @ 30 req/s → 50K in 28 minutes
```

**Action**: Benchmark with 1K, 5K, 10K to find optimal

### **2. Batch Size Optimization**

Smaller batches = better queue throughput:
```
10K batches: More granular, better queue management
50K batches: Fewer API calls, simpler tracking
```

**Recommendation**: Stick with 50K (simpler)

### **3. Multiple GPUs** (Future)

If you add more GPUs:
```
2 GPUs: 2 batches in parallel → 2x throughput
4 GPUs: 4 batches in parallel → 4x throughput
```

**Not applicable now** (single RTX 4080)

### **4. Model Optimization**

Smaller/faster model:
```
Gemma 2B: ~3x faster than 12B
Gemma 7B: ~1.5x faster than 12B
```

**Trade-off**: Speed vs quality

---

## 🔧 Implementation Plan

### **Phase 1: Optimize Worker Count** ✅ NOW

**Goal**: Find optimal workers for 50K batches

**Steps**:
1. Create benchmark script for 1K, 5K, 10K requests
2. Test with 2, 4, 8, 16, 32 workers
3. Measure rate, VRAM, CPU usage
4. Find optimal configuration

**Script**: `tools/find_optimal_workers.py`

**Expected time**: 30-60 minutes

### **Phase 2: Test 50K Batch** ✅ AFTER PHASE 1

**Goal**: Validate performance at scale

**Steps**:
1. Run single 50K batch with optimal workers
2. Monitor VRAM, rate, errors
3. Validate results
4. Measure actual time

**Expected time**: ~1 hour

### **Phase 3: Queue Management** ✅ AFTER PHASE 2

**Goal**: Handle multiple batches efficiently

**Steps**:
1. Implement queue picker (get next pending batch)
2. Add concurrency control (max 1 batch at a time)
3. Add progress tracking (update DB during processing)
4. Test with 3 batches

**Expected time**: 2-3 hours implementation + testing

### **Phase 4: Production Run** ✅ FINAL

**Goal**: Process all 170K candidates

**Steps**:
1. Split 170K into batches (1×170K or 3×50K+1×20K)
2. Submit all batches
3. Monitor queue
4. Collect results

**Expected time**: 3-10 hours (depending on configuration)

---

## 🎯 Immediate Next Steps

### **1. Find Optimal Workers** (NOW):

```bash
# Create and run benchmark
./venv/bin/python tools/find_optimal_workers.py
```

**This will**:
- Test 1K, 5K, 10K requests
- Try 2, 4, 8, 16, 32 workers
- Find optimal configuration
- Estimate 50K and 170K times

**Expected output**:
```
Optimal workers: 4-8
Sustained rate: 12-15 req/s
50K estimate: 55-70 minutes
170K estimate: 3-4 hours
```

### **2. Run 50K Test** (AFTER #1):

```bash
# Run with optimal workers
./venv/bin/python tools/run_batch_jsonl.py batch_50k.jsonl
```

**Expected time**: ~1 hour

### **3. Implement Queue** (AFTER #2):

Update batch processor to:
- Pick next pending batch from database
- Process one at a time
- Update progress during processing
- Handle multiple batches sequentially

---

## 📈 Success Metrics

### **Performance**:
- ✅ 50K batch in < 70 minutes
- ✅ Sustained rate > 12 req/s
- ✅ 100% success rate

### **Scalability**:
- ✅ Multiple batches queue correctly
- ✅ No resource conflicts
- ✅ Predictable timing

### **Robustness**:
- ✅ Checkpointing works
- ✅ Resume on crash
- ✅ Progress tracking accurate

---

## 🔥 Bottom Line

**Current state**:
- ✅ Parallel processing works (14.65 req/s)
- ✅ 50K batch file created
- ❓ Need to find optimal workers for large batches
- ❓ Need to implement queue management

**Next action**:
1. **Create `tools/find_optimal_workers.py`** ← DO THIS NOW
2. Run benchmark to find optimal workers
3. Test 50K batch
4. Implement queue
5. Process 170K

**Expected timeline**:
- Optimization: 1 hour
- 50K test: 1 hour
- Queue implementation: 2-3 hours
- 170K production: 3-4 hours
- **Total: ~8-10 hours to completion** 🚀

Let's find the optimal workers NOW!

