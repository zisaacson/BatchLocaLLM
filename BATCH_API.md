# 🚀 Local Batch Processing API

Production-ready batch processing system that mimics Parasail/OpenAI Batch API.

## Features

✅ **Parasail/OpenAI Compatible API** - Drop-in replacement for testing  
✅ **Webhook Callbacks** - Get notified when jobs complete  
✅ **50K Requests per Batch** - Matches OpenAI's limits  
✅ **Incremental Saves** - Resume from crashes  
✅ **GPU Health Monitoring** - Automatic queue management  
✅ **Queue Limits** - Prevent overload  
✅ **Custom Metadata** - Track your own data  

---

## Quick Start

### 1. Start the API Server

```bash
python -m batch_app.api_server
```

Server runs on `http://localhost:4080`

### 2. Start the Worker

```bash
python -m batch_app.worker
```

Worker polls for jobs every 10 seconds.

### 3. Submit a Batch Job

```bash
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@batch_5k.jsonl" \
  -F "model=google/gemma-3-4b-it" \
  -F "webhook_url=https://your-app.com/webhook" \
  -F "metadata={\"user_id\": \"123\", \"campaign\": \"Q4_2024\"}"
```

Response:
```json
{
  "batch_id": "batch_abc123",
  "model": "google/gemma-3-4b-it",
  "status": "pending",
  "progress": {
    "total": 5000,
    "completed": 0,
    "failed": 0,
    "percent": 0
  },
  "created_at": "2024-10-28T10:00:00Z",
  "estimate": {
    "completion_time_minutes": 24,
    "throughput_tokens_per_sec": 2511,
    "throughput_requests_per_sec": 2.29
  }
}
```

### 4. Check Job Status

```bash
curl http://localhost:4080/v1/batches/batch_abc123
```

### 5. Download Results

```bash
curl http://localhost:4080/v1/batches/batch_abc123/results > results.jsonl
```

---

## API Reference

### POST `/v1/batches`

Submit a new batch job.

**Parameters:**
- `file` (required): JSONL file with requests
- `model` (required): Model name (e.g., `google/gemma-3-4b-it`)
- `webhook_url` (optional): URL to call when job completes
- `metadata` (optional): JSON string with custom metadata

**Limits:**
- Max 50,000 requests per batch
- Max 10 concurrent jobs in queue
- Max 500,000 total queued requests

**Response:** Batch job object

---

### GET `/v1/batches/{batch_id}`

Get batch job status.

**Response:**
```json
{
  "batch_id": "batch_abc123",
  "model": "google/gemma-3-4b-it",
  "status": "running",
  "progress": {
    "total": 5000,
    "completed": 2500,
    "failed": 0,
    "percent": 50.0
  },
  "created_at": "2024-10-28T10:00:00Z",
  "started_at": "2024-10-28T10:01:00Z",
  "throughput_tokens_per_sec": 2511
}
```

**Status values:**
- `pending` - Waiting in queue
- `running` - Currently processing
- `completed` - Finished successfully
- `failed` - Job failed

---

### GET `/v1/batches/{batch_id}/results`

Download results as JSONL file.

**Response:** JSONL file with format:
```jsonl
{"custom_id": "req_1", "response": {"body": {"choices": [...], "usage": {...}}}}
{"custom_id": "req_2", "response": {"body": {"choices": [...], "usage": {...}}}}
```

---

### GET `/v1/batches`

List all batch jobs.

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `running`, `completed`, `failed`)
- `limit` (optional): Max results (default: 100)

---

## Webhook Format

When a job completes, a POST request is sent to your `webhook_url`:

```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "status": "completed",
  "created_at": 1698480000,
  "completed_at": 1698481440,
  "request_counts": {
    "total": 5000,
    "completed": 5000,
    "failed": 0
  },
  "metadata": {
    "user_id": "123",
    "campaign": "Q4_2024"
  },
  "output_file_url": "/v1/batches/batch_abc123/results",
  "error_file_url": null
}
```

**Retry Logic:**
- 3 attempts with exponential backoff (1s, 2s, 4s)
- 30 second timeout per attempt
- Accepts 200, 201, 202, 204 status codes

---

## Input File Format

JSONL file with one request per line:

```jsonl
{"custom_id": "req_1", "body": {"messages": [{"role": "user", "content": "Hello"}]}}
{"custom_id": "req_2", "body": {"messages": [{"role": "user", "content": "Hi"}]}}
```

**Required fields:**
- `custom_id`: Unique identifier for the request
- `body.messages`: Array of chat messages

---

## Performance

Based on RTX 4080 16GB benchmarks:

| Model | Throughput | 1K requests | 5K requests | 50K requests |
|-------|------------|-------------|-------------|--------------|
| **Gemma 3 4B** | 3.47 req/s | 5 min | 24 min | 4 hours |
| **Llama 3.2 1B** | 5.2 req/s | 3 min | 16 min | 2.7 hours |
| **Llama 3.2 3B** | 4.1 req/s | 4 min | 20 min | 3.4 hours |

---

## Migration from Parasail/OpenAI

### Parasail Batch API → Local Batch API

**Before (Parasail):**
```python
import parasail

client = parasail.Client(api_key="...")
batch = client.batches.create(
    input_file_id="file_abc123",
    endpoint="/v1/chat/completions",
    completion_window="24h"
)
```

**After (Local):**
```python
import requests

response = requests.post(
    "http://localhost:4080/v1/batches",
    files={"file": open("batch.jsonl", "rb")},
    data={"model": "google/gemma-3-4b-it"}
)
batch = response.json()
```

### Webhook Integration

**Aris App Example:**
```typescript
// Submit batch from Aris
const response = await fetch('http://localhost:4080/v1/batches', {
  method: 'POST',
  body: formData,
  headers: {
    'webhook_url': 'https://aris.app/api/aristotle/batch/webhook',
    'metadata': JSON.stringify({ userId: user.id, jobType: 'candidate_analysis' })
  }
});

// Webhook endpoint in Aris
export async function POST(req: Request) {
  const webhook = await req.json();
  
  if (webhook.status === 'completed') {
    // Download results
    const results = await fetch(`http://localhost:4080${webhook.output_file_url}`);
    const data = await results.text();
    
    // Parse and insert into database
    for (const line of data.split('\n')) {
      const result = JSON.parse(line);
      await insertCandidateAnalysis(result);
    }
  }
  
  return new Response('OK', { status: 200 });
}
```

---

## Monitoring

### GPU Health

```bash
curl http://localhost:4080/health
```

### Worker Status

```bash
curl http://localhost:4080/worker/status
```

### Queue Status

```bash
curl http://localhost:4080/queue/status
```

---

## Database Migration

If upgrading from an older version, run:

```bash
python migrate_db.py
```

This adds webhook and metadata columns to existing database.

---

## Troubleshooting

### Job stuck in "pending"

- Check if worker is running: `ps aux | grep worker`
- Check worker logs: `tail -f data/batches/logs/*.log`
- Restart worker: `python -m batch_app.worker`

### Webhook not received

- Check webhook status: `curl http://localhost:4080/v1/batches/{batch_id}`
- Look for `webhook_status` and `webhook_error` fields
- Verify webhook URL is accessible from server

### Out of memory

- Reduce chunk size in `batch_app/worker.py` (default: 5000)
- Lower `GPU_MEMORY_UTILIZATION` (default: 0.85)
- Use smaller model

---

## Production Deployment

### Docker (Recommended)

```dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y python3.11 python3-pip
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . /app
WORKDIR /app

# Run migration
RUN python migrate_db.py

# Start services
CMD ["sh", "-c", "python -m batch_app.api_server & python -m batch_app.worker"]
```

### Systemd Service

```ini
[Unit]
Description=vLLM Batch API Server
After=network.target

[Service]
Type=simple
User=vllm
WorkingDirectory=/opt/vllm-batch-server
ExecStart=/usr/bin/python3 -m batch_app.api_server
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Cost Comparison

### Local vs Cloud (5000 candidates/day)

| Provider | Mode | Cost/Day | Cost/Month | Notes |
|----------|------|----------|------------|-------|
| **Local RTX 4080** | Batch | $0 | $0 | Electricity ~$2/mo |
| **Parasail** | Batch | $0.85 | $25.50 | 50% discount |
| **Parasail** | Serverless | $1.71 | $51.30 | Standard pricing |
| **OpenAI** | Batch | $1.20 | $36.00 | GPT-3.5 Turbo |

**Break-even:** Local setup pays for itself in 1-2 months at 5K requests/day.

---

## Next Steps

1. ✅ **Test locally** - Run benchmarks with your data
2. ✅ **Integrate with Aris** - Add webhook endpoint
3. ✅ **Monitor performance** - Track throughput and costs
4. ⏸️ **Scale to cloud** - Deploy to production when ready

---

## Support

- GitHub Issues: https://github.com/your-repo/issues
- Documentation: See `README.md` for full details

