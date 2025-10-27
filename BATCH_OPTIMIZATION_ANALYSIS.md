# Batch Processing Optimization Analysis

## Your Use Case: 170k Candidate Scoring

**Scenario**:
- 170,000 candidates to evaluate
- **Same prompt** for all candidates (system message + scoring instructions)
- **Same sample data** for all candidates (examples, rubric, etc.)
- **Only variable**: Individual candidate data

**Current Implementation**: ❌ **NOT OPTIMIZED**
- Each request re-tokenizes the entire prompt
- No context reuse between requests
- Model may unload between requests
- Estimated waste: **~99% of tokenization is redundant**

---

## Tokenization Overhead Analysis

### Example Request Structure
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a candidate scoring assistant. Use the following rubric: [2000 tokens of rubric]"
    },
    {
      "role": "user",
      "content": "Score this candidate: [50 tokens of candidate data]"
    }
  ]
}
```

### Current (Unoptimized) Processing
```
Request 1: Tokenize 2050 tokens → Inference → Output
Request 2: Tokenize 2050 tokens → Inference → Output  (2000 tokens WASTED)
Request 3: Tokenize 2050 tokens → Inference → Output  (2000 tokens WASTED)
...
Request 170,000: Tokenize 2050 tokens → Inference → Output

Total tokenization: 170,000 × 2,050 = 348,500,000 tokens
Unique content: 2,000 (system) + (170,000 × 50) = 8,502,000 tokens
WASTE: 340,000,000 tokens (97.6% redundant!)
```

### Optimized Processing (With Prompt Caching)
```
Request 1: Tokenize 2050 tokens → Cache system prompt → Inference → Output
Request 2: Reuse cached 2000 tokens + Tokenize 50 new → Inference → Output
Request 3: Reuse cached 2000 tokens + Tokenize 50 new → Inference → Output
...
Request 170,000: Reuse cached 2000 tokens + Tokenize 50 new → Inference → Output

Total tokenization: 2,000 + (170,000 × 50) = 8,502,000 tokens
SAVINGS: 340,000,000 tokens (97.6% reduction!)
```

---

## Ollama Optimization Features

### 1. **`keep_alive` Parameter**
**Purpose**: Keep model loaded in memory between requests

**Default**: 5 minutes
**Recommended for batches**: `"24h"` or `-1` (infinite)

**Impact**:
- ✅ Eliminates model loading overhead (~5-10 seconds per load)
- ✅ For 170k requests: Saves **~236 hours** of model loading time
- ✅ Keeps KV cache warm

**Implementation**:
```json
{
  "model": "gemma3:12b",
  "messages": [...],
  "keep_alive": "24h"  // Keep model loaded for entire batch
}
```

### 2. **`context` Parameter (KV Cache Reuse)**
**Purpose**: Reuse previously computed key-value cache

**How it works**:
1. First request returns a `context` array (encoded KV cache state)
2. Subsequent requests send this `context` back
3. Ollama reuses the cached computation for matching prefix

**Impact**:
- ✅ Eliminates re-tokenization of identical prompt prefix
- ✅ Eliminates re-computation of attention for cached tokens
- ✅ For 170k requests with 2000-token prefix: **97.6% tokenization reduction**

**Implementation**:
```python
# First request
response1 = ollama.chat(model="gemma3:12b", messages=[...])
context = response1["context"]  # Save this!

# Subsequent requests
response2 = ollama.chat(
    model="gemma3:12b",
    messages=[...],  # Same system message + new user message
    context=context  # Reuse cached computation
)
```

### 3. **Batch Grouping Strategy**
**Purpose**: Group requests with identical prefixes

**Strategy**:
1. Detect requests with identical system messages
2. Process them sequentially with context reuse
3. Reset context when prefix changes

**Impact**:
- ✅ Maximizes cache hit rate
- ✅ Reduces memory usage (single context vs multiple)
- ✅ Simplifies implementation

---

## Proposed Optimizations

### Optimization 1: Keep Model Loaded
**Effort**: Low (5 minutes)
**Savings**: ~236 hours of model loading for 170k requests

```python
# Add to ollama_backend.py
ollama_request["keep_alive"] = "24h"  # or -1 for infinite
```

### Optimization 2: Prompt Caching (Context Reuse)
**Effort**: Medium (1-2 hours)
**Savings**: 97.6% tokenization reduction (340M tokens)

**Implementation**:
1. Detect identical prompt prefixes in batch
2. Use first request to establish context
3. Reuse context for subsequent requests
4. Track context per unique prefix

### Optimization 3: Batch Grouping
**Effort**: Medium (1-2 hours)
**Savings**: Maximizes cache efficiency

**Implementation**:
1. Pre-process batch to group by system message
2. Process each group with context reuse
3. Merge results back in original order

### Optimization 4: Progress Tracking & Metrics
**Effort**: Low (30 minutes)
**Savings**: Visibility into optimization impact

**Metrics to track**:
- Tokens processed (prompt + completion)
- Tokens cached (reused from context)
- Cache hit rate (%)
- Requests per second
- Time saved vs unoptimized

---

## Estimated Performance Gains

### Scenario: 170k Candidates, 2000-token System Prompt, 50-token Candidate Data

| Metric | Unoptimized | Optimized | Improvement |
|--------|-------------|-----------|-------------|
| **Total Prompt Tokens** | 348,500,000 | 8,502,000 | **97.6% reduction** |
| **Model Loads** | ~34,000 (5min timeout) | 1 | **99.997% reduction** |
| **Model Load Time** | ~236 hours | ~10 seconds | **99.998% reduction** |
| **Tokenization Time** | ~193 hours (2ms/req) | ~4.7 hours | **97.6% reduction** |
| **Total Processing Time** | ~429 hours | ~10 hours | **97.7% reduction** |
| **Cost (if cloud)** | $348,500 (@$1/M) | $8,502 | **$340,000 saved** |

**Assumptions**:
- Model load: 10 seconds
- Tokenization: 2ms per request
- Inference: 100ms per request (50 tokens @ 500 tokens/sec)
- Ollama default keep_alive: 5 minutes

---

## Implementation Priority

### Phase 1: Quick Wins (30 minutes)
1. ✅ Add `keep_alive` parameter to all requests
2. ✅ Add token usage tracking to batch results
3. ✅ Create benchmark test (100 requests)

### Phase 2: Context Caching (2-3 hours)
1. ✅ Detect identical prompt prefixes
2. ✅ Implement context reuse in `ollama_backend.py`
3. ✅ Add context management to `batch_processor.py`
4. ✅ Test with 1000 requests

### Phase 3: Advanced Optimizations (4-6 hours)
1. ✅ Batch grouping by system message
2. ✅ Parallel processing (multiple models if GPU allows)
3. ✅ Adaptive batching (adjust batch size based on GPU memory)
4. ✅ Comprehensive benchmarking suite

---

## Testing Strategy

### Test 1: Baseline (No Optimization)
```bash
# 100 requests, no optimization
python test_batch_benchmark.py --requests 100 --optimize false
```

**Expected**:
- Total time: ~30 seconds
- Prompt tokens: 205,000
- Model loads: ~6

### Test 2: Keep-Alive Only
```bash
# 100 requests, keep_alive=24h
python test_batch_benchmark.py --requests 100 --keep-alive 24h
```

**Expected**:
- Total time: ~20 seconds (33% faster)
- Prompt tokens: 205,000 (same)
- Model loads: 1 (83% reduction)

### Test 3: Full Optimization (Keep-Alive + Context Caching)
```bash
# 100 requests, keep_alive=24h, context reuse
python test_batch_benchmark.py --requests 100 --optimize true
```

**Expected**:
- Total time: ~12 seconds (60% faster)
- Prompt tokens: 7,000 (96.6% reduction)
- Model loads: 1
- Cache hit rate: 99%

### Test 4: Large Scale (10k requests)
```bash
# 10k requests, full optimization
python test_batch_benchmark.py --requests 10000 --optimize true
```

**Expected**:
- Total time: ~20 minutes
- Prompt tokens: 502,000 (vs 20.5M unoptimized)
- Throughput: ~8 requests/second

---

## Next Steps

1. **Implement `keep_alive` optimization** (5 minutes)
2. **Create benchmark test** (30 minutes)
3. **Run baseline benchmark** (5 minutes)
4. **Implement context caching** (2 hours)
5. **Run optimized benchmark** (5 minutes)
6. **Compare results and document savings** (15 minutes)

**Total estimated time**: ~3-4 hours for full optimization

**Expected ROI for 170k candidates**:
- Time saved: ~419 hours (17.5 days)
- Tokens saved: 340M tokens
- If cloud: $340,000 saved

---

## Questions to Answer

1. ✅ **Does Ollama support context caching?** → YES (`context` parameter)
2. ✅ **Can we keep model loaded?** → YES (`keep_alive` parameter)
3. ⏳ **How much memory does context cache use?** → Need to test
4. ⏳ **What's the actual cache hit rate?** → Need to benchmark
5. ⏳ **Can we process multiple requests in parallel?** → Depends on GPU memory

---

**Status**: Ready to implement
**Priority**: HIGH (97.6% potential savings)
**Risk**: LOW (Ollama native features, well-documented)

