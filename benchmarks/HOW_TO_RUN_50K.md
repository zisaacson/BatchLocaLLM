# How to Run 50K Benchmark with GPU Monitoring

## Prerequisites

✅ **5K benchmark complete** - Validated vLLM works  
✅ **GPU monitoring tool ready** - `tools/monitor_gpu.py`  
✅ **50K input file** - Need to create `batch_50k.jsonl`  

---

## Step 1: Prepare 50K Input File

**Option A: Use existing 5K file 10 times**
```bash
# Create 50K by repeating 5K file 10 times
for i in {1..10}; do cat batch_5k.jsonl; done > batch_50k.jsonl

# Verify
wc -l batch_50k.jsonl  # Should show 50,000
```

**Option B: Use real Aris data (if available)**
```bash
# If you have more candidate data
cp /path/to/aris/batch_50k.jsonl .
```

---

## Step 2: Start GPU Monitoring

**Terminal 1: Start monitoring**
```bash
# Start GPU monitoring in background
python tools/monitor_gpu.py \
    --output benchmarks/monitoring/vllm-50k-gpu-$(date +%Y-%m-%d).log \
    --interval 1 &

# Save the PID to kill it later
echo $! > /tmp/gpu_monitor.pid
```

**What it monitors:**
- GPU memory usage (MB and %)
- GPU utilization (%)
- Memory utilization (%)
- Temperature (°C)
- Power draw (W)

**Sampling:** Every 1 second

---

## Step 3: Run 50K Benchmark

**Terminal 2: Run benchmark**
```bash
# Activate venv
source venv/bin/activate

# Run benchmark (will take ~6 hours)
time python benchmark_vllm_native.py \
    batch_50k.jsonl \
    benchmarks/raw/vllm-native-gemma3-4b-50000-$(date +%Y-%m-%d).jsonl \
    2>&1 | tee benchmarks/logs/vllm-50k-$(date +%Y-%m-%d).log
```

**Expected duration:** ~6 hours (based on 5K = 36 min)

---

## Step 4: Monitor Progress

**Check progress in real-time:**
```bash
# Watch GPU monitoring output
tail -f benchmarks/monitoring/vllm-50k-gpu-*.log

# Check how many results have been written
watch -n 10 'wc -l benchmarks/raw/vllm-native-gemma3-4b-50000-*.jsonl'

# Check GPU memory directly
watch -n 5 nvidia-smi
```

**What to watch for:**
- ⚠️ **Memory > 15 GB** - Approaching OOM
- ⚠️ **Temperature > 85°C** - Thermal throttling risk
- ✅ **Memory ~11 GB** - Normal (same as 5K)
- ✅ **GPU Util 90-100%** - Good utilization

---

## Step 5: Stop Monitoring When Complete

**After benchmark finishes:**
```bash
# Kill GPU monitoring process
kill $(cat /tmp/gpu_monitor.pid)

# This will print summary statistics automatically
```

**Or manually:**
```bash
pkill -f monitor_gpu.py
```

---

## Step 6: Analyze Results

**Check metadata:**
```bash
cat benchmarks/metadata/vllm-native-gemma3-4b-50000-*.json | jq .
```

**Check GPU monitoring summary:**
```bash
cat benchmarks/monitoring/vllm-50k-gpu-*.summary.json | jq .
```

**Compare to 5K:**
```bash
python tools/compare_benchmarks.py
```

---

## Expected Results (Projections from 5K)

| Metric | 5K Actual | 50K Projected |
|--------|-----------|---------------|
| **Requests** | 5,000 | 50,000 |
| **Success Rate** | 100% | 100% |
| **Total Time** | 36.8 min | 368 min (6.1 hrs) |
| **Throughput** | 2,511 tok/s | 2,511 tok/s |
| **Total Tokens** | 5.5M | 55M |
| **Memory Used** | ~11 GB | ~11 GB (same!) |
| **GPU Util** | 90-100% | 90-100% |

---

## What Could Go Wrong

### Scenario 1: OOM Error
**Symptoms:** Process crashes, CUDA out of memory error

**Solutions:**
1. Reduce `gpu_memory_utilization` to 0.85
2. Reduce `max_model_len` to 2048
3. Use KV cache quantization: `--kv-cache-dtype fp8`

**Edit `benchmark_vllm_native.py`:**
```python
llm = LLM(
    model="google/gemma-3-4b-it",
    max_model_len=2048,  # Reduced from 4096
    gpu_memory_utilization=0.85,  # Reduced from 0.90
)
```

### Scenario 2: Thermal Throttling
**Symptoms:** Temperature > 85°C, throughput drops

**Solutions:**
1. Improve GPU cooling (case fans, room temp)
2. Reduce power limit: `sudo nvidia-smi -pl 250` (RTX 4080 default is 320W)
3. Take breaks: Process in 10K chunks with cooldown

### Scenario 3: Process Killed by System
**Symptoms:** Process dies unexpectedly, no error message

**Solutions:**
1. Check system RAM (not GPU): `free -h`
2. Close other applications
3. Increase swap space if needed

### Scenario 4: Slower Than Expected
**Symptoms:** Throughput < 2,000 tok/s

**Solutions:**
1. Check GPU utilization: Should be 90-100%
2. Check for background processes: `nvidia-smi`
3. Verify no thermal throttling: `nvidia-smi -q -d TEMPERATURE`

---

## Emergency Stop

**If you need to stop the benchmark:**
```bash
# Kill benchmark process
pkill -f benchmark_vllm_native.py

# Kill GPU monitoring
kill $(cat /tmp/gpu_monitor.pid)

# Check GPU is free
nvidia-smi
```

**Partial results are saved!** Check how many lines were written:
```bash
wc -l benchmarks/raw/vllm-native-gemma3-4b-50000-*.jsonl
```

---

## After Completion

### 1. Verify Results
```bash
# Check success rate
jq -r 'select(.response.body.choices != null) | "SUCCESS"' \
    benchmarks/raw/vllm-native-gemma3-4b-50000-*.jsonl | wc -l

# Should be 50,000
```

### 2. Review GPU Monitoring
```bash
# View summary
cat benchmarks/monitoring/vllm-50k-gpu-*.summary.json | jq .

# Key metrics to check:
# - memory_mb.max < 15000 (no OOM)
# - temperature_c.max < 85 (no throttling)
# - gpu_utilization_pct.avg > 80 (good utilization)
```

### 3. Generate Report
```bash
# Compare all benchmarks
python tools/compare_benchmarks.py

# View comparison
cat benchmarks/reports/COMPARISON.md
```

### 4. Decide on 200K
Based on 50K results:
- ✅ If memory stable (~11 GB): 200K is feasible
- ✅ If throughput consistent (2,500 tok/s): 200K will take ~24 hours
- ⚠️ If any issues: Investigate before scaling further

---

## Quick Command Reference

```bash
# Start monitoring
python tools/monitor_gpu.py --output benchmarks/monitoring/vllm-50k-gpu.log --interval 1 &

# Run benchmark
python benchmark_vllm_native.py batch_50k.jsonl benchmarks/raw/vllm-50k-results.jsonl

# Watch progress
tail -f benchmarks/monitoring/vllm-50k-gpu.log
watch -n 10 'wc -l benchmarks/raw/vllm-50k-results.jsonl'

# Stop monitoring
pkill -f monitor_gpu.py

# Analyze
python tools/compare_benchmarks.py
```

---

## Notes

- **Time commitment:** 6+ hours - run overnight or during work day
- **GPU will be busy:** Can't use for other tasks during benchmark
- **Power consumption:** ~250-300W for 6 hours = ~1.5-1.8 kWh
- **Disk space:** ~50 MB for results file

---

**Ready to run when you are!**

