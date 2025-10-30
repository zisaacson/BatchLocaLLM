# Production Architecture: vLLM Batch Processing Server

## Overview

This document outlines the production architecture for a vLLM-based batch processing server to score 170K+ candidates efficiently.

---

## System Requirements

### Current Setup (Development)
- **GPU**: NVIDIA RTX 4080 16GB
- **vLLM**: v0.11.0 (V1 engine)
- **Python**: 3.9-3.12
- **Models**: 1B-4B parameter models

### Production Recommendations
- **GPU**: NVIDIA A100 40GB or H100 80GB (for larger models + higher throughput)
- **CPU**: 16+ cores
- **RAM**: 64GB+
- **Storage**: 500GB+ NVMe SSD (for model caching)

---

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Application (Aris)                  │
│                  (Candidate Database: 170K+)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP POST /batch
                         │ (JSONL batch file)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Batch Server                       │
│  - Receives batch job requests                              │
│  - Validates input                                           │
│  - Assigns job ID                                            │
│  - Queues job                                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Enqueue
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Job Queue (Redis)                       │
│  - Stores pending jobs                                       │
│  - Tracks job status                                         │
│  - Handles retries                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Dequeue
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   vLLM Batch Worker                          │
│  - Runs vllm.entrypoints.openai.run_batch                   │
│  - Processes batches offline                                 │
│  - Saves results incrementally                               │
│  - Updates job status                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Save results
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Results Storage (S3/MinIO)                 │
│  - Stores JSONL result files                                 │
│  - Versioned by job ID                                       │
│  - Accessible via presigned URLs                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Poll/Webhook
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Main Application (Aris)                  │
│  - Polls for job completion                                  │
│  - Downloads results                                         │
│  - Updates candidate scores                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## API Design

### 1. Submit Batch Job

**Endpoint**: `POST /v1/batch`

**Request**:
```json
{
  "model": "qwen3-4b",
  "input_file_url": "https://s3.../batch_input.jsonl",
  "webhook_url": "https://aris.app/webhooks/batch-complete",
  "metadata": {
    "job_name": "candidate_scoring_batch_1",
    "priority": "normal"
  }
}
```

**Response**:
```json
{
  "job_id": "batch_abc123",
  "status": "queued",
  "created_at": "2025-10-28T14:30:00Z",
  "estimated_completion": "2025-10-28T15:00:00Z"
}
```

### 2. Check Job Status

**Endpoint**: `GET /v1/batch/{job_id}`

**Response**:
```json
{
  "job_id": "batch_abc123",
  "status": "processing",
  "progress": {
    "completed": 1530,
    "total": 5000,
    "percent": 30.6
  },
  "throughput": {
    "req_per_sec": 3.36,
    "estimated_remaining": "17m 11s"
  },
  "created_at": "2025-10-28T14:30:00Z",
  "started_at": "2025-10-28T14:31:00Z",
  "estimated_completion": "2025-10-28T15:00:00Z"
}
```

### 3. Get Results

**Endpoint**: `GET /v1/batch/{job_id}/results`

**Response**:
```json
{
  "job_id": "batch_abc123",
  "status": "completed",
  "results_url": "https://s3.../batch_abc123_results.jsonl",
  "expires_at": "2025-11-04T14:30:00Z",
  "stats": {
    "total": 5000,
    "successful": 4998,
    "failed": 2,
    "avg_response_time": "0.3s"
  }
}
```

---

## Implementation Plan

### Phase 1: Core Batch Processing (Week 1)
- [x] vLLM offline batch mode working
- [x] Model name conversion script
- [x] Benchmark scripts for all models
- [ ] FastAPI server with job submission endpoint
- [ ] Redis job queue integration
- [ ] Worker process to consume jobs

### Phase 2: Monitoring & Reliability (Week 2)
- [ ] Grafana dashboard for GPU metrics
- [ ] Prometheus metrics export
- [ ] Job status tracking in Redis
- [ ] Retry logic for failed jobs
- [ ] Webhook notifications

### Phase 3: Scaling & Optimization (Week 3)
- [ ] Multi-GPU support (if needed)
- [ ] Model hot-swapping (switch models without restart)
- [ ] Batch size optimization
- [ ] Cost analysis dashboard
- [ ] Load testing with 170K candidates

### Phase 4: Production Deployment (Week 4)
- [ ] Docker containerization
- [ ] Kubernetes deployment (optional)
- [ ] CI/CD pipeline
- [ ] Backup & disaster recovery
- [ ] Documentation & runbooks

---

## Monitoring & Alerting

### Key Metrics to Track

1. **GPU Metrics**:
   - Utilization (%)
   - Memory usage (GB)
   - Temperature (°C)
   - Power consumption (W)

2. **Throughput Metrics**:
   - Requests per second
   - Tokens per second
   - Batch completion time
   - Queue depth

3. **Quality Metrics**:
   - Success rate (%)
   - Error rate (%)
   - Response validation failures
   - Recommendation distribution

4. **System Metrics**:
   - CPU usage
   - RAM usage
   - Disk I/O
   - Network I/O

### Alerts

- **Critical**:
  - GPU utilization < 50% for > 10 minutes (stuck job)
  - Error rate > 5%
  - Queue depth > 100 jobs
  - Disk space < 10%

- **Warning**:
  - GPU temperature > 80°C
  - Memory usage > 90%
  - Job completion time > 2x expected
  - No progress for > 5 minutes

---

## Cost Analysis

### Current Benchmarks (RTX 4080 16GB)

| Model | Speed (req/s) | Time for 170K | Cost (Self-Hosted) | Cost (Parasail) |
|-------|---------------|---------------|-------------------|-----------------|
| Qwen 3-4B | 3.36 | ~14 hours | $0 (electricity) | TBD |
| Gemma 3-4B | TBD | TBD | $0 (electricity) | TBD |
| Llama 3.2-3B | TBD | TBD | $0 (electricity) | TBD |
| Llama 3.2-1B | TBD | TBD | $0 (electricity) | TBD |

### Production Estimates (A100 40GB)

Assuming 2-3x throughput improvement:

| Model | Speed (req/s) | Time for 170K | Parasail Cost (est.) |
|-------|---------------|---------------|---------------------|
| Qwen 3-4B | ~8 | ~6 hours | $X |
| Gemma 3-4B | ~8 | ~6 hours | $Y |

**Note**: Fill in Parasail costs after benchmarking completes.

---

## Security Considerations

1. **API Authentication**:
   - API keys for job submission
   - JWT tokens for status checks
   - Rate limiting per API key

2. **Data Privacy**:
   - Encrypt batch files in transit (HTTPS)
   - Encrypt results at rest (S3 encryption)
   - Auto-delete results after 7 days

3. **Access Control**:
   - RBAC for different user roles
   - Audit logs for all API calls
   - IP whitelisting (optional)

---

## Disaster Recovery

1. **Job Checkpointing**:
   - Save progress every 100 requests
   - Store checkpoint in Redis
   - Resume from checkpoint on failure

2. **Backup Strategy**:
   - Daily backup of job queue state
   - Weekly backup of results storage
   - Model weights cached locally

3. **Failover**:
   - Health checks every 30 seconds
   - Auto-restart worker on failure
   - Alert on-call engineer if > 3 failures

---

## Next Steps

1. **Complete Benchmarks** (Today):
   - Finish Qwen 3-4B (in progress)
   - Run Gemma 3-4B
   - Run Llama 3.2-3B
   - Run Llama 3.2-1B

2. **Analyze Results** (Today):
   - Run `python3 analyze_benchmark_results.py`
   - Compare speed vs quality
   - Choose production model

3. **Build FastAPI Server** (Tomorrow):
   - Job submission endpoint
   - Status check endpoint
   - Results download endpoint

4. **Set Up Monitoring** (This Week):
   - Grafana dashboard
   - Prometheus metrics
   - Alerting rules

---

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM Offline Batch Guide](./VLLM_OFFLINE_BATCH_GUIDE.md)
- [Benchmark Results](./analyze_benchmark_results.py)

