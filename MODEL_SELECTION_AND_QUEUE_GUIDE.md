# Model Selection and Queue Processing Guide
**Date:** October 30, 2025  
**Scenario:** 200K candidates on Qwen3, then 200K candidates on Gemma3

---

## 🎯 How End Users Choose Models

### **Method 1: Web UI** (Recommended for most users)

**URL:** `http://localhost:8001/submit_batch.html`

**Steps:**
1. User opens submit batch page
2. Selects JSONL file with candidates
3. **Chooses model from dropdown** (populated from `/v1/models` API)
4. Clicks "Submit Batch"

**Available Models** (auto-populated):
- `Qwen/Qwen2.5-3B-Instruct`
- `google/gemma-3-4b-it`
- `meta-llama/Llama-3.2-3B-Instruct`
- `meta-llama/Llama-3.2-1B-Instruct`

**UI Code:**
```html
<select id="modelSelect" class="form-select" required>
    <option value="">Loading models...</option>
    <!-- Populated via JavaScript from /v1/models -->
</select>
```

---

### **Method 2: REST API** (For programmatic access)

**Endpoint:** `POST http://localhost:4080/v1/batches`

**Request:**
```bash
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@candidates_200k.jsonl" \
  -F "model=Qwen/Qwen2.5-3B-Instruct" \
  -F "webhook_url=https://myapp.com/webhook"
```

**Response:**
```json
{
  "batch_id": "batch_a1b2c3d4e5f6g7h8",
  "status": "pending",
  "model": "Qwen/Qwen2.5-3B-Instruct",
  "total_requests": 200000,
  "estimated_completion_time": "2025-10-30T12:00:00Z",
  "queue_position": 1
}
```

---

## 🔄 How the System Handles Multiple Models

### **Scenario: 200K Qwen3 → 200K Gemma3**

**Timeline:**

```
T=0:00:00  User submits Job 1: 200K candidates, model=Qwen3
           → Status: pending
           → Queue position: 1

T=0:00:05  User submits Job 2: 200K candidates, model=Gemma3
           → Status: pending
           → Queue position: 2

T=0:00:10  Worker picks Job 1 (FIFO order)
           → Status: running
           → Loads Qwen3 (34.9s)

T=0:00:45  Qwen3 loaded, processing starts
           → Processing 200K requests in 5K chunks
           → 40 chunks total (200K / 5K = 40)

T=3:00:00  Job 1 completes (~3 hours for 200K @ 18 req/s)
           → Status: completed
           → Unloads Qwen3
           → 2-second cooldown

T=3:00:02  Worker picks Job 2 (next in queue)
           → Status: running
           → Loads Gemma3 (28.1s)

T=3:00:30  Gemma3 loaded, processing starts
           → Processing 200K requests in 5K chunks

T=4:30:00  Job 2 completes (~1.5 hours for 200K @ 37 req/s)
           → Status: completed
           → Total time: ~4.5 hours
```

---

## 📊 Queue Processing Logic

### **FIFO Queue (First In, First Out)**

**Code:** `batch_app/worker.py` lines 102-106

```python
def get_next_pending_job(self, db: Session) -> Optional[BatchJob]:
    """Get the next pending job from the queue."""
    return db.query(BatchJob).filter(
        BatchJob.status == 'pending'
    ).order_by(BatchJob.created_at).first()  # ← FIFO: oldest first
```

**Key Points:**
- ✅ Jobs processed in **submission order** (created_at timestamp)
- ✅ **One job at a time** (single GPU, single worker)
- ✅ **Automatic model switching** between jobs
- ✅ **No manual intervention** required

---

## 🔧 Hot-Swapping Between Jobs

### **Automatic Model Switching**

**Code:** `batch_app/worker.py` lines 187-214

```python
def load_model(self, model: str, log_file):
    """Load vLLM model with hot-swapping support."""
    
    # Unload previous model if exists
    if self.current_llm is not None:
        self.log(log_file, f"Unloading previous model: {self.current_model}")
        del self.current_llm
        self.current_llm = None
        self.current_model = None
        time.sleep(2)  # Give GPU time to free memory
    
    # Load new model
    start_time = time.time()
    self.current_llm = LLM(
        model=model,
        max_model_len=4096,
        gpu_memory_utilization=0.85,
        disable_log_stats=True,
    )
    load_time = time.time() - start_time
    
    self.current_model = model
    self.log(log_file, f"✅ Model loaded in {load_time:.1f}s")
```

**Process:**
1. Worker checks if current model matches job model
2. If different: unload old model → 2s cooldown → load new model
3. If same: reuse loaded model (no reload needed)

---

## ⏱️ Performance Estimates

### **200K Candidates per Model**

| Model | Throughput | Time per 200K | Load Time | Total Time |
|-------|------------|---------------|-----------|------------|
| **Qwen3 4B** | ~18 req/s | ~3.1 hours | 34.9s | **3.1 hours** |
| **Gemma3 4B** | ~37 req/s | ~1.5 hours | 28.1s | **1.5 hours** |

### **Sequential Processing (200K Qwen3 → 200K Gemma3)**

```
Job 1 (Qwen3):
  Load time:       35 seconds
  Processing:      3.1 hours (11,111 seconds)
  Total:           3.1 hours

Swap overhead:     2 seconds (cooldown)

Job 2 (Gemma3):
  Load time:       28 seconds
  Processing:      1.5 hours (5,405 seconds)
  Total:           1.5 hours

GRAND TOTAL:       4.6 hours (16,581 seconds)
```

**Swap overhead:** 65 seconds / 16,581 seconds = **0.4%** (negligible)

---

## 🚦 Queue Limits

### **System Limits** (configured in `batch_app/api_server.py`)

```python
MAX_REQUESTS_PER_JOB = 50_000      # Max requests per single job
MAX_QUEUE_DEPTH = 10               # Max pending/running jobs
MAX_TOTAL_QUEUED_REQUESTS = 500_000  # Max total queued requests
```

### **For 200K Candidates:**

**Option 1: Split into 4 jobs of 50K each**
```bash
# Submit 4 jobs for Qwen3
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@qwen3_batch_1.jsonl" -F "model=Qwen/Qwen2.5-3B-Instruct"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@qwen3_batch_2.jsonl" -F "model=Qwen/Qwen2.5-3B-Instruct"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@qwen3_batch_3.jsonl" -F "model=Qwen/Qwen2.5-3B-Instruct"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@qwen3_batch_4.jsonl" -F "model=Qwen/Qwen2.5-3B-Instruct"

# Submit 4 jobs for Gemma3
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@gemma3_batch_1.jsonl" -F "model=google/gemma-3-4b-it"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@gemma3_batch_2.jsonl" -F "model=google/gemma-3-4b-it"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@gemma3_batch_3.jsonl" -F "model=google/gemma-3-4b-it"
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@gemma3_batch_4.jsonl" -F "model=google/gemma-3-4b-it"
```

**Queue order:**
1. Qwen3 batch 1 (50K) - processes first
2. Qwen3 batch 2 (50K) - processes second (no model reload!)
3. Qwen3 batch 3 (50K) - processes third (no model reload!)
4. Qwen3 batch 4 (50K) - processes fourth (no model reload!)
5. **HOT-SWAP** (unload Qwen3, load Gemma3)
6. Gemma3 batch 1 (50K) - processes fifth
7. Gemma3 batch 2 (50K) - processes sixth (no model reload!)
8. Gemma3 batch 3 (50K) - processes seventh (no model reload!)
9. Gemma3 batch 4 (50K) - processes eighth (no model reload!)

**Total hot-swaps:** 1 (only between Qwen3 and Gemma3)

---

## 📈 Optimization: Batch Same Models Together

### **Best Practice:**

**✅ GOOD:** Submit all Qwen3 jobs first, then all Gemma3 jobs
```
Queue: [Qwen3, Qwen3, Qwen3, Qwen3, Gemma3, Gemma3, Gemma3, Gemma3]
Hot-swaps: 1 (Qwen3 → Gemma3)
```

**❌ BAD:** Alternate between models
```
Queue: [Qwen3, Gemma3, Qwen3, Gemma3, Qwen3, Gemma3, Qwen3, Gemma3]
Hot-swaps: 7 (constant reloading!)
Overhead: 7 × 65s = 455 seconds wasted
```

---

## 🔍 Monitoring Queue Status

### **Check Queue via API:**

```bash
curl http://localhost:4080/v1/batches
```

**Response:**
```json
{
  "batches": [
    {
      "batch_id": "batch_abc123",
      "model": "Qwen/Qwen2.5-3B-Instruct",
      "status": "running",
      "total_requests": 50000,
      "completed_requests": 12500,
      "progress_percent": 25.0
    },
    {
      "batch_id": "batch_def456",
      "model": "Qwen/Qwen2.5-3B-Instruct",
      "status": "pending",
      "total_requests": 50000,
      "completed_requests": 0,
      "progress_percent": 0.0
    },
    {
      "batch_id": "batch_ghi789",
      "model": "google/gemma-3-4b-it",
      "status": "pending",
      "total_requests": 50000,
      "completed_requests": 0,
      "progress_percent": 0.0
    }
  ],
  "count": 3
}
```

### **Check Queue via Web UI:**

**URL:** `http://localhost:8001/dashboard.html`

Shows:
- Current running job
- Queue position
- Estimated completion time
- GPU status

---

## ✅ Summary

### **How Users Choose Models:**
1. **Web UI:** Select from dropdown on submit page
2. **API:** Specify `model` parameter in POST request

### **How System Handles 200K Qwen3 → 200K Gemma3:**
1. User submits 4×50K jobs with `model=Qwen3`
2. User submits 4×50K jobs with `model=Gemma3`
3. Worker processes in FIFO order (oldest first)
4. Automatically hot-swaps between Qwen3 and Gemma3
5. Total time: ~4.6 hours (0.4% swap overhead)

### **Key Features:**
- ✅ **FIFO queue** - Jobs processed in submission order
- ✅ **Automatic hot-swapping** - No manual intervention
- ✅ **Model reuse** - Same model jobs don't reload
- ✅ **Progress tracking** - Real-time status updates
- ✅ **Webhook notifications** - Alerts when jobs complete

### **Best Practice:**
**Group same-model jobs together** to minimize hot-swap overhead!

