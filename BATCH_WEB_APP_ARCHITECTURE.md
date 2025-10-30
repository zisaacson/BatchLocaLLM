# Web App + vLLM Offline Batch Processing Architecture

**Goal:** Accept 200K batch requests via web API, process with vLLM Offline, return results.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER / WEB APP                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ POST /v1/batches
                              │ (Upload JSONL file)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BATCH API SERVER                           │
│                     (FastAPI / Flask)                           │
│                                                                 │
│  • Accept batch job requests                                    │
│  • Validate input files                                         │
│  • Generate batch_id                                            │
│  • Queue job in database                                        │
│  • Return batch_id to user                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Write to queue
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      JOB QUEUE / DATABASE                       │
│                     (SQLite / PostgreSQL)                       │
│                                                                 │
│  batch_id | status   | input_file | output_file | created_at   │
│  ──────────────────────────────────────────────────────────────│
│  abc-123  | pending  | batch.jsonl| results.jsonl| 2025-10-28  │
│  def-456  | running  | batch2.jsonl| ...         | 2025-10-28  │
│  ghi-789  | completed| batch3.jsonl| done.jsonl  | 2025-10-27  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Poll for pending jobs
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BATCH WORKER                               │
│                   (Background Process)                          │
│                                                                 │
│  while True:                                                    │
│    job = get_next_pending_job()                                 │
│    if job:                                                      │
│      run_vllm_offline(job)                                      │
│      update_status(job, "completed")                            │
│    sleep(10)                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Runs vLLM Offline
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      vLLM OFFLINE ENGINE                        │
│                                                                 │
│  from vllm import LLM, SamplingParams                           │
│  llm = LLM(model="google/gemma-3-4b-it")                        │
│  outputs = llm.generate(prompts, sampling_params)               │
│                                                                 │
│  • Processes 200K requests                                      │
│  • Takes ~24 hours                                              │
│  • Saves results to file                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Results saved
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RESULTS STORAGE                            │
│                   (File System / S3)                            │
│                                                                 │
│  /results/abc-123/output.jsonl                                  │
│  /results/def-456/output.jsonl                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ GET /v1/batches/{batch_id}
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         USER / WEB APP                          │
│                                                                 │
│  • Poll for status                                              │
│  • Download results when complete                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 API Endpoints

### **1. Submit Batch Job**
```http
POST /v1/batches
Content-Type: multipart/form-data

{
  "file": <batch.jsonl>,
  "model": "google/gemma-3-4b-it"
}
```

**Response:**
```json
{
  "batch_id": "batch_abc123",
  "status": "pending",
  "created_at": "2025-10-28T10:00:00Z",
  "estimated_completion": "2025-10-29T10:00:00Z"
}
```

---

### **2. Check Batch Status**
```http
GET /v1/batches/{batch_id}
```

**Response (Pending):**
```json
{
  "batch_id": "batch_abc123",
  "status": "pending",
  "progress": {
    "total": 200000,
    "completed": 0,
    "failed": 0
  },
  "created_at": "2025-10-28T10:00:00Z"
}
```

**Response (Running):**
```json
{
  "batch_id": "batch_abc123",
  "status": "running",
  "progress": {
    "total": 200000,
    "completed": 50000,
    "failed": 0,
    "percent": 25.0
  },
  "started_at": "2025-10-28T10:05:00Z",
  "estimated_completion": "2025-10-29T10:00:00Z"
}
```

**Response (Completed):**
```json
{
  "batch_id": "batch_abc123",
  "status": "completed",
  "progress": {
    "total": 200000,
    "completed": 200000,
    "failed": 0
  },
  "started_at": "2025-10-28T10:05:00Z",
  "completed_at": "2025-10-29T10:15:00Z",
  "results_url": "/v1/batches/batch_abc123/results"
}
```

---

### **3. Download Results**
```http
GET /v1/batches/{batch_id}/results
```

**Response:**
```
Content-Type: application/x-ndjson
Content-Disposition: attachment; filename="batch_abc123_results.jsonl"

{"custom_id": "req-1", "response": {...}}
{"custom_id": "req-2", "response": {...}}
...
```

---

### **4. List All Batches**
```http
GET /v1/batches?status=completed&limit=10
```

**Response:**
```json
{
  "batches": [
    {
      "batch_id": "batch_abc123",
      "status": "completed",
      "created_at": "2025-10-28T10:00:00Z"
    },
    {
      "batch_id": "batch_def456",
      "status": "running",
      "created_at": "2025-10-28T11:00:00Z"
    }
  ]
}
```

---

## 🔧 Implementation Components

### **Component 1: Batch API Server** (`batch_api_server.py`)
- FastAPI web server
- Handles HTTP requests
- Validates input files
- Manages job queue
- Serves results

### **Component 2: Batch Worker** (`batch_worker.py`)
- Background process
- Polls database for pending jobs
- Runs vLLM Offline
- Updates job status
- Handles errors

### **Component 3: Database** (`batch_jobs.db`)
- SQLite or PostgreSQL
- Stores job metadata
- Tracks progress
- Manages queue

### **Component 4: File Storage**
- Input files: `/data/batches/input/`
- Output files: `/data/batches/output/`
- Logs: `/data/batches/logs/`

---

## 🚀 How It Works

### **User Workflow:**

1. **User uploads batch file** (200K requests)
   ```bash
   curl -X POST http://localhost:8080/v1/batches \
     -F "file=@batch_200k.jsonl" \
     -F "model=google/gemma-3-4b-it"
   ```

2. **Server returns batch_id**
   ```json
   {"batch_id": "batch_abc123", "status": "pending"}
   ```

3. **User polls for status** (every 60 seconds)
   ```bash
   curl http://localhost:8080/v1/batches/batch_abc123
   ```

4. **Worker picks up job** (background)
   - Loads vLLM model
   - Processes 200K requests
   - Saves results
   - Updates status to "completed"

5. **User downloads results**
   ```bash
   curl http://localhost:8080/v1/batches/batch_abc123/results > results.jsonl
   ```

---

## ⚙️ Technical Details

### **Concurrency Model:**
- **API Server:** Async (handles many users)
- **Worker:** Single-threaded (one batch at a time)
- **GPU:** Dedicated to worker process

### **Queue Management:**
- **FIFO:** First-in, first-out
- **Priority:** Optional (premium users first)
- **Retry:** Failed jobs can be retried

### **Progress Tracking:**
- Worker updates database every 1,000 requests
- API server reads from database
- Real-time progress available

### **Error Handling:**
- **Validation errors:** Return 400 immediately
- **Processing errors:** Mark job as "failed", save error log
- **GPU OOM:** Retry with smaller batch size

---

## 📊 Performance Estimates

| Batch Size | Processing Time | Queue Wait | Total Time |
|------------|-----------------|------------|------------|
| 5K | 37 min | 0-10 min | ~47 min |
| 50K | 6.1 hours | 0-30 min | ~6.5 hours |
| 200K | 24.5 hours | 0-2 hours | ~26 hours |

**Assumptions:**
- Single RTX 4080 16GB
- Gemma 3 4B model
- 2,511 tok/s throughput
- No other jobs in queue

---

## 🔐 Security Considerations

1. **Authentication:** Require API keys
2. **Rate Limiting:** Max 10 batches per user per day
3. **File Size Limits:** Max 500 MB upload
4. **Input Validation:** Sanitize JSONL files
5. **Resource Limits:** Max 200K requests per batch

---

## 🎯 Advantages of This Architecture

✅ **Scalable:** Add more workers/GPUs as needed
✅ **Reliable:** Jobs survive server restarts
✅ **User-Friendly:** Simple HTTP API
✅ **Efficient:** Uses vLLM Offline (proven to work)
✅ **Flexible:** Can add real-time API later

---

## 🚧 Next Steps

1. **Build Batch API Server** (FastAPI)
2. **Build Batch Worker** (Python script)
3. **Set up Database** (SQLite for MVP)
4. **Test with 5K batch**
5. **Scale to 200K**

---

## 💡 Alternative: Hybrid Mode

**Can you run BOTH batch processing AND real-time API?**

**Option 1: Time-sharing**
- 9am-5pm: Real-time API (vLLM Serve)
- 5pm-9am: Batch processing (vLLM Offline)

**Option 2: Multi-GPU**
- GPU 1: Real-time API (always on)
- GPU 2: Batch processing (queue)

**Option 3: Dynamic switching**
- If no batch jobs: Run vLLM Serve
- If batch job arrives: Stop Serve, run Offline, restart Serve

---

## 📝 Summary

**YES, you can build a web app that:**
1. Accepts 200K batch requests
2. Runs vLLM Offline in background
3. Returns results when complete

**This is exactly how ALCF's system works!**

**Want me to build the MVP?**

