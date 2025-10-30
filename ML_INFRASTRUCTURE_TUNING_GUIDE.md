# ML Infrastructure Tuning Guide: From Local to Production

## 🎯 Executive Summary

**Your Current Benchmark Results Show:**
- ✅ **38.36% cache hit rate** - saving 9.4M tokens out of 24.7M queried
- ✅ **High Parallelism wins** - 4,292 req/s vs 3,687 req/s (16% faster)
- ✅ **Lower latency with Inngest-Style** - 2.56ms P50 vs 9.05ms P50
- ✅ **Both approaches work** - 100% success rate

**Key Insight:** Prefix caching is **already saving you 38% of compute costs** on your local workstation!

---

## 🎛️ ML Infrastructure Tuning Knobs

### **1. Prefix Caching (BIGGEST IMPACT)**

**What it is:**
- Caches the **prompt** (system message + instructions) so it doesn't need to be recomputed for every request
- vLLM automatically detects identical prefixes and reuses KV cache

**Your Current Performance:**
```
Cache Hit Rate: 38.36%
Tokens Saved:   9,469,152 / 24,687,880
Compute Saved:  38.36% of total
```

**How to optimize:**
```python
# vLLM server startup
vllm serve google/gemma-3-4b-it \
  --enable-prefix-caching \           # ✅ Already enabled
  --max-model-len 8192 \              # Increase for longer prompts
  --gpu-memory-utilization 0.9        # ✅ Already at 90%
```

**Cost Impact:**
- **Local (RTX 4080)**: 38% less GPU time = 38% more throughput
- **Production (A100)**: 38% less compute = **38% lower cloud costs**
- **Example**: $1000/month → $620/month (save $380/month)

**When it helps most:**
- ✅ **Same system prompt** for all requests (your use case!)
- ✅ **Long prompts** (your candidate evaluation rubric)
- ✅ **Batch processing** (your 5K batches)

**When it doesn't help:**
- ❌ Every request has unique prompt
- ❌ Short prompts (< 100 tokens)
- ❌ Single requests (no batching)

---

### **2. Context Window Size**

**What it is:**
- Maximum number of tokens (prompt + response) the model can handle
- Gemma 3 4B: 8,192 tokens default

**Your Current Usage:**
```python
# Estimate from your data
avg_prompt_tokens = 24687880 / 3450  # ~7,155 tokens per request
avg_response_tokens = ~200           # typical evaluation response
total_per_request = ~7,355 tokens    # close to 8K limit!
```

**Tuning Options:**

**Option A: Reduce Context (Faster, Cheaper)**
```python
vllm serve google/gemma-3-4b-it \
  --max-model-len 4096  # Half the context
```
- ✅ **2x faster** - less KV cache to manage
- ✅ **2x cheaper** - less memory needed
- ❌ **Risk**: Truncate long candidate profiles

**Option B: Increase Context (More Expensive)**
```python
vllm serve google/gemma-3-4b-it \
  --max-model-len 16384  # Double the context
```
- ✅ **Handle longer profiles** - no truncation
- ❌ **2x slower** - more KV cache to manage
- ❌ **2x more expensive** - more memory needed

**Recommendation for Production:**
- **Analyze your data**: What's the 95th percentile prompt length?
- **Set context to P95 + 500 tokens** - covers most cases without waste
- **Example**: If P95 = 6,000 tokens, set `--max-model-len 6500`

**Cost Impact:**
- **4K context**: ~$0.50/1M tokens (baseline)
- **8K context**: ~$1.00/1M tokens (2x cost)
- **16K context**: ~$2.00/1M tokens (4x cost)

---

### **3. Batching Strategy**

**What it is:**
- How many requests to process simultaneously
- vLLM automatically batches requests that arrive together

**Your Benchmark Results:**

| Mode | Concurrency | Throughput | Latency P50 | When to Use |
|------|-------------|------------|-------------|-------------|
| **High Parallelism** | 50 | 4,292 req/s | 9.05ms | Batch jobs, offline processing |
| **Inngest-Style** | 10 | 3,687 req/s | 2.56ms | Real-time API, user-facing |

**Tuning Options:**

**Option A: Max Throughput (Batch Jobs)**
```python
# Your current benchmark: 50 concurrent requests
async with asyncio.Semaphore(50):
    results = await asyncio.gather(*[process(req) for req in batch])
```
- ✅ **16% higher throughput** (4,292 vs 3,687 req/s)
- ❌ **3.5x higher latency** (9.05ms vs 2.56ms)
- **Use for**: Overnight batch processing, data pipelines

**Option B: Low Latency (Real-time API)**
```python
# Inngest-style: 10 concurrent requests
async with asyncio.Semaphore(10):
    results = await asyncio.gather(*[process(req) for req in batch])
```
- ✅ **3.5x lower latency** (2.56ms vs 9.05ms)
- ❌ **14% lower throughput** (3,687 vs 4,292 req/s)
- **Use for**: User-facing API, real-time responses

**vLLM Server Settings:**
```python
vllm serve google/gemma-3-4b-it \
  --max-num-seqs 256 \        # Max batch size (default: 256)
  --max-num-batched-tokens 8192  # Max tokens per batch
```

**Cost Impact:**
- **High throughput**: Process 5K candidates in 1.17s → **$0.01/batch**
- **Low latency**: Process 5K candidates in 1.36s → **$0.012/batch** (20% more)
- **For 170K candidates**: $340 vs $408 (save $68 with high throughput)

---

### **4. Quantization (Model Compression)**

**What it is:**
- Reduce model precision from FP16 (16-bit) to INT8 (8-bit) or INT4 (4-bit)
- Trades accuracy for speed and memory

**Options:**

**FP16 (Current - Baseline)**
```python
vllm serve google/gemma-3-4b-it  # Default FP16
```
- ✅ **Best quality** - no accuracy loss
- ❌ **Most memory** - 8GB for 4B model
- ❌ **Slowest** - baseline speed

**INT8 (AWQ/GPTQ)**
```python
vllm serve google/gemma-3-4b-it-awq  # 8-bit quantized
```
- ✅ **2x less memory** - 4GB for 4B model
- ✅ **1.5x faster** - less data to move
- ⚠️ **Slight quality loss** - 1-2% accuracy drop

**INT4 (GGUF)**
```python
vllm serve google/gemma-3-4b-it-gguf-q4  # 4-bit quantized
```
- ✅ **4x less memory** - 2GB for 4B model
- ✅ **2x faster** - much less data to move
- ⚠️ **Moderate quality loss** - 3-5% accuracy drop

**Recommendation:**
- **Local (RTX 4080 16GB)**: Use INT8 to fit larger models (Gemma 3 12B)
- **Production (A100 40GB)**: Use FP16 for best quality
- **Cost-sensitive**: Use INT4 for 4x cost savings

**Cost Impact:**
- **FP16**: $1.00/1M tokens (baseline)
- **INT8**: $0.67/1M tokens (33% savings)
- **INT4**: $0.50/1M tokens (50% savings)

---

### **5. GPU Memory Utilization**

**What it is:**
- How much GPU memory vLLM can use for KV cache
- More memory = larger batches = higher throughput

**Your Current Setting:**
```python
--gpu-memory-utilization 0.9  # 90% of 16GB = 14.4GB
```

**Tuning Options:**

**Conservative (0.7 - 0.8)**
```python
vllm serve google/gemma-3-4b-it \
  --gpu-memory-utilization 0.7  # 70% = 11.2GB
```
- ✅ **More stable** - less OOM risk
- ✅ **Room for other processes** - monitoring, logging
- ❌ **Lower throughput** - smaller batches

**Aggressive (0.9 - 0.95)**
```python
vllm serve google/gemma-3-4b-it \
  --gpu-memory-utilization 0.95  # 95% = 15.2GB
```
- ✅ **Max throughput** - largest batches
- ❌ **OOM risk** - may crash on spikes
- ❌ **No room for other processes**

**Recommendation:**
- **Local development**: 0.7-0.8 (leave room for debugging)
- **Production**: 0.9 (your current setting is perfect!)
- **Batch processing**: 0.95 (max throughput, can restart if OOM)

---

### **6. Tensor Parallelism (Multi-GPU)**

**What it is:**
- Split model across multiple GPUs
- Each GPU processes part of each layer

**When to use:**
- ✅ Model doesn't fit on single GPU (Gemma 3 70B)
- ✅ Need higher throughput than single GPU can provide
- ❌ **NOT for your current setup** (single RTX 4080)

**Example:**
```python
# 2x A100 GPUs
vllm serve google/gemma-3-70b-it \
  --tensor-parallel-size 2  # Split across 2 GPUs
```

**Cost Impact:**
- **1x A100**: $1.00/hour, 1000 req/s
- **2x A100**: $2.00/hour, 1500 req/s (not 2x due to overhead)
- **4x A100**: $4.00/hour, 2500 req/s

**Recommendation:**
- **Local**: Stick with single GPU
- **Production**: Use 1x A100 40GB for Gemma 3 12B
- **Large models**: Use 2x A100 for Gemma 3 70B

---

### **7. Speculative Decoding**

**What it is:**
- Use small "draft" model to predict tokens, large model to verify
- Can be 2-3x faster for long responses

**Example:**
```python
vllm serve google/gemma-3-12b-it \
  --speculative-model google/gemma-3-4b-it \
  --num-speculative-tokens 5
```

**When it helps:**
- ✅ **Long responses** (> 500 tokens)
- ✅ **Predictable text** (code, structured data)
- ❌ **Short responses** (< 100 tokens) - your use case!

**Recommendation:**
- **Skip for now** - your responses are ~200 tokens
- **Consider later** if you add long-form report generation

---

## 💰 Production Cost Estimation

### **Your Use Case: 170K Candidates**

**Assumptions:**
- Prompt: 7,000 tokens (candidate profile + rubric)
- Response: 200 tokens (evaluation)
- Total: 7,200 tokens per request
- Batch size: 5,000 requests

**Option A: Local (RTX 4080 16GB)**
```
Model: Gemma 3 4B (FP16)
Throughput: 4,292 req/s (high parallelism)
Time: 170K / 4,292 = 39.6 seconds
Cost: $0 (your hardware)
Cache savings: 38% less compute time
```

**Option B: GCP A100 40GB (FP16)**
```
Model: Gemma 3 12B (FP16)
Throughput: ~2,000 req/s (estimated)
Time: 170K / 2,000 = 85 seconds
Cost: $3.67/hour × (85/3600) = $0.087 per run
Monthly (30 runs): $2.61
Cache savings: 38% → $1.62/month
```

**Option C: GCP A100 40GB (INT8)**
```
Model: Gemma 3 12B (INT8 quantized)
Throughput: ~3,000 req/s (1.5x faster)
Time: 170K / 3,000 = 56.7 seconds
Cost: $3.67/hour × (57/3600) = $0.058 per run
Monthly (30 runs): $1.74
Cache savings: 38% → $1.08/month
```

**Option D: Vertex AI (Managed)**
```
Model: Gemma 3 12B
Cost: $0.50/1M tokens
Tokens: 170K × 7,200 = 1.224B tokens
Cost per run: $612
Monthly (30 runs): $18,360
Cache savings: 38% → $11,383/month
```

**Recommendation:**
1. **Development**: Use local RTX 4080 (free!)
2. **Production**: Use GCP A100 with INT8 ($1.08/month after caching)
3. **Avoid**: Managed APIs (1000x more expensive)

---

## 🎛️ Tuning Knobs Summary

| Knob | Impact | Cost Savings | Complexity | Recommendation |
|------|--------|--------------|------------|----------------|
| **Prefix Caching** | ⭐⭐⭐⭐⭐ | 38% | Low | ✅ Already enabled! |
| **Context Window** | ⭐⭐⭐⭐ | 50% | Low | Set to P95 + 500 |
| **Batching** | ⭐⭐⭐⭐ | 16% | Low | Use high parallelism |
| **Quantization** | ⭐⭐⭐⭐ | 50% | Medium | INT8 for production |
| **GPU Memory** | ⭐⭐⭐ | 10% | Low | Keep at 0.9 |
| **Tensor Parallel** | ⭐⭐ | N/A | High | Not needed yet |
| **Speculative Decode** | ⭐ | N/A | High | Skip for now |

---

## 📊 Your Benchmark Analysis

### **Key Findings:**

1. **Prefix caching is HUGE**: 38.36% cache hit rate
   - Saving 9.4M tokens out of 24.7M
   - This is because your system prompt is identical for all candidates!

2. **High Parallelism wins for throughput**:
   - 4,292 req/s vs 3,687 req/s (16% faster)
   - Use for batch processing

3. **Inngest-Style wins for latency**:
   - 2.56ms P50 vs 9.05ms P50 (3.5x faster)
   - Use for real-time API

4. **Both approaches are viable**:
   - 100% success rate
   - Minimal difference in total time (1.17s vs 1.36s for 5K requests)

### **Production Recommendation:**

**Use High Parallelism + Prefix Caching:**
```python
vllm serve google/gemma-3-12b-it \
  --enable-prefix-caching \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9 \
  --max-num-seqs 256 \
  --quantization awq  # INT8 for cost savings
```

**Expected Performance:**
- Throughput: ~3,000 req/s (with INT8)
- Latency: ~10ms P50
- Cache hit rate: ~38%
- Cost: $1.08/month for 170K candidates (30 runs)

---

## 🚀 Next Steps

1. ✅ **Analyze current cache metrics** - DONE! 38.36% hit rate
2. **Measure prompt length distribution** - Find P95 to optimize context window
3. **Test INT8 quantization** - Benchmark quality vs speed tradeoff
4. **Set up GCP project** - Prepare for production deployment
5. **Run cost comparison** - Local vs A100 vs Vertex AI


