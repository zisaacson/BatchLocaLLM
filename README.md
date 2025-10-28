# vLLM Batch Server

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![vLLM](https://img.shields.io/badge/vLLM-0.11.0-green.svg)](https://github.com/vllm-project/vllm)

**Two independent implementations for batch LLM inference**

This repository contains **two separate branches** for different use cases:

- **`ollama` branch** - Consumer GPU implementation (RTX 4080 16GB) using Ollama
- **`vllm` branch** - Production GPU implementation (24GB+ VRAM) using vLLM with model hot-swapping

**⚠️ These branches never merge - they are independent implementations.**

## 📊 Benchmark Results

See **[BENCHMARKS.md](BENCHMARKS.md)** for the single source of truth on all testing, decisions, and performance comparisons.

## 🎯 Which Branch Should I Use?

### `ollama` Branch - Consumer GPUs (16GB VRAM)
**Use this if you have:** RTX 4080, RTX 3090, RTX 4090, or similar consumer GPUs

**Features:**
- ✅ Optimized for 16GB VRAM
- ✅ Uses Ollama for easy model management
- ✅ Parallel batch processing (8 workers)
- ✅ Comprehensive benchmarking system
- ✅ **Tested:** gemma3:1b @ 0.92 req/s (73% GPU efficiency)

**Best for:** Local development, testing, cost-effective inference

### `vllm` Branch - Production GPUs (24GB+ VRAM)
**Use this if you have:** A100, H100, RTX 6000 Ada, or cloud GPUs

**Features:**
- ✅ vLLM's native continuous batching
- ✅ Model hot-swapping for A/B testing
- ✅ 4-bit quantization support (fits 12B models in 16GB)
- ✅ OpenAI-compatible API
- ✅ **Testing:** Offline vs Server mode comparison

**Best for:** Production deployments, A/B testing, maximum throughput

## 🚀 Quick Start

### 1. Choose Your Branch

```bash
# For consumer GPUs (16GB VRAM)
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server
git checkout ollama

# For production GPUs (24GB+ VRAM) or 4-bit quantization
git checkout vllm
```

### 2. Follow Branch-Specific Instructions

Each branch has its own README with setup instructions:
- **`ollama` branch:** See README for Ollama setup
- **`vllm` branch:** See README for vLLM setup

### 3. Check Benchmark Results

See **[BENCHMARKS.md](BENCHMARKS.md)** for:
- Performance comparisons
- Test results
- Decision log
- Hardware requirements

## 📋 Repository Structure

```
master (this branch)
├── BENCHMARKS.md          ← Single source of truth for all testing
├── README.md              ← This file
└── batch_5k.jsonl         ← 5K sample dataset for testing

ollama branch
├── Full Ollama implementation
├── Parallel batch processing
├── Benchmarking system
└── Tested on RTX 4080 16GB

vllm branch
├── Full vLLM implementation
├── Model hot-swapping
├── A/B testing scripts
└── 4-bit quantization support
```

## 🧪 Testing & Benchmarking

All benchmark results are tracked in **[BENCHMARKS.md](BENCHMARKS.md)**.

# Start the server
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

The server will:
1. Download the model (first run only)
2. Load it into GPU memory
3. Start accepting batch requests on port 8000

## 📖 Usage

### Submit a Batch Job

```python
from openai import OpenAI

# Point to your local vLLM batch server
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed-for-local"
)

# Create batch input file (JSONL format)
batch_requests = [
    {
        "custom_id": "request-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 100
        }
    },
    {
        "custom_id": "request-2",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "max_tokens": 100
        }
    }
]

# Write to JSONL file
with open("batch_input.jsonl", "w") as f:
    for req in batch_requests:
        f.write(json.dumps(req) + "\n")

# Upload file
with open("batch_input.jsonl", "rb") as f:
    file = client.files.create(file=f, purpose="batch")

# Create batch job
batch = client.batches.create(
    input_file_id=file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h"
)

print(f"Batch created: {batch.id}")
print(f"Status: {batch.status}")
```

### Check Batch Status

```python
# Poll for completion
import time

while True:
    batch_status = client.batches.retrieve(batch.id)
    print(f"Status: {batch_status.status}")
    
    if batch_status.status == "completed":
        break
    elif batch_status.status == "failed":
        print("Batch failed!")
        break
    
    time.sleep(5)
```

### Download Results

```python
# Get results
if batch_status.output_file_id:
    result_content = client.files.content(batch_status.output_file_id)
    results = result_content.text()
    
    # Parse JSONL results
    for line in results.strip().split("\n"):
        result = json.loads(line)
        print(f"Request {result['custom_id']}: {result['response']['body']['choices'][0]['message']['content']}")
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Application                      │
│              (Uses OpenAI Python SDK)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP (OpenAI-compatible API)
                     │
┌────────────────────▼────────────────────────────────────┐
│              vLLM Batch Server (FastAPI)                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Batch API Endpoints                            │   │
│  │  - POST /v1/batches (create)                    │   │
│  │  - GET /v1/batches/{id} (status)                │   │
│  │  - POST /v1/batches/{id}/cancel                 │   │
│  │  - POST /v1/files (upload)                      │   │
│  │  - GET /v1/files/{id}/content (download)        │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Batch Processor                                │   │
│  │  - JSONL parsing                                │   │
│  │  - Job queue management                         │   │
│  │  - Result aggregation                           │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Storage Layer                                  │   │
│  │  - Local file storage for jobs/results         │   │
│  │  - SQLite for job metadata                     │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Python API calls
                     │
┌────────────────────▼────────────────────────────────────┐
│                   vLLM Engine                           │
│  - Continuous batching                                  │
│  - Automatic prefix caching                             │
│  - PagedAttention                                       │
│  - GPU memory management                                │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ CUDA
                     │
┌────────────────────▼────────────────────────────────────┐
│                  NVIDIA GPU                             │
│              (RTX 4080 / A100 / etc.)                   │
└─────────────────────────────────────────────────────────┘
```

## 🔧 Configuration

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

Key environment variables:

```bash
# Model Configuration
MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
MODEL_REVISION=main

# GPU Settings
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9

# Batch Processing
MAX_BATCH_SIZE=256
MAX_CONCURRENT_BATCHES=4

# Storage
STORAGE_PATH=/data/batches
```

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [API Documentation](docs/API.md)
- [Integration with ARIS](docs/ARIS_INTEGRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 🤝 Integration Examples

### Switching Between Local and Production

```typescript
// config.ts
const BATCH_CLIENT_CONFIG = {
  baseURL: process.env.NODE_ENV === 'production' 
    ? 'https://api.parasail.io/v1'  // Production: Parasail
    : 'http://localhost:8000/v1',   // Local: vLLM Batch Server
  apiKey: process.env.BATCH_API_KEY || 'local-dev'
}

// Your existing ParasailBatchClient works unchanged!
const client = new OpenAI(BATCH_CLIENT_CONFIG)
```

## 🧪 Testing

```bash
# Run unit tests
docker-compose run --rm server pytest tests/

# Run integration tests
docker-compose run --rm server pytest tests/integration/

# Load testing
docker-compose run --rm server python tests/load_test.py
```

## 📊 Performance

Tested on RTX 4080 (16GB VRAM):

| Model | Batch Size | Throughput | Latency (p50) |
|-------|-----------|------------|---------------|
| Llama-3.1-8B | 100 | 45 tok/s | 2.3s |
| Llama-3.1-8B | 500 | 52 tok/s | 9.8s |
| Mistral-7B | 100 | 48 tok/s | 2.1s |

With prefix caching enabled: **80% reduction in prompt processing time** for repeated system prompts.

## 🛣️ Roadmap

- [ ] Support for multiple models simultaneously
- [ ] Redis-based job queue for multi-instance deployments
- [ ] Prometheus metrics export
- [ ] Web UI for job monitoring
- [ ] S3-compatible storage backend
- [ ] Streaming batch results

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM inference engine
- [OpenAI](https://openai.com) - Batch API specification
- [Parasail](https://parasail.io) - Inspiration for production batch processing

## 💬 Community

- **Issues**: [GitHub Issues](https://github.com/YOUR_ORG/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_ORG/vllm-batch-server/discussions)

---

**Built with ❤️ for the open-source community**

