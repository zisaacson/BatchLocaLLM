# Docker Quick Start

Get vLLM Batch Server running in **under 5 minutes** with Docker.

## Prerequisites

- **NVIDIA GPU** with 12GB+ VRAM (RTX 3060, 3090, 4080, 4090)
- **Docker** and **Docker Compose** installed
- **NVIDIA Container Toolkit** installed

### Install NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify installation
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## One-Command Setup

```bash
# Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Start everything
docker compose up -d

# Check status
docker compose ps
```

That's it! The server is now running at http://localhost:4080

## What Just Happened?

The `docker compose up` command:

1. ✅ Started PostgreSQL database
2. ✅ Initialized database schema
3. ✅ Started vLLM Batch API server (port 4080)
4. ✅ Started batch worker with GPU access
5. ✅ Started monitoring stack (Grafana on port 4220)

## Verify Installation

```bash
# Check API health
curl http://localhost:4080/health

# Expected output:
# {"status":"healthy","version":"1.0.0"}

# Open web UI
xdg-open http://localhost:4080/queue-monitor.html
```

## Submit Your First Batch

```bash
# Download example dataset
curl -O https://raw.githubusercontent.com/zisaacson/vllm-batch-server/main/examples/datasets/synthetic_candidates_10.jsonl

# Upload file
FILE_ID=$(curl -s -X POST http://localhost:4080/v1/files \
  -F "file=@synthetic_candidates_10.jsonl" \
  -F "purpose=batch" | jq -r '.id')

echo "Uploaded file: $FILE_ID"

# Create batch job
BATCH_ID=$(curl -s -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\"
  }" | jq -r '.id')

echo "Created batch: $BATCH_ID"

# Monitor progress
watch -n 2 "curl -s http://localhost:4080/v1/batches/$BATCH_ID | jq '.status, .request_counts'"
```

## Access Monitoring

```bash
# Open Grafana
xdg-open http://localhost:4220

# Default credentials:
# Username: admin
# Password: admin
```

Pre-configured dashboards:
- **Batch Processing** - Job queue, throughput, completion rates
- **GPU Metrics** - GPU utilization, memory, temperature
- **System Health** - CPU, RAM, disk usage

## Configuration

### Environment Variables

Create a `.env` file to customize settings:

```bash
# Copy example
cp .env.example .env

# Edit configuration
nano .env
```

**Key settings:**

```bash
# GPU Settings
GPU_MEMORY_UTILIZATION=0.90  # Use 90% of GPU memory
MAX_MODEL_LEN=8192           # Max context length

# Model Settings
DEFAULT_MODEL=google/gemma-3-4b-it

# Performance
CHUNK_SIZE=100               # Requests per batch

# Ports
BATCH_API_PORT=4080
GRAFANA_PORT=4220
```

### GPU-Specific Configurations

**RTX 3060 12GB:**
```bash
GPU_MEMORY_UTILIZATION=0.85
MAX_MODEL_LEN=4096
CHUNK_SIZE=50
DEFAULT_MODEL=google/gemma-3-2b-it
```

**RTX 3090 24GB:**
```bash
GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=8192
CHUNK_SIZE=150
DEFAULT_MODEL=google/gemma-3-4b-it
```

**RTX 4080 16GB:**
```bash
GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=8192
CHUNK_SIZE=100
DEFAULT_MODEL=google/gemma-3-4b-it
```

**RTX 4090 24GB:**
```bash
GPU_MEMORY_UTILIZATION=0.92
MAX_MODEL_LEN=12288
CHUNK_SIZE=200
DEFAULT_MODEL=google/gemma-3-4b-it
```

After changing `.env`, restart services:
```bash
docker compose restart
```

## Docker Compose Services

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api-server
docker compose logs -f worker
docker compose logs -f postgres
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart worker
docker compose restart api-server
```

### Stop Services

```bash
# Stop all (keeps data)
docker compose stop

# Stop and remove containers (keeps data)
docker compose down

# Stop and remove everything (including data)
docker compose down -v
```

## Troubleshooting

### Issue: GPU not accessible in container

**Check:**
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

**If this fails:**
```bash
# Reinstall NVIDIA Container Toolkit
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Issue: Port already in use

**Solution:**
```bash
# Change port in .env
BATCH_API_PORT=4081

# Restart
docker compose down
docker compose up -d
```

### Issue: Out of memory

**Solution:**
```bash
# Edit .env
GPU_MEMORY_UTILIZATION=0.80  # Reduce from 0.90
CHUNK_SIZE=50                # Reduce from 100

# Restart
docker compose restart worker
```

### Issue: Worker not processing jobs

**Check worker logs:**
```bash
docker compose logs -f worker
```

**Restart worker:**
```bash
docker compose restart worker
```

## Advanced Usage

### Custom Docker Compose

Create `docker-compose.override.yml` for custom settings:

```yaml
version: '3.8'

services:
  worker:
    environment:
      - GPU_MEMORY_UTILIZATION=0.85
      - DEFAULT_MODEL=google/gemma-3-7b-it
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Multiple GPUs

```yaml
# docker-compose.override.yml
services:
  worker:
    environment:
      - TENSOR_PARALLEL_SIZE=2  # Use 2 GPUs
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2  # Use 2 GPUs
              capabilities: [gpu]
```

### Development Mode

```bash
# Mount local code for development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Production Deployment

### Enable HTTPS

```bash
# Install Caddy reverse proxy
docker run -d \
  --name caddy \
  -p 80:80 -p 443:443 \
  -v caddy_data:/data \
  -v caddy_config:/config \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
  caddy:latest
```

**Caddyfile:**
```
your-domain.com {
    reverse_proxy localhost:4080
}
```

### Persistent Storage

Data is automatically persisted in Docker volumes:
- `postgres_data` - Database
- `model_cache` - Downloaded models
- `batch_files` - Uploaded files
- `batch_results` - Job results

**Backup:**
```bash
# Backup database
docker exec vllm-postgres pg_dump -U vllm_user vllm_batch > backup.sql

# Backup volumes
docker run --rm -v postgres_data:/data -v $PWD:/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

**Restore:**
```bash
# Restore database
docker exec -i vllm-postgres psql -U vllm_user vllm_batch < backup.sql
```

## Next Steps

- **Add Models**: http://localhost:4080/model-management.html
- **Run Benchmarks**: http://localhost:4080/benchmark-runner.html
- **View Queue**: http://localhost:4080/queue-monitor.html
- **Read Docs**: [Documentation](.)

## Support

- **Issues**: [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)
- **Troubleshooting**: [Troubleshooting Guide](TROUBLESHOOTING.md)

