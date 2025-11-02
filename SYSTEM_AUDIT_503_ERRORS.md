# System Audit: 503 "Server Busy" Errors - Root Cause & Evolution Plan

**Date:** 2025-11-02  
**Issue:** API returns 503 "Worker busy" when processing jobs, blocking new requests  
**Impact:** Poor user experience, appears broken when actually working correctly

---

## 🔍 Root Cause Analysis

### **Current Architecture**

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│   API Server    │────────▶│   PostgreSQL     │◀────────│   Worker    │
│   (Port 4080)   │         │   (Job Queue)    │         │   (GPU)     │
└─────────────────┘         └──────────────────┘         └─────────────┘
        │                                                        │
        │ 1. Accept job                                         │
        │ 2. Write to DB                                        │
        │ 3. Return 200 OK                                      │
        │                                                        │
        │                                                        │ 4. Poll queue
        │                                                        │ 5. Process job
        │                                                        │ 6. Update status
        │                                                        │
        │ 7. Check status                                       │
        │ 8. Return results                                     │
        └────────────────────────────────────────────────────────┘
```

### **The Problem: Sequential Processing + Rejection Logic**

**Worker Design (Intentional):**
```python
# core/batch_app/worker.py:817-843
while True:
    job = self.get_next_pending_job(db)  # Get ONE job
    
    if job:
        self.update_heartbeat(db, status='processing')  # Mark busy
        self.process_job(job, db)  # BLOCKS until complete (could be hours)
    else:
        time.sleep(10)  # Poll every 10 seconds
```

**Why Sequential?**
- RTX 4080 has only 16GB VRAM
- Loading a model takes 8-14GB
- Processing one job at a time prevents OOM
- **This is correct for single-GPU systems**

**API Rejection Logic (The Issue):**
```python
# core/batch_app/api_server.py:946-951
if worker_heartbeat.status == 'processing':
    raise HTTPException(
        status_code=503,
        detail=f"Worker busy processing job {worker_heartbeat.current_job_id}. Try again later."
    )
```

**Why This Exists:**
- Prevents queue buildup when worker is slow
- Protects against OOM from too many queued jobs
- **BUT: Rejects jobs even when queue has capacity**

---

## 📊 Current Limits & Behavior

### **Configuration** (`core/config.py`)

```python
MAX_QUEUE_DEPTH: int = 20              # Max concurrent jobs in queue
MAX_REQUESTS_PER_JOB: int = 50000      # Max requests per job (OpenAI limit)
MAX_TOTAL_QUEUED_REQUESTS: int = 1000000  # Max total requests across all jobs
```

### **Actual Behavior**

| Scenario | Queue Depth | Worker Status | API Response |
|----------|-------------|---------------|--------------|
| No jobs | 0 | idle | ✅ 200 OK - Accept job |
| 1 job queued | 1 | idle | ✅ 200 OK - Accept job |
| 1 job processing | 1 | **processing** | ❌ **503 - Reject job** |
| 19 jobs queued | 19 | processing | ❌ 503 - Reject job |
| 20 jobs queued | 20 | processing | ❌ 429 - Queue full |

**The Bug:** API rejects jobs when `worker.status == 'processing'` **even if queue has capacity** (1-19 jobs).

---

## 🎯 Why This Is Wrong

### **Example: Lead Engineer's Experience**

1. **Submit Job #1** → ✅ 200 OK (queue: 1, worker: idle)
2. **Worker picks up Job #1** → Worker status: `processing`
3. **Submit Job #2** → ❌ **503 "Worker busy"** (queue: 1, worker: processing)
4. **Submit Job #3** → ❌ **503 "Worker busy"** (queue: 1, worker: processing)
5. **Job #1 completes** → Worker status: `idle`
6. **Submit Job #4** → ✅ 200 OK (queue: 1, worker: idle)

**Result:** Users can only submit ONE job at a time, even though we support 20 jobs in queue!

### **What Should Happen**

1. **Submit Job #1** → ✅ 200 OK (queue: 1)
2. **Submit Job #2** → ✅ 200 OK (queue: 2)
3. **Submit Job #3** → ✅ 200 OK (queue: 3)
4. **Submit Job #20** → ✅ 200 OK (queue: 20)
5. **Submit Job #21** → ❌ 429 "Queue full" (queue: 20)

Worker processes jobs **sequentially** (one at a time), but API should **accept jobs up to queue limit**.

---

## ✅ Solution: Remove Worker Status Check

### **Current Code** (WRONG)

```python
# core/batch_app/api_server.py:946-951
if worker_heartbeat.status == 'processing':
    raise HTTPException(
        status_code=503,
        detail=f"Worker busy processing job {worker_heartbeat.current_job_id}. Try again later."
    )
```

### **Fixed Code** (CORRECT)

```python
# Remove the worker status check entirely
# Queue depth check is sufficient:

if len(pending_jobs) >= MAX_QUEUE_DEPTH:
    raise HTTPException(
        status_code=429,
        detail=f"Queue full ({len(pending_jobs)}/{MAX_QUEUE_DEPTH} jobs). Try again later."
    )
```

**Why This Works:**
- ✅ Queue depth check prevents OOM (20 jobs max)
- ✅ Worker processes jobs sequentially (prevents parallel OOM)
- ✅ Users can submit multiple jobs (better UX)
- ✅ Worker heartbeat still monitored (offline detection)

---

## 🚀 Evolution Plan

### **Phase 1: Fix Immediate Issue** (5 minutes)

**Action:** Remove worker status check from `create_batch()`

**Files to change:**
- `core/batch_app/api_server.py` (lines 946-951)

**Testing:**
```bash
# Submit 5 jobs in rapid succession
for i in {1..5}; do
  python examples/simple_batch.py &
done

# All should return 200 OK
# Worker processes them sequentially
```

---

### **Phase 2: Improve Queue Visibility** (30 minutes)

**Problem:** Users don't know their position in queue or ETA

**Solution:** Add queue position and ETA to batch status

**API Response Enhancement:**
```json
{
  "id": "batch_abc123",
  "status": "validating",
  "queue_position": 3,
  "estimated_start_time": "2025-11-02T02:30:00Z",
  "estimated_completion_time": "2025-11-02T03:15:00Z"
}
```

**Implementation:**
```python
# Calculate queue position
queue_position = db.query(BatchJob).filter(
    BatchJob.status == 'validating',
    BatchJob.created_at < job.created_at
).count() + 1

# Estimate start time based on current job progress
current_job = db.query(BatchJob).filter(
    BatchJob.status == 'in_progress'
).first()

if current_job and current_job.estimated_completion_time:
    estimated_start = current_job.estimated_completion_time
else:
    estimated_start = datetime.now(timezone.utc)
```

---

### **Phase 3: Add Webhook Notifications** (1 hour)

**Problem:** Users must poll for status updates

**Solution:** Webhook callbacks when job status changes

**User Experience:**
```python
# Submit job with webhook
client.batches.create(
    input_file_id="file-abc123",
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={
        "webhook_url": "https://myapp.com/batch-complete"
    }
)

# Server calls webhook when job completes
POST https://myapp.com/batch-complete
{
  "batch_id": "batch_abc123",
  "status": "completed",
  "output_file_id": "file-out-xyz789"
}
```

**Already Implemented!** (Just needs documentation)
- `core/batch_app/database.py` has webhook fields
- `core/batch_app/worker.py` has webhook logic
- Just needs to be enabled and documented

---

### **Phase 4: Priority Queue** (2 hours)

**Problem:** All jobs treated equally (FIFO)

**Solution:** Add priority levels

**Use Cases:**
- **High priority:** Production customer requests
- **Normal priority:** Standard batch jobs
- **Low priority:** Benchmarking, testing

**Implementation:**
```python
# Add priority field to BatchJob
class BatchJob(Base):
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # -1 = low (testing), 0 = normal, 1 = high (production)

# Update queue query
def get_next_pending_job(self, db: Session) -> BatchJob | None:
    return db.query(BatchJob).filter(
        BatchJob.status == 'validating'
    ).order_by(
        BatchJob.priority.desc(),  # High priority first
        BatchJob.created_at        # Then FIFO
    ).first()
```

---

## 📈 Expected Impact

### **Before Fix:**
- ❌ Users can only submit 1 job at a time
- ❌ 503 errors appear as "server broken"
- ❌ No visibility into queue position
- ❌ Must poll for status updates

### **After Phase 1:**
- ✅ Users can submit up to 20 jobs
- ✅ 429 "Queue full" is clear and actionable
- ✅ Better throughput (queue stays full)

### **After Phase 2:**
- ✅ Users see queue position and ETA
- ✅ Can plan around wait times
- ✅ Transparent system behavior

### **After Phase 3:**
- ✅ No polling needed
- ✅ Instant notifications
- ✅ Better integration with external systems

### **After Phase 4:**
- ✅ Production jobs prioritized
- ✅ Testing doesn't block production
- ✅ Fair resource allocation

---

## 🔧 Implementation Priority

| Phase | Time | Impact | Priority |
|-------|------|--------|----------|
| **Phase 1: Fix 503 bug** | 5 min | 🔴 **CRITICAL** | **DO NOW** |
| Phase 2: Queue visibility | 30 min | 🟡 High | Next |
| Phase 3: Webhooks | 1 hour | 🟢 Medium | Soon |
| Phase 4: Priority queue | 2 hours | 🟢 Medium | Later |

---

## 📝 Testing Plan

### **Test 1: Multiple Jobs**
```bash
# Submit 5 jobs rapidly
for i in {1..5}; do
  curl -X POST http://localhost:4080/v1/batches \
    -H "Content-Type: application/json" \
    -d @job_$i.json
done

# Expected: All return 200 OK
# Worker processes sequentially
```

### **Test 2: Queue Full**
```bash
# Submit 21 jobs
for i in {1..21}; do
  curl -X POST http://localhost:4080/v1/batches ...
done

# Expected: First 20 return 200 OK, 21st returns 429
```

### **Test 3: Worker Offline**
```bash
# Kill worker
pkill -f "python -m core.batch_app.worker"

# Wait 61 seconds (heartbeat timeout)

# Submit job
curl -X POST http://localhost:4080/v1/batches ...

# Expected: 503 "Worker offline (last seen 61s ago)"
```

---

**Ready to implement Phase 1 (5 minutes) to fix the immediate issue?**

