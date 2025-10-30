# 🧠 Intelligent Memory Management Guide

**How to avoid OOM errors and optimize vLLM performance on RTX 4080 16GB**

---

## 🎯 The Problem

Different models have different memory requirements, and vLLM's V1 engine can be sensitive to memory configuration. Running out of memory (OOM) during initialization wastes time and GPU resources.

**Common OOM scenarios:**
- ❌ Model too large for GPU
- ❌ `gpu_memory_utilization` set too high
- ❌ Context window (`max_model_len`) too large
- ❌ CUDA graphs consuming too much memory

---

## ✅ The Solution: Memory Optimizer

We built an **intelligent memory optimizer** that:
1. Checks current GPU memory usage
2. Estimates model memory requirements
3. Learns from previous benchmark failures
4. Recommends optimal vLLM configuration

---

## 🚀 Quick Start

### **Check recommended settings for a model:**

```bash
python memory_optimizer.py "Qwen/Qwen3-4B-Instruct-2507"
```

**Output:**
```
================================================================================
🧠 MEMORY OPTIMIZER
================================================================================

🎮 GPU: NVIDIA GeForce RTX 4080
   Total: 16.0 GB
   Used:  0.5 GB
   Free:  15.5 GB

🤖 Model: Qwen/Qwen3-4B-Instruct-2507
   Context: 4096 tokens

📊 Analysis:
⚠️  Tight fit: 14.7 GB / 16.0 GB
Reducing gpu_memory_utilization to 0.80
⚠️  Known issue: OOM with gpu_memory_utilization=0.90, needs 0.85 or lower
Using gpu_memory_utilization=0.8 based on previous failures

✅ Recommended Configuration:
   gpu_memory_utilization = 0.8
   max_model_len = 4096
   enforce_eager = True

💻 Code:
```python
from vllm import LLM

llm = LLM(
    model="Qwen/Qwen3-4B-Instruct-2507",
    max_model_len=4096,
    gpu_memory_utilization=0.8,
    enforce_eager=True,
    disable_log_stats=True,
)
```
```

---

## 📊 Memory Profiles

### **Known Working Configurations:**

| Model | Size | Memory | gpu_util | max_len | Notes |
|-------|------|--------|----------|---------|-------|
| **Llama 3.2 1B** | 2.5 GB | 5.0 GB | 0.90 | 4096 | ✅ Fastest, plenty of room |
| **Gemma 3 4B** | 8.6 GB | 11.0 GB | 0.90 | 4096 | ✅ Production ready |
| **Qwen 3 4B** | 7.6 GB | 14.7 GB | 0.80 | 4096 | ⚠️  Tight fit, needs enforce_eager |
| **Llama 3.2 3B** | 6.0 GB | 9.0 GB | 0.90 | 4096 | 🟡 Not tested yet |

### **Models That Won't Fit:**

| Model | Size | Memory | Status |
|-------|------|--------|--------|
| **Gemma 3 12B** | 24 GB | 27 GB | ❌ OOM - needs 24GB+ GPU |
| **Qwen 2.5 14B** | 28 GB | 31 GB | ❌ OOM - needs 32GB+ GPU |
| **GPT-OSS 20B** | 40 GB | 43 GB | ❌ Incompatible with vLLM |

---

## 🔧 vLLM Memory Parameters

### **1. gpu_memory_utilization** (Most Important!)

**What it does:** Controls how much GPU memory vLLM can use.

**Values:**
- `0.90` (90%) - Default, works for most models
- `0.85` (85%) - Use for tight fits
- `0.80` (80%) - Use for very tight fits or OOM issues
- `0.75` (75%) - Last resort before giving up

**When to lower:**
- Model uses >90% of GPU memory
- Getting OOM during initialization
- CUDA graph capture fails

**Example:**
```python
llm = LLM(
    model="Qwen/Qwen3-4B-Instruct-2507",
    gpu_memory_utilization=0.80,  # Lower for tight fit
)
```

---

### **2. max_model_len** (Context Window)

**What it does:** Maximum sequence length (prompt + completion).

**Values:**
- `4096` - Standard, works for most use cases
- `2048` - Reduce to save memory
- `8192` - Only if you have memory to spare

**Memory impact:** Larger context = more KV cache memory

**When to reduce:**
- OOM errors
- Don't need long context
- Want to fit larger model

**Example:**
```python
llm = LLM(
    model="google/gemma-3-4b-it",
    max_model_len=2048,  # Reduce from 4096 to save memory
)
```

---

### **3. enforce_eager** (Disable CUDA Graphs)

**What it does:** Disables CUDA graph optimization to save memory.

**Tradeoff:**
- ✅ Saves ~0.5-1 GB memory
- ❌ Slightly slower inference (~10-20%)

**When to use:**
- OOM during CUDA graph capture
- Very tight memory fit
- Model barely fits

**Example:**
```python
llm = LLM(
    model="Qwen/Qwen3-4B-Instruct-2507",
    enforce_eager=True,  # Disable CUDA graphs
)
```

---

### **4. max_num_seqs** (Concurrent Sequences)

**What it does:** Limits number of concurrent sequences.

**Default:** Auto-calculated based on available memory

**When to set:**
- Want to limit concurrency
- OOM during inference (not initialization)

**Example:**
```python
llm = LLM(
    model="google/gemma-3-4b-it",
    max_num_seqs=128,  # Limit to 128 concurrent sequences
)
```

---

### **5. kv_cache_dtype** (KV Cache Quantization)

**What it does:** Quantizes KV cache to save memory.

**Values:**
- `None` (default) - No quantization
- `"fp8"` - 8-bit quantization, saves ~50% KV cache memory

**Tradeoff:**
- ✅ Can double effective context length
- ❌ Slight quality degradation

**When to use:**
- Need longer context
- OOM with large batches
- Last resort optimization

**Example:**
```python
llm = LLM(
    model="google/gemma-3-4b-it",
    kv_cache_dtype="fp8",  # Quantize KV cache
)
```

---

## 🎯 Decision Tree

```
Is model > 90% of GPU memory?
├─ YES → Will NOT fit
│   └─ Try quantization or smaller model
└─ NO → Continue

Is model > 80% of GPU memory?
├─ YES → Tight fit
│   ├─ Set gpu_memory_utilization=0.80
│   ├─ Set enforce_eager=True
│   └─ Consider reducing max_model_len
└─ NO → Continue

Is model > 70% of GPU memory?
├─ YES → Moderate fit
│   └─ Set gpu_memory_utilization=0.85
└─ NO → Plenty of room
    └─ Use gpu_memory_utilization=0.90 (default)
```

---

## 📝 Best Practices

### **1. Always check GPU before loading:**
```bash
nvidia-smi
```

### **2. Kill zombie processes:**
```bash
ps aux | grep -E "python.*vllm" | grep -v grep
pkill -f "python.*vllm"
```

### **3. Use memory optimizer:**
```bash
python memory_optimizer.py "model-name"
```

### **4. Start conservative, then optimize:**
```python
# First attempt - conservative
llm = LLM(
    model="new-model",
    gpu_memory_utilization=0.80,  # Start low
    max_model_len=2048,            # Start small
    enforce_eager=True,            # Disable graphs
)

# If it works, gradually increase:
# - gpu_memory_utilization → 0.85 → 0.90
# - max_model_len → 4096 → 8192
# - enforce_eager → False
```

### **5. Save successful configurations:**

The memory optimizer automatically learns from benchmarks. When a test succeeds, it saves the configuration for future reference.

---

## 🔍 Troubleshooting

### **OOM during initialization:**
```
RuntimeError: CUDA out of memory occurred when warming up sampler
```

**Solutions:**
1. Lower `gpu_memory_utilization` (0.90 → 0.85 → 0.80)
2. Enable `enforce_eager=True`
3. Reduce `max_model_len` (4096 → 2048)
4. Set `max_num_seqs=128`

### **OOM during inference:**
```
torch.OutOfMemoryError: CUDA out of memory
```

**Solutions:**
1. Reduce batch size
2. Set `max_num_seqs` lower
3. Use `kv_cache_dtype="fp8"`
4. Reduce `max_model_len`

### **Model loads but crashes:**
```
CUDA error: out of memory
```

**Solutions:**
1. Check for zombie processes
2. Restart Python kernel
3. Clear CUDA cache: `torch.cuda.empty_cache()`

---

## 💡 Pro Tips

1. **Test with small batch first** - Don't jump straight to 5K
2. **Monitor GPU during load** - Use `nvidia-smi` in another terminal
3. **Save working configs** - Document what works for each model
4. **Use memory optimizer** - It learns from failures
5. **Start conservative** - Easier to increase than decrease

---

## 📊 Example Workflow

```bash
# 1. Check GPU
nvidia-smi

# 2. Get recommendation
python memory_optimizer.py "meta-llama/Llama-3.2-3B-Instruct"

# 3. Test with small batch (10 requests)
python test_model.py --model "meta-llama/Llama-3.2-3B-Instruct" --batch-size 10

# 4. If successful, scale up to 5K
python test_model.py --model "meta-llama/Llama-3.2-3B-Instruct" --batch-size 5000

# 5. Memory optimizer learns from success!
```

---

## 🎯 Summary

**Key Takeaways:**
1. ✅ Use `memory_optimizer.py` before testing new models
2. ✅ Start with conservative settings
3. ✅ Lower `gpu_memory_utilization` for tight fits
4. ✅ Use `enforce_eager=True` to save memory
5. ✅ Monitor GPU usage during tests
6. ✅ Learn from failures and successes

**The memory optimizer makes this automatic!** 🎉

