# How to Test vLLM Serve with GPU Monitoring

**Goal:** Properly test vLLM's OpenAI-compatible API server for batch processing with full GPU monitoring.

---

## 🎯 Two-Mode Architecture

### **Mode 1: Batch Processing (Offline)** ✅ TESTED
- **Use:** Large batches (5K-200K)
- **Tool:** `benchmark_vllm_native.py`
- **Status:** 100% success on 5K requests, 2,511 tok/s

### **Mode 2: Real-Time Serving (API)** ⏳ NEEDS PROPER TEST
- **Use:** Real-time API, interactive queries, small batches
- **Tool:** `test_vllm_serve_proper.py`
- **Status:** Needs testing (previous test had server not running)

---

## 📋 Prerequisites

1. ✅ vLLM installed (`pip install vllm`)
2. ✅ GPU monitoring tool ready (`tools/monitor_gpu.py`)
3. ✅ Test data ready (`batch_100.jsonl` or `batch_5k.jsonl`)
4. ✅ No zombie processes running

**Check for zombies:**
```bash
ps aux | grep -E "vllm|python.*batch" | grep -v grep
nvidia-smi
```

---

## 🚀 Step-by-Step Testing Guide

### **Step 1: Start GPU Monitoring**

Open **Terminal 1**:

```bash
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server

# Create monitoring directory
mkdir -p benchmarks/monitoring

# Start monitoring (1 second intervals)
python tools/monitor_gpu.py \
    --output benchmarks/monitoring/vllm-serve-100-gpu.log \
    --interval 1
```

**Expected output:**
```
🔍 GPU Monitoring Started
📝 Logging to: benchmarks/monitoring/vllm-serve-100-gpu.log
⏱️  Interval: 1.0s
Press Ctrl+C to stop

[2025-10-28T...] MEM:   506/16376 MB (  3.1%) | GPU:   0% | TEMP:  37°C | PWR:   14.0W
```

---

### **Step 2: Start vLLM Server**

Open **Terminal 2**:

```bash
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server
source venv/bin/activate

# Start vLLM server
vllm serve google/gemma-3-4b-it \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    --port 8000
```

**Expected output:**
```
INFO: Started server process
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Wait for model to load** (~30 seconds). You'll see GPU memory jump to ~11 GB in Terminal 1.

---

### **Step 3: Verify Server is Running**

Open **Terminal 3**:

```bash
# Check health endpoint
curl http://localhost:8000/health

# Should return: "OK" or similar
```

---

### **Step 4: Run Batch Test**

In **Terminal 3**:

```bash
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server
source venv/bin/activate

# Test with 100 requests first
python test_vllm_serve_proper.py \
    batch_100_real.jsonl \
    benchmarks/raw/vllm-serve-100-results.jsonl
```

**Expected output:**
```
================================================================================
vLLM SERVE BATCH TEST (OpenAI-Compatible API)
================================================================================
Input: batch_100_real.jsonl
Output: benchmarks/raw/vllm-serve-100-results.jsonl
================================================================================

🔍 Checking if vLLM server is running...
✅ vLLM server is running

📥 Loading requests...
✅ Loaded 100 requests

⚡ Processing 100 requests...
Using OpenAI-compatible API with controlled concurrency (max 10 concurrent)
✅ Processing complete in 45.2s

💾 Saving results to benchmarks/raw/vllm-serve-100-results.jsonl...
✅ Saved 100 results

================================================================================
📊 BENCHMARK RESULTS
================================================================================
Requests:              100
Successful:            100 (100.0%)
Failed:                0 (0.0%)
Total time:            45.2s
Prompt tokens:         82,223
Completion tokens:     32,397
Total tokens:          114,620
Throughput:            2535 tokens/sec
Requests/sec:          2.21
================================================================================

🎉 Test complete!
```

---

### **Step 5: Stop Monitoring**

In **Terminal 1**, press **Ctrl+C**:

```
🛑 Monitoring stopped

================================================================================
📊 MONITORING SUMMARY
================================================================================
Duration:          45.2s (45 samples)

Memory Usage (MB):
  Min:             10,856 MB (66.3%)
  Max:             11,234 MB (68.6%)
  Avg:             11,045 MB (67.5%)

GPU Utilization:
  Min:             45%
  Max:             98%
  Avg:             87%

Temperature:
  Min:             52°C
  Max:             68°C
  Avg:             61°C

Power Draw:
  Min:             145.2W
  Max:             285.4W
  Avg:             234.5W
================================================================================

✅ Summary saved: benchmarks/monitoring/vllm-serve-100-gpu.summary.json
```

---

## 📊 Compare Results

### **vLLM Offline vs vLLM Serve**

| Metric | Offline (5K) | Serve (100) | Serve (5K) |
|--------|--------------|-------------|------------|
| **Throughput** | 2,511 tok/s | ??? tok/s | ??? tok/s |
| **Success Rate** | 100% | ??? % | ??? % |
| **Memory** | ~11 GB | ??? GB | ??? GB |
| **Complexity** | Simple | Medium | Medium |
| **Use Case** | Large batches | Real-time API | TBD |

---

## 🧪 Testing 5K with vLLM Serve

**After 100 request test succeeds**, try 5K:

```bash
# Terminal 3
python test_vllm_serve_proper.py \
    batch_5k.jsonl \
    benchmarks/raw/vllm-serve-5k-results.jsonl
```

**Expected time:** ~6-10 minutes (with 10 concurrent requests)

**Watch Terminal 1 for:**
- Memory spikes
- GPU utilization
- Temperature increases

---

## 🚨 Troubleshooting

### **Server won't start**
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill zombie processes
pkill -f "vllm serve"
```

### **Connection refused errors**
- Make sure server is running (Terminal 2)
- Check `curl http://localhost:8000/health`
- Wait 30s for model to load

### **OOM errors**
- Reduce `--gpu-memory-utilization` to 0.85
- Reduce `--max-model-len` to 2048
- Reduce concurrent requests in test script

### **Slow throughput**
- Check GPU utilization in Terminal 1
- Should be 80-95% during inference
- If low, increase concurrent requests

---

## 📁 Files Generated

After testing, you'll have:

```
benchmarks/
├── monitoring/
│   ├── vllm-serve-100-gpu.log          # Raw monitoring data
│   └── vllm-serve-100-gpu.summary.json # Summary statistics
└── raw/
    └── vllm-serve-100-results.jsonl    # Inference results
```

---

## 🎯 Next Steps

1. **Test 100 requests** - Validate vLLM Serve works
2. **Test 5K requests** - See if it scales
3. **Compare to Offline** - Which is better for what?
4. **Document findings** - Update comparison table

---

## 💡 Key Questions to Answer

1. **Does vLLM Serve handle 5K batches?**
   - Previous test failed because server wasn't running
   - Need proper test to know

2. **What's the throughput difference?**
   - Offline: 2,511 tok/s
   - Serve: ??? tok/s

3. **When to use each mode?**
   - Offline: Batch jobs
   - Serve: Real-time API
   - Both: ???

---

**Status:** Ready to test. All tools prepared.

**Estimated time:** 15 minutes for 100 requests, 1 hour for 5K requests

