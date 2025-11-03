# Getting Started with vLLM Batch Server

This guide will walk you through setting up and using vLLM Batch Server for the first time.

## Prerequisites

Before you begin, ensure you have:

- **NVIDIA GPU** with 16GB+ VRAM (RTX 4080, RTX 4090, A100, etc.)
- **Linux OS** (Ubuntu 22.04+ recommended, also works on Debian, Fedora)
- **Python 3.10+** (Python 3.11 or 3.12 recommended)
- **Docker** and **Docker Compose** (for PostgreSQL and monitoring)
- **CUDA 12.1+** (for vLLM)

### Check Your System

```bash
# Check GPU
nvidia-smi

# Check Python version
python3 --version

# Check Docker
docker --version
docker compose version

# Check CUDA
nvcc --version
```

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate  # On Linux/Mac
# OR
.\venv\Scripts\activate  # On Windows (if supported)
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Verify vLLM installation
python -c "import vllm; print(f'vLLM version: {vllm.__version__}')"
```

**Note:** vLLM installation can take 5-10 minutes as it compiles CUDA kernels.

### Step 4: Start PostgreSQL

```bash
# Start PostgreSQL with Docker Compose
docker compose -f docker-compose.postgres.yml up -d

# Verify PostgreSQL is running
docker ps | grep postgres

# Check logs if needed
docker compose -f docker-compose.postgres.yml logs
```

### Step 5: Initialize Database

```bash
# Initialize database schema
python -c "from core.batch_app.database import init_db; init_db()"

# Verify tables were created
docker exec -it vllm-postgres psql -U vllm_user -d vllm_batch -c "\dt"
```

You should see tables: `batch_jobs`, `uploaded_files`, `worker_heartbeat`, `model_registry`, `benchmarks`.

### Step 6: Configure Environment (Optional)

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration (optional)
nano .env
```

**Key settings:**
- `BATCH_API_PORT`: API server port (default: 4080)
- `GPU_MEMORY_UTILIZATION`: GPU memory usage (default: 0.90)
- `DEFAULT_MODEL`: Default model to use

### Step 7: Start Services

```bash
# Start all services (API server + Worker)
./scripts/start_all.sh

# OR start individually:
# API Server
python -m core.batch_app.api_server &

# Worker
python -m core.batch_app.worker &
```

### Step 8: Verify Installation

```bash
# Check API health
curl http://localhost:4080/health

# Expected output:
# {"status":"healthy","version":"1.0.0"}

# Check queue status
curl http://localhost:4080/v1/queue

# Open web UI
xdg-open http://localhost:4080/queue-monitor.html  # Linux
# OR
open http://localhost:4080/queue-monitor.html  # Mac
```

## Your First Batch Job

### Option 1: Using the Example Script

```bash
# Run the simple example
python examples/simple_batch.py
```

This will:
1. Upload a test batch file (10 requests)
2. Create a batch job
3. Poll for completion
4. Download and display results

### Option 2: Using curl

```bash
# 1. Upload batch file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@examples/datasets/synthetic_candidates_10.jsonl" \
  -F "purpose=batch"

# Save the file_id from response
FILE_ID="file-abc123..."

# 2. Create batch job
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\"
  }"

# Save the batch_id from response
BATCH_ID="batch-xyz789..."

# 3. Check status
curl http://localhost:4080/v1/batches/$BATCH_ID

# 4. Download results (when status is "completed")
OUTPUT_FILE_ID=$(curl -s http://localhost:4080/v1/batches/$BATCH_ID | jq -r '.output_file_id')
curl http://localhost:4080/v1/files/$OUTPUT_FILE_ID/content > results.jsonl

# 5. View results
cat results.jsonl | jq
```

### Option 3: Using Python

```python
import requests
import time
import json

API_URL = "http://localhost:4080"

# 1. Upload file
with open("examples/datasets/synthetic_candidates_10.jsonl", "rb") as f:
    response = requests.post(
        f"{API_URL}/v1/files",
        files={"file": f},
        data={"purpose": "batch"}
    )
    file_id = response.json()["id"]
    print(f"Uploaded file: {file_id}")

# 2. Create batch
response = requests.post(
    f"{API_URL}/v1/batches",
    json={
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
)
batch_id = response.json()["id"]
print(f"Created batch: {batch_id}")

# 3. Poll for completion
while True:
    response = requests.get(f"{API_URL}/v1/batches/{batch_id}")
    batch = response.json()
    status = batch["status"]
    print(f"Status: {status} ({batch.get('request_counts', {}).get('completed', 0)}/{batch.get('request_counts', {}).get('total', 0)} completed)")
    
    if status in ["completed", "failed", "cancelled"]:
        break
    
    time.sleep(5)

# 4. Download results
if status == "completed":
    output_file_id = batch["output_file_id"]
    response = requests.get(f"{API_URL}/v1/files/{output_file_id}/content")
    
    # Save results
    with open("results.jsonl", "w") as f:
        f.write(response.text)
    
    # Print first result
    first_result = json.loads(response.text.split("\n")[0])
    print(json.dumps(first_result, indent=2))
```

## Next Steps

### Add More Models

```bash
# See available models
curl http://localhost:4080/v1/models

# Add a new model via web UI
xdg-open http://localhost:4080/model-management.html
```

See [docs/ADD_MODEL_GUIDE.md](ADD_MODEL_GUIDE.md) for detailed instructions.

### Run Benchmarks

```bash
# Generate synthetic test data
python tools/generate_synthetic_data.py --count 100 --output test_100.jsonl

# Run benchmark
python tools/benchmark_models.py --input test_100.jsonl --models gemma-3-4b llama-3.2-3b
```

### Enable Monitoring (Optional)

```bash
# Start monitoring stack (Grafana + Prometheus + Loki)
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana
xdg-open http://localhost:4220

# Default credentials: admin / admin
```

### Explore the Web UI

- **Queue Monitor**: http://localhost:4080/queue-monitor.html
- **Model Management**: http://localhost:4080/model-management.html
- **Workbench**: http://localhost:4080/workbench.html
- **Benchmark Runner**: http://localhost:4080/benchmark-runner.html

## Troubleshooting

### GPU Out of Memory

```bash
# Reduce GPU memory utilization in .env
GPU_MEMORY_UTILIZATION=0.80  # Default is 0.90

# Or use a smaller model
DEFAULT_MODEL=google/gemma-2-2b-it  # Instead of 4B
```

### Worker Not Processing Jobs

```bash
# Check worker logs
tail -f logs/worker.log

# Check worker heartbeat
curl http://localhost:4080/v1/worker/heartbeat

# Restart worker
pkill -f "batch_app.worker"
python -m core.batch_app.worker &
```

### PostgreSQL Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check logs
docker compose -f docker-compose.postgres.yml logs

# Restart PostgreSQL
docker compose -f docker-compose.postgres.yml restart
```

### Port Already in Use

```bash
# Find process using port 4080
lsof -i :4080

# Kill process
kill -9 <PID>

# Or change port in .env
BATCH_API_PORT=4081
```

## Common Issues

### Issue: vLLM fails to load model

**Solution**: Ensure you have enough GPU memory and the model is compatible with vLLM 0.11.0.

```bash
# Check GPU memory
nvidia-smi

# Try a smaller model first
DEFAULT_MODEL=google/gemma-2-2b-it
```

### Issue: Batch job stuck in "validating" status

**Solution**: Check worker is running and has access to the model.

```bash
# Check worker status
ps aux | grep worker

# Check worker logs
tail -f logs/worker.log
```

### Issue: Results file not found

**Solution**: Wait for batch to complete, then check output_file_id.

```bash
# Check batch status
curl http://localhost:4080/v1/batches/<batch_id>

# Ensure status is "completed" before downloading results
```

## Getting Help

- **Documentation**: [docs/](.)
- **Issues**: [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)

## What's Next?

- Read the [Architecture Guide](ARCHITECTURE.md) to understand how it works
- Check the [API Reference](API.md) for all available endpoints
- See [Deployment Guide](DEPLOYMENT.md) for production setup
- Explore [Examples](../examples/) for more use cases

