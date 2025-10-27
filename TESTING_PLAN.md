# 🧪 Critical Testing Plan

**Date**: 2025-10-27  
**Branch**: `ollama`  
**Status**: ⚠️ TESTS NEEDED BEFORE PRODUCTION

---

## 🚨 Why These Tests Are CRITICAL

### Current Status: **We're Guessing!**

Right now we have hardcoded values:
```python
MAX_CONTEXT_TOKENS = 32000  # ❓ Is this right?
CONTEXT_TRIM_THRESHOLD = 28000  # ❓ Is this safe?
TRIM_INTERVAL = 50  # ❓ Is this optimal?
```

**For 170,000 requests, we CANNOT guess!**

If we get this wrong:
- ❌ **Too high** → OOM crash, lose all progress
- ❌ **Too low** → Waste performance, slower processing
- ❌ **Wrong trim interval** → Either OOM or excessive trimming

---

## 📋 Test Suite Overview

### Test 1: Context Window Limits (`test_context_limits.py`)

**Purpose**: Find the ACTUAL limits for Gemma 3 12B

**What it tests**:
1. Maximum context length before OOM
2. VRAM growth rate (bytes per token)
3. Optimal context trim threshold
4. Safe operating limits

**Why it's critical**:
- We need to know the REAL limit, not guess
- VRAM usage grows with context (KV cache)
- One OOM crash = lose all 170k request progress
- Need data-driven safe limits

**How it works**:
```python
# Test increasing context lengths
test_sizes = [10, 25, 50, 100, 200, 300, 400, 500]

for size in test_sizes:
    # Build conversation with N exchanges
    # Measure VRAM usage
    # Stop when OOM or timeout
    
# Analyze results:
# - Maximum safe context
# - VRAM per token
# - Recommended limits
```

**Expected output**:
```
✅ Maximum tested context:
   Exchanges: 400
   Estimated tokens: 40,000
   VRAM usage: 14.5 GB

💡 Recommended safe limits (80% of max):
   MAX_CONTEXT_TOKENS = 32,000
   CONTEXT_TRIM_THRESHOLD = 28,000
   TRIM_INTERVAL = 50
```

---

### Test 2: Performance Benchmarks (`test_performance_benchmarks.py`)

**Purpose**: Validate optimization works at scale

**What it tests**:
1. 100 requests (~15 seconds)
2. 1,000 requests (~2.5 minutes)
3. 10,000 requests (~25 minutes)

**Why it's critical**:
- Validates conversation batching works at scale
- Validates context trimming prevents OOM
- Validates performance is consistent
- Validates token savings match predictions
- Extrapolates to 170k requests

**How it works**:
```python
for num_requests in [100, 1000, 10000]:
    # Create batch with identical system prompts
    # Upload and process
    # Measure:
    #   - Total time
    #   - Throughput (req/s)
    #   - Token usage
    #   - Token savings %
    #   - VRAM usage
    
# Extrapolate to 170k:
# - Estimated time
# - Estimated token savings
# - Estimated VRAM usage
```

**Expected output**:
```
Size       Time         Req/s      Tokens/s     Savings   
---------- ------------ ---------- ------------ ----------
100        15.1s        6.62       2213.4       10.3%     
1,000      151.0s       6.62       2213.4       10.3%     
10,000     1510.0s      6.62       2213.4       10.3%     

📊 EXTRAPOLATION TO 170,000 REQUESTS:
   Estimated time: 25,670s (7.1 hours)
   Estimated throughput: 6.62 req/s
   Estimated token savings: 10.3%
```

---

## 🎯 What We Need to Learn

### 1. **Actual Context Limits**

**Questions**:
- What's Gemma 3 12B's real context limit?
- At what context length does VRAM overflow?
- How much VRAM does KV cache use per token?

**Why it matters**:
- Need to set safe MAX_CONTEXT_TOKENS
- Need to know when to trim
- Need to prevent OOM crashes

**Current assumptions** (UNVALIDATED):
```python
MAX_CONTEXT_TOKENS = 32000  # ❓ Guess
CONTEXT_TRIM_THRESHOLD = 28000  # ❓ Guess
```

**After testing** (DATA-DRIVEN):
```python
MAX_CONTEXT_TOKENS = 35000  # ✅ Tested safe limit
CONTEXT_TRIM_THRESHOLD = 30000  # ✅ 85% of tested max
```

---

### 2. **VRAM Growth Rate**

**Questions**:
- How much VRAM does the model use? (We assume 8GB)
- How much VRAM does KV cache use per token?
- What's the maximum safe context before hitting 16GB limit?

**Why it matters**:
- RTX 4080 has 16GB total
- Model + KV cache must fit in VRAM
- Need to know when we're approaching limit

**Current assumptions** (UNVALIDATED):
```python
MODEL_VRAM_GB = 8.0  # ❓ Guess
KV_CACHE_PER_TOKEN_MB = 0.5  # ❓ Guess
```

**After testing** (DATA-DRIVEN):
```python
MODEL_VRAM_GB = 8.2  # ✅ Measured
KV_CACHE_PER_TOKEN_MB = 0.42  # ✅ Measured
MAX_SAFE_CONTEXT = 35000  # ✅ Calculated from VRAM limit
```

---

### 3. **Optimal Trim Strategy**

**Questions**:
- How often should we trim? (Every 50 requests?)
- How many messages should we keep? (Last 40?)
- What's the performance impact of trimming?

**Why it matters**:
- Trim too often → Waste performance
- Trim too rarely → Risk OOM
- Keep too few messages → Lose context quality
- Keep too many messages → Risk OOM

**Current assumptions** (UNVALIDATED):
```python
TRIM_INTERVAL = 50  # ❓ Guess
KEEP_MESSAGES = 40  # ❓ Guess
```

**After testing** (DATA-DRIVEN):
```python
TRIM_INTERVAL = 75  # ✅ Optimal based on VRAM growth
KEEP_MESSAGES = 50  # ✅ Optimal based on context quality
```

---

### 4. **Performance at Scale**

**Questions**:
- Does optimization work for 1,000+ requests?
- Does context trimming work correctly?
- Is performance consistent?
- Do token savings match predictions?

**Why it matters**:
- 170k requests is HUGE
- Need to validate system works at scale
- Need to validate no memory leaks
- Need to validate no performance degradation

**Current status**: ✅ Tested with 20 requests  
**Need to test**: 100, 1,000, 10,000 requests

---

## 📊 Success Criteria

### Context Limit Tests

✅ **PASS** if:
- Find maximum context length without OOM
- Measure VRAM growth rate
- Generate safe limit recommendations
- Recommendations are < 80% of maximum

❌ **FAIL** if:
- Cannot find safe limits
- VRAM growth is unpredictable
- OOM occurs below expected limits

### Performance Benchmarks

✅ **PASS** if:
- All test sizes complete successfully
- Performance is consistent across scales
- Token savings match predictions (>90%)
- VRAM stays within safe limits
- No errors or crashes

❌ **FAIL** if:
- Any test size fails
- Performance degrades at scale
- Token savings don't match predictions
- VRAM overflows
- Errors or crashes occur

---

## 🚀 Execution Plan

### Phase 1: Context Limits (30-60 minutes)

```bash
# Make sure Ollama is running
ollama serve

# Run context limit tests
chmod +x test_context_limits.py
python test_context_limits.py

# Review results
cat context_limit_results.json

# Update config with recommended limits
# Edit src/batch_processor.py with new values
```

**Expected time**: 30-60 minutes  
**Risk**: May cause OOM (that's the point!)  
**Mitigation**: Save progress frequently

---

### Phase 2: Performance Benchmarks (1-2 hours)

```bash
# Make sure server is running
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080

# Run performance benchmarks
chmod +x test_performance_benchmarks.py
python test_performance_benchmarks.py

# Review results
cat performance_benchmarks.json

# Validate extrapolation to 170k requests
```

**Expected time**: 1-2 hours  
**Risk**: Long-running tests  
**Mitigation**: Can stop after 1,000 requests if needed

---

### Phase 3: Update Configuration (15 minutes)

Based on test results, update:

**`src/batch_processor.py`**:
```python
# OLD (guessed values)
MAX_CONTEXT_TOKENS = 32000
CONTEXT_TRIM_THRESHOLD = 28000
TRIM_INTERVAL = 50

# NEW (data-driven values)
MAX_CONTEXT_TOKENS = 35000  # From context limit tests
CONTEXT_TRIM_THRESHOLD = 30000  # 85% of max
TRIM_INTERVAL = 75  # From performance benchmarks
```

**`BATCH_OPTIMIZATION_REQUIREMENTS.md`**:
- Update with actual measured values
- Update recommendations
- Update projections for 170k requests

---

## 📈 Expected Results

### Context Limit Tests

```
Maximum safe context: 35,000 tokens
VRAM at max context: 14.8 GB
VRAM per token: 0.42 MB/token
Recommended MAX_CONTEXT_TOKENS: 35,000
Recommended TRIM_THRESHOLD: 30,000
```

### Performance Benchmarks

```
100 requests: 15s (6.67 req/s)
1,000 requests: 150s (6.67 req/s)
10,000 requests: 1,500s (6.67 req/s)

Extrapolation to 170k:
  Time: 25,500s (7.1 hours)
  Throughput: 6.67 req/s
  Token savings: 97.6%
```

---

## 🎓 Why This Matters

### Without These Tests

❌ **Guessing** context limits  
❌ **Hoping** VRAM doesn't overflow  
❌ **Assuming** optimization works at scale  
❌ **Risking** OOM crash after hours of processing  
❌ **Wasting** time with suboptimal settings  

### With These Tests

✅ **Know** exact context limits  
✅ **Measure** VRAM usage  
✅ **Validate** optimization at scale  
✅ **Prevent** OOM crashes  
✅ **Optimize** for maximum performance  

---

## 🚨 Critical Risks

### Risk 1: OOM During Testing
**Probability**: HIGH (that's what we're testing!)  
**Impact**: LOW (expected, just restart)  
**Mitigation**: Save progress, test incrementally

### Risk 2: Tests Take Too Long
**Probability**: MEDIUM (10k requests = 25 minutes)  
**Impact**: LOW (just time)  
**Mitigation**: Can stop after 1k requests

### Risk 3: Results Don't Match Predictions
**Probability**: MEDIUM (we're guessing now)  
**Impact**: HIGH (need to adjust strategy)  
**Mitigation**: Analyze results, update approach

---

## ✅ Next Steps

1. **Run context limit tests** → Get actual limits
2. **Run performance benchmarks** → Validate at scale
3. **Update configuration** → Use data-driven values
4. **Document results** → Update requirements doc
5. **Ready for production** → Process 170k requests!

**Status**: Ready to test  
**Priority**: CRITICAL before processing 170k requests  
**Time required**: 2-3 hours total

