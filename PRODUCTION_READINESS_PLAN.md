# Production Readiness Plan - vLLM Batch Server
**Date:** 2025-10-29  
**Goal:** Handle 200K+ batch jobs from web app without straining desktop, with durability

---

## Executive Summary

### Current State: 3/10 Production Ready ⚠️

**What Works:**
- ✅ vLLM handles batching automatically (2,511 tok/s on 5K requests)
- ✅ FastAPI server accepts jobs
- ✅ SQLite queue with background worker
- ✅ Web UI for viewing results
- ✅ Benchmark integration

**Critical Gaps:**
- ❌ No chunking for 200K requests (will OOM)
- ❌ No incremental saves (crash = lose all progress)
- ❌ No queue limits (can accept unlimited jobs)
- ❌ No dead letter queue (failed requests lost)
- ❌ No resource management (can kill GPU)
- ❌ No monitoring/recovery (worker can die silently)

---

## Conversation Review & Audit

### What We Discussed

1. **System Evolution** ✅ DONE
   - Unified web UI design system
   - Standardized dataset representation
   - Fixed duplicate dataset display
   - All viewers now parse evaluation criteria

2. **Batch System Audit** ✅ DONE
   - Created `BATCH_SYSTEM_AUDIT.md`
   - Identified 7 critical gaps
   - Scored system 3/10 for production readiness

3. **vLLM Batching Clarification** ✅ CONFIRMED
   - vLLM handles batching automatically
   - We only need chunking for memory management (not batching efficiency)
   - 5K requests work perfectly
   - 200K requests need chunking to avoid OOM

4. **UI Dataset Fix** ✅ DONE
   - Collapsed duplicate batch files by base name
   - `batch_5k_*.jsonl` → all show under `batch_5k.jsonl`
   - Model names extracted and displayed

### What We Built

**Files Created:**
- `static/css/shared.css` - Unified design system
- `static/js/parsers.js` - Shared parsing functions
- `WEB_VIEWER_AUDIT_AND_STANDARDIZATION.md` - System audit
- `SYSTEM_EVOLUTION_COMPLETE.md` - Evolution summary
- `BATCH_SYSTEM_AUDIT.md` - Production readiness audit

**Files Updated:**
- `index.html` - Light theme, dataset grouping
- `table_view.html` - Already had updates
- `compare_results.html` - Light theme, JSON parsing
- `view_results.html` - Light theme, JSON parsing
- `compare_models.html` - Light theme integration
- `serve_results.py` - Dataset grouping logic

**Files Deleted:**
- `compare_models_v2.html` - Duplicate
- `view_results_improved.html` - Temporary

### What We Learned

**From Benchmarks:**
- vLLM can process 5K requests in 36 minutes (2,511 tok/s)
- Memory usage is CONSTANT (~11 GiB) regardless of batch size
- vLLM uses continuous batching (no manual chunking needed for efficiency)
- 200K requests would take ~24 hours on RTX 4080 16GB

**From Code Review:**
- Current worker processes entire batch at once: `outputs = self.current_llm.generate(prompts, sampling_params)`
- No incremental saves - writes results only at end
- No error handling per request
- No GPU health checks

---

## The Plan: Production-Ready Batch System

### Phase 1: Critical Fixes (MUST DO) 🔥

**Priority:** Prevent data loss and system crashes

#### 1.1 Intelligent Chunking for Memory Management

**Problem:** 200K requests will OOM the GPU  
**Solution:** Chunk into 5K pieces, let vLLM batch within each chunk

```python
# batch_app/worker.py
CHUNK_SIZE = 5000  # Safe size based on 5K benchmark

def process_job_chunked(self, job: BatchJob, db: Session):
    """Process job in chunks to avoid OOM."""
    
    # Load all requests
    requests = load_requests(job.input_file)
    total = len(requests)
    
    # Get resume point (if job was interrupted)
    completed = count_completed_results(job.output_file)
    if completed > 0:
        self.log(log_file, f"📍 Resuming from request {completed + 1}")
        requests = requests[completed:]
    
    # Process in chunks
    for chunk_start in range(0, len(requests), CHUNK_SIZE):
        chunk_end = min(chunk_start + CHUNK_SIZE, len(requests))
        chunk = requests[chunk_start:chunk_end]
        
        self.log(log_file, f"⚡ Processing chunk {chunk_start}-{chunk_end} of {total}")
        
        # vLLM handles batching within this chunk
        outputs = self.current_llm.generate(chunk_prompts, sampling_params)
        
        # Save incrementally (see next section)
        save_chunk_results(outputs, job.output_file, append=True)
        
        # Update progress
        job.completed_requests += len(outputs)
        db.commit()
```

**Impact:** Can handle 200K requests without OOM

---

#### 1.2 Incremental Saves with Resume Capability

**Problem:** Crash after 20 hours = lose everything  
**Solution:** Append results as we process, resume from checkpoint

```python
def save_chunk_results(outputs, output_file, requests, start_idx):
    """Save results incrementally in append mode."""
    with open(output_file, 'a') as f:  # APPEND mode!
        for i, output in enumerate(outputs):
            result = format_result(output, requests[start_idx + i])
            f.write(json.dumps(result) + '\n')
            f.flush()  # Force write to disk immediately

def count_completed_results(output_file):
    """Count how many results already saved (for resume)."""
    if not os.path.exists(output_file):
        return 0
    with open(output_file) as f:
        return sum(1 for _ in f)

def resume_job(job, db):
    """Resume interrupted job from last checkpoint."""
    completed = count_completed_results(job.output_file)
    if completed > 0:
        job.status = 'running'  # Change from 'failed' to 'running'
        job.completed_requests = completed
        db.commit()
        return completed
    return 0
```

**Impact:** Can resume 200K job after crash, no data loss

---

#### 1.3 Queue Limits & Resource Checks

**Problem:** Can accept 10 jobs × 200K = 2M queued requests  
**Solution:** Validate before accepting jobs

```python
# batch_app/api_server.py
MAX_REQUESTS_PER_JOB = 50000  # Match OpenAI limit
MAX_QUEUE_DEPTH = 5  # Max concurrent jobs
MAX_TOTAL_QUEUED_REQUESTS = 100000

@app.post("/v1/batches")
async def create_batch(file: UploadFile, model: str, db: Session = Depends(get_db)):
    # Count pending jobs
    pending_jobs = db.query(BatchJob).filter(
        BatchJob.status.in_(['pending', 'running'])
    ).all()
    
    # Check queue depth
    if len(pending_jobs) >= MAX_QUEUE_DEPTH:
        raise HTTPException(
            status_code=429,
            detail=f"Queue full ({len(pending_jobs)} jobs). Try again later."
        )
    
    # Check total queued requests
    total_queued = sum(j.total_requests - j.completed_requests for j in pending_jobs)
    if total_queued >= MAX_TOTAL_QUEUED_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many queued requests ({total_queued}). Try again later."
        )
    
    # Validate job size
    num_requests = count_requests(file)
    if num_requests > MAX_REQUESTS_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Max {MAX_REQUESTS_PER_JOB} requests per job (got {num_requests})"
        )
    
    # Check GPU health before accepting
    gpu_status = check_gpu_health()
    if not gpu_status['healthy']:
        raise HTTPException(
            status_code=503,
            detail=f"GPU unhealthy: {gpu_status['reason']}"
        )
    
    # Accept job
    # ... rest of code
```

**Impact:** Prevents queue explosion and GPU overload

---

### Phase 2: Reliability (SHOULD DO) 🛡️

**Priority:** Handle failures gracefully

#### 2.1 Dead Letter Queue for Failed Requests

```python
# batch_app/database.py
class FailedRequest(Base):
    __tablename__ = 'failed_requests'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(64), ForeignKey('batch_jobs.batch_id'))
    custom_id = Column(String(256))
    request_index = Column(Integer)
    error_message = Column(Text)
    error_type = Column(String(64))
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_retry_at = Column(DateTime, nullable=True)

# batch_app/worker.py
def process_chunk_with_error_handling(chunk, job, db):
    """Process chunk with per-request error handling."""
    results = []
    
    for i, request in enumerate(chunk):
        try:
            # Process single request
            output = self.current_llm.generate([request_prompt], sampling_params)[0]
            results.append(format_result(output, request))
            job.completed_requests += 1
            
        except Exception as e:
            # Log to dead letter queue
            failed_req = FailedRequest(
                batch_id=job.batch_id,
                custom_id=request['custom_id'],
                request_index=i,
                error_message=str(e),
                error_type=type(e).__name__,
                retry_count=0
            )
            db.add(failed_req)
            job.failed_requests += 1
            
            self.log(log_file, f"❌ Request {request['custom_id']} failed: {e}")
        
        # Commit after each request (durability)
        db.commit()
    
    return results
```

**Impact:** Failed requests tracked, can retry later

---

#### 2.2 GPU Resource Management

```python
import pynvml

def check_gpu_health():
    """Check GPU memory and temperature."""
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Memory
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_percent = (mem_info.used / mem_info.total) * 100
        
        # Temperature
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        
        # Health check
        healthy = mem_percent < 95 and temp < 85
        reason = None
        if mem_percent >= 95:
            reason = f"GPU memory at {mem_percent:.1f}%"
        if temp >= 85:
            reason = f"GPU temperature at {temp}°C"
        
        return {
            'healthy': healthy,
            'reason': reason,
            'memory_percent': mem_percent,
            'temperature_c': temp
        }
    except Exception as e:
        return {'healthy': False, 'reason': f"GPU check failed: {e}"}

def calculate_safe_chunk_size(gpu_status):
    """Adjust chunk size based on available GPU memory."""
    mem_percent = gpu_status['memory_percent']
    
    if mem_percent < 70:
        return 5000  # Plenty of room
    elif mem_percent < 80:
        return 3000  # Getting full
    elif mem_percent < 90:
        return 1000  # Very full
    else:
        return 500   # Critical
```

**Impact:** Prevents GPU crashes, adapts to conditions

---

### Phase 3: Monitoring & Recovery (NICE TO HAVE) 📊

**Priority:** Visibility and automation

#### 3.1 Worker Heartbeat & Health Checks

```python
# batch_app/database.py
class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeat'
    id = Column(Integer, primary_key=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    current_job_id = Column(String(64), nullable=True)
    gpu_memory_percent = Column(Float)
    gpu_temperature = Column(Float)
    status = Column(String(32))  # 'idle', 'processing', 'error'

# batch_app/worker.py - in main loop
def update_heartbeat(db, job_id=None, status='idle'):
    gpu_status = check_gpu_health()
    heartbeat = db.query(WorkerHeartbeat).first()
    if not heartbeat:
        heartbeat = WorkerHeartbeat()
        db.add(heartbeat)
    
    heartbeat.last_seen = datetime.utcnow()
    heartbeat.current_job_id = job_id
    heartbeat.gpu_memory_percent = gpu_status['memory_percent']
    heartbeat.gpu_temperature = gpu_status['temperature_c']
    heartbeat.status = status
    db.commit()

# batch_app/api_server.py
@app.get("/health/worker")
async def worker_health(db: Session = Depends(get_db)):
    heartbeat = db.query(WorkerHeartbeat).first()
    if not heartbeat:
        return {"status": "unknown", "message": "Worker never started"}
    
    age = (datetime.utcnow() - heartbeat.last_seen).total_seconds()
    if age > 60:
        return {"status": "dead", "last_seen": age, "message": "Worker not responding"}
    
    return {
        "status": "healthy",
        "current_job": heartbeat.current_job_id,
        "gpu_memory": heartbeat.gpu_memory_percent,
        "gpu_temp": heartbeat.gpu_temperature
    }
```

**Impact:** Know when worker dies, can restart manually

---

## Implementation Roadmap

### Week 1: Critical Fixes (Phase 1)
- [ ] Day 1-2: Implement chunking with resume capability
- [ ] Day 3: Add incremental saves
- [ ] Day 4: Add queue limits and validation
- [ ] Day 5: Test with 10K batch, then 50K batch

### Week 2: Reliability (Phase 2)
- [ ] Day 1-2: Implement dead letter queue
- [ ] Day 3: Add GPU resource management
- [ ] Day 4-5: Test with 200K batch (24 hour run)

### Week 3: Monitoring (Phase 3)
- [ ] Day 1-2: Add worker heartbeat
- [ ] Day 3: Add health check endpoints
- [ ] Day 4-5: Integration testing

---

## Success Criteria

**After Phase 1 (Critical):**
- ✅ Can process 200K requests without OOM
- ✅ Can resume after crash
- ✅ Won't accept jobs that will kill system

**After Phase 2 (Reliability):**
- ✅ Failed requests tracked and retryable
- ✅ GPU health monitored
- ✅ System adapts to resource constraints

**After Phase 3 (Monitoring):**
- ✅ Know when worker is alive/dead
- ✅ Can see current job progress
- ✅ GPU metrics visible

---

## Resource Requirements (Desktop-Friendly)

**Current System:**
- RTX 4080 16GB
- Processes 5K in 36 min (2,511 tok/s)
- Memory usage: ~11 GiB (constant)

**With Chunking:**
- Same hardware
- Same throughput
- Can handle 200K in ~24 hours
- No additional strain (just longer runtime)

**Recommendations:**
1. Run overnight for large batches
2. Set `MAX_QUEUE_DEPTH = 1` to prevent concurrent jobs
3. Monitor GPU temp (should stay <80°C)
4. Use `gpu_memory_utilization=0.85` instead of 0.90 for safety

---

## Next Steps

1. **Review this plan** - Does it address your concerns?
2. **Prioritize phases** - Do all 3 phases, or just Phase 1?
3. **Start implementation** - Begin with chunking + incremental saves?

**Estimated Time:**
- Phase 1 (Critical): 5 days
- Phase 2 (Reliability): 5 days
- Phase 3 (Monitoring): 5 days
- **Total: 3 weeks to production-ready**

---

**Status:** Ready to implement  
**Risk Level:** Low (building on proven vLLM foundation)  
**Confidence:** High (based on successful 5K benchmark)

