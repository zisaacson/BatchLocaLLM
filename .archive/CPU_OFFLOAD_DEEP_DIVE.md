# vLLM CPU Offload Deep Dive

## 🎯 Problem Statement

**Initial Issue:** OLMo 2 7B (13.6 GB model) failed to load on RTX 4080 16GB with vLLM V1 engine.

**Error:**
```
Model loading took 13.5958 GiB
Available KV cache memory: -3.44 GiB  ❌ NEGATIVE!
ValueError: No available memory for the cache blocks
```

**Root Cause:** vLLM V1 engine has significant overhead. Even though the model is 13.6 GB and GPU has 16 GB VRAM, the engine needs additional memory for:
- KV cache (stores attention keys/values for context)
- CUDA graphs (optimized execution paths)
- Temporary buffers
- PyTorch overhead

## 💡 Solution: CPU Offload

vLLM supports `cpu_offload_gb` parameter to offload model weights to CPU RAM.

### How It Works

```python
llm = LLM(
    model="allenai/OLMo-2-1124-7B-Instruct",
    gpu_memory_utilization=0.85,
    cpu_offload_gb=8,  # Offload 8GB to CPU RAM
    swap_space=4,      # 4GB swap for KV cache overflow
    max_num_seqs=16    # Fewer concurrent sequences
)
```

**What gets offloaded:**
- Model layers are split between GPU and CPU
- GPU keeps the most frequently accessed layers
- CPU stores less critical layers
- Data transfers happen during inference (slower but works!)

### Results

| Metric | Without Offload | With 8GB Offload | Impact |
|--------|----------------|------------------|--------|
| **Model on GPU** | 13.6 GB | 5.6 GB | **-59%** ✅ |
| **KV Cache Available** | -3.44 GB ❌ | 6.9 GB ✅ | **WORKS!** |
| **Load Time** | Failed | 80s | Slower but acceptable |
| **Inference Speed** | N/A | 14-23 tok/s | Slower than pure GPU |

## 🔧 Implementation

### 1. Database Schema

Added `cpu_offload_gb` column to `model_registry` table:

```sql
ALTER TABLE model_registry 
ADD COLUMN cpu_offload_gb FLOAT DEFAULT 0.0;
```

### 2. Model Manager

Updated `model_manager.py` to support CPU offload:

```python
class AddModelRequest(BaseModel):
    cpu_offload_gb: float = Field(default=0, description="GB to offload to CPU")

def _create_test_script(model: ModelRegistry, num_requests: int) -> str:
    # Auto-configure based on model size
    if model.estimated_memory_gb >= 14:
        max_num_seqs = 16  # 7B+ models need fewer concurrent sequences
    
    # Add CPU offload if configured
    if model.cpu_offload_gb > 0:
        vllm_kwargs += """
    cpu_offload_gb=CPU_OFFLOAD_GB,
    swap_space=4"""
```

### 3. Web UI

Added CPU offload field to model management UI:

```html
<div class="form-group">
    <label for="cpu-offload-gb">CPU Offload (GB)</label>
    <input type="number" id="cpu-offload-gb" step="0.5" value="0" min="0" max="32">
    <small>Use 8GB for 7B models on 16GB VRAM</small>
</div>
```

Model cards now display CPU offload when configured:

```javascript
${model.cpu_offload_gb > 0 ? `
<div class="stat">
    <div class="stat-label">CPU Offload</div>
    <div class="stat-value">${model.cpu_offload_gb} GB</div>
</div>
` : ''}
```

## 📊 Performance Testing

### Current Status

**OLMo 2 7B Test (100 requests):**
- ✅ Model loaded successfully with 8GB CPU offload
- ✅ Using 5.6 GB GPU memory (vs 13.6 GB without offload)
- ✅ 6.9 GB KV cache available
- 🔄 Currently running (33% complete)
- ⚠️ Slower throughput: 14-23 tok/s (vs ~50+ tok/s for pure GPU 4B models)

### Planned A/B Test

Created `scripts/ab_test_cpu_offload.py` to measure performance impact:

**Test Plan:**
1. **Test A:** Gemma 3 4B with NO CPU offload (baseline)
2. **Test B:** Gemma 3 4B with 4GB CPU offload

**Metrics to Compare:**
- Load time
- Throughput (tokens/sec)
- Latency (ms per request)
- Total inference time

**Goal:** Quantify the performance cost of CPU offload to determine:
- Is it worth using for models that fit in VRAM?
- What's the acceptable threshold for 7B+ models?

## 🎓 Key Learnings

### 1. vLLM V1 Engine Memory Requirements

**For 7B models on 16GB VRAM:**
- Model weights: ~13-14 GB
- KV cache: ~3-4 GB minimum
- Engine overhead: ~2-3 GB
- **Total needed:** ~18-21 GB ❌ Doesn't fit!

**Solution:** CPU offload 6-8 GB to free up VRAM for KV cache

### 2. When to Use CPU Offload

| Model Size | VRAM | CPU Offload Needed? | Recommended Setting |
|-----------|------|---------------------|---------------------|
| 1-3B | 16GB | ❌ No | `cpu_offload_gb=0` |
| 4B | 16GB | ❌ No | `cpu_offload_gb=0` |
| 7B | 16GB | ✅ Yes | `cpu_offload_gb=8` |
| 12B+ | 16GB | ✅ Yes | `cpu_offload_gb=12+` |

### 3. Performance Tradeoffs

**Pros:**
- ✅ Enables running larger models on consumer GPUs
- ✅ Better than not running at all
- ✅ Still faster than pure CPU inference

**Cons:**
- ⚠️ Slower throughput (CPU-GPU data transfer overhead)
- ⚠️ Longer load times
- ⚠️ Requires sufficient system RAM (30GB+ recommended)

### 4. System Requirements

**For CPU Offload to Work:**
- ✅ Sufficient system RAM (model size + offload amount)
- ✅ Fast CPU-GPU interconnect (PCIe 4.0+ recommended)
- ✅ vLLM V1 engine (V0 doesn't support it)

**Your System:**
- RAM: 30 GB ✅ (enough for 8GB offload)
- GPU: RTX 4080 16GB ✅
- vLLM: 0.11.0 ✅

## 🚀 Next Steps

### Immediate
1. ✅ Wait for OLMo 2 7B test to complete
2. ⏳ Run A/B test to quantify CPU offload performance impact
3. ⏳ Update model registry with optimal CPU offload settings

### Future Enhancements
1. **Auto-detection:** Calculate optimal `cpu_offload_gb` based on model size and available VRAM
2. **Dynamic adjustment:** Allow changing CPU offload without re-adding model
3. **Performance profiles:** Store A/B test results in database for comparison
4. **UI improvements:** Show real-time GPU/CPU memory usage during tests

## 📝 Recommendations

### For 4B Models (Gemma 3, Qwen 3, Llama 3.2)
- **Don't use CPU offload** - they fit comfortably in 16GB VRAM
- Use `gpu_memory_utilization=0.90` for maximum performance
- Expected throughput: 50-80 tok/s

### For 7B Models (OLMo 2, Llama 3.1)
- **Use 8GB CPU offload** - required to fit in 16GB VRAM
- Use `gpu_memory_utilization=0.85` to leave headroom
- Use `max_num_seqs=16` (fewer concurrent sequences)
- Expected throughput: 15-25 tok/s (slower but functional)

### For 12B+ Models
- **Use 12GB+ CPU offload** or consider cloud GPUs with 24GB+ VRAM
- Performance will be significantly degraded
- Consider using llama.cpp instead for better CPU offload efficiency

## 🔗 References

- [vLLM Engine Args Documentation](https://docs.vllm.ai/en/latest/models/engine_args.html)
- [Reddit: How does cpu_offload_gb work?](https://www.reddit.com/r/LocalLLaMA/comments/1o1iaw2/vllm_how_does_cpu_offload_gb_work/)
- [vLLM GitHub Issue #13517](https://github.com/vllm-project/vllm/issues/13517)

## 📊 Test Results

### OLMo 2 7B with CPU Offload (In Progress)
```
Model: allenai/OLMo-2-1124-7B-Instruct
Config:
  - cpu_offload_gb: 8.0
  - gpu_memory_utilization: 0.85
  - max_num_seqs: 16
  - max_model_len: 4096

Results:
  - Model on GPU: 5.59 GiB
  - KV cache available: 6.90 GiB
  - Load time: 79.9s
  - Status: Running (33/100 requests complete)
  - Throughput: 14-23 tok/s
```

### Gemma 3 4B A/B Test (Pending)
```
Test A (No Offload): TBD
Test B (4GB Offload): TBD
Performance Impact: TBD
```

