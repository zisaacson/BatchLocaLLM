# Batch Optimization Requirements - First Principles

**Date**: 2025-10-27  
**Branch**: `ollama`  
**Purpose**: Define what we MUST track and manage for enterprise-grade batch inference

---

## 🎯 Core Problem Statement

**Goal**: Process 170,000 candidate evaluations efficiently and reliably

**Constraints**:
- RTX 4080 16GB VRAM (consumer GPU)
- Ollama backend (sequential processing)
- OpenAI-compatible API (non-negotiable)
- Same system prompt for all requests (scoring rubric)

---

## 📊 Critical Metrics We MUST Track

### 1. **Token Usage** (Cost & Efficiency)

**Why it matters**:
- Tokens = Cost (if cloud)
- Tokens = Processing time
- Redundant tokenization = waste

**What to track**:
- ✅ **Prompt tokens per request** - How many tokens in input
- ✅ **Completion tokens per request** - How many tokens generated
- ✅ **Total tokens per batch** - Sum across all requests
- ✅ **Cached tokens** - How many tokens reused from context
- ✅ **Cache hit rate** - % of tokens served from cache
- ✅ **Token savings** - Baseline vs optimized

**Optimization target**: 
- Baseline: 170k × 2050 tokens = 348M tokens
- Optimized: 2000 + (170k × 50) = 8.5M tokens
- **Target: 97.6% reduction**

---

### 2. **Context Window Management** (VRAM Safety)

**Why it matters**:
- Context overflow = OOM crash
- Long context = slower inference
- VRAM fills up with KV cache

**What to track**:
- ✅ **Current context length** - Tokens in conversation
- ✅ **Max context limit** - Model's maximum (Gemma 3: 128K)
- ✅ **Safe context limit** - Conservative limit (32K for safety)
- ✅ **Context utilization %** - How full is the context
- ✅ **Trim events** - When we had to trim context
- ✅ **Trim strategy** - What we kept vs discarded

**Safety thresholds**:
- Max: 128K tokens (Gemma 3 12B limit)
- Safe: 32K tokens (25% of max - conservative)
- Trim at: 28K tokens (87.5% of safe limit)
- Reserve: 4K tokens (always keep space for response)

---

### 3. **VRAM Usage** (Hardware Limits)

**Why it matters**:
- 16GB total VRAM (RTX 4080)
- Model takes ~8GB
- KV cache grows with context
- OOM = crash

**What to track**:
- ✅ **Model memory** - Base model size (~8GB for Gemma 3 12B)
- ✅ **KV cache memory** - Grows with context length
- ✅ **Peak VRAM usage** - Maximum observed
- ✅ **Available VRAM** - Free memory remaining
- ✅ **VRAM utilization %** - How full is GPU memory
- ✅ **OOM warnings** - Near-limit alerts

**VRAM breakdown** (Gemma 3 12B):
- Model weights: ~8GB (Q4_K_M quantization)
- KV cache: ~0.5MB per token × context_length
  - 1K context: ~500MB
  - 10K context: ~5GB
  - 32K context: ~16GB ⚠️ (DANGER!)
- System overhead: ~500MB

**Safety limits**:
- Total VRAM: 16GB
- Model: 8GB
- Max KV cache: 6GB (leaves 2GB buffer)
- **Max safe context: ~12K tokens**

---

### 4. **Processing Time** (Throughput)

**Why it matters**:
- 170k requests = days of processing
- Time = money
- Users need estimates

**What to track**:
- ✅ **Time per request** - Average latency
- ✅ **Requests per second** - Throughput
- ✅ **Total batch time** - End-to-end duration
- ✅ **Time remaining** - ETA for completion
- ✅ **Tokens per second** - Generation speed
- ✅ **Model load time** - Overhead per load
- ✅ **Tokenization time** - Preprocessing overhead

**Performance targets**:
- Baseline: 10s per request = 472 hours (19.7 days)
- Optimized: 5s per request = 236 hours (9.8 days)
- **Target: 50% faster**

---

### 5. **Tokens Per Second** (Generation Speed)

**Why it matters**:
- Indicates GPU utilization
- Detects bottlenecks
- Measures optimization impact

**What to track**:
- ✅ **Prompt tokens/sec** - Input processing speed
- ✅ **Generation tokens/sec** - Output generation speed
- ✅ **Total tokens/sec** - Overall throughput
- ✅ **Batch tokens/sec** - Aggregate across batch

**Expected performance** (Gemma 3 12B on RTX 4080):
- Prompt processing: ~2000 tokens/sec
- Generation: ~50-100 tokens/sec
- Bottleneck: Generation (always slower)

---

### 6. **Error Handling** (Reliability)

**Why it matters**:
- 170k requests = high failure probability
- One error shouldn't kill entire batch
- Need retry logic

**What to track**:
- ✅ **Success count** - Completed requests
- ✅ **Failure count** - Failed requests
- ✅ **Error types** - Categorize failures
- ✅ **Retry attempts** - How many retries per request
- ✅ **Partial results** - Save progress on crash

**Error categories**:
- OOM errors (VRAM overflow)
- Timeout errors (request too slow)
- Model errors (generation failure)
- Network errors (Ollama connection)
- Validation errors (bad input)

---

### 7. **Progress Tracking** (User Experience)

**Why it matters**:
- 170k requests = hours/days
- Users need visibility
- Enable pause/resume

**What to track**:
- ✅ **Requests completed** - Progress count
- ✅ **Requests remaining** - Work left
- ✅ **Completion %** - Visual progress
- ✅ **ETA** - Estimated time remaining
- ✅ **Current request** - What's processing now
- ✅ **Batch state** - validating/in_progress/completed/failed

---

## 🏗️ System Architecture Requirements

### Resource Limits (Per Batch)

```python
class BatchLimits:
    # Context window
    MAX_CONTEXT_TOKENS = 32000      # Conservative limit
    TRIM_THRESHOLD = 28000          # Start trimming at 87.5%
    MIN_RESERVE = 4000              # Always keep space for response
    
    # VRAM
    MAX_VRAM_GB = 16                # RTX 4080 total
    MODEL_VRAM_GB = 8               # Gemma 3 12B
    MAX_KV_CACHE_GB = 6             # Safe limit
    
    # Performance
    MAX_BATCH_SIZE = 50000          # Max requests per batch
    TRIM_INTERVAL = 50              # Trim every N requests
    PROGRESS_LOG_INTERVAL = 100     # Log every N requests
    
    # Timeouts
    REQUEST_TIMEOUT_SEC = 300       # 5 minutes per request
    BATCH_TIMEOUT_SEC = 86400       # 24 hours per batch
```

### Monitoring & Metrics

```python
class BatchMetrics:
    # Token metrics
    total_prompt_tokens: int
    total_completion_tokens: int
    cached_tokens: int
    cache_hit_rate: float
    
    # Context metrics
    current_context_length: int
    max_context_length: int
    context_utilization_pct: float
    trim_count: int
    
    # VRAM metrics
    model_vram_gb: float
    kv_cache_vram_gb: float
    peak_vram_gb: float
    vram_utilization_pct: float
    
    # Performance metrics
    requests_completed: int
    requests_failed: int
    avg_time_per_request_sec: float
    tokens_per_second: float
    eta_seconds: int
    
    # Error metrics
    oom_errors: int
    timeout_errors: int
    model_errors: int
    retry_count: int
```

---

## 🎯 Optimization Strategies

### Strategy 1: Conversation Batching (IMPLEMENTED)
**When**: All requests share same system prompt  
**How**: Process as single conversation, reuse tokenized system prompt  
**Savings**: 97.6% token reduction  
**Risk**: Context overflow, VRAM overflow  
**Mitigation**: Trim context every 50 requests

### Strategy 2: Context Trimming (NEEDED)
**When**: Context approaches limit (28K tokens)  
**How**: Keep system prompt + last N exchanges  
**Savings**: Prevents OOM, maintains performance  
**Risk**: Lose conversation history  
**Mitigation**: Only trim old exchanges, keep recent context

### Strategy 3: Keep-Alive (NEEDED)
**When**: Processing batch  
**How**: Set `keep_alive=-1` to keep model loaded  
**Savings**: Eliminates model reload overhead (~10s per load)  
**Risk**: None  
**Mitigation**: None needed

### Strategy 4: Progress Checkpointing (FUTURE)
**When**: Long-running batches (>1 hour)  
**How**: Save results every N requests  
**Savings**: Recover from crashes  
**Risk**: Disk I/O overhead  
**Mitigation**: Async writes, configurable interval

---

## 📋 Implementation Checklist

### Phase 1: Core Optimization (NOW)
- [x] Detect identical system prompts
- [x] Implement conversation batching
- [x] Add context trimming (every 50 requests)
- [x] Add keep_alive=-1
- [ ] Test with 100 requests
- [ ] Test with 1000 requests

### Phase 2: Monitoring (NEXT)
- [ ] Track token usage (prompt/completion/cached)
- [ ] Track context length
- [ ] Track VRAM usage (via nvidia-smi)
- [ ] Track processing time
- [ ] Track tokens/second
- [ ] Log progress every 100 requests

### Phase 3: Safety (CRITICAL)
- [ ] Implement context overflow protection
- [ ] Implement VRAM overflow protection
- [ ] Implement request timeout
- [ ] Implement batch timeout
- [ ] Add error categorization
- [ ] Add retry logic

### Phase 4: User Experience (POLISH)
- [ ] Real-time progress updates
- [ ] ETA calculation
- [ ] Pause/resume support
- [ ] Partial result download
- [ ] Metrics dashboard

---

## 🚨 Critical Risks & Mitigations

### Risk 1: VRAM Overflow (OOM)
**Probability**: HIGH (if context grows unchecked)  
**Impact**: CRITICAL (crashes entire batch)  
**Mitigation**: 
- Trim context every 50 requests
- Monitor VRAM usage
- Set conservative context limit (32K)

### Risk 2: Context Window Overflow
**Probability**: MEDIUM (170k requests in one conversation)  
**Impact**: HIGH (request fails, loses progress)  
**Mitigation**:
- Trim to last 20 exchanges
- Keep system prompt always
- Log trim events

### Risk 3: Single Point of Failure
**Probability**: MEDIUM (one error kills batch)  
**Impact**: HIGH (lose all progress)  
**Mitigation**:
- Try/catch per request
- Continue on error
- Save partial results

### Risk 4: Slow Performance
**Probability**: LOW (Ollama is fast)  
**Impact**: MEDIUM (takes too long)  
**Mitigation**:
- Use keep_alive
- Monitor tokens/sec
- Optimize context size

---

## 📊 Success Metrics

**Baseline (No Optimization)**:
- Prompt tokens: 348M
- Time: 472 hours
- VRAM: Stable (no overflow)
- Failures: 0%

**Target (Optimized)**:
- Prompt tokens: 8.5M (97.6% reduction) ✅
- Time: 236 hours (50% faster) ✅
- VRAM: Stable (no overflow) ✅
- Failures: <1% ✅
- Cache hit rate: >95% ✅

---

## 🎓 Key Insights

1. **Token optimization is the biggest win** - 97.6% reduction possible
2. **VRAM is the hard limit** - Must trim context to prevent OOM
3. **Context window is generous** - 128K is plenty, use 32K for safety
4. **Model loading is expensive** - Keep-alive saves ~10s per request
5. **Monitoring is critical** - Can't optimize what you don't measure
6. **Errors will happen** - Need robust error handling for 170k requests

---

**Status**: Requirements defined, core optimization implemented  
**Next**: Add monitoring and safety checks  
**Priority**: Test with 1000 requests to validate approach

