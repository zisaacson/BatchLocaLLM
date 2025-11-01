# 🚀 Add Model Guide

## The Problem We Solved

**Before:** You had to:
1. Manually calculate memory requirements
2. Figure out if CPU offload is needed
3. Find the right GGUF file to download
4. Run huggingface-cli commands
5. Update the model registry
6. Run benchmarks manually
7. Compare results to existing models

**Now:** You just:
1. Paste a HuggingFace URL
2. Click "Analyze"
3. Click "Download & Benchmark"
4. Done!

---

## How to Use

### Step 1: Open the Add Model Page

Navigate to: **http://localhost:4080/add-model.html**

### Step 2: Paste HuggingFace Content

You can paste either:
- **Just the URL**: `https://huggingface.co/bartowski/OLMo-2-1124-7B-Instruct-GGUF`
- **The entire model page** (copy/paste everything from the HuggingFace page)

### Step 3: Click "Analyze Model"

The system will automatically:
- ✅ Parse the model information
- ✅ Calculate memory requirements (model + KV cache + overhead)
- ✅ Determine if it fits on RTX 4080 16GB
- ✅ Calculate CPU offload needed (if any)
- ✅ Estimate throughput (with offload penalty)
- ✅ Assign quality tier (1-5 stars based on size)
- ✅ Compare to existing models in your registry

### Step 4: Review the Analysis

You'll see:

```
✅ Will fit on RTX 4080 16GB (no CPU offload)

Model Size:    4.2 GB
Total Memory:  11.5 GB
CPU Offload:   None
Est. Speed:    ~700 tok/s
Quality:       ⭐⭐⭐⭐

Comparison to Existing Models:
┌─────────────────┬──────────┬─────────────────┐
│ Model           │ Speed    │ Comparison      │
├─────────────────┼──────────┼─────────────────┤
│ Gemma 3 4B      │ 2,511    │ 🔴 3.6x slower  │
│ Qwen 3 4B       │ 1,533    │ 🔴 2.2x slower  │
│ OLMo 2 7B Q4    │ 700      │ 🟢 NEW          │
└─────────────────┴──────────┴─────────────────┘
```

### Step 5: Click "Download & Benchmark"

The system will:
1. **Download** the GGUF file (with progress bar)
2. **Add to registry** with all metadata
3. **Run benchmark** on 100 samples
4. **Update comparison table** with real results
5. **Redirect to workbench** when complete

---

## What Happens Behind the Scenes

### 1. Model Parser (`model_parser.py`)
- Extracts model ID from URL or content
- Finds GGUF files and quantization types
- Estimates model size from quantization

### 2. Memory Estimator (`model_parser.py`)
```python
Total Memory = Model Size + KV Cache + vLLM Overhead

KV Cache = params_b × 0.46 GB per 8K context per 100 batch
Overhead = 2 GB + (params_b / 10) × 0.5 GB
```

### 3. Smart Offload Calculator (`smart_offload.py`)
```python
Available GPU = 16 GB (RTX 4080)
Required = Total Memory

if Required <= Available:
    CPU Offload = 0 GB
    Penalty = 0%
else:
    CPU Offload = Required - Available + 2 GB buffer
    Penalty = min(95%, CPU Offload / 10)
```

### 4. Throughput Estimator
```python
Base throughput (heuristic):
- 4B models:  ~2,000 tok/s
- 7B models:  ~700 tok/s
- 12B models: ~300 tok/s
- 20B models: ~100 tok/s

With CPU offload:
Actual = Base × (1 - Penalty)
```

### 5. Model Installer (`model_installer.py`)
```bash
# Downloads using HuggingFace CLI
huggingface-cli download \
    bartowski/OLMo-2-7B-Q4_0 \
    --include "OLMo-2-7B-Q4_0.gguf" \
    --local-dir ./models/olmo2-7b-q4

# Adds to database
INSERT INTO model_registry (
    model_id, name, local_path, size_gb,
    quantization_type, cpu_offload_gb, ...
)

# Runs benchmark
python scripts/benchmark.py --model MODEL_ID --samples 100
```

---

## Example: Adding OLMo 2 7B Q4_0

### Input:
```
https://huggingface.co/bartowski/OLMo-2-1124-7B-Instruct-GGUF
```

### Analysis Output:
```json
{
  "success": true,
  "model_id": "bartowski/OLMo-2-1124-7B-Instruct-GGUF",
  "model_name": "OLMo 2 7B Q4_0 GGUF",
  "quantization": "Q4_0",
  "will_fit": true,
  "fits_without_offload": true,
  "memory": {
    "total_gb": 11.5,
    "model_gb": 4.23,
    "kv_cache_gb": 3.22,
    "overhead_gb": 2.05,
    "available_gb": 16.0,
    "cpu_offload_gb": 0.0
  },
  "performance": {
    "estimated_throughput": 700,
    "quality_stars": 4,
    "offload_penalty": 0
  },
  "comparison": {
    "total_models": 4,
    "comparisons": [
      {"model_name": "Gemma 3 4B", "throughput": 2511, "ratio": 0.28, "faster": false},
      {"model_name": "Qwen 3 4B", "throughput": 1533, "ratio": 0.46, "faster": false}
    ]
  }
}
```

### Installation:
1. Downloads `OLMo-2-1124-7B-Instruct-Q4_0.gguf` (4.23 GB)
2. Saves to `./models/bartowski_OLMo-2-1124-7B-Instruct-GGUF/`
3. Adds to registry with metadata
4. Runs 100-sample benchmark
5. Updates throughput with real results

---

## Key Features

### ✅ Automatic Everything
- No manual calculations
- No command-line knowledge needed
- No guessing about compatibility

### ✅ Smart Recommendations
- Shows if model will fit
- Explains CPU offload impact
- Compares to existing models

### ✅ Real-Time Progress
- WebSocket updates during download
- Progress bar shows percentage
- Benchmark progress tracking

### ✅ Quality vs Speed Tradeoffs
- Visual comparison table
- Star ratings for quality
- Speed comparisons (faster/slower)

---

## Troubleshooting

### "Analysis failed"
- Check that you pasted a valid HuggingFace URL or content
- Make sure the model has GGUF files available

### "Too large for RTX 4080 16GB"
- Model requires more than 16 GB even with CPU offload
- Try a smaller quantization (Q2_K instead of Q4_0)
- Or use a smaller model

### "Download failed"
- Check internet connection
- Verify HuggingFace is accessible
- Check disk space (need ~2x model size)

### "Benchmark failed"
- Check GPU is available (`nvidia-smi`)
- Verify no other models are loaded
- Check logs: `tail -f logs/api.log`

---

## Next Steps

After adding a model:
1. **View in Workbench** - See all models and benchmarks
2. **Run Full Benchmark** - Test on 5K samples for accurate results
3. **Compare Quality** - View side-by-side outputs
4. **Use in Production** - Add to batch processing jobs

---

## Technical Details

### API Endpoints

**POST /api/models/analyze**
```json
{
  "content": "https://huggingface.co/..."
}
```

**POST /api/models/install**
```json
{
  "model_id": "bartowski/OLMo-2-7B-Q4_0",
  "gguf_file": "OLMo-2-7B-Q4_0.gguf"
}
```

**WebSocket /ws/model-install/{model_id}**
```json
{
  "status": "downloading",
  "progress": 45.2
}
```

### Database Schema

```sql
CREATE TABLE model_registry (
    id INTEGER PRIMARY KEY,
    model_id TEXT UNIQUE,
    name TEXT,
    local_path TEXT,              -- NEW: Path to GGUF file
    quantization_type TEXT,       -- NEW: Q4_0, Q2_K, etc.
    size_gb REAL,
    estimated_memory_gb REAL,
    cpu_offload_gb REAL,
    throughput_tokens_per_sec REAL,
    status TEXT,                  -- untested, downloading, tested
    ...
);
```

---

## Why This Matters

**For End Users:**
- No technical knowledge required
- Instant feedback on compatibility
- Clear tradeoffs (speed vs quality)
- One-click installation

**For Developers:**
- Reusable components (parser, estimator, installer)
- WebSocket for real-time updates
- Extensible to other model sources
- Production-ready error handling

**For the Project:**
- Lowers barrier to entry
- Encourages experimentation
- Builds trust through transparency
- Showcases AI-assisted development

