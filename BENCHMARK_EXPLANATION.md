# Benchmark Explanation: What We're Testing

## 🎯 The Big Question

**"Should we use high parallelism (50 concurrent requests) or Inngest-style (10 concurrent requests) for our vLLM inference endpoint?"**

This benchmark answers that question by testing both approaches with real candidate evaluation data.

---

## 🔬 What We're Testing

### **Test 1: High Parallelism (Batched)**
- **What it is**: Send 50 requests at once, let vLLM batch them internally
- **How it works**: 
  ```python
  BATCH_SIZE = 50  # Send 50 requests simultaneously
  for i in range(0, 5000, 50):
      batch = requests[i:i+50]
      await asyncio.gather(*[send_request(req) for req in batch])
  ```
- **vLLM behavior**: Automatically batches the 50 concurrent requests together
- **Prefix caching**: ✅ Works great! vLLM sees all 50 requests at once and can reuse the cached system prompt
- **Use case**: Batch processing, offline jobs, data pipelines

### **Test 2: Inngest-Style (Independent)**
- **What it is**: Limit to 10 concurrent requests (simulating Inngest's execution model)
- **How it works**:
  ```python
  CONCURRENCY = 10  # Max 10 requests at a time
  semaphore = asyncio.Semaphore(10)
  async with semaphore:
      await send_request(req)
  ```
- **vLLM behavior**: Processes requests in smaller groups (max 10 at a time)
- **Prefix caching**: ✅ Still works, but less effective (smaller batches = less reuse)
- **Use case**: Real-time API, user-facing applications, Inngest workflows

---

## 📊 What We're Measuring

### **1. Throughput (req/s)**
- **What it is**: How many requests per second we can process
- **Why it matters**: Higher = faster batch processing, lower costs
- **Example**: 4,292 req/s means we can process 5,000 candidates in 1.17 seconds

### **2. Latency (ms)**
- **What it is**: How long each individual request takes
- **Metrics**:
  - **P50 (median)**: 50% of requests finish faster than this
  - **P95**: 95% of requests finish faster than this (important for SLAs)
  - **P99**: 99% of requests finish faster than this (worst-case)
- **Why it matters**: Lower = better user experience for real-time APIs
- **Example**: P50 of 2.56ms means half the requests finish in under 2.56ms

### **3. GPU Memory (GB)**
- **What it is**: Average GPU memory used during the benchmark
- **Why it matters**: Shows if we're efficiently using our RTX 4080's 16GB
- **Example**: 15.31 GB means we're using 95.7% of available memory (good!)

### **4. GPU Utilization (%)**
- **What it is**: How busy the GPU is (0% = idle, 100% = maxed out)
- **Why it matters**: Higher = better hardware utilization, lower costs per request
- **Example**: 100% means the GPU is fully utilized (no wasted compute)

### **5. Success Rate (%)**
- **What it is**: Percentage of requests that completed successfully
- **Why it matters**: Must be 100% for production use
- **Example**: 100% = all 5,000 requests succeeded

---

## 🔍 Your Benchmark Results Explained

Based on the data from `benchmark_20251029_220013.json`:

### **High Parallelism (50 concurrent)**
```
Size: 5000 requests
Time: 1.17 seconds
Throughput: 4,292 req/s
Latency P50: 9.05ms
Latency P95: 10.38ms
GPU Memory: 15.31 GB
Success Rate: 100%
```

**What this means:**
- ✅ **FASTEST throughput** - processes 5K candidates in just 1.17 seconds
- ⚠️ **Higher latency** - individual requests take ~9ms (3.5x slower than Inngest-style)
- ✅ **Full GPU utilization** - using all available memory and compute
- ✅ **Perfect reliability** - no errors

**Best for:**
- Batch processing 170K candidates overnight
- Data pipelines where total time matters more than individual request time
- Maximizing throughput and minimizing cost

### **Inngest-Style (10 concurrent)**
```
Size: 5000 requests
Time: 1.36 seconds
Throughput: 3,687 req/s
Latency P50: 2.56ms
Latency P95: 2.79ms
GPU Memory: 15.31 GB
Success Rate: 100%
```

**What this means:**
- ⚠️ **Slower throughput** - takes 16% longer (1.36s vs 1.17s)
- ✅ **LOWEST latency** - individual requests finish in ~2.56ms (3.5x faster!)
- ✅ **Same GPU usage** - still using full memory
- ✅ **Perfect reliability** - no errors

**Best for:**
- Real-time API where users are waiting for responses
- Inngest workflows with concurrency limits
- When you need predictable, low latency

---

## 💡 Key Insights

### **1. The Difference is Small for Total Time**
- High Parallelism: 1.17 seconds for 5K requests
- Inngest-Style: 1.36 seconds for 5K requests
- **Difference: Only 0.19 seconds (16% slower)**

**Why?** Both approaches max out the GPU! The bottleneck is GPU compute, not request batching.

### **2. Latency Difference is HUGE**
- High Parallelism: 9.05ms P50
- Inngest-Style: 2.56ms P50
- **Difference: 3.5x faster per request!**

**Why?** With 50 concurrent requests, each request waits for the other 49 to finish. With 10 concurrent, there's less waiting.

### **3. Prefix Caching is Working!**
- Cache hit rate: **38.36%** (from earlier analysis)
- This means 38% of tokens are FREE (reused from cache)
- Both approaches benefit from caching, but High Parallelism benefits more (larger batches = more reuse)

### **4. Both Approaches Max Out the GPU**
- GPU Memory: 15.31 GB (95.7% of 16GB)
- GPU Utilization: 100%
- **Conclusion**: You're getting full value from your RTX 4080!

---

## 🎯 Which Should You Use?

### **Use High Parallelism (50 concurrent) if:**
- ✅ You're processing large batches (170K candidates)
- ✅ Total time matters more than individual request time
- ✅ You want maximum throughput (4,292 req/s)
- ✅ You want to maximize prefix cache benefits
- ✅ Users aren't waiting for results (offline processing)

**Example:** Overnight batch job to evaluate all 170K candidates
- Time: 170,000 / 4,292 = **39.6 seconds**
- Cost: Minimal (local GPU)

### **Use Inngest-Style (10 concurrent) if:**
- ✅ You're building a real-time API
- ✅ Users are waiting for responses
- ✅ You need predictable, low latency (2.56ms P50)
- ✅ You're using Inngest (which limits concurrency)
- ✅ You want to avoid request timeouts

**Example:** Real-time candidate evaluation API
- Latency: 2.56ms per candidate (feels instant!)
- Throughput: Still fast (3,687 req/s)

---

## 📈 Production Recommendations

### **For Your Use Case (170K Candidates)**

**Recommendation: Use High Parallelism**

**Why?**
1. **You're doing batch processing** - users aren't waiting for results
2. **16% faster** - saves time on large batches
3. **Better cache utilization** - 38% of compute is free
4. **Same reliability** - 100% success rate

**Expected Performance:**
```
170,000 candidates / 4,292 req/s = 39.6 seconds
```

**Cost Savings from Caching:**
```
Without cache: 39.6 seconds
With cache (38% savings): ~24.5 seconds
Time saved: 15.1 seconds per run
```

### **If You Add Real-Time API Later**

**Recommendation: Use Inngest-Style**

**Why?**
1. **Users are waiting** - 2.56ms feels instant
2. **Predictable latency** - P95 is only 2.79ms (very consistent)
3. **Still fast enough** - 3,687 req/s is plenty for real-time

**Expected Performance:**
```
Single candidate: 2.56ms (feels instant to user)
100 candidates: 100 / 3,687 = 0.027 seconds (27ms)
```

---

## 🔧 How to Switch Between Modes

### **High Parallelism Mode**
```python
# In your code
BATCH_SIZE = 50
for i in range(0, len(requests), BATCH_SIZE):
    batch = requests[i:i+BATCH_SIZE]
    await asyncio.gather(*[process(req) for req in batch])
```

### **Inngest-Style Mode**
```python
# In your code
CONCURRENCY = 10
semaphore = asyncio.Semaphore(CONCURRENCY)

async def process_with_limit(req):
    async with semaphore:
        return await process(req)

await asyncio.gather(*[process_with_limit(req) for req in requests])
```

---

## 📊 Summary Table

| Metric | High Parallelism | Inngest-Style | Winner |
|--------|------------------|---------------|--------|
| **Throughput** | 4,292 req/s | 3,687 req/s | 🏆 High Parallelism (+16%) |
| **Latency P50** | 9.05ms | 2.56ms | 🏆 Inngest-Style (3.5x faster) |
| **Latency P95** | 10.38ms | 2.79ms | 🏆 Inngest-Style (3.7x faster) |
| **Total Time (5K)** | 1.17s | 1.36s | 🏆 High Parallelism (16% faster) |
| **GPU Memory** | 15.31 GB | 15.31 GB | 🤝 Tie |
| **Success Rate** | 100% | 100% | 🤝 Tie |
| **Cache Benefit** | Higher | Lower | 🏆 High Parallelism |
| **Best For** | Batch jobs | Real-time API | - |

---

## 🚀 Next Steps

1. **For batch processing**: Use High Parallelism (50 concurrent)
2. **Monitor cache hit rate**: Should stay around 38%
3. **Test with 170K candidates**: Verify it completes in ~40 seconds
4. **If you build real-time API**: Switch to Inngest-Style (10 concurrent)

---

## ❓ FAQ

**Q: Why is latency so different if total time is similar?**
A: With 50 concurrent requests, each request waits for the other 49. With 10 concurrent, less waiting. But total throughput is similar because the GPU is maxed out either way.

**Q: Can I use 100 concurrent requests for even faster throughput?**
A: Probably not much faster. You're already maxing out the GPU at 50 concurrent. More concurrency = more waiting, higher latency, same throughput.

**Q: What if I need both low latency AND high throughput?**
A: You can't have both with a single GPU. Low latency requires low concurrency (less waiting). High throughput requires high concurrency (more batching). Pick based on your use case.

**Q: Is 38% cache hit rate good?**
A: YES! That's excellent. It means 38% of your compute is free. This is because your system prompt is identical for all candidates.

**Q: Should I worry about the 16% throughput difference?**
A: For batch processing, no. 1.17s vs 1.36s for 5K requests is negligible. For real-time API, latency matters more than throughput anyway.

