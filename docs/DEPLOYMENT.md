# Deployment Guide

## Prerequisites

- **GPU**: 16GB+ VRAM (RTX 4080, RTX 3090, A100, etc.)
- **Python**: 3.13+
- **CUDA**: 12.1+
- **PostgreSQL**: 14+ (optional, defaults to SQLite)

---

## Quick Start (Development)

```bash
# Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from core.batch_app.database import init_db; init_db()"

# Start API server (background)
nohup python -m core.batch_app.api_server > logs/api_server.log 2>&1 &

# Start worker (background)
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &

# Start static server (for web UI)
nohup python -m core.batch_app.static_server > logs/static_server.log 2>&1 &

# Check status
curl http://localhost:4080/
```

---

## Production Deployment

### 1. Environment Variables

Create `.env` file:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:4332/vllm_batch

# API Server
BATCH_API_HOST=0.0.0.0
BATCH_API_PORT=4080

# Worker
WORKER_POLL_INTERVAL=10
CHUNK_SIZE=100

# GPU
GPU_MEMORY_UTILIZATION=0.9

# Monitoring (optional)
SENTRY_DSN=https://...
PROMETHEUS_PORT=4222
```

### 2. PostgreSQL Setup

```bash
# Start PostgreSQL
docker run -d \
  --name vllm-postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=vllm_batch \
  -p 4332:5432 \
  postgres:14

# Initialize schema
python scripts/init_postgres_schema.py
```

### 3. Start Services

```bash
# API Server
nohup python -m core.batch_app.api_server > logs/api_server.log 2>&1 &

# Worker
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &

# Static Server (web UI)
nohup python -m core.batch_app.static_server > logs/static_server.log 2>&1 &
```

### 4. Verify Services

```bash
# Check API
curl http://localhost:4080/

# Check worker logs
tail -f logs/worker.log

# Check queue status
curl http://localhost:4080/v1/queue
```

---

## Systemd Services (Recommended)

Create systemd service files for automatic startup:

### API Server Service

`/etc/systemd/system/vllm-batch-api.service`:

```ini
[Unit]
Description=vLLM Batch API Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/vllm-batch-server
Environment="PATH=/path/to/vllm-batch-server/venv/bin"
ExecStart=/path/to/vllm-batch-server/venv/bin/python -m core.batch_app.api_server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Worker Service

`/etc/systemd/system/vllm-batch-worker.service`:

```ini
[Unit]
Description=vLLM Batch Worker
After=network.target vllm-batch-api.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/vllm-batch-server
Environment="PATH=/path/to/vllm-batch-server/venv/bin"
ExecStart=/path/to/vllm-batch-server/venv/bin/python -m core.batch_app.worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable vllm-batch-api vllm-batch-worker
sudo systemctl start vllm-batch-api vllm-batch-worker

# Check status
sudo systemctl status vllm-batch-api
sudo systemctl status vllm-batch-worker
```

---

## Monitoring

### Prometheus Metrics

Metrics exposed at `http://localhost:4080/metrics`:

- `batch_jobs_active` - Active jobs by status
- `batch_requests_processed` - Total requests processed
- `tokens_generated` - Total tokens generated
- `throughput_tokens_per_second` - Current throughput
- `gpu_memory_used_bytes` - GPU memory usage
- `gpu_temperature_celsius` - GPU temperature

### Grafana Dashboard

Import dashboard from `monitoring/grafana/dashboards/vllm-batch.json`

---

## Troubleshooting

### Worker Not Processing Jobs

```bash
# Check worker logs
tail -f logs/worker.log

# Check GPU status
nvidia-smi

# Check database connection
psql -h localhost -U user -d vllm_batch -c "SELECT * FROM batch_jobs;"
```

### OOM Errors

1. **Reduce GPU memory utilization**: Set `GPU_MEMORY_UTILIZATION=0.8` in `.env`
2. **Enable CPU offload**: Add model to registry with `cpu_offload_gb=8`
3. **Use smaller models**: Switch from 7B to 4B models
4. **Use GGUF quantization**: Use Q4_0 quantized models

### Slow Throughput

1. **Check CPU offload**: Models with CPU offload are 28-95% slower
2. **Use GGUF models**: Quantized models fit in VRAM without offload
3. **Increase chunk size**: Set `CHUNK_SIZE=200` (default 100)
4. **Check GPU temperature**: Thermal throttling reduces performance

---

## Scaling

### Multiple Workers (Same GPU)

Not recommended - workers will compete for GPU memory and cause OOM.

### Multiple Workers (Different GPUs)

```bash
# Worker 1 (GPU 0)
CUDA_VISIBLE_DEVICES=0 python -m core.batch_app.worker &

# Worker 2 (GPU 1)
CUDA_VISIBLE_DEVICES=1 python -m core.batch_app.worker &
```

Both workers poll the same queue and process jobs in parallel.

---

## Backup and Recovery

### Database Backup

```bash
# PostgreSQL
pg_dump vllm_batch > backup.sql

# SQLite
cp batch_server.db backup.db
```

### Restore

```bash
# PostgreSQL
psql vllm_batch < backup.sql

# SQLite
cp backup.db batch_server.db
```

### Resume Failed Jobs

Jobs with status `in_progress` will automatically resume from last saved chunk when worker restarts.

