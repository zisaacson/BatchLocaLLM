# vLLM Batch Server

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![vLLM](https://img.shields.io/badge/vLLM-0.11.0-green.svg)](https://github.com/vllm-project/vllm)

**OpenAI-compatible batch processing server powered by vLLM with integrated data curation system**

Production-ready batch inference system for local LLMs running on consumer GPUs (RTX 4080 16GB). Includes beautiful web UI for curating training datasets from batch results.

---

## 📦 Repository Structure

This is a **monorepo** with public and private code:

```
vllm-batch-server/
├── core/                      ← OPEN SOURCE (Apache 2.0)
│   ├── batch_app/             # Batch processing server
│   ├── result_handlers/       # Plugin system
│   ├── config.py              # Configuration
│   ├── tests/                 # Test suite
│   └── README.md              # Public documentation
│
├── integrations/              ← PRIVATE (gitignored)
│   ├── aris/                  # Aris-specific code (private)
│   └── examples/              # Example integrations (public)
│
├── benchmarks/                # Benchmark results
├── scripts/                   # Utility scripts
└── README.md                  # This file
```

**📚 For open source documentation, see [`core/README.md`](core/README.md)**

**🔌 For integration examples, see [`integrations/examples/README.md`](integrations/examples/README.md)**

---

## ✨ Features

### 🚀 Batch Processing
- **OpenAI-compatible API** - Drop-in replacement for OpenAI Batch API
- **vLLM Offline Engine** - Optimized for RTX 4080 16GB (Gemma 3 4B, Qwen 2.5 3B, Llama 3.2 3B)
- **Intelligent Chunking** - Process 5K+ requests safely with automatic memory management
- **Incremental Saves** - Resume from crashes, never lose progress
- **Webhook Notifications** - Get notified when batches complete

### 🎨 Data Curation System
- **Beautiful Web UI** - View and curate all batch results
- **Label Studio Backend** - PostgreSQL-backed annotation database
- **Schema-Driven** - Support for 6 conquest types (candidate evaluation, CV parsing, etc.)
- **Gold-Star Datasets** - Mark best examples for in-context learning and fine-tuning
- **Auto-Import** - Batch results automatically flow into curation UI

### 📊 Monitoring & Benchmarking
- **Prometheus + Grafana** - GPU metrics, throughput tracking
- **Benchmark System** - Compare models, track quality vs speed
- **Health Checks** - GPU temperature and memory monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Aris (Next.js App)                       │
│              http://10.0.0.223:3000                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              vLLM Batch API (Port 4080)                     │
│  • OpenAI-compatible endpoints                              │
│  • SQLite job queue                                         │
│  • File upload/download                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Batch Worker (Background)                      │
│  • Polls job queue                                          │
│  • Loads models with vLLM                                   │
│  • Processes 5K chunks                                      │
│  • Saves incrementally                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Label Studio (Port 8080)                          │
│  • PostgreSQL database                                      │
│  • Stores tasks & annotations                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Curation API (Port 8001)                          │
│  • Schema-driven wrapper                                    │
│  • Beautiful web UI                                         │
│  • Export gold-star datasets                                │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **GPU**: RTX 4080 16GB (or similar with 16GB+ VRAM)
- **Python**: 3.13+
- **CUDA**: 12.1+
- **PostgreSQL**: 14+ (for Label Studio)

### Installation

```bash
# Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install vLLM (requires CUDA)
pip install vllm==0.11.0

# Initialize databases
python -c "from batch_app.database import init_db; init_db()"
```

### Start Services

```bash
# Terminal 1: Start Label Studio
docker-compose -f docker/docker-compose.yml up label-studio

# Terminal 2: Start Batch API
make run-api

# Terminal 3: Start Batch Worker
make run-worker

# Terminal 4: Start Curation UI
make run-curation
```

### Access UIs

- **Batch API**: http://localhost:4080
- **Curation UI**: http://localhost:8001
- **Label Studio**: http://localhost:8080
- **Prometheus**: http://localhost:4022
- **Grafana**: http://localhost:4023

## 📖 Usage

### Submit a Batch Job

```python
import requests
import json

# Create batch input file (JSONL format)
batch_requests = [
    {
        "custom_id": "request-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "google/gemma-2-2b-it",
            "messages": [
                {"role": "user", "content": "Evaluate this candidate..."}
            ],
            "max_tokens": 500
        }
    }
]

# Write to file
with open("batch_input.jsonl", "w") as f:
    for req in batch_requests:
        f.write(json.dumps(req) + "\n")

# Upload file and create batch
response = requests.post(
    "http://localhost:4080/v1/files",
    files={"file": open("batch_input.jsonl", "rb")},
    data={"purpose": "batch"}
)
file_id = response.json()["id"]

# Create batch job
batch_response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
)
batch_id = batch_response.json()["id"]
print(f"Batch created: {batch_id}")
```

### View Results in Curation UI

After batch completes, results are automatically imported to the curation UI:

1. Open http://localhost:8001
2. Select conquest type (e.g., "candidate_evaluation")
3. View all results side-by-side
4. Mark gold-star examples for training datasets
5. Export curated datasets for ICL or fine-tuning

## 📋 Repository Structure

```
vllm-batch-server/
├── batch_app/              # Batch processing system
│   ├── api_server.py       # OpenAI-compatible API (port 4080)
│   ├── worker.py           # Background job processor
│   ├── database.py         # SQLite models
│   ├── webhooks.py         # Webhook notifications
│   └── benchmarks.py       # Benchmark tracking
├── curation_app/           # Data curation system
│   ├── api.py              # FastAPI backend (port 8001)
│   ├── conquest_schemas.py # Schema registry
│   └── label_studio_client.py  # Label Studio integration
├── conquest_schemas/       # JSON schema definitions
│   ├── candidate_evaluation.json
│   ├── cv_parsing.json
│   ├── cartographer.json
│   ├── quil_email.json
│   ├── email_evaluation.json
│   └── report_evaluation.json
├── static/                 # Web UI assets
├── tests/                  # Test suite
├── tools/                  # Utility scripts
├── benchmarks/             # Benchmark results
├── docker/                 # Docker configs
├── docs/                   # Documentation
└── Makefile               # Common commands
```
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

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture deep dive
- **[docs/API.md](docs/API.md)** - API reference
- **[docs/ARIS_INTEGRATION.md](docs/ARIS_INTEGRATION.md)** - Integration with Aris app
- **[ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md)** - Architecture analysis

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test
pytest tests/test_curation_api.py -v
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **vLLM Team** - For the excellent inference engine
- **Label Studio** - For the annotation platform
- **OpenAI** - For the Batch API specification

