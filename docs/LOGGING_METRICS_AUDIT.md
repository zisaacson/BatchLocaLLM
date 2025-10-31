# Logging & Metrics Audit

**Production-ready logging and monitoring for vLLM Batch Server**

---

## 📊 Current State: B+ (Good, but needs improvements)

### **✅ What's Good:**

1. **Prometheus Metrics** ✅
   - `/metrics` endpoint exists
   - Tracks batch jobs, requests, GPU metrics
   - Prometheus + Grafana configured

2. **Basic Logging** ✅
   - Logs to stdout
   - Optional file logging
   - Timestamp + level + message

3. **GPU Monitoring** ✅
   - pynvml integration
   - Temperature + memory tracking
   - Health checks

4. **Infrastructure** ✅
   - Prometheus + Grafana + Loki in docker-compose
   - Promtail for log aggregation

### **❌ What's Missing:**

1. **Structured Logging** ❌
   - Currently: Plain text logs
   - Should be: JSON structured logs

2. **Log Levels Not Used Properly** ❌
   - Most logs are `print()` statements
   - Should use `logger.info()`, `logger.error()`

3. **No Request Tracing** ❌
   - Can't trace a single request through system
   - Should have: Request IDs, correlation IDs

4. **No Error Tracking** ❌
   - No Sentry/Rollbar integration
   - Errors just logged, not tracked

5. **Metrics Not Comprehensive** ❌
   - Missing: Request duration, queue depth, throughput
   - Should track: P50/P95/P99 latencies

---

## 🎯 Recommendations

### **Priority 1: Structured Logging (IMPLEMENTED)**

**Status:** ✅ **DONE** - See `core/batch_app/logging_config.py`

**What it does:**
- JSON structured logs for easy parsing
- Request ID tracking
- Batch ID tracking
- Integration with Loki/Grafana

**Usage:**
```python
from core.batch_app.logging_config import get_logger, set_request_context

logger = get_logger(__name__)

# Set context
set_request_context(request_id="req_123", batch_id="batch_456")

# Log with structured data
logger.info("Processing batch", extra={
    "requests": 5000,
    "model": "gemma-3-4b",
    "chunk_size": 5000
})
```

**Output:**
```json
{
  "timestamp": "2025-10-31T12:34:56Z",
  "level": "INFO",
  "logger": "core.batch_app.worker",
  "message": "Processing batch",
  "request_id": "req_123",
  "batch_id": "batch_456",
  "requests": 5000,
  "model": "gemma-3-4b",
  "chunk_size": 5000
}
```

---

### **Priority 2: Replace `print()` with `logger` (TODO)**

**Current:**
```python
print(f"✅ Model loaded in {load_time:.1f}s")
```

**Should be:**
```python
logger.info("Model loaded", extra={"load_time_seconds": load_time})
```

**Files to update:**
- `core/batch_app/worker.py` - 50+ print statements
- `core/batch_app/api_server.py` - 20+ print statements
- `core/batch_app/benchmarks.py` - 10+ print statements

**Effort:** 2-3 hours  
**Impact:** High (enables proper log filtering, structured parsing)

---

### **Priority 3: Add Request Tracing (TODO)**

**What:** Add request IDs to track requests through the system

**Implementation:**
```python
# In api_server.py
from core.batch_app.logging_config import set_request_context
import uuid

@app.post("/v1/batches")
async def create_batch(...):
    request_id = str(uuid.uuid4())
    set_request_context(request_id=request_id, batch_id=batch_id)
    
    logger.info("Batch created", extra={"requests": len(requests)})
    # All subsequent logs will include request_id and batch_id
```

**Effort:** 1-2 hours  
**Impact:** High (enables request tracing in Grafana)

---

### **Priority 4: Comprehensive Metrics (TODO)**

**Current Metrics:**
- Batch job counts (queued, processing, completed, failed)
- Request counts (total, completed, failed)
- GPU metrics (memory, temperature)
- File metrics (count, bytes)

**Missing Metrics:**
- **Request Duration** - How long each request takes
- **Queue Depth** - How many jobs waiting
- **Throughput** - Requests/second
- **Latency Percentiles** - P50, P95, P99
- **Model Load Time** - Time to load models
- **Chunk Processing Time** - Time per chunk

**Implementation:**
```python
# Add to api_server.py
from prometheus_client import Histogram, Gauge

# Define metrics
request_duration = Histogram(
    'vllm_request_duration_seconds',
    'Request processing duration',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

queue_depth = Gauge(
    'vllm_queue_depth',
    'Number of jobs in queue'
)

# Use metrics
with request_duration.time():
    process_request()

queue_depth.set(len(pending_jobs))
```

**Effort:** 3-4 hours  
**Impact:** High (enables performance monitoring)

---

### **Priority 5: Error Tracking (OPTIONAL)**

**What:** Integrate Sentry for error tracking

**Why:**
- Automatic error grouping
- Stack traces with context
- Email/Slack notifications
- Error trends over time

**Implementation:**
```python
# Install
pip install sentry-sdk

# In api_server.py
import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1  # 10% of requests
    )
```

**Effort:** 1 hour  
**Impact:** Medium (nice to have for production)

---

## 📈 Open Source Standards Comparison

### **Industry Best Practices:**

| Feature | Current | Industry Standard | Gap |
|---------|---------|-------------------|-----|
| Structured Logging | ✅ Implemented | ✅ JSON logs | ✅ Done |
| Log Levels | ❌ print() | ✅ logger.info() | ❌ TODO |
| Request Tracing | ❌ None | ✅ Request IDs | ❌ TODO |
| Metrics | ⚠️ Basic | ✅ Comprehensive | ⚠️ Partial |
| Error Tracking | ❌ None | ⚠️ Optional | ⚠️ Optional |
| Distributed Tracing | ❌ None | ⚠️ Optional | ⚠️ Optional |

**Legend:**
- ✅ = Meets standard
- ⚠️ = Partial / Optional
- ❌ = Missing

---

## 🚀 Implementation Plan

### **Phase 1: Structured Logging (DONE)**
- [x] Create `logging_config.py`
- [x] Implement JSON formatter
- [x] Add request context tracking
- [ ] Update all `print()` to `logger.*()` calls

### **Phase 2: Request Tracing (TODO)**
- [ ] Add request ID generation
- [ ] Add middleware for request context
- [ ] Update all endpoints to use context
- [ ] Test in Grafana

### **Phase 3: Comprehensive Metrics (TODO)**
- [ ] Add duration metrics
- [ ] Add queue depth metrics
- [ ] Add throughput metrics
- [ ] Add latency percentiles
- [ ] Create Grafana dashboards

### **Phase 4: Error Tracking (OPTIONAL)**
- [ ] Add Sentry integration
- [ ] Configure error grouping
- [ ] Set up notifications
- [ ] Test error reporting

---

## 📊 Grafana Dashboard Examples

### **Dashboard 1: Batch Processing**
- Batch jobs over time (queued, processing, completed, failed)
- Request throughput (requests/second)
- Average processing time per batch
- Queue depth over time

### **Dashboard 2: GPU Monitoring**
- GPU memory utilization
- GPU temperature
- Model load times
- Inference throughput (tokens/second)

### **Dashboard 3: System Health**
- API response times (P50, P95, P99)
- Error rate
- Worker heartbeats
- Database query times

---

## 🔧 Configuration

### **Development:**
```bash
# .env
LOG_LEVEL=INFO
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE=  # stdout only
ENABLE_PROMETHEUS=true
```

### **Production:**
```bash
# .env
LOG_LEVEL=WARNING
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE=/var/log/vllm/app.log
ENABLE_PROMETHEUS=true
SENTRY_DSN=https://your-sentry-dsn
```

---

## 📝 Example Usage

### **Before (Current):**
```python
print(f"✅ Model loaded in {load_time:.1f}s")
print(f"Processing batch {batch_id}")
print(f"❌ Failed to process: {e}")
```

### **After (Recommended):**
```python
from core.batch_app.logging_config import get_logger, set_request_context

logger = get_logger(__name__)

# Set context
set_request_context(batch_id=batch_id)

# Structured logging
logger.info("Model loaded", extra={"load_time_seconds": load_time})
logger.info("Processing batch", extra={"requests": 5000})
logger.error("Failed to process", exc_info=True, extra={"error": str(e)})
```

---

## ✅ Checklist for Production

- [x] Structured logging implemented
- [ ] All `print()` replaced with `logger.*()` 
- [ ] Request tracing added
- [ ] Comprehensive metrics added
- [ ] Grafana dashboards created
- [ ] Error tracking configured (optional)
- [ ] Log rotation configured
- [ ] Monitoring alerts configured

---

## 🎯 Recommendation Summary

### **Do Now (High Priority):**
1. ✅ **Structured Logging** - Already implemented
2. ❌ **Replace print() with logger** - 2-3 hours, high impact
3. ❌ **Add Request Tracing** - 1-2 hours, high impact

### **Do Soon (Medium Priority):**
4. ❌ **Comprehensive Metrics** - 3-4 hours, high impact
5. ❌ **Grafana Dashboards** - 2-3 hours, medium impact

### **Do Later (Low Priority):**
6. ❌ **Error Tracking (Sentry)** - 1 hour, optional
7. ❌ **Distributed Tracing** - 4-6 hours, optional

**Total Effort:** 10-15 hours for full production-ready logging/metrics

---

## 📚 Resources

- **Structured Logging:** `core/batch_app/logging_config.py`
- **Prometheus Metrics:** `core/batch_app/api_server.py` (line 464)
- **Grafana Config:** `monitoring/grafana/`
- **Prometheus Config:** `monitoring/prometheus.yml`

---

**Questions?** See `core/README.md` or open an issue on GitHub.

