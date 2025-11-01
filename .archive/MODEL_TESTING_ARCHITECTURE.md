# Model Testing & Hot-Swapping Architecture

**Date:** 2025-10-31  
**Status:** Critical Gap Identified - Needs Design  
**Priority:** High (blocks scalable open source adoption)

---

## 🚨 Current Problem

### **What Happens When Testing New Models?**

**Current Behavior:**
1. ❌ **Worker blocks the entire GPU** - When testing a new model, the worker loads it into GPU memory
2. ❌ **API server keeps accepting requests** - Users can still submit batch jobs via API
3. ❌ **New jobs queue up** - They sit in `validating` status waiting for the worker
4. ❌ **No visibility** - Users don't know the worker is busy testing a model
5. ❌ **No isolation** - Test workloads compete with production workloads

**Example Scenario:**
```
User A: Submits production batch (5K requests, Gemma 3 4B)
Admin: Starts testing OLMo 2 7B (loads model, runs test batch)
User B: Submits production batch (1K requests, Qwen 3 4B)

Result:
- User A's job: ✅ Completes normally
- Admin test: 🔄 Loads OLMo 2 7B (GPU now full)
- User B's job: ⏳ Queued, waiting indefinitely
- User B: 😡 No idea why their job isn't processing
```

### **Why This Is a Problem for Open Source**

1. **Multi-tenant environments** - Multiple users/teams sharing one GPU server
2. **Model experimentation** - Users want to test new models without disrupting others
3. **No queue management** - FIFO queue doesn't distinguish test vs production jobs
4. **No resource reservation** - Can't reserve GPU for testing
5. **No visibility** - No way to see "worker is testing a model, ETA 30 min"

---

## 🏗️ Current Architecture Analysis

### **Worker Model Loading** (`core/batch_app/worker.py`)

```python
def load_model(self, model: str, log_file: str | None):
    """Load vLLM model if not already loaded."""
    if self.current_model == model and self.current_llm is not None:
        self.log(log_file, f"✅ Model {model} already loaded, reusing")
        return

    # Unload previous model
    if self.current_llm is not None:
        del self.current_llm
        self.current_llm = None
        time.sleep(2)  # Give GPU time to free memory

    # Load new model
    self.current_llm = LLM(model=model, ...)
    self.current_model = model
```

**Issues:**
- ✅ Hot-swapping works (can switch models between jobs)
- ❌ No way to "pause" the worker
- ❌ No way to mark jobs as "test" vs "production"
- ❌ No priority queue
- ❌ Model loading blocks all other jobs

### **API Server** (`core/batch_app/api_server.py`)

```python
@app.post("/v1/batches")
@limiter.limit("10/minute")
async def create_batch(...):
    # Check GPU health
    gpu_status = check_gpu_health()
    if not gpu_status['healthy']:
        raise HTTPException(503, "GPU unhealthy")
    
    # Create job (always accepts if GPU healthy)
    job = BatchJob(...)
    db.add(job)
    return job
```

**Issues:**
- ✅ Checks GPU health before accepting
- ❌ Doesn't check if worker is busy testing
- ❌ Doesn't check queue depth
- ❌ No way to reject jobs during maintenance

### **Worker Heartbeat** (`core/batch_app/database.py`)

```python
class WorkerHeartbeat(Base):
    status: Mapped[str]  # idle, processing, error
    current_job_id: Mapped[str | None]
    gpu_memory_percent: Mapped[float | None]
    gpu_temperature: Mapped[float | None]
    last_seen: Mapped[datetime]
```

**Issues:**
- ✅ Tracks worker status
- ❌ No "testing" or "maintenance" status
- ❌ No ETA for current job
- ❌ No way to signal "don't accept new jobs"

---

## 💡 Proposed Solutions

### **Option 1: Maintenance Mode (Simple, Recommended for v1.0)**

**Concept:** Add a maintenance mode flag that pauses job acceptance

**Implementation:**
```python
# New table
class SystemStatus(Base):
    maintenance_mode: Mapped[bool] = False
    maintenance_reason: Mapped[str | None]  # "Testing OLMo 2 7B"
    maintenance_eta: Mapped[datetime | None]

# API server checks before accepting jobs
@app.post("/v1/batches")
async def create_batch(...):
    system_status = db.query(SystemStatus).first()
    if system_status.maintenance_mode:
        raise HTTPException(
            503,
            f"System in maintenance: {system_status.maintenance_reason}. "
            f"ETA: {system_status.maintenance_eta}"
        )
    # ... rest of logic
```

**Usage:**
```bash
# Admin starts testing
curl -X POST http://localhost:4080/admin/maintenance \
  -d '{"enabled": true, "reason": "Testing OLMo 2 7B", "eta": "30 minutes"}'

# Run tests
python core/tests/manual/test_olmo2_7b_single.py
python core/tests/manual/test_olmo2_7b_100.py

# Admin ends testing
curl -X POST http://localhost:4080/admin/maintenance \
  -d '{"enabled": false}'
```

**Pros:**
- ✅ Simple to implement (1-2 hours)
- ✅ Clear user communication
- ✅ Works for single-GPU setups
- ✅ No complex queue logic

**Cons:**
- ⚠️ Manual process (admin must remember to disable)
- ⚠️ Blocks all jobs (even if GPU has capacity)

---

### **Option 2: Job Priority Queue (Medium Complexity)**

**Concept:** Add priority levels to jobs, process high-priority first

**Implementation:**
```python
# Add to BatchJob
class BatchJob(Base):
    priority: Mapped[int] = 0  # 0=normal, 1=high, -1=test/low

# Worker gets next job by priority
def get_next_pending_job(self, db: Session):
    return db.query(BatchJob)\
        .filter(BatchJob.status == 'validating')\
        .order_by(BatchJob.priority.desc(), BatchJob.created_at)\
        .first()
```

**Usage:**
```python
# Production jobs (default priority=0)
batch = client.batches.create(input_file_id="file-123", ...)

# Test jobs (low priority=-1)
batch = client.batches.create(
    input_file_id="file-456",
    metadata={"priority": -1, "test": true}
)
```

**Pros:**
- ✅ Test jobs don't block production
- ✅ Automatic (no manual maintenance mode)
- ✅ Flexible (can have multiple priority levels)

**Cons:**
- ⚠️ Test jobs may never run if production is busy
- ⚠️ More complex queue logic
- ⚠️ Still no resource reservation

---

### **Option 3: Dedicated Test Worker (Complex, Multi-GPU)**

**Concept:** Run separate worker processes for production vs testing

**Implementation:**
```bash
# Production worker (GPU 0)
CUDA_VISIBLE_DEVICES=0 python -m core.batch_app.worker --queue=production

# Test worker (GPU 1 or CPU)
CUDA_VISIBLE_DEVICES=1 python -m core.batch_app.worker --queue=test
```

**Database:**
```python
class BatchJob(Base):
    queue: Mapped[str] = "production"  # production, test, dev

class WorkerHeartbeat(Base):
    worker_id: Mapped[str]  # production-worker-1, test-worker-1
    queue: Mapped[str]
```

**Pros:**
- ✅ Complete isolation (test never blocks production)
- ✅ Can use different GPUs or CPU for testing
- ✅ Scales to multi-GPU setups

**Cons:**
- ⚠️ Requires multiple GPUs or CPU fallback
- ⚠️ More complex deployment
- ⚠️ Overkill for single-GPU setups

---

### **Option 4: Time-Based Scheduling (Advanced)**

**Concept:** Reserve time slots for testing (e.g., "test window: 2-4 AM")

**Implementation:**
```python
class MaintenanceWindow(Base):
    start_time: Mapped[time]  # 02:00
    end_time: Mapped[time]    # 04:00
    days_of_week: Mapped[str]  # "0,6" (Sunday, Saturday)
    reason: Mapped[str]  # "Model testing window"

# API checks if in maintenance window
def is_maintenance_window() -> bool:
    now = datetime.now()
    windows = db.query(MaintenanceWindow).all()
    for window in windows:
        if window.start_time <= now.time() <= window.end_time:
            if str(now.weekday()) in window.days_of_week.split(','):
                return True
    return False
```

**Pros:**
- ✅ Predictable testing windows
- ✅ Automatic (no manual intervention)
- ✅ Good for shared resources

**Cons:**
- ⚠️ Inflexible (can't test outside window)
- ⚠️ Complex scheduling logic
- ⚠️ May not fit all use cases

---

## 🎯 Recommendation for vLLM Batch Server v1.0

### **Implement Option 1 (Maintenance Mode) + Option 2 (Priority Queue)**

**Why:**
1. **Maintenance Mode** - Simple, immediate solution for admins testing models
2. **Priority Queue** - Allows users to self-service test jobs without blocking production
3. **Combined** - Best of both worlds (manual control + automatic prioritization)

**Implementation Plan:**

### **Phase 1: Maintenance Mode (1-2 hours)**
```python
# 1. Add SystemStatus table
class SystemStatus(Base):
    id: Mapped[int] = 1  # Singleton
    maintenance_mode: Mapped[bool] = False
    maintenance_reason: Mapped[str | None]
    maintenance_started_at: Mapped[datetime | None]
    maintenance_eta_minutes: Mapped[int | None]

# 2. Add admin endpoint
@app.post("/admin/maintenance")
async def set_maintenance_mode(request: MaintenanceModeRequest):
    system_status = db.query(SystemStatus).first()
    system_status.maintenance_mode = request.enabled
    system_status.maintenance_reason = request.reason
    system_status.maintenance_eta_minutes = request.eta_minutes
    db.commit()
    return {"status": "ok"}

# 3. Check in create_batch
@app.post("/v1/batches")
async def create_batch(...):
    system_status = db.query(SystemStatus).first()
    if system_status.maintenance_mode:
        eta = system_status.maintenance_started_at + timedelta(
            minutes=system_status.maintenance_eta_minutes
        )
        raise HTTPException(
            503,
            f"System in maintenance: {system_status.maintenance_reason}. "
            f"Expected to resume at {eta.isoformat()}"
        )
```

### **Phase 2: Priority Queue (2-3 hours)**
```python
# 1. Add priority to BatchJob
class BatchJob(Base):
    priority: Mapped[int] = 0  # -1=test, 0=normal, 1=high

# 2. Update worker query
def get_next_pending_job(self, db: Session):
    return db.query(BatchJob)\
        .filter(BatchJob.status == 'validating')\
        .order_by(
            BatchJob.priority.desc(),  # High priority first
            BatchJob.created_at        # Then FIFO
        )\
        .first()

# 3. Allow priority in metadata
@app.post("/v1/batches")
async def create_batch(batch_request: CreateBatchRequest, ...):
    priority = batch_request.metadata.get("priority", 0)
    if priority not in [-1, 0, 1]:
        raise HTTPException(400, "Priority must be -1, 0, or 1")
    
    job = BatchJob(
        ...,
        priority=priority
    )
```

---

## 📋 Testing Workflow (After Implementation)

### **Scenario 1: Admin Testing New Model**
```bash
# 1. Enable maintenance mode
curl -X POST http://localhost:4080/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "enabled": true,
    "reason": "Testing OLMo 2 7B model",
    "eta_minutes": 45
  }'

# 2. Run progressive tests
python core/tests/manual/test_olmo2_7b_single.py    # 2 min
python core/tests/manual/test_olmo2_7b_100.py       # 5 min
bash scripts/test_olmo2_7b_5k_offline.sh            # 30 min

# 3. Disable maintenance mode
curl -X POST http://localhost:4080/admin/maintenance \
  -d '{"enabled": false}'
```

### **Scenario 2: User Testing Model (No Admin Access)**
```python
# Submit test job with low priority
batch = client.batches.create(
    input_file_id="file-test-123",
    endpoint="/v1/chat/completions",
    metadata={
        "priority": -1,  # Low priority (won't block production)
        "test": True,
        "model": "allenai/OLMo-2-1124-7B-Instruct"
    }
)

# Job will run when GPU is idle
# Production jobs (priority=0) will jump ahead
```

---

## 🚀 Future Enhancements (v2.0+)

1. **Multi-GPU Support** - Dedicated test worker on GPU 1
2. **Resource Quotas** - Limit test jobs to 20% of GPU time
3. **Scheduled Maintenance** - Automatic testing windows
4. **Model Registry Integration** - Mark models as "testing", "production", "deprecated"
5. **A/B Testing** - Run same batch through multiple models for comparison

---

## 📊 Impact on Open Source Adoption

**Before (Current):**
- ❌ Users can't test models without disrupting production
- ❌ No clear workflow for model evaluation
- ❌ Admins must manually coordinate testing
- ❌ Poor multi-user experience

**After (With Maintenance Mode + Priority Queue):**
- ✅ Clear testing workflow (maintenance mode for admins)
- ✅ Self-service testing (low-priority jobs for users)
- ✅ Production workloads protected
- ✅ Good multi-user experience
- ✅ Scales to teams (Parasail use case)

**Estimated Implementation Time:** 4-5 hours total
**Priority:** High (blocks scalable adoption)

