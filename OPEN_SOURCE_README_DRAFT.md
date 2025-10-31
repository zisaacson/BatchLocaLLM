# vLLM Batch Server

**Self-hosted OpenAI-compatible batch processing for local GPUs**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![vLLM](https://img.shields.io/badge/vLLM-0.11.0-green.svg)](https://github.com/vllm-project/vllm)

Run OpenAI Batch API on your RTX 4080 with optional data curation.

---

## 🎯 Why This Exists

**Problem:** You want OpenAI Batch API, but:
- ❌ Can't send data to cloud (HIPAA/SOC2)
- ❌ Don't want to pay per token
- ❌ Need custom models not available in cloud
- ❌ Want to curate training data from results

**Solution:** Self-hosted batch server with OpenAI-compatible API

---

## ✨ Features

### 🚀 **Core Batch Processing**
- **OpenAI-compatible API** - Drop-in replacement for OpenAI Batch API
- **Consumer GPU optimized** - Works on RTX 4080 16GB (vLLM requires 24GB+)
- **Intelligent chunking** - Process 5K+ requests safely
- **Incremental saves** - Resume from crashes, never lose progress
- **Webhook notifications** - Get notified when batches complete

### 🎨 **Optional Data Curation**
- **Label Studio integration** - Review and annotate batch results
- **Schema-driven** - Define custom data types and validation
- **Gold-star marking** - Mark best examples for training
- **Export datasets** - ICL and fine-tuning formats

### 📊 **Production Ready**
- **Prometheus + Grafana** - GPU metrics, throughput tracking
- **Health checks** - GPU temperature and memory monitoring
- **PostgreSQL** - Production-grade job queue
- **Docker Compose** - One-command deployment

---

## 🚀 Quick Start

### Prerequisites
- **GPU**: RTX 4080 16GB (or similar with 16GB+ VRAM)
- **Python**: 3.13+
- **CUDA**: 12.1+
- **Docker**: 20.10+ (optional but recommended)

### Installation (Docker - Recommended)

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/vllm-batch-server.git
cd vllm-batch-server

# Start basic batch processing
docker-compose up -d

# Or with data curation
docker-compose --profile curation up -d
```

### Installation (Manual)

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install vllm==0.11.0

# Initialize database
python -c "from batch_app.database import init_db; init_db()"

# Start API server
python -m batch_app.api_server

# Start worker (in another terminal)
python -m batch_app.worker
```

---

## 📖 Usage

### Basic Batch Processing

```python
import requests

# 1. Upload input file
with open("batch_input.jsonl", "rb") as f:
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

# 3. Check status
response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}")
print(response.json()["status"])  # "validating" -> "in_progress" -> "completed"

# 4. Download results
response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}/results")
with open("batch_output.jsonl", "wb") as f:
    f.write(response.content)
```

### With Parasail's openai-batch Library

```python
from openai_batch import Batch
from openai_batch.providers import get_provider_by_name

# Point to your self-hosted server
provider = get_provider_by_name("openai")
provider.base_url = "http://localhost:4080/v1"

# Use Parasail's library with your server!
with Batch(provider=provider) as batch:
    batch.add_to_batch(
        model="meta-llama/Meta-Llama-3-8B-Instruct",
        messages=[{"role": "user", "content": "Tell me a joke"}]
    )
    result, output_path, error_path = batch.submit_wait_download()
```

### With Data Curation (Optional)

```python
# After batch completes, results auto-import to Label Studio
# Access curation UI at http://localhost:8001

# Mark gold-star examples
requests.post(
    "http://localhost:8001/api/tasks/1/gold-star",
    json={"gold_star": True}
)

# Export training dataset
response = requests.post(
    "http://localhost:8001/api/export",
    json={
        "schema_type": "chat_completion",
        "format": "icl"  # or "finetuning"
    }
)
dataset = response.json()
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                         │
│              (or Parasail's openai-batch)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Batch API (Port 4080)                          │
│  • OpenAI-compatible endpoints                              │
│  • PostgreSQL job queue                                     │
│  • File upload/download                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Batch Worker (Background)                      │
│  • Polls job queue                                          │
│  • Loads models with vLLM                                   │
│  • Processes 5K chunks (RTX 4080 optimized)                 │
│  • Saves incrementally                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼ (Optional: --profile curation)
┌─────────────────────────────────────────────────────────────┐
│           Label Studio + Curation API                       │
│  • Review batch results                                     │
│  • Mark gold-star examples                                  │
│  • Export training datasets                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 vs Cloud Batch APIs

| Feature | OpenAI/Parasail | vLLM Batch Server |
|---------|----------------|-------------------|
| **Hosting** | Cloud | Self-hosted |
| **Privacy** | Data sent to cloud | Data stays local |
| **Cost** | $$ per token | Free (your GPU) |
| **Models** | Fixed catalog | Any vLLM model |
| **GPU** | N/A | RTX 4080 optimized |
| **Curation** | None | Optional Label Studio |
| **Monitoring** | Limited | Full Prometheus/Grafana |

---

## 🤝 Relationship to Parasail's openai-batch

[Parasail's openai-batch](https://github.com/parasail-ai/openai-batch) is a **client library** that simplifies batch submission to cloud APIs.

vLLM Batch Server is the **server** that processes batches locally.

**They're complementary!** Use Parasail's library to submit to your self-hosted server.

---

## 📊 Consumer GPU Optimization

**Problem:** vLLM requires 24GB+ VRAM, doesn't work on RTX 4080 (16GB)

**Our Solution:**
- ✅ Intelligent chunking (5K requests per chunk)
- ✅ Dynamic memory management
- ✅ Incremental saves (resume from crashes)
- ✅ GPU health monitoring

**Tested on:**
- RTX 4080 16GB - ✅ Works
- RTX 3090 24GB - ✅ Works
- A100 40GB - ✅ Works

**Models tested:**
- Llama 3.2 3B - ✅ Works
- Qwen 2.5 3B - ✅ Works
- Gemma 3 4B - ✅ Works
- Llama 3.1 8B - ✅ Works (with chunking)

---

## 📚 Documentation

- [Quick Start Guide](docs/QUICKSTART.md) - 5-minute setup
- [Architecture Overview](docs/ARCHITECTURE.md) - System design
- [API Reference](docs/API.md) - OpenAI-compatible endpoints
- [Data Curation Guide](docs/CURATION.md) - Optional curation features
- [Custom Schemas](docs/SCHEMAS.md) - Define your own data types

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/           # Unit tests (fast)
pytest tests/integration/    # Integration tests
pytest tests/e2e/            # End-to-end tests
```

**Test Coverage:**
- 78 tests (100% pass rate)
- 28% overall coverage
- 71% coverage on critical paths

---

## 🛠️ Configuration

```bash
# .env file
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vllm_batch
POSTGRES_USER=vllm
POSTGRES_PASSWORD=your_password

# GPU settings
GPU_MEMORY_UTILIZATION=0.9
CHUNK_SIZE=5000

# Optional: Label Studio
LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_KEY=your_api_key
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas we'd love help with:**
- Support for more GPU types (AMD, Intel)
- Additional model optimizations
- More schema examples
- Documentation improvements

---

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - Fast LLM inference engine
- [Label Studio](https://github.com/heartexlabs/label-studio) - Data annotation platform
- [Parasail](https://parasail.io) - Inspiration for OpenAI-compatible API
- [OpenAI](https://openai.com) - Batch API specification

---

## 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/YOUR_ORG/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_ORG/vllm-batch-server/discussions)
- **Email**: your-email@example.com

---

## 🌟 Star History

If you find this project useful, please consider giving it a star! ⭐

---

**Built with ❤️ by [Your Team Name]**

*Self-hosted batch processing for the privacy-conscious, cost-conscious, and control-conscious.*

