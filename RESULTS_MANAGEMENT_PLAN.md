# Results Management & UI Evolution Plan

## 🎯 Goals

1. **Standardize result file naming and metadata**
2. **Evolve UI to show evaluation criteria and allow model selection**
3. **Prevent losing results again**
4. **Decide: Build vs. Use Open Source Tools**

---

## 📊 Current State Audit

### What We Have (Successful Benchmarks)
```
✅ Qwen 3-4B:      qwen3_4b_5k_offline_results.jsonl (5000, HTTP 200)
✅ Gemma 3-4B:     benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl (5000, HTTP 200)
✅ Llama 3.2-3B:   llama32_3b_5k_results.jsonl (5000, HTTP 200)
✅ Llama 3.2-1B:   llama32_1b_5k_results.jsonl (5000, HTTP 200)
❌ OLMo 2-1B:      olmo2_1b_5k_offline_results.jsonl (5000, HTTP 400 - no chat template)
```

### Problems
1. **Inconsistent naming**: 3 different patterns
2. **No metadata**: Can't tell model/dataset/timestamp from filename
3. **Lost results**: Gemma in `benchmarks/raw/` not found by analysis script
4. **Web UI confusion**: Matches by line count, shows wrong models

---

## 🏗️ Proposed Solution: Metadata-Driven Results System

### 1. Standardized File Structure
```
results/
├── metadata.json              # Central registry of all benchmark runs
├── qwen-3-4b/
│   ├── batch_5k_20241028_143300.jsonl
│   ├── batch_5k_20241028_143300.log
│   └── batch_5k_20241028_143300.meta.json
├── gemma-3-4b/
│   ├── batch_5k_20241028_084000.jsonl
│   ├── batch_5k_20241028_084000.log
│   └── batch_5k_20241028_084000.meta.json
└── llama-3.2-3b/
    ├── batch_5k_20241028_120000.jsonl
    ├── batch_5k_20241028_120000.log
    └── batch_5k_20241028_120000.meta.json
```

### 2. Metadata Schema
```json
{
  "run_id": "qwen-3-4b-batch_5k-20241028-143300",
  "model": {
    "name": "Qwen 3-4B",
    "id": "Qwen/Qwen3-4B-Instruct-2507",
    "size": "4B",
    "vram_gb": 7.6
  },
  "dataset": {
    "name": "batch_5k.jsonl",
    "count": 5000,
    "prompt_template": "candidate_evaluation_v1",
    "criteria": {
      "educational_pedigree": "...",
      "company_pedigree": "...",
      "trajectory": "...",
      "is_software_engineer": "..."
    }
  },
  "execution": {
    "started_at": "2024-10-28T14:33:00Z",
    "completed_at": "2024-10-28T14:57:35Z",
    "duration_seconds": 1475,
    "req_per_sec": 3.39,
    "vllm_version": "0.11.0",
    "command": "python -m vllm.entrypoints.openai.run_batch ..."
  },
  "results": {
    "total": 5000,
    "success": 5000,
    "errors": 0,
    "success_rate": 100.0,
    "avg_prompt_tokens": 1234,
    "avg_completion_tokens": 567
  },
  "files": {
    "results": "results/qwen-3-4b/batch_5k_20241028_143300.jsonl",
    "log": "results/qwen-3-4b/batch_5k_20241028_143300.log",
    "input": "batch_5k.jsonl"
  }
}
```

### 3. Central Registry (`results/metadata.json`)
```json
{
  "runs": [
    {
      "run_id": "qwen-3-4b-batch_5k-20241028-143300",
      "model": "Qwen 3-4B",
      "dataset": "batch_5k.jsonl",
      "status": "completed",
      "timestamp": "2024-10-28T14:33:00Z",
      "results_file": "results/qwen-3-4b/batch_5k_20241028_143300.jsonl"
    },
    {
      "run_id": "gemma-3-4b-batch_5k-20241028-084000",
      "model": "Gemma 3-4B",
      "dataset": "batch_5k.jsonl",
      "status": "completed",
      "timestamp": "2024-10-28T08:40:00Z",
      "results_file": "results/gemma-3-4b/batch_5k_20241028_084000.jsonl"
    }
  ],
  "datasets": {
    "batch_5k.jsonl": {
      "count": 5000,
      "prompt_version": "candidate_evaluation_v1",
      "created": "2024-10-27T10:00:00Z"
    }
  },
  "models": {
    "qwen-3-4b": {
      "name": "Qwen 3-4B",
      "hf_id": "Qwen/Qwen3-4B-Instruct-2507",
      "runs": 1
    },
    "gemma-3-4b": {
      "name": "Gemma 3-4B",
      "hf_id": "google/gemma-3-4b-it",
      "runs": 1
    }
  }
}
```

---

## 🎨 UI Evolution

### New Features

#### 1. **Evaluation Criteria Display**
```
┌─────────────────────────────────────────────────────────┐
│ 📋 Evaluation Criteria for batch_5k.jsonl              │
├─────────────────────────────────────────────────────────┤
│ Educational Pedigree:                                   │
│ • Bachelor's degree is strongest signal                │
│ • Top-tier CS/Engineering = Great                      │
│ • Mid-tier = Average/Weak                              │
│                                                         │
│ Company Pedigree:                                       │
│ • Tier-1 tech, high-growth startups                    │
│                                                         │
│ Trajectory:                                             │
│ • >8 years → ≥ Senior SWE                              │
│ • >12 years → ≥ Staff SWE                              │
└─────────────────────────────────────────────────────────┘
```

#### 2. **Model Selection Checkboxes**
```
┌─────────────────────────────────────────────────────────┐
│ 🎯 Select Models to Compare                            │
├─────────────────────────────────────────────────────────┤
│ ☑ Qwen 3-4B        (3.39 req/s, 100% success)         │
│ ☑ Gemma 3-4B       (2.51 req/s, 100% success)         │
│ ☑ Llama 3.2-3B     (6.70 req/s, 100% success)         │
│ ☐ Llama 3.2-1B     (8.20 req/s, 100% success)         │
│ ☐ OLMo 2-1B        (ERROR: No chat template)           │
└─────────────────────────────────────────────────────────┘
```

#### 3. **Side-by-Side Comparison with Diff Highlighting**
```
Candidate #1: Min Thet K (Software Engineer at Bloomberg)

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Qwen 3-4B    │ Gemma 3-4B   │ Llama 3.2-3B │ Llama 3.2-1B │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ Strong Yes   │ Strong Yes   │ Strong Yes   │ N/A          │
│              │              │              │              │
│ MIT BS+MEng  │ MIT BS+MEng  │ MIT BS+MEng  │ (no response)│
│ Bloomberg +  │ Bloomberg +  │ Bloomberg +  │              │
│ Microsoft    │ Microsoft    │ Microsoft    │              │
│              │              │              │              │
│ ✅ Agree     │ ✅ Agree     │ ✅ Agree     │ ❌ Error     │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 🔧 Implementation Plan

### Phase 1: Migrate Existing Results (30 min)
1. Create `results/` directory structure
2. Move existing result files to standardized locations
3. Generate metadata for each run
4. Create central registry

### Phase 2: Update Analysis Script (20 min)
1. Read from `results/metadata.json`
2. Auto-discover all completed runs
3. Support comparing any combination of models

### Phase 3: Evolve Web UI (60 min)
1. Add evaluation criteria display
2. Add model selection checkboxes
3. Improve comparison table with diff highlighting
4. Add filtering by agreement/disagreement

### Phase 4: Update Benchmark Scripts (30 min)
1. Auto-generate metadata on completion
2. Save to standardized locations
3. Update central registry

---

## 🤔 Build vs. Open Source Tools

### Option A: Build Our Own (Current Path)
**Pros:**
- ✅ Tailored to our exact needs
- ✅ Simple, no dependencies
- ✅ Full control

**Cons:**
- ❌ Reinventing the wheel
- ❌ No community support
- ❌ Limited features

### Option B: Use LM Evaluation Harness
**Pros:**
- ✅ Industry standard
- ✅ Rich features (metrics, leaderboards)
- ✅ Community support

**Cons:**
- ❌ Overkill for our use case
- ❌ Designed for academic benchmarks, not business evaluation
- ❌ Steep learning curve

### Option C: Use MLflow
**Pros:**
- ✅ Experiment tracking
- ✅ Model registry
- ✅ UI included

**Cons:**
- ❌ Heavy infrastructure
- ❌ Designed for ML training, not inference benchmarking
- ❌ Requires server setup

### Option D: Use Weights & Biases (W&B)
**Pros:**
- ✅ Beautiful UI
- ✅ Collaboration features
- ✅ Cloud-hosted

**Cons:**
- ❌ Requires account/cloud
- ❌ Overkill for local benchmarking
- ❌ Privacy concerns with candidate data

### **RECOMMENDATION: Hybrid Approach**
1. **Build lightweight metadata system** (Phase 1-4 above)
2. **Use simple JSON + Python** for tracking
3. **Keep web UI simple** but functional
4. **Later**: Consider MLflow if we need experiment tracking at scale

**Why?**
- Our use case is unique (candidate evaluation, not academic benchmarks)
- We need privacy (can't send candidate data to cloud)
- Simple is better for now
- Can always migrate to MLflow later if needed

---

## 📝 Next Steps

1. **Approve this plan**
2. **Migrate existing results** (I'll do this now)
3. **Update UI** with model selection + criteria display
4. **Test with all 4 models**
5. **Document the system**

**Estimated Time:** 2-3 hours total

---

## 🎯 Success Criteria

- ✅ All 4 successful benchmarks visible in UI
- ✅ Can select which models to compare
- ✅ Evaluation criteria clearly displayed
- ✅ Never lose results again (metadata tracking)
- ✅ Easy to add new benchmark runs

