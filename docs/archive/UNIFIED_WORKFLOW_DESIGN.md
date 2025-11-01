# Unified Workflow Design - First Principles

## The Problem

We built 4 separate UIs:
1. Model Management (add/test models)
2. Benchmark Runner (run models on datasets)
3. Results Viewer (see outputs)
4. Conquest Curation (annotate/fix)

**This is wrong.** Users don't think in these silos.

---

## What Users Actually Do

### Workflow 1: "I want to test a new model"
```
1. Upload dataset (5K candidates)
2. Select model (OLMo 2 7B)
3. Click "Run"
4. Watch progress (live)
5. See results (immediately when done)
6. Compare to other models (side-by-side)
7. Mark good examples (golden data)
8. Fix bad examples (corrections)
9. Export curated dataset
```

**All in ONE place, ONE flow.**

### Workflow 2: "I want to compare models"
```
1. Select dataset (5K candidates)
2. Select models (Gemma 3 4B, OLMo 2 7B, GPT-OSS 20B)
3. Click "Compare All"
4. See side-by-side results
5. Filter to differences only
6. Mark which model is better for each example
7. Export comparison report
```

### Workflow 3: "I want to build golden dataset"
```
1. Upload seed data (100 candidates)
2. Run best model (Gemma 3 4B)
3. Review results one-by-one
4. Mark: ✅ Good / ❌ Bad / ⭐ Golden
5. Fix bad examples
6. Export golden dataset (50 examples)
7. Use for ICL/fine-tuning
```

---

## The Unified UI

### Single Page: "Dataset Workbench"

**Left Sidebar: Datasets**
```
📁 Datasets
  ├─ batch_5k.jsonl (5,000)
  ├─ batch_100.jsonl (100)
  └─ golden_seed.jsonl (50) ⭐
  
[+ Upload Dataset]
```

**Center: Results Grid**
```
┌─────────────────────────────────────────────────────────────┐
│ Dataset: batch_5k.jsonl (5,000 candidates)                  │
├─────────────────────────────────────────────────────────────┤
│ Models:                                                      │
│ [✓] Gemma 3 4B    [✓] OLMo 2 7B    [ ] GPT-OSS 20B         │
│                                                              │
│ [▶ Run Selected Models]  [📊 Compare]  [⭐ Export Golden]   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Candidate 1: John Smith - Senior Engineer @ Google          │
│ ┌──────────────────┬──────────────────┬──────────────────┐ │
│ │ Gemma 3 4B       │ OLMo 2 7B        │ GPT-OSS 20B      │ │
│ ├──────────────────┼──────────────────┼──────────────────┤ │
│ │ ✅ Strong Yes    │ ✅ Strong Yes    │ (running...)     │ │
│ │ Trajectory: Good │ Trajectory: Good │                  │ │
│ │ Pedigree: Strong │ Pedigree: Strong │                  │ │
│ │                  │                  │                  │ │
│ │ [⭐ Golden]      │ [⭐ Golden]      │                  │ │
│ │ [✏️ Edit]        │ [✏️ Edit]        │                  │ │
│ └──────────────────┴──────────────────┴──────────────────┘ │
│                                                              │
│ Candidate 2: Jane Doe - ML Engineer @ Meta                  │
│ ┌──────────────────┬──────────────────┬──────────────────┐ │
│ │ Gemma 3 4B       │ OLMo 2 7B        │ GPT-OSS 20B      │ │
│ ├──────────────────┼──────────────────┼──────────────────┤ │
│ │ ⚠️ Maybe         │ ✅ Yes           │ (running...)     │ │
│ │ Trajectory: Avg  │ Trajectory: Good │                  │ │
│ │ Pedigree: Good   │ Pedigree: Strong │                  │ │
│ │                  │                  │                  │ │
│ │ [❌ Wrong]       │ [⭐ Golden]      │                  │ │
│ │ [✏️ Fix]         │ [✏️ Edit]        │                  │ │
│ └──────────────────┴──────────────────┴──────────────────┘ │
│                                                              │
│ [Load More...]                                               │
└─────────────────────────────────────────────────────────────┘
```

**Right Sidebar: Actions**
```
🎯 Quick Actions
  ├─ Run new model
  ├─ Compare models
  ├─ Filter results
  └─ Export data

📊 Stats
  ├─ Total: 5,000
  ├─ Completed: 500
  ├─ Golden: 12 ⭐
  └─ Fixed: 3 ✏️

⚙️ Active Jobs
  ├─ OLMo 2 7B
  │   └─ 500/5000 (10%)
  │       32 tok/s, ETA 2.5h
  └─ GPT-OSS 20B
      └─ Queued
```

---

## Key Features

### 1. **Inline Model Comparison**
- See all model outputs side-by-side
- Highlight differences automatically
- Click to mark which is better

### 2. **Live Progress**
- Models run in background
- Results appear as they complete
- No page refresh needed

### 3. **Inline Annotation**
- Click ⭐ to mark golden
- Click ✏️ to edit/fix
- Click ❌ to mark wrong
- All saved immediately

### 4. **Smart Filtering**
```
Show:
[ ] All results
[✓] Differences only (models disagree)
[ ] Golden examples only
[ ] Needs review (marked wrong)
```

### 5. **Export Options**
```
Export:
[ ] All results (5,000)
[ ] Golden dataset (12 examples)
[ ] Comparison report (CSV)
[ ] Training data (JSONL)
```

---

## Technical Implementation

### Single API Endpoint
```http
GET /api/workbench?dataset_id=batch_5k&models=gemma3-4b,olmo2-7b
```

Response:
```json
{
  "dataset": {
    "id": "batch_5k",
    "name": "batch_5k.jsonl",
    "count": 5000
  },
  "models": [
    {
      "id": "gemma3-4b",
      "name": "Gemma 3 4B",
      "status": "completed",
      "results_count": 5000
    },
    {
      "id": "olmo2-7b",
      "name": "OLMo 2 7B",
      "status": "running",
      "progress": 500,
      "total": 5000,
      "throughput": 32.0,
      "eta_seconds": 9000
    }
  ],
  "results": [
    {
      "candidate_id": "candidate-1",
      "candidate_name": "John Smith",
      "candidate_title": "Senior Engineer @ Google",
      "models": {
        "gemma3-4b": {
          "recommendation": "Strong Yes",
          "trajectory": "Good",
          "pedigree": "Strong",
          "is_golden": false,
          "is_fixed": false
        },
        "olmo2-7b": {
          "recommendation": "Strong Yes",
          "trajectory": "Good",
          "pedigree": "Strong",
          "is_golden": false,
          "is_fixed": false
        }
      },
      "agreement": true,
      "needs_review": false
    }
  ]
}
```

### WebSocket for Live Updates
```javascript
const ws = new WebSocket('ws://localhost:4080/api/workbench/live');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  
  if (update.type === 'progress') {
    updateProgress(update.model_id, update.progress);
  }
  
  if (update.type === 'result') {
    addResult(update.candidate_id, update.model_id, update.response);
  }
};
```

---

## Benefits

### For Users
✅ **One place** for everything
✅ **Live updates** - see results as they come
✅ **Inline comparison** - no switching pages
✅ **Quick annotation** - mark golden/fix in-place
✅ **Smart filtering** - focus on what matters

### For Open Source
✅ **Self-service** - upload dataset, run models, get results
✅ **Model comparison** - see which model is best
✅ **Quality curation** - build golden datasets
✅ **Export ready** - download for training/ICL

### For Parasail Team
✅ **Demo ready** - show live model comparison
✅ **Quality focus** - highlight model differences
✅ **Production ready** - export curated data
✅ **Scalable** - works for 5K, 50K, 200K

---

## Migration Plan

### Phase 1: Build Unified Workbench
- [ ] Single page UI (`static/workbench.html`)
- [ ] Unified API (`/api/workbench`)
- [ ] WebSocket live updates
- [ ] Inline model comparison

### Phase 2: Add Annotation
- [ ] Mark golden (⭐)
- [ ] Edit/fix (✏️)
- [ ] Mark wrong (❌)
- [ ] Export curated data

### Phase 3: Deprecate Old UIs
- [ ] Keep model-management.html (admin only)
- [ ] Remove benchmark-runner.html (merged into workbench)
- [ ] Remove conquest-curation.html (merged into workbench)
- [ ] Update docs

---

## Example: Your Current Workflow

**What you're doing now:**
```
1. Run: python scripts/benchmark_olmo2_7b_5k.py
2. Wait 2-3 hours
3. Open: benchmarks/raw/olmo2-7b-5k-*.jsonl
4. Compare manually to gemma3 results
5. Copy good examples to separate file
```

**What you'll do with Workbench:**
```
1. Open workbench
2. Select batch_5k.jsonl
3. Check: [✓] Gemma 3 4B  [✓] OLMo 2 7B  [✓] GPT-OSS 20B
4. Click "Run Selected Models"
5. Watch live progress
6. See results side-by-side as they complete
7. Click ⭐ on good examples
8. Click "Export Golden Dataset"
```

**All in one place. All in real-time. All self-service.**

---

This is what you meant by "think about the workflows from first principles and evolve the system."

Should I build this?

