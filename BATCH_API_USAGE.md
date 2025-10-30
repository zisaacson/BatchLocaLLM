# vLLM Batch Processing API - Usage Guide

**Complete web API for submitting and managing large-scale LLM inference batch jobs on your RTX 4080.**

---

## 🚀 Quick Start

### **1. Install Dependencies**

```bash
# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install fastapi uvicorn sqlalchemy
```

### **2. Start the API Server** (Terminal 1)

```bash
chmod +x start_api_server.sh
./start_api_server.sh
```

**Expected output:**
```
==================================
Starting Batch API Server
==================================
✅ Database initialized at sqlite:///data/database/batch_jobs.db
✅ Loaded benchmark for google/gemma-3-4b-it
✅ Batch API Server started
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### **3. Start the Worker** (Terminal 2)

```bash
chmod +x start_worker.sh
./start_worker.sh
```

**Expected output:**
```
==================================
Starting Batch Worker
==================================
================================================================================
🚀 BATCH WORKER STARTED
================================================================================
Poll interval: 10s
Waiting for jobs...
================================================================================
```

---

## 📋 API Endpoints

### **1. Check Available Models**

```bash
curl http://localhost:8080/v1/models
```

**Response:**
```json
{
  "models": [
    {
      "model": "google/gemma-3-4b-it",
      "platform": "vllm-native",
      "throughput_tokens_per_sec": 2511,
      "throughput_requests_per_sec": 2.29,
      "max_model_len": 4096,
      "gpu_memory_utilization": 0.9,
      "last_benchmark": "2025-10-28T08:40:32Z",
      "success_rate": 100.0
    }
  ],
  "count": 1
}
```

---

### **2. Submit a Batch Job**

```bash
curl -X POST http://localhost:8080/v1/batches \
  -F "file=@batch_100_real.jsonl" \
  -F "model=google/gemma-3-4b-it"
```

**Response:**
```json
{
  "batch_id": "batch_a1b2c3d4e5f6g7h8",
  "model": "google/gemma-3-4b-it",
  "status": "pending",
  "progress": {
    "total": 100,
    "completed": 0,
    "failed": 0,
    "percent": 0.0
  },
  "created_at": "2025-10-28T10:00:00.000000",
  "started_at": null,
  "completed_at": null,
  "throughput_tokens_per_sec": null,
  "total_tokens": null,
  "error_message": null,
  "results_url": null,
  "estimate": {
    "estimated_seconds": 73,
    "estimated_hours": 0.02,
    "estimated_completion": "2025-10-28T10:01:13Z",
    "throughput_tokens_per_sec": 2511,
    "throughput_requests_per_sec": 2.29,
    "based_on_benchmark": "vllm-native-gemma3-4b-5000-2025-10-28"
  }
}
```

---

### **3. Check Job Status**

```bash
curl http://localhost:8080/v1/batches/batch_a1b2c3d4e5f6g7h8
```

**Response (Running):**
```json
{
  "batch_id": "batch_a1b2c3d4e5f6g7h8",
  "model": "google/gemma-3-4b-it",
  "status": "running",
  "progress": {
    "total": 100,
    "completed": 0,
    "failed": 0,
    "percent": 0.0
  },
  "created_at": "2025-10-28T10:00:00.000000",
  "started_at": "2025-10-28T10:00:05.000000",
  "completed_at": null
}
```

**Response (Completed):**
```json
{
  "batch_id": "batch_a1b2c3d4e5f6g7h8",
  "model": "google/gemma-3-4b-it",
  "status": "completed",
  "progress": {
    "total": 100,
    "completed": 100,
    "failed": 0,
    "percent": 100.0
  },
  "created_at": "2025-10-28T10:00:00.000000",
  "started_at": "2025-10-28T10:00:05.000000",
  "completed_at": "2025-10-28T10:01:18.000000",
  "throughput_tokens_per_sec": 2487,
  "total_tokens": 114620,
  "results_url": "/v1/batches/batch_a1b2c3d4e5f6g7h8/results"
}
```

---

### **4. Download Results**

```bash
curl http://localhost:8080/v1/batches/batch_a1b2c3d4e5f6g7h8/results \
  -o results.jsonl
```

**Output file format (JSONL):**
```jsonl
{"custom_id": "req-1", "response": {"status_code": 200, "body": {...}}}
{"custom_id": "req-2", "response": {"status_code": 200, "body": {...}}}
```

---

### **5. List All Batches**

```bash
# List all batches
curl http://localhost:8080/v1/batches

# Filter by status
curl http://localhost:8080/v1/batches?status=completed

# Limit results
curl http://localhost:8080/v1/batches?limit=10
```

---

### **6. View Logs**

```bash
curl http://localhost:8080/v1/batches/batch_a1b2c3d4e5f6g7h8/logs
```

---

### **7. Cancel a Pending Job**

```bash
curl -X DELETE http://localhost:8080/v1/batches/batch_a1b2c3d4e5f6g7h8
```

**Note:** Can only cancel jobs with status `pending`. Running jobs cannot be cancelled.

---

## 🧪 Testing with Python

```python
import requests

# Submit batch job
with open('batch_100_real.jsonl', 'rb') as f:
    response = requests.post(
        'http://localhost:8080/v1/batches',
        files={'file': f},
        data={'model': 'google/gemma-3-4b-it'}
    )

batch_id = response.json()['batch_id']
print(f"Batch ID: {batch_id}")

# Poll for status
import time
while True:
    status = requests.get(f'http://localhost:8080/v1/batches/{batch_id}').json()
    print(f"Status: {status['status']} - {status['progress']['percent']}%")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(10)

# Download results
if status['status'] == 'completed':
    results = requests.get(f'http://localhost:8080/v1/batches/{batch_id}/results')
    with open('results.jsonl', 'wb') as f:
        f.write(results.content)
    print("✅ Results downloaded!")
```

---

## 📊 Performance Estimates

The API uses your existing benchmark data to provide accurate time estimates:

| Batch Size | Estimated Time | Based On |
|------------|----------------|----------|
| 100 | ~1 minute | Gemma 3 4B benchmark |
| 5,000 | ~37 minutes | Gemma 3 4B benchmark |
| 50,000 | ~6.1 hours | Gemma 3 4B benchmark |
| 200,000 | ~24.5 hours | Gemma 3 4B benchmark |

**Estimates automatically update as you run more jobs!**

---

## 🔧 Architecture

```
User → API Server (Port 8080) → Database (SQLite)
                                      ↓
                                 Worker Process
                                      ↓
                                 vLLM Offline
                                      ↓
                                 RTX 4080 GPU
```

**Components:**
1. **API Server** - FastAPI web server accepting HTTP requests
2. **Database** - SQLite storing job queue and metadata
3. **Worker** - Background process running vLLM Offline
4. **Benchmark System** - Tracks performance and provides estimates

---

## 📁 File Structure

```
vllm-batch-server/
├── batch_app/
│   ├── __init__.py
│   ├── api_server.py       # FastAPI server
│   ├── worker.py            # Background worker
│   ├── database.py          # Database models
│   └── benchmarks.py        # Benchmark integration
├── data/
│   ├── batches/
│   │   ├── input/           # Uploaded JSONL files
│   │   ├── output/          # Results files
│   │   └── logs/            # Job logs
│   └── database/
│       └── batch_jobs.db    # SQLite database
├── benchmarks/
│   └── metadata/            # Benchmark data (existing)
├── start_api_server.sh      # Start API server
└── start_worker.sh          # Start worker
```

---

## 🚨 Troubleshooting

### **API server won't start**
```bash
# Check if port 8080 is in use
lsof -i :8080

# Kill existing process
pkill -f "uvicorn batch_app"
```

### **Worker not processing jobs**
```bash
# Check worker logs
tail -f data/batches/logs/*.log

# Restart worker
pkill -f "batch_app.worker"
./start_worker.sh
```

### **Job stuck in "pending"**
- Make sure worker is running (Terminal 2)
- Check worker logs for errors
- Verify GPU is available: `nvidia-smi`

### **Out of memory errors**
- Only one job runs at a time
- Check GPU memory: `nvidia-smi`
- Kill zombie processes: `pkill -f vllm`

---

## 🎯 Next Steps

1. ✅ **Test with 100 requests** - Verify system works
2. ✅ **Test with 5K requests** - Validate performance
3. ✅ **Add more models** - Run benchmarks, add to system
4. ✅ **Scale to 200K** - Process large batches

---

## 💡 Tips

- **Model switching:** Worker automatically loads/unloads models as needed
- **Benchmark data:** Every completed job adds to benchmark database
- **Estimates improve:** More jobs = better time estimates
- **Queue management:** Jobs processed in FIFO order
- **Remote access:** Change `0.0.0.0` to your IP for remote access

---

**Ready to process 200K requests!** 🚀

