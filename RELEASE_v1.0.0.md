# vLLM Batch Server v1.0.0 🎉

**Production-ready OpenAI-compatible batch inference for local LLMs**

Process **50,000+ requests** on consumer GPUs (RTX 4080 16GB) with automatic model hot-swapping, fine-tuning, and real-time monitoring.

---

## 🌟 What's New in v1.0.0

### Core Features

✅ **OpenAI-Compatible Batch API** - Drop-in replacement for OpenAI Batch API  
✅ **Model Hot-Swapping** - Automatic model loading/unloading between jobs  
✅ **Crash-Resistant Processing** - Incremental saves every 100 requests  
✅ **Real-Time Monitoring** - Grafana + Prometheus + Loki dashboards  
✅ **Web UI** - Queue monitor, model management, workbench  

### Fine-Tuning System (NEW!)

✅ **Dataset Export** - Export gold star conquests for training  
✅ **Training Abstraction** - Support for Unsloth (2x faster), Axolotl, OpenAI, HuggingFace  
✅ **Model Deployment** - Deploy fine-tuned models to vLLM  
✅ **A/B Testing** - Compare base vs fine-tuned model performance  
✅ **Web Dashboard** - Fine-tuning UI and model comparison interface  

### Label Studio Integration

✅ **ML Backend Server** - 50-70% faster labeling with pre-labeling  
✅ **Webhook Automation** - 8 event types with automatic triggers  
✅ **Ground Truth Tracking** - Mark and track high-quality annotations  
✅ **Accuracy Calculation** - Compare predictions vs human annotations  

### Developer Experience

✅ **CLI Tool** - `vllm-batch` command-line interface  
✅ **Docker Compose** - One-command setup  
✅ **Systemd Services** - Auto-start on boot  
✅ **Comprehensive Docs** - 8 guides + API reference  

---

## 🚀 Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server
docker compose up -d
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d

# Start API server
python -m core.batch_app.api_server

# Start worker (in another terminal)
python -m core.batch_app.worker
```

---

## 📊 Supported Models

Out-of-the-box support for:

- **Gemma 3** (2B, 4B, 7B, 12B)
- **Llama 3.2** (1B, 3B)
- **Llama 3.1** (8B)
- **Qwen 2.5** (3B, 7B)
- **OLMo 2** (7B, 13B)
- **IBM Granite** (3B, 8B)

Any HuggingFace model compatible with vLLM 0.11.0 will work!

---

## 💻 System Requirements

| GPU | VRAM | Recommended Models | Throughput |
|-----|------|-------------------|-----------|
| RTX 3060 | 12GB | Gemma 3 2B, Llama 3.2 1B | 300-400 tok/s |
| RTX 3090 | 24GB | Gemma 3 4B, Llama 3.2 3B | 400-500 tok/s |
| RTX 4080 | 16GB | Gemma 3 4B, Qwen 2.5 3B | 450-520 tok/s |
| RTX 4090 | 24GB | Gemma 3 7B, Llama 3.1 8B | 550-620 tok/s |

**Requirements:**
- **OS**: Linux (Ubuntu 22.04+)
- **Python**: 3.10, 3.11, or 3.12
- **CUDA**: 12.1+
- **Docker**: For PostgreSQL and monitoring

---

## 📚 Documentation

- **[Getting Started](docs/guides/getting-started.md)** - Installation and first batch
- **[Docker Quick Start](docs/quick-start/5-minute-quickstart.md)** - Docker setup in 5 minutes
- **[API Reference](docs/reference/api.md)** - Complete API documentation
- **[Architecture](docs/architecture/system-design.md)** - System design
- **[Fine-Tuning Guide](ZACKSNOTES/FINE_TUNING_USAGE_GUIDE.md)** - Train custom models
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues

---

## 🎯 Use Cases

### 1. Model Comparison
Compare multiple models on the same dataset to find the best one for your use case.

### 2. Training Data Curation
Process thousands of examples, review results in Label Studio, and export gold star data for fine-tuning.

### 3. Fine-Tuning
Train custom models on your curated datasets and deploy them for inference.

### 4. Cost Savings
Process 50K requests locally for ~$0 vs $50-100 on cloud APIs.

---

## 🐛 Known Issues

- Integration tests may fail if curation system is not set up (optional feature)
- Some type hints are incomplete (mypy warnings)
- Windows support is experimental (WSL2 recommended)

See [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues) for full list.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed changes.

---

## 📧 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/zisaacson/vllm-batch-server/issues)
- **GitHub Discussions**: [Ask questions or share ideas](https://github.com/zisaacson/vllm-batch-server/discussions)

---

## 🙏 Acknowledgments

Built with:
- **[vLLM](https://github.com/vllm-project/vllm)** - Fast inference engine
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework
- **[PostgreSQL](https://www.postgresql.org/)** - Reliable database
- **[Grafana](https://grafana.com/)** - Beautiful dashboards
- **[Unsloth](https://github.com/unslothai/unsloth)** - 2x faster fine-tuning

Inspired by:
- **[OpenAI Batch API](https://platform.openai.com/docs/guides/batch)** - API design
- **[Parasail](https://www.parasail.io/)** - Batch processing patterns

---

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

