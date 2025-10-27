# Gemma 3 12B - Official Specifications

**Source**: HuggingFace Model Card  
**URL**: https://huggingface.co/google/gemma-3-12b-it  
**Date Retrieved**: 2025-10-27

---

## ✅ Confirmed Specifications

### Context Window
```
Input context: 128,000 tokens (128K)
Output context: 8,192 tokens (8K)
```

**This is CRITICAL for our batch processing!**

### Model Size
```
Parameters: 12 billion (12B)
Training data: 12 trillion tokens
Quantization: Available in Q4_K_M via Ollama
```

### Multimodal Capabilities
```
Input: Text + Images (896x896, encoded to 256 tokens each)
Output: Text only
```

### Language Support
```
Languages: 140+ languages
Primary: English
```

---

## 🎯 Impact on Our System

### What We Thought
```python
MAX_CONTEXT_TOKENS = 32000  # Conservative guess
CONTEXT_TRIM_THRESHOLD = 28000
TRIM_INTERVAL = 50  # Trim every 50 requests
```

**We were being VERY conservative!**

### What's Actually Possible
```python
# Context window limit
MAX_CONTEXT_WINDOW = 128000  # ✅ Confirmed from model card

# But VRAM is the real limit!
# RTX 4080 has 16GB VRAM
# Model takes ~8GB
# KV cache grows with context
# VRAM will hit limit WAY before 128K context!
```

---

## 🚨 Critical Insight: VRAM is the Bottleneck

### Context Window vs VRAM

**Context window**: 128K tokens (plenty of room!)  
**VRAM**: 16GB (this is the hard limit!)

### The Math

If KV cache uses ~0.5MB per token:
```
Context Length    KV Cache Size    Total VRAM (Model + KV)
--------------    -------------    ------------------------
1,000 tokens      0.5 GB           8.5 GB   ✅ Safe
5,000 tokens      2.5 GB           10.5 GB  ✅ Safe
10,000 tokens     5.0 GB           13.0 GB  ✅ Safe
15,000 tokens     7.5 GB           15.5 GB  ⚠️ Close to limit
20,000 tokens     10.0 GB          18.0 GB  ❌ Exceeds 16GB!
32,000 tokens     16.0 GB          24.0 GB  ❌ Way over!
128,000 tokens    64.0 GB          72.0 GB  ❌ Impossible!
```

**Estimated max safe context: ~14,000 tokens**

**BUT**: This assumes 0.5MB/token, which is a GUESS!

---

## 🧪 What We MUST Test

### Test 1: Actual VRAM Usage

**Question**: How much VRAM does the model actually use?

**Current assumption**: 8GB  
**Need to measure**: Actual VRAM with model loaded

**How to test**:
```bash
# Load model
ollama run gemma3:12b

# Check VRAM
nvidia-smi --query-gpu=memory.used --format=csv
```

### Test 2: KV Cache Growth Rate

**Question**: How much VRAM does KV cache use per token?

**Current assumption**: 0.5MB/token  
**Need to measure**: Actual VRAM growth with increasing context

**How to test**:
```python
# Test with different context lengths
for context_length in [1000, 5000, 10000, 15000]:
    # Build conversation with N tokens
    # Measure VRAM before and after
    # Calculate VRAM per token
```

### Test 3: Maximum Safe Context

**Question**: What's the maximum context before OOM?

**Current assumption**: ~14K tokens  
**Need to measure**: Actual OOM point

**How to test**:
```python
# Binary search for OOM point
# Start at 10K, increase until OOM
# Find exact limit
```

---

## 📊 Updated Strategy

### Phase 1: Measure Actual Limits (CRITICAL)

1. **Measure base model VRAM** (with no context)
2. **Measure KV cache growth rate** (VRAM per token)
3. **Find maximum safe context** (before OOM)
4. **Calculate optimal trim threshold** (80% of max)

### Phase 2: Update Configuration (Based on Data)

**Current (guessed)**:
```python
MAX_CONTEXT_TOKENS = 32000
CONTEXT_TRIM_THRESHOLD = 28000
TRIM_INTERVAL = 50
```

**After testing (data-driven)**:
```python
MAX_CONTEXT_TOKENS = <measured_max>
CONTEXT_TRIM_THRESHOLD = int(<measured_max> * 0.8)
TRIM_INTERVAL = <calculated_from_vram_growth>
```

### Phase 3: Optimize for 170K Requests

With actual limits, we can:
- Calculate exact trim frequency needed
- Optimize context window usage
- Maximize performance while staying safe

---

## 🎓 Key Learnings

### 1. Context Window ≠ Usable Context

**Context window**: 128K tokens (what the model supports)  
**Usable context**: ~14K tokens (what VRAM allows)

**The model CAN handle 128K tokens, but our GPU CANNOT!**

### 2. VRAM is the Hard Limit

For consumer GPUs (RTX 4080 16GB):
- Model size is fixed (~8GB)
- KV cache grows with context
- VRAM fills up LONG before context window limit

**We're VRAM-constrained, not context-constrained!**

### 3. Testing is Non-Negotiable

We CANNOT guess these values:
- Model VRAM usage
- KV cache growth rate
- Maximum safe context

**One wrong guess = OOM crash = lose all 170K request progress!**

---

## 🚀 Next Steps

### Immediate (Before Processing 170K Requests)

1. ✅ **Run `test_context_limits.py`**
   - Find actual VRAM limits
   - Measure KV cache growth
   - Get data-driven safe limits

2. ✅ **Run `test_performance_benchmarks.py`**
   - Validate at 100, 1K, 10K requests
   - Confirm optimization works at scale
   - Extrapolate to 170K

3. ✅ **Update configuration**
   - Replace guessed values with measured values
   - Set safe limits based on data
   - Document assumptions and measurements

### Future Optimizations

With 128K context window, we could:
- **Batch larger groups** (if VRAM allows)
- **Trim less frequently** (if VRAM allows)
- **Keep more context** (if VRAM allows)

**But first, we need to know the VRAM limits!**

---

## 📋 Summary

### What We Know (Confirmed)
✅ Context window: 128K tokens  
✅ Output limit: 8K tokens  
✅ Model size: 12B parameters  
✅ Languages: 140+  

### What We Don't Know (Need to Test)
❓ Actual model VRAM usage  
❓ KV cache growth rate  
❓ Maximum safe context before OOM  
❓ Optimal trim threshold  
❓ Optimal trim frequency  

### What We Must Do
🧪 Run context limit tests  
🧪 Run performance benchmarks  
📝 Update configuration with measured values  
✅ Validate before processing 170K requests  

---

## 🎯 Bottom Line

**Good news**: Gemma 3 12B has a HUGE 128K context window!

**Reality check**: RTX 4080's 16GB VRAM is the real limit.

**Action required**: Test to find actual VRAM-constrained limits.

**Priority**: CRITICAL before processing 170K requests!

---

**Status**: Specifications confirmed, testing plan ready  
**Next**: Run `test_context_limits.py` to get actual limits  
**ETA**: 30-60 minutes for context tests, 1-2 hours for performance tests

