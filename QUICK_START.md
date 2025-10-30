# Quick Start Guide - Production vLLM Batch Server

**Get your production-ready batch server running in 5 minutes!**

---

## Prerequisites

- Python 3.9-3.12
- NVIDIA GPU with 16GB+ VRAM
- vLLM installed (`pip install vllm`)
- FastAPI installed (`pip install fastapi uvicorn`)

---

## Step 1: Initialize Database

The database will be created automatically on first run, but you can initialize it manually:

```bash
python -c "from batch_app.database import init_db; init_db()"
```

**Expected output:**
```
✅ Database initialized at sqlite:///data/database/batch_jobs.db
```

---

## Step 2: Start API Server

```bash
python -m batch_app.api_server
```

**Expected output:**
```
✅ Batch API Server started
INFO:     Uvicorn running on http://0.0.0.0:8080
```

**Test it:**
```bash
curl http://localhost:8080/health
```

---

## Step 3: Start Worker (Separate Terminal)

```bash
python -m batch_app.worker
```

**Expected output:**
```
================================================================================
🚀 BATCH WORKER STARTED
================================================================================
Poll interval: 10s
Chunk size: 5000
GPU memory utilization: 0.85
Waiting for jobs...
================================================================================
```

---

## Step 4: Submit Your First Batch

### Option A: Using curl

```bash
# Create test batch file
cat > test_batch.jsonl << 'EOF'
{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "What is 2+2?"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "What is 3+3?"}]}}
EOF

# Submit batch
curl -X POST http://localhost:8080/v1/batches \
  -F "file=@test_batch.jsonl" \
  -F "model=google/gemma-3-4b-it"
```

### Option B: Using Python

```python
import requests

# Submit batch
with open('test_batch.jsonl', 'rb') as f:
    response = requests.post(
        'http://localhost:8080/v1/batches',
        files={'file': f},
        data={'model': 'google/gemma-3-4b-it'}
    )

batch_id = response.json()['batch_id']
print(f"Batch submitted: {batch_id}")
```

---

## Step 5: Monitor Progress

### Check Health

```bash
curl http://localhost:8080/health | jq
```

**Response:**
```json
{
  "status": "healthy",
  "gpu": {
    "healthy": true,
    "memory_percent": 68.5,
    "temperature_c": 72
  },
  "worker": {
    "status": "processing",
    "current_job_id": "batch_abc123",
    "age_seconds": 5
  },
  "queue": {
    "active_jobs": 1,
    "queue_available": 4
  }
}
```

### Check Batch Status

```bash
curl http://localhost:8080/v1/batches/{batch_id} | jq
```

### Get Results

```bash
curl http://localhost:8080/v1/batches/{batch_id}/results
```

---

## Step 6: Run Production Test

Test with 10K requests to validate chunking and incremental saves:

```bash
python test_phase1.py
```

This will:
1. ✅ Check system health
2. ✅ Submit 10K batch
3. ✅ Test queue limits
4. ✅ Test request limits
5. ✅ Monitor progress

---

## Common Commands

### List All Batches

```bash
curl http://localhost:8080/v1/batches | jq
```

### Get Batch Logs

```bash
curl http://localhost:8080/v1/batches/{batch_id}/logs
```

### View Failed Requests

```bash
curl http://localhost:8080/v1/batches/{batch_id}/failed | jq
```

### Cancel Pending Batch

```bash
curl -X DELETE http://localhost:8080/v1/batches/{batch_id}
```

---

## Production Settings

### For Overnight Processing (200K requests)

Edit `batch_app/worker.py`:

```python
CHUNK_SIZE = 5000  # Safe for RTX 4080 16GB
GPU_MEMORY_UTILIZATION = 0.85  # Conservative
```

Edit `batch_app/api_server.py`:

```python
MAX_REQUESTS_PER_JOB = 50000  # OpenAI limit
MAX_QUEUE_DEPTH = 1  # One job at a time (desktop-friendly)
MAX_TOTAL_QUEUED_REQUESTS = 50000  # Total limit
```

### Expected Performance

| Batch Size | Time | GPU Memory | Safe? |
|------------|------|------------|-------|
| 5K | 36 min | ~11 GB | ✅ |
| 10K | 72 min | ~11 GB | ✅ |
| 50K | 6 hours | ~11 GB | ✅ |
| 200K | 24 hours | ~11 GB | ✅ |

---

## Troubleshooting

### Worker Not Starting

**Problem:** Worker crashes on startup

**Solution:** Check GPU availability
```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### Queue Full Error

**Problem:** `429 Queue full`

**Solution:** Wait for current jobs to complete or increase `MAX_QUEUE_DEPTH`

### GPU OOM Error

**Problem:** Out of memory during processing

**Solution:** Reduce `CHUNK_SIZE` or `GPU_MEMORY_UTILIZATION`

### Worker Appears Dead

**Problem:** `/health` shows worker status "dead"

**Solution:** Restart worker
```bash
# Kill old worker
pkill -f "batch_app.worker"

# Start new worker
python -m batch_app.worker
```

---

## Integration with Your Web App

### Submit Batch from Web App

```python
import requests

def submit_batch_job(candidates: list, model: str = "google/gemma-3-4b-it"):
    """Submit batch job to vLLM server."""
    
    # Create batch file
    batch_file = "batch_input.jsonl"
    with open(batch_file, 'w') as f:
        for i, candidate in enumerate(candidates):
            request = {
                "custom_id": f"candidate-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": candidate['prompt']}
                    ],
                    "max_tokens": 2000
                }
            }
            f.write(json.dumps(request) + '\n')
    
    # Submit to batch server
    with open(batch_file, 'rb') as f:
        response = requests.post(
            'http://localhost:8080/v1/batches',
            files={'file': f},
            data={'model': model}
        )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Batch submission failed: {response.json()}")

# Usage
candidates = [
    {"prompt": "Evaluate this candidate: ..."},
    # ... 200K more
]

batch_info = submit_batch_job(candidates)
print(f"Batch ID: {batch_info['batch_id']}")
print(f"Estimated time: {batch_info['estimate']['estimated_time_minutes']} minutes")
```

### Poll for Completion

```python
import time

def wait_for_batch(batch_id: str, poll_interval: int = 60):
    """Wait for batch to complete."""
    
    while True:
        response = requests.get(f'http://localhost:8080/v1/batches/{batch_id}')
        data = response.json()
        
        status = data['status']
        progress = data['progress']
        
        print(f"Status: {status} | Progress: {progress['completed']}/{progress['total']} ({progress['percent']}%)")
        
        if status in ['completed', 'failed']:
            return data
        
        time.sleep(poll_interval)

# Usage
result = wait_for_batch(batch_info['batch_id'])
if result['status'] == 'completed':
    # Download results
    results_response = requests.get(f"http://localhost:8080/v1/batches/{batch_id}/results")
    with open('results.jsonl', 'wb') as f:
        f.write(results_response.content)
```

---

## Monitoring Dashboard (Optional)

### Simple Health Monitor

```bash
# Watch health in terminal
watch -n 5 'curl -s http://localhost:8080/health | jq'
```

### Log Monitoring

```bash
# Watch worker logs
tail -f data/batches/logs/*.log
```

---

## Next Steps

1. ✅ Run `test_phase1.py` to validate setup
2. ✅ Submit real batch from your web app
3. ✅ Monitor with `/health` endpoint
4. ✅ Check results in `data/batches/output/`

**You're ready for production!** 🚀

---

## Support

- **Documentation:** See `PRODUCTION_IMPLEMENTATION_COMPLETE.md`
- **Architecture:** See `PRODUCTION_READINESS_PLAN.md`
- **Issues:** Check worker logs in `data/batches/logs/`

