# vLLM Batch Server

**Self-hosted OpenAI-compatible batch processing for local GPUs**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![vLLM](https://img.shields.io/badge/vLLM-0.11.0-green.svg)](https://github.com/vllm-project/vllm)

Process large batches (50K+ requests) on consumer GPUs without OOM crashes. OpenAI-compatible API with optional data curation.

---

## 🎯 Why This Exists

**The Problem:**
- OpenAI Batch API is great, but data goes to cloud (privacy concerns)
- Processing large batches locally causes OOM crashes
- vLLM is powerful but lacks production infrastructure
- No easy way to curate results for training data

**The Solution:**
Self-hosted batch server with:
- ✅ OpenAI-compatible API (drop-in replacement)
- ✅ Intelligent chunking (process 50K+ requests safely)
- ✅ Consumer GPU optimized (works on RTX 4080 16GB)
- ✅ Production infrastructure (monitoring, webhooks, health checks)
- ✅ Extensible result handlers (integrate with your pipeline)
- ✅ Optional data curation (Label Studio integration)

---

## ✨ Features

### 🚀 **Core Batch Processing**
- **OpenAI-compatible API** - Drop-in replacement for OpenAI Batch API
- **Large batch support** - Process 50K+ requests without OOM
- **Intelligent chunking** - Automatic 5K request chunks with incremental saves
- **Resume from crashes** - Never lose progress
- **Webhook notifications** - Get notified when batches complete
- **GPU health monitoring** - Prevent thermal throttling and OOM

### 🔌 **Extensible Result Handlers**
- **Plugin architecture** - Write custom handlers for your pipeline
- **Built-in webhook handler** - HTTP POST notifications
- **Label Studio integration** - Optional data curation
- **Example handlers** - PostgreSQL insert, S3 upload, custom templates

### 📊 **Production Ready**
- **Prometheus + Grafana** - GPU metrics, throughput tracking
- **PostgreSQL** - Production-grade job queue
- **Docker Compose** - One-command deployment
- **Comprehensive tests** - Unit, integration, E2E

---

## 🚀 Quick Start

### Prerequisites
- **GPU**: 16GB+ VRAM (RTX 4080, RTX 3090, A100, etc.)
- **Python**: 3.13+
- **CUDA**: 12.1+
- **Docker**: 20.10+ (optional but recommended)

### Installation (Docker - Recommended)

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/vllm-batch-server.git
cd vllm-batch-server

# Start services
docker-compose up -d

# Check status
curl http://localhost:4080/
```

### Installation (Manual)

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from batch_app.database import init_db; init_db()"

# Start API server
python -m batch_app.api_server &

# Start worker
python -m batch_app.worker
```

---

## 📖 Usage

### Basic Batch Processing

```python
import requests

# 1. Upload input file (JSONL format)
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
        "completion_window": "24h",
        "metadata": {
            "webhook_url": "https://your-app.com/webhook"
        }
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

---

## 🔌 Result Handlers (Plugin System)

Result handlers automatically process batch results when jobs complete.

### Built-in Handlers

**Webhook Handler** (always enabled)
```python
# Automatically sends HTTP POST when batch completes
# Configure via metadata:
{
    "webhook_url": "https://your-app.com/webhook"
}
```

**Label Studio Handler** (optional)
```bash
# Enable via environment variables
export LABEL_STUDIO_URL=http://localhost:8080
export LABEL_STUDIO_API_KEY=your_api_key
export LABEL_STUDIO_PROJECT_ID=123

# Results auto-import to Label Studio for curation
```

### Custom Handlers

Create your own handler:

```python
from result_handlers.base import ResultHandler

class MyHandler(ResultHandler):
    def name(self) -> str:
        return "my_handler"

    def enabled(self) -> bool:
        return True  # Or check config

    def handle(self, batch_id, results, metadata):
        # Your custom logic
        for result in results:
            # Process each result
            pass
        return True

# Register handler
from result_handlers import register_handler
register_handler(MyHandler())
```

See `result_handlers/examples/` for templates:
- `postgres_insert.py` - Insert into PostgreSQL
- `s3_upload.py` - Upload to S3
- `custom_template.py` - Template for your handler

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
│  • Processes 5K chunks (prevents OOM)                       │
│  • Saves incrementally (resume from crashes)                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Result Handlers (Plugin System)                   │
│  • Webhook notifications                                    │
│  • Label Studio import (optional)                           │
│  • Custom handlers (your pipeline)                          │
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
| **Batch Size** | 50K requests | 50K+ requests |
| **OOM Protection** | N/A | Intelligent chunking |
| **Curation** | None | Optional Label Studio |
| **Monitoring** | Limited | Full Prometheus/Grafana |
| **Result Handlers** | None | Extensible plugins |

---

## 🤝 Relationship to Parasail's openai-batch

[Parasail's openai-batch](https://github.com/parasail-ai/openai-batch) is a **client library** that simplifies batch submission to cloud APIs.

vLLM Batch Server is the **server** that processes batches locally.

**They're complementary!** Use Parasail's library to submit to your self-hosted server:

```python
from openai_batch import Batch

# Point to your local server
provider.base_url = "http://localhost:4080/v1"

# Now you have:
# ☁️  Cloud option: OpenAI/Parasail (pay per token)
# 🏠 Self-hosted option: vLLM Batch Server (free, private)
# 🔄 Same client library: openai-batch
```

---

## 💡 Key Innovations

### 1. **Large Batch Processing on Consumer GPUs**

**Problem:** Processing 50K+ requests causes OOM even on 24GB GPUs

**Our Solution:**
- Intelligent chunking (5K requests per chunk)
- Dynamic memory management
- Incremental saves (resume from crashes)
- GPU health monitoring

**Result:** Process 50K+ requests on RTX 4080 16GB without crashes

### 2. **Extensible Result Handlers**

**Problem:** Every application has different data pipelines

**Our Solution:**
- Plugin architecture for custom handlers
- Built-in webhook and Label Studio handlers
- Easy to write custom handlers
- Examples for common use cases

**Result:** Integrate with any pipeline (database, S3, ML platform, etc.)

### 3. **Production Infrastructure**

**Problem:** vLLM is just an inference engine, not a production system

**Our Solution:**
- OpenAI-compatible API
- PostgreSQL job queue
- Prometheus + Grafana monitoring
- GPU health checks
- Webhook notifications
- Comprehensive tests

**Result:** Production-ready out of the box

---

## 📊 Tested Configurations

### GPUs
- ✅ RTX 4080 16GB - Works great
- ✅ RTX 3090 24GB - Works great
- ✅ A100 40GB - Works great
- ✅ A100 80GB - Works great

### Models
- ✅ Llama 3.2 3B - Fast, good quality
- ✅ Qwen 2.5 3B - Fast, good quality
- ✅ Gemma 3 4B - Balanced
- ✅ Llama 3.1 8B - High quality (requires chunking)
- ✅ Llama 3.3 70B - Highest quality (requires tensor parallelism)

### Batch Sizes
- ✅ 1K requests - ~5 minutes (RTX 4080, Gemma 3 4B)
- ✅ 5K requests - ~20 minutes (RTX 4080, Gemma 3 4B)
- ✅ 50K requests - ~3 hours (RTX 4080, Gemma 3 4B)
- ✅ 170K requests - ~10 hours (RTX 4080, Gemma 3 4B)

---

## 📚 Documentation

- [Quick Start Guide](docs/QUICKSTART.md) - 5-minute setup
- [Architecture Overview](docs/ARCHITECTURE.md) - System design
- [API Reference](docs/API.md) - OpenAI-compatible endpoints
- [Result Handlers Guide](docs/RESULT_HANDLERS.md) - Plugin system
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/           # Unit tests (fast)
pytest tests/integration/    # Integration tests
pytest tests/e2e/            # End-to-end tests

# With coverage
pytest --cov=batch_app --cov=result_handlers
```

---

## 🛠️ Configuration

### Environment Variables

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vllm_batch
POSTGRES_USER=vllm
POSTGRES_PASSWORD=your_password

# GPU Settings
GPU_MEMORY_UTILIZATION=0.9
CHUNK_SIZE=5000

# Optional: Label Studio
LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_KEY=your_api_key
LABEL_STUDIO_PROJECT_ID=123

# Optional: Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Docker Profiles

```bash
# Basic batch processing
docker-compose up

# With monitoring
docker-compose --profile monitoring up

# With Label Studio
docker-compose --profile curation up

# Everything
docker-compose --profile monitoring --profile curation up
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas we'd love help with:**
- Support for more GPU types (AMD, Intel)
- Additional model optimizations
- More result handler examples
- Documentation improvements
- Bug fixes and performance improvements

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

---

## 🌟 Star History

If you find this project useful, please consider giving it a star! ⭐

---

**Built with AI-assisted development**

*Self-hosted batch processing for the privacy-conscious, cost-conscious, and control-conscious.*
