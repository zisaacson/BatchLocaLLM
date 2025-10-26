# Deployment Guide - RTX 4080

This guide shows how to deploy vLLM Batch Server on your RTX 4080 machine (10.0.0.223).

## 🎯 Overview

**Replace Ollama with vLLM Batch Server** for:
- ✅ OpenAI-compatible Batch API
- ✅ 85x more concurrent requests (256 vs 3)
- ✅ 3-5x higher throughput (45-52 tok/s)
- ✅ Automatic prefix caching (80% speedup)
- ✅ Better GPU utilization (90% vs ~50%)

## 📋 Prerequisites

**On RTX 4080 machine (10.0.0.223):**
- NVIDIA RTX 4080 (16GB VRAM) ✅
- Docker & Docker Compose
- NVIDIA Container Toolkit
- Port 8000 available (or change in .env)

## 🚀 Deployment Steps

### Step 1: Stop Ollama (Optional)

If you want to replace Ollama completely:

```bash
# On 10.0.0.223
docker stop ollama  # or however Ollama is running
# Or change vLLM port to 8001 to run both
```

### Step 2: Transfer Files to RTX 4080

```bash
# From your local machine
cd /home/zack/Documents/augment-projects/Local
scp -r vllm-batch-server user@10.0.0.223:~/
```

### Step 3: Configure Environment

```bash
# On 10.0.0.223
cd ~/vllm-batch-server

# .env is already configured for RTX 4080!
# Just add your Hugging Face token if using gated models
nano .env
# Set: HF_TOKEN=hf_xxxxxxxxxxxxx
```

### Step 4: Deploy

```bash
# On 10.0.0.223
cd ~/vllm-batch-server

# Quick start (automated)
./scripts/quick-start.sh

# Or manual deployment
docker-compose up -d
```

### Step 5: Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# From your local machine
curl http://10.0.0.223:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "model_name": "meta-llama/Llama-3.1-8B-Instruct",
#   "gpu_memory_used": "12.5 GB",
#   "gpu_memory_total": "16.0 GB"
# }
```

## 🔧 Configuration Options

### Run on Different Port (Keep Ollama)

```bash
# Edit .env
PORT=8001

# Then access at:
# http://10.0.0.223:8001
```

### Use Different Model

```bash
# Edit .env
MODEL_NAME=meta-llama/Llama-3.2-3B-Instruct  # Smaller, faster
# or
MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3
```

### Optimize for Memory

```bash
# Edit .env
GPU_MEMORY_UTILIZATION=0.85  # Use less GPU memory
MAX_MODEL_LEN=4096           # Smaller context window
MAX_NUM_SEQS=128             # Fewer concurrent sequences
```

## 📊 Performance Tuning

### RTX 4080 Optimized Settings (Default)

```bash
# Already configured in .env
TENSOR_PARALLEL_SIZE=1              # Single GPU
GPU_MEMORY_UTILIZATION=0.9          # 90% of 16GB
MAX_NUM_SEQS=256                    # 256 concurrent requests
ENABLE_PREFIX_CACHING=true          # 80% speedup
ENABLE_CUDA_GRAPH=true              # 20-30% faster
```

### For Maximum Throughput

```bash
MAX_NUM_SEQS=512                    # More concurrent requests
GPU_MEMORY_UTILIZATION=0.95         # Use more GPU memory
SCHEDULER_DELAY=0.1                 # Batch more requests
```

### For Lower Latency

```bash
MAX_NUM_SEQS=64                     # Fewer concurrent requests
SCHEDULER_DELAY=0.0                 # Process immediately
```

## 🧪 Testing

### Test Single Request

```bash
curl -X POST http://10.0.0.223:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### Test Batch Processing

```bash
# From your local machine
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server

# Edit examples/simple_batch.py
# Change: base_url="http://10.0.0.223:8000/v1"

python examples/simple_batch.py
```

## 🔍 Monitoring

### View Logs

```bash
# On 10.0.0.223
docker-compose logs -f
```

### Check GPU Usage

```bash
# On 10.0.0.223
watch -n 1 nvidia-smi
```

### Prometheus Metrics

```bash
curl http://10.0.0.223:9090/metrics
```

## 🛠️ Troubleshooting

### Server Won't Start

```bash
# Check logs
docker-compose logs

# Common issues:
# 1. Out of GPU memory → Reduce GPU_MEMORY_UTILIZATION
# 2. Model download failed → Check HF_TOKEN
# 3. Port already in use → Change PORT in .env
```

### Low Performance

```bash
# Check GPU utilization
nvidia-smi

# If GPU usage < 80%:
# - Increase MAX_NUM_SEQS
# - Increase SCHEDULER_DELAY
# - Enable CUDA graphs (should be on by default)
```

### Out of Memory

```bash
# Reduce memory usage:
GPU_MEMORY_UTILIZATION=0.8
MAX_MODEL_LEN=4096
MAX_NUM_SEQS=128
```

## 🔄 Updating

```bash
# On 10.0.0.223
cd ~/vllm-batch-server

# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## 🗑️ Uninstall

```bash
# On 10.0.0.223
cd ~/vllm-batch-server

# Stop and remove containers
docker-compose down -v

# Remove files
cd ~
rm -rf vllm-batch-server
```

## 📞 Support

- **GitHub Issues**: https://github.com/YOUR_ORG/vllm-batch-server/issues
- **Documentation**: See `docs/` directory
- **API Reference**: See `docs/API.md`
