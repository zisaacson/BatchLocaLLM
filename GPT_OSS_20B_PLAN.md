# GPT-OSS 20B on RTX 4080 16GB - Plan

**Branch:** `gpt-oss-20b`  
**Goal:** Test if we can run OpenAI's GPT-OSS 20B model on RTX 4080 16GB using quantization

---

## Model Options

### Available Quantizations (from unsloth/gpt-oss-20b-GGUF)

| Quantization | Size | Will it fit? |
|--------------|------|--------------|
| **Q2_K** | 11.5 GB | ✅ Yes (4.5 GB headroom) |
| **Q3_K_M** | 11.5 GB | ✅ Yes (4.5 GB headroom) |
| **Q4_K_M** | 11.6 GB | ✅ Yes (4.4 GB headroom) |
| **Q4_K_XL** | 11.9 GB | ✅ Yes (4.1 GB headroom) |
| **Q5_K_M** | 11.7 GB | ✅ Yes (4.3 GB headroom) |
| **Q6_K** | 12.0 GB | ✅ Yes (4.0 GB headroom) |
| **Q8_0** | 12.1 GB | ✅ Yes (3.9 GB headroom) |
| **F16** | 13.8 GB | ⚠️ Tight (2.2 GB headroom) |

**Recommended:** Q4_K_M (11.6 GB) - Best balance of quality and size

---

## Approach

### Option 1: vLLM Native with GGUF ✅ **RECOMMENDED**

vLLM supports GGUF models directly!

```bash
# Install vLLM (already have it)
source venv/bin/activate

# Run with vLLM
vllm serve unsloth/gpt-oss-20b-GGUF \
    --quantization gguf \
    --gpu-memory-utilization 0.90 \
    --max-model-len 4096
```

**Pros:**
- ✅ Uses same vLLM infrastructure we already validated
- ✅ Native batching (no wrapper code)
- ✅ Proven to work with Gemma 3 4B

**Cons:**
- ⚠️ Need to verify vLLM supports GGUF quantization
- ⚠️ May need specific vLLM version

### Option 2: llama.cpp (Fallback)

If vLLM doesn't support GGUF well:

```bash
# Install llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1

# Run server
./llama-server \
    -hf unsloth/gpt-oss-20b-GGUF:gpt-oss-20b-Q4_K_M.gguf \
    -ngl 999 \
    --ctx-size 4096
```

**Pros:**
- ✅ GGUF is native format for llama.cpp
- ✅ Proven to work with quantized models

**Cons:**
- ❌ Different infrastructure than vLLM
- ❌ May not have same batching performance

---

## Testing Plan

### Phase 1: Load Test (5 minutes)

**Goal:** Verify model loads and fits in memory

```bash
# Test with vLLM
python test_gpt_oss_load.py
```

**Success criteria:**
- ✅ Model loads without OOM
- ✅ Memory usage < 15 GB
- ✅ Can generate 1 response

### Phase 2: Small Batch Test (10 minutes)

**Goal:** Test with 10 requests

```bash
# Use same benchmark script, different model
python benchmark_vllm_native.py \
    --model unsloth/gpt-oss-20b-GGUF \
    --quantization gguf \
    batch_10.jsonl \
    gpt_oss_10_results.jsonl
```

**Success criteria:**
- ✅ 10/10 requests succeed
- ✅ Memory stable
- ✅ Throughput > 500 tok/s (lower than 4B is expected)

### Phase 3: 100 Request Test (30 minutes)

**Goal:** Validate at scale

```bash
python benchmark_vllm_native.py \
    --model unsloth/gpt-oss-20b-GGUF \
    --quantization gguf \
    batch_100.jsonl \
    gpt_oss_100_results.jsonl
```

**Success criteria:**
- ✅ 100/100 requests succeed
- ✅ No OOM errors
- ✅ Consistent throughput

---

## Expected Performance

### Gemma 3 4B (baseline)
- Model size: 8.6 GB (bfloat16)
- Throughput: 2,511 tok/s
- Memory: ~11 GB total

### GPT-OSS 20B Q4_K_M (projected)
- Model size: 11.6 GB (4-bit quantized)
- Throughput: **~800-1,200 tok/s** (estimated 30-50% of 4B)
- Memory: **~13-14 GB total** (model + KV cache + overhead)

**Reasoning:**
- 5x more parameters (4B → 20B)
- 4-bit quantization reduces memory but not compute
- Expect 2-3x slower throughput

---

## Quality Comparison

**Why test GPT-OSS 20B?**

1. **Better reasoning** - 20B model should give higher quality evaluations
2. **OpenAI pedigree** - Built by the team we're recruiting for
3. **Aspirational goal** - From memories: "OpenAI GPT-OSS 20B as an aspirational stretch goal"

**Trade-off:**
- Gemma 3 4B: Fast (2,511 tok/s), fits easily
- GPT-OSS 20B: Slower (~1,000 tok/s), tighter fit, better quality

---

## Risk Assessment

### High Risk: OOM
**Probability:** Medium  
**Mitigation:**
- Start with Q4_K_M (11.6 GB)
- If OOM, try Q2_K (11.5 GB)
- Monitor with GPU monitoring tool

### Medium Risk: Slow Throughput
**Probability:** High  
**Impact:** 5K batch might take 2-3 hours instead of 36 minutes

**Mitigation:**
- Accept slower speed for better quality
- Or stick with Gemma 3 4B for production

### Low Risk: vLLM GGUF Support
**Probability:** Low  
**Mitigation:**
- Fallback to llama.cpp if needed
- Check vLLM docs first

---

## Decision Tree

```
Can we load GPT-OSS 20B Q4_K_M?
├─ YES → Does it fit in memory?
│   ├─ YES → Is throughput acceptable (>500 tok/s)?
│   │   ├─ YES → Is quality better than Gemma 3 4B?
│   │   │   ├─ YES → ✅ USE GPT-OSS 20B
│   │   │   └─ NO → ❌ STICK WITH GEMMA 3 4B
│   │   └─ NO → ❌ TOO SLOW, STICK WITH GEMMA 3 4B
│   └─ NO → Try Q2_K (smaller)
└─ NO → ❌ STICK WITH GEMMA 3 4B
```

---

## Next Steps

1. **Create load test script** - `test_gpt_oss_load.py`
2. **Test model loading** - Verify it fits
3. **Run 10 request test** - Validate functionality
4. **Measure throughput** - Compare to Gemma 3 4B
5. **Evaluate quality** - Compare outputs
6. **Make decision** - GPT-OSS 20B vs Gemma 3 4B

---

## Files to Create

- `test_gpt_oss_load.py` - Simple load test
- `benchmark_gpt_oss.py` - Modified benchmark script for GPT-OSS
- `GPT_OSS_RESULTS.md` - Results documentation

---

**Status:** Ready to test. Need to verify vLLM GGUF support first.

