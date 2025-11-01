# Troubleshooting Guide

This guide covers common issues and their solutions.

## Table of Contents

- [Installation Issues](#installation-issues)
- [GPU & Memory Issues](#gpu--memory-issues)
- [Worker Issues](#worker-issues)
- [API Server Issues](#api-server-issues)
- [Database Issues](#database-issues)
- [Model Loading Issues](#model-loading-issues)
- [Performance Issues](#performance-issues)
- [Networking Issues](#networking-issues)

---

## Installation Issues

### Issue: vLLM installation fails

**Symptoms:**
```
ERROR: Failed building wheel for vllm
```

**Solutions:**

1. **Check CUDA version:**
```bash
nvcc --version
# vLLM requires CUDA 12.1+
```

2. **Install CUDA toolkit:**
```bash
# Ubuntu/Debian
sudo apt install nvidia-cuda-toolkit

# Or download from NVIDIA
wget https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda_12.1.0_530.30.02_linux.run
sudo sh cuda_12.1.0_530.30.02_linux.run
```

3. **Use pre-built wheels:**
```bash
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu121
```

### Issue: Python version incompatibility

**Symptoms:**
```
ERROR: Package 'vllm' requires a different Python: 3.9.0 not in '>=3.10'
```

**Solution:**
```bash
# Install Python 3.11
sudo apt install python3.11 python3.11-venv

# Create venv with Python 3.11
python3.11 -m venv venv
source venv/bin/activate
```

---

## GPU & Memory Issues

### Issue: CUDA Out of Memory (OOM)

**Symptoms:**
```
torch.cuda.OutOfMemoryError: CUDA out of memory
```

**Solutions:**

1. **Reduce GPU memory utilization:**
```bash
# Edit .env
GPU_MEMORY_UTILIZATION=0.80  # Default is 0.90
```

2. **Use a smaller model:**
```bash
# Instead of 7B, use 4B or 3B
DEFAULT_MODEL=google/gemma-3-4b-it
```

3. **Enable CPU offload (for larger models):**
```bash
# In model configuration
CPU_OFFLOAD_GB=8  # Offload 8GB to CPU
```

4. **Check GPU memory:**
```bash
nvidia-smi
# Kill any other processes using GPU
```

### Issue: GPU not detected

**Symptoms:**
```
RuntimeError: No CUDA GPUs are available
```

**Solutions:**

1. **Check NVIDIA driver:**
```bash
nvidia-smi
# If this fails, reinstall NVIDIA drivers
```

2. **Verify CUDA installation:**
```bash
python -c "import torch; print(torch.cuda.is_available())"
# Should print: True
```

3. **Reinstall PyTorch with CUDA:**
```bash
pip uninstall torch
pip install torch --extra-index-url https://download.pytorch.org/whl/cu121
```

---

## Worker Issues

### Issue: Worker not processing jobs

**Symptoms:**
- Batch jobs stuck in "validating" status
- Worker logs show no activity

**Solutions:**

1. **Check worker is running:**
```bash
ps aux | grep worker
# Should show: python -m core.batch_app.worker
```

2. **Check worker logs:**
```bash
tail -f logs/worker.log
```

3. **Restart worker:**
```bash
pkill -f "batch_app.worker"
python -m core.batch_app.worker &
```

4. **Check worker heartbeat:**
```bash
curl http://localhost:4080/v1/worker/heartbeat
# Should return recent timestamp
```

### Issue: Worker crashes during processing

**Symptoms:**
```
Worker process terminated unexpectedly
```

**Solutions:**

1. **Check for OOM:**
```bash
dmesg | grep -i "out of memory"
```

2. **Reduce batch size:**
```bash
# Edit .env
CHUNK_SIZE=50  # Default is 100
```

3. **Enable incremental saves:**
```bash
# Already enabled by default
INCREMENTAL_SAVE_INTERVAL=100
```

---

## API Server Issues

### Issue: Port already in use

**Symptoms:**
```
ERROR: [Errno 98] Address already in use
```

**Solutions:**

1. **Find process using port:**
```bash
lsof -i :4080
```

2. **Kill existing process:**
```bash
kill -9 <PID>
```

3. **Use different port:**
```bash
# Edit .env
BATCH_API_PORT=4081
```

### Issue: API returns 500 errors

**Symptoms:**
```
{"detail":"Internal Server Error"}
```

**Solutions:**

1. **Check API logs:**
```bash
tail -f logs/api_server.log
```

2. **Check database connection:**
```bash
docker ps | grep postgres
# Ensure PostgreSQL is running
```

3. **Restart API server:**
```bash
pkill -f "batch_app.api_server"
python -m core.batch_app.api_server &
```

---

## Database Issues

### Issue: PostgreSQL connection refused

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**

1. **Check PostgreSQL is running:**
```bash
docker ps | grep postgres
```

2. **Start PostgreSQL:**
```bash
docker compose -f docker-compose.postgres.yml up -d
```

3. **Check connection string:**
```bash
# In .env
DATABASE_URL=postgresql://vllm_user:vllm_password@localhost:4332/vllm_batch
```

4. **Test connection:**
```bash
docker exec -it vllm-postgres psql -U vllm_user -d vllm_batch -c "SELECT 1;"
```

### Issue: Database tables not found

**Symptoms:**
```
psycopg2.errors.UndefinedTable: relation "batch_jobs" does not exist
```

**Solution:**
```bash
# Initialize database
python -c "from core.batch_app.database import init_db; init_db()"
```

---

## Model Loading Issues

### Issue: Model not found

**Symptoms:**
```
ValueError: Model 'google/gemma-3-4b-it' not found
```

**Solutions:**

1. **Check model registry:**
```bash
curl http://localhost:4080/v1/models
```

2. **Add model to registry:**
```bash
# Via web UI
xdg-open http://localhost:4080/model-management.html

# Or via API
curl -X POST http://localhost:4080/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "google/gemma-3-4b-it",
    "model_name": "Gemma 3 4B",
    "hf_model_id": "google/gemma-3-4b-it"
  }'
```

### Issue: Model download fails

**Symptoms:**
```
OSError: Can't load tokenizer for 'google/gemma-3-4b-it'
```

**Solutions:**

1. **Check internet connection:**
```bash
ping huggingface.co
```

2. **Set HuggingFace token (for gated models):**
```bash
export HF_TOKEN=your_token_here
```

3. **Pre-download model:**
```bash
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('google/gemma-3-4b-it')"
```

---

## Performance Issues

### Issue: Slow inference speed

**Symptoms:**
- Throughput < 100 tokens/second
- Jobs taking much longer than expected

**Solutions:**

1. **Check GPU utilization:**
```bash
nvidia-smi
# GPU utilization should be 90-100%
```

2. **Increase batch size:**
```bash
# Edit .env
CHUNK_SIZE=200  # Default is 100
```

3. **Disable CPU offload (if enabled):**
```bash
# Only use CPU offload for models that don't fit in VRAM
CPU_OFFLOAD_GB=0
```

4. **Use FP16 instead of FP32:**
```bash
# In model configuration
DTYPE=float16
```

### Issue: High memory usage

**Symptoms:**
- System running out of RAM
- Swap usage increasing

**Solutions:**

1. **Reduce KV cache size:**
```bash
MAX_MODEL_LEN=4096  # Default is 8192
```

2. **Limit concurrent requests:**
```bash
CHUNK_SIZE=50  # Process fewer requests at once
```

---

## Networking Issues

### Issue: Cannot access API from another machine

**Symptoms:**
```
curl: (7) Failed to connect to 10.0.0.223 port 4080
```

**Solutions:**

1. **Check firewall:**
```bash
sudo ufw allow 4080/tcp
```

2. **Verify API is listening on 0.0.0.0:**
```bash
# In .env
BATCH_API_HOST=0.0.0.0  # Not 127.0.0.1
```

3. **Check network connectivity:**
```bash
ping <server-ip>
telnet <server-ip> 4080
```

---

## Getting More Help

### Collect Diagnostic Information

```bash
# System info
uname -a
python --version
nvidia-smi

# Service status
ps aux | grep -E "api_server|worker"
docker ps

# Logs
tail -100 logs/api_server.log
tail -100 logs/worker.log

# Database status
curl http://localhost:4080/v1/queue
```

### Report an Issue

When reporting issues, please include:

1. **Environment details** (OS, Python version, GPU, CUDA version)
2. **Steps to reproduce**
3. **Error messages** (full stack trace)
4. **Logs** (API server, worker, database)
5. **Configuration** (.env file, model config)

**Report issues at:** https://github.com/zisaacson/vllm-batch-server/issues

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `CUDA out of memory` | GPU VRAM full | Reduce GPU_MEMORY_UTILIZATION or use smaller model |
| `Address already in use` | Port conflict | Kill existing process or change port |
| `Model not found` | Model not in registry | Add model via web UI or API |
| `Connection refused` | PostgreSQL not running | Start PostgreSQL with docker-compose |
| `Worker not responding` | Worker crashed | Check logs and restart worker |
| `Batch stuck in validating` | Worker not processing | Restart worker |

---

## Performance Tuning

### Optimal Settings for RTX 3090 24GB

```bash
# .env
GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=8192
CHUNK_SIZE=150
TENSOR_PARALLEL_SIZE=1

# Recommended models
# - Gemma 3 4B: 420 tok/s
# - Llama 3.2 3B: 450 tok/s
# - Qwen 2.5 3B: 480 tok/s
# - Gemma 3 7B: 250 tok/s (fits with 24GB!)
```

### Optimal Settings for RTX 4080 16GB

```bash
# .env
GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=8192
CHUNK_SIZE=100
TENSOR_PARALLEL_SIZE=1

# Recommended models
# - Gemma 3 4B: 450 tok/s
# - Llama 3.2 3B: 480 tok/s
# - Qwen 2.5 3B: 520 tok/s
```

### Optimal Settings for RTX 4090 24GB

```bash
# .env
GPU_MEMORY_UTILIZATION=0.92
MAX_MODEL_LEN=12288
CHUNK_SIZE=200
TENSOR_PARALLEL_SIZE=1

# Recommended models
# - Gemma 3 4B: 550 tok/s
# - Llama 3.2 3B: 580 tok/s
# - Qwen 2.5 3B: 620 tok/s
# - Gemma 3 7B: 320 tok/s
# - Llama 3.1 8B: 280 tok/s
```

### Optimal Settings for RTX 3060 12GB (Budget Option)

```bash
# .env
GPU_MEMORY_UTILIZATION=0.85
MAX_MODEL_LEN=4096
CHUNK_SIZE=50
TENSOR_PARALLEL_SIZE=1

# Recommended models
# - Gemma 3 2B: 380 tok/s
# - Llama 3.2 1B: 450 tok/s
# - Qwen 2.5 3B: 280 tok/s (tight fit)
```

---

## Still Having Issues?

- **Documentation**: [docs/](.)
- **GitHub Issues**: [Report a bug](https://github.com/zisaacson/vllm-batch-server/issues/new?template=bug_report.md)
- **Discussions**: [Ask a question](https://github.com/zisaacson/vllm-batch-server/discussions)

