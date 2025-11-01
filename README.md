<div align="center">

# vLLM Batch Server

**Production-ready OpenAI-compatible batch inference for local LLMs**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![vLLM](https://img.shields.io/badge/vLLM-0.11.0-green.svg)](https://github.com/vllm-project/vllm)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Process **50,000+ requests** on consumer GPUs (RTX 4080 16GB) with automatic model hot-swapping, incremental saves, and real-time monitoring.

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Examples](#-examples) • [Architecture](#-architecture)

</div>

---

## 🎯 Why This Exists

Running large-scale LLM inference locally is **hard**:
- ❌ OpenAI Batch API costs add up fast ($$$)
- ❌ Consumer GPUs run out of memory (OOM crashes)
- ❌ Processing 50K requests takes days without batching
- ❌ Comparing multiple models requires manual orchestration
- ❌ No visibility into progress or failures

**This project solves all of that.**

Built for teams who need:
- ✅ **Cost-effective inference** on local hardware
- ✅ **Model comparison** across multiple LLMs
- ✅ **Training data curation** with human-in-the-loop
- ✅ **Production reliability** with monitoring and error recovery

---

## ✨ Features

### Core Capabilities

- **🔄 OpenAI-Compatible API** - Drop-in replacement for OpenAI Batch API
  - Same JSONL format, same endpoints
  - Works with existing OpenAI client libraries
  - Supports `/v1/chat/completions` endpoint

- **🚀 Model Hot-Swapping** - Automatic model loading/unloading
  - Queue jobs for different models
  - Worker automatically switches models
  - Prevents OOM by unloading before loading

- **💾 Crash-Resistant Processing** - Never lose progress
  - Incremental saves every 100 requests
  - Resume from last checkpoint on crash
  - Atomic file operations

- **📊 Real-Time Monitoring** - Full observability stack
  - Grafana dashboards (GPU, API, throughput)
  - Prometheus metrics
  - Loki log aggregation
  - Web-based queue monitor

### Advanced Features

- **🎯 Consumer GPU Optimized** - Runs on RTX 4080 16GB
  - Tested with 4B-7B parameter models
  - Automatic memory management
  - CPU offload support for larger models

- **📈 Benchmarking Tools** - Compare models scientifically
  - Side-by-side result comparison
  - Quality vs speed vs cost analysis
  - Synthetic test data generation

- **🔍 Dataset Workbench** - Interactive result exploration
  - Upload datasets via web UI
  - Select models to compare
  - View results side-by-side
  - Export curated datasets

- **🐳 Production-Ready Deployment**
  - Docker Compose for one-command setup
  - PostgreSQL for durable job storage
  - Systemd services for auto-start
  - Health checks and graceful shutdown

---

## 🚀 Quick Start

### Prerequisites

- **GPU**: NVIDIA GPU with 16GB+ VRAM (RTX 4080, A100, etc.)
- **OS**: Linux (Ubuntu 22.04+ recommended)
- **Python**: 3.10 or higher
- **Docker**: For PostgreSQL and monitoring stack

### Installation

```bash
# 1. Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d

# 5. Initialize database
python -c "from core.batch_app.database import init_db; init_db()"

# 6. Start services
./scripts/start_gemma3_conquest.sh
```

### Verify Installation

```bash
# Check API health
curl http://localhost:4080/health

# View queue status
curl http://localhost:4080/v1/queue

# Open web UI
open http://localhost:4080/queue-monitor.html
```

---

## 📖 Usage

### Basic Workflow

```python
import requests

# 1. Upload batch file
with open("examples/datasets/demo_batch_10.jsonl", "rb") as f:
    response = requests.post(
        "http://localhost:4080/v1/files",
        files={"file": f},
        data={"purpose": "batch"}
    )
    file_id = response.json()["id"]

# 2. Create batch job
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
)
batch_id = response.json()["id"]

# 3. Poll for completion
import time
while True:
    response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}")
    status = response.json()["status"]
    if status in ["completed", "failed", "cancelled"]:
        break
    time.sleep(5)

# 4. Download results
output_file_id = response.json()["output_file_id"]
results = requests.get(f"http://localhost:4080/v1/files/{output_file_id}/content")
print(results.text)
```

### Using the CLI Client

```bash
# Run the example client
python integrations/examples/simple_client.py

# Generate synthetic test data
python tools/generate_synthetic_data.py --count 1000 --output my_batch.jsonl
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/API.md) | Complete API documentation with examples |
| [Architecture](docs/ARCHITECTURE.md) | System design and component overview |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment instructions |
| [Adding Models](docs/ADD_MODEL_GUIDE.md) | How to add new models to the registry |

---

## 💡 Examples

### Example 1: Simple Batch Processing

```bash
# Upload a batch file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@examples/datasets/demo_batch_10.jsonl" \
  -F "purpose=batch"

# Create batch job
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file_abc123",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'

# Check status
curl http://localhost:4080/v1/batches/batch_xyz789

# Download results
curl http://localhost:4080/v1/files/file_output123/content > results.jsonl
```

### Example 2: Model Comparison

```python
# Compare Gemma 3 4B vs Llama 3.2 3B on same dataset
models = ["google/gemma-3-4b-it", "meta-llama/Llama-3.2-3B-Instruct"]

for model in models:
    # Create batch file with specific model
    batch_file = create_batch_file(dataset, model)

    # Upload and process
    file_id = upload_file(batch_file)
    batch_id = create_batch(file_id)

    # Wait for completion
    wait_for_batch(batch_id)

    # Download and analyze results
    results = download_results(batch_id)
    analyze_quality(results, model)
```

### Example 3: Generate Synthetic Test Data

```bash
# Generate 1000 synthetic candidates
python tools/generate_synthetic_data.py \
  --count 1000 \
  --output benchmarks/synthetic/candidates_1k.jsonl \
  --metadata

# Use for benchmarking
python integrations/examples/simple_client.py
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Application                    │
│              (Your app, curl, Python script, etc.)          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Server (FastAPI)                    │
│  • /v1/batches - Create/list/cancel batch jobs             │
│  • /v1/files - Upload/download files                       │
│  • /v1/queue - Real-time queue status                      │
│  • /health - Health checks                                 │
└────────────────────────┬────────────────────────────────────┘
                         │ PostgreSQL
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  • batch_jobs - Job metadata and status                    │
│  • uploaded_files - File storage                           │
│  • worker_heartbeat - Worker health tracking               │
│  • model_registry - Available models                       │
└────────────────────────┬────────────────────────────────────┘
                         │ Polling
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Worker Process                            │
│  1. Poll database for pending jobs                         │
│  2. Load required model (hot-swap if needed)               │
│  3. Process batch with vLLM                                │
│  4. Save results incrementally (every 100 requests)        │
│  5. Update job status and metrics                          │
└────────────────────────┬────────────────────────────────────┘
                         │ vLLM API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      vLLM Engine                             │
│  • Model loading/unloading                                  │
│  • Batch inference with KV cache                           │
│  • GPU memory management                                    │
│  • Automatic batching and scheduling                        │
└─────────────────────────────────────────────────────────────┘

                    Monitoring Stack
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   Grafana    │  Prometheus  │     Loki     │ Queue Monitor│
│  (Port 4020) │ (Port 4022)  │ (Port 4021)  │ (Web UI)     │
│  Dashboards  │   Metrics    │     Logs     │  Real-time   │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

### Key Design Decisions

1. **Sequential Processing** - One job at a time prevents OOM and simplifies debugging
2. **Model Hot-Swapping** - Automatic model switching enables multi-model workflows
3. **Incremental Saves** - Checkpoint every 100 requests prevents data loss
4. **PostgreSQL** - Durable job storage with ACID guarantees
5. **Separate Worker** - Decoupled from API server for reliability

---

## 🎯 Use Cases

### 1. Cost-Effective Batch Inference

Replace expensive OpenAI Batch API calls with local inference:
- **Before**: $0.50/1M tokens × 50K requests = $$$
- **After**: Free (local GPU) + electricity

### 2. Model Comparison & Selection

Test multiple models on the same dataset:
- Compare quality, speed, and cost
- A/B test different prompts
- Find the best model for your use case

### 3. Training Data Curation

Generate and curate training datasets:
- Process thousands of examples
- Review and label outputs
- Export gold-standard datasets
- Build in-context learning examples

### 4. Research & Experimentation

Rapid prototyping for ML research:
- Test new prompting strategies
- Evaluate model capabilities
- Benchmark performance
- Reproduce experiments

---

## 🔧 Configuration

| Model | Params | Throughput | Memory | Notes |
|-------|--------|------------|--------|-------|
| Gemma 3 4B | 4B | 450 tok/s | 6.5 GB | No offload needed |
| Qwen 2.5 3B | 3B | 520 tok/s | 5.8 GB | Fastest |
| Llama 3.2 3B | 3B | 480 tok/s | 6.2 GB | Best quality |
| OLMo 2 7B | 7B | 200 tok/s | 14 GB | Needs 8GB CPU offload |

**Test:** 5,000 requests (~800 tokens each)
- Gemma 3 4B: ~12 minutes
- OLMo 2 7B: ~45 minutes (CPU offload penalty)

## Architecture

```
Client → FastAPI Server → PostgreSQL Queue → Worker → vLLM Engine
                                              ↓
                                         Incremental
                                           Saves
```

**Key Design:**
- **Separate API + Worker** - API never blocks, worker polls queue
- **Model hot-swap** - Worker unloads previous model before loading next (prevents OOM)
- **Chunked processing** - 100-request chunks with incremental saves
- **Database-driven** - Model configs in PostgreSQL, not hardcoded

---

## Tech Stack

- **vLLM 0.11.0** - Offline batch engine
- **FastAPI** - OpenAI-compatible REST API
- **PostgreSQL** - Job queue + model registry
- **SQLAlchemy 2.0** - Type-safe ORM
- **Prometheus** - Metrics (GPU temp, throughput, queue depth)

---

## Why Not Just Use vLLM Directly?

vLLM's offline engine is great, but lacks:
- ❌ Job queue (can't submit multiple batches)
- ❌ Model hot-swap (manual restart needed)
- ❌ Incremental saves (lose all progress on crash)
- ❌ OpenAI compatibility (different API format)
- ❌ Multi-model support (one model at a time)

This server adds all of that.

---

## Current Limitations

- **Single GPU only** - No tensor parallelism (yet)
- **GGUF support limited** - vLLM 0.11.0 doesn't support OLMo2/GPT-OSS GGUF
- **No streaming** - Batch-only (by design)
- **Local only** - No distributed workers (yet)
---

## Repository Structure

```
vllm-batch-server/
├── core/
│   ├── batch_app/
│   │   ├── api_server.py       # FastAPI server (port 4080)
│   │   ├── worker.py           # Background job processor
│   │   ├── database.py         # PostgreSQL models
│   │   └── model_manager.py    # Model registry & hot-swap logic
│   └── config.py               # Configuration
├── static/
│   ├── workbench.html          # Dataset comparison UI
│   ├── model-management.html   # Add/remove models
│   └── benchmark-runner.html   # Run benchmarks
├── benchmarks/                 # Benchmark results
├── scripts/                    # Utility scripts
└── README.md                   # This file
```

---

## Documentation

- **[docs/API.md](docs/API.md)** - API reference
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment guide

---

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **vLLM Team** - Excellent inference engine
- **OpenAI** - Batch API specification
---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)

---

<div align="center">

**Built with ❤️ for the open source community**

⭐ Star this repo if you find it useful!

</div>
