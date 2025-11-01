# Benchmark Runner UI - Design Document

## Overview

The Benchmark Runner UI allows users to:
1. **Upload test datasets** (JSONL files with candidate data)
2. **Run any model on any dataset** (like running OLMo 2 7B on 5K candidates)
3. **See results live** (progress, throughput, ETA)
4. **View completed results** (full results, comparisons)

This makes the vLLM batch server fully self-service for open source users.

---

## User Flow

### Step 1: Upload Dataset
```
User uploads batch_5k.jsonl
↓
Server stores it in data/datasets/
↓
Dataset appears in UI with metadata:
- Name: "batch_5k.jsonl"
- Count: 5,000 requests
- Uploaded: 2025-10-31
```

### Step 2: Select Model & Run
```
User selects:
- Model: OLMo 2 7B
- Dataset: batch_5k.jsonl
↓
Clicks "Run Benchmark"
↓
Server starts background process
↓
Benchmark appears in "Active Benchmarks"
```

### Step 3: Watch Live Progress
```
Active Benchmarks shows:
- Progress: 500/5000 (10%)
- Throughput: 32 tok/s
- ETA: 2.5 hours
- Progress bar updating every 2 seconds
```

### Step 4: View Results
```
When complete, benchmark moves to "Completed Benchmarks"
↓
User clicks "View Results"
↓
Shows:
- Total time: 2.8 hours
- Throughput: 28 tok/s
- All 5,000 responses in a table
- Download results as JSONL
```

---

## UI Components

### 1. Dataset Upload (`static/benchmark-runner.html`)
- Drag & drop JSONL files
- Shows uploaded datasets with metadata
- Delete datasets

### 2. Model Selection
- Dropdown of all available models
- Shows model name, size, memory requirements

### 3. Active Benchmarks
- Live progress bars
- Real-time metrics (throughput, ETA)
- Auto-refreshes every 2 seconds

### 4. Completed Benchmarks
- Summary metrics
- "View Results" button
- Download results

### 5. Results Viewer (`static/benchmark-results.html`)
- Table of all responses
- Filter by candidate name
- Compare multiple models side-by-side
- Export to CSV/JSONL

---

## Backend API Endpoints

### Dataset Management

**Upload Dataset**
```http
POST /admin/datasets/upload
Content-Type: multipart/form-data

file: batch_5k.jsonl
```

Response:
```json
{
  "dataset_id": "ds_abc123",
  "name": "batch_5k.jsonl",
  "count": 5000,
  "uploaded_at": "2025-10-31T17:35:00Z"
}
```

**List Datasets**
```http
GET /admin/datasets
```

Response:
```json
{
  "datasets": [
    {
      "id": "ds_abc123",
      "name": "batch_5k.jsonl",
      "count": 5000,
      "uploaded_at": "2025-10-31T17:35:00Z"
    }
  ]
}
```

**Delete Dataset**
```http
DELETE /admin/datasets/{dataset_id}
```

### Benchmark Management

**Run Benchmark**
```http
POST /admin/benchmarks/run
Content-Type: application/json

{
  "model_id": "allenai/OLMo-2-1124-7B-Instruct",
  "dataset_id": "ds_abc123"
}
```

Response:
```json
{
  "benchmark_id": "bm_xyz789",
  "status": "running",
  "started_at": "2025-10-31T17:35:00Z"
}
```

**List Benchmarks**
```http
GET /admin/benchmarks
```

Response:
```json
{
  "benchmarks": [
    {
      "benchmark_id": "bm_xyz789",
      "model_id": "allenai/OLMo-2-1124-7B-Instruct",
      "model_name": "OLMo 2 7B",
      "dataset_id": "ds_abc123",
      "dataset_name": "batch_5k.jsonl",
      "status": "running",
      "progress": 10,
      "completed": 500,
      "total": 5000,
      "throughput": 32.0,
      "eta_seconds": 9000,
      "started_at": "2025-10-31T17:35:00Z"
    }
  ]
}
```

**Get Benchmark Results**
```http
GET /admin/benchmarks/{benchmark_id}/results
```

Response:
```json
{
  "benchmark_id": "bm_xyz789",
  "model_name": "OLMo 2 7B",
  "dataset_name": "batch_5k.jsonl",
  "status": "completed",
  "total_time_seconds": 10080,
  "throughput": 28.5,
  "results": [
    {
      "custom_id": "candidate-1",
      "response": {
        "status_code": 200,
        "body": {
          "choices": [{
            "message": {
              "content": "..."
            }
          }]
        }
      }
    }
  ]
}
```

---

## Database Schema

### `datasets` Table
```sql
CREATE TABLE datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    count INTEGER NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `benchmarks` Table
```sql
CREATE TABLE benchmarks (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    total INTEGER NOT NULL,
    throughput FLOAT DEFAULT 0,
    eta_seconds INTEGER DEFAULT 0,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    total_time_seconds FLOAT,
    results_file TEXT,
    metadata_file TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES model_registry(model_id),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);
```

---

## Implementation Status

### ✅ Completed
- [x] UI design (`static/benchmark-runner.html`)
- [x] JavaScript client (`static/js/benchmark-runner.js`)
- [x] Pydantic models (`RunBenchmarkRequest`)

### ⏳ TODO
- [ ] Database tables (`datasets`, `benchmarks`)
- [ ] API endpoints (upload, list, run, get results)
- [ ] Background benchmark runner (similar to model test runner)
- [ ] Results viewer UI (`static/benchmark-results.html`)
- [ ] Model comparison UI (side-by-side view)

---

## Example Usage

**For Parasail Team:**
```
1. Upload their candidate dataset (10K candidates)
2. Select Gemma 3 4B
3. Click "Run Benchmark"
4. Watch live progress (10K in ~60 minutes)
5. View results and compare to their current system
6. Try OLMo 2 7B to see quality difference
7. Export results for analysis
```

**For Internal Use:**
```
1. Upload 5K candidates from Aris
2. Run Gemma 3 4B, Qwen 3 4B, OLMo 2 7B, GPT-OSS 20B
3. Compare results side-by-side
4. Identify which model gives best quality
5. Export golden examples for training data
```

---

## Next Steps

1. **Finish backend implementation** (database + API)
2. **Test with OLMo 2 7B** (currently running)
3. **Build results viewer** (table + comparison)
4. **Add model comparison** (side-by-side view)
5. **Test with GPT-OSS 20B** (after OLMo completes)

---

**This makes the vLLM batch server a complete, self-service benchmarking platform for open source users.**

