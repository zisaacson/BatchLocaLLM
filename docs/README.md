# Documentation

Welcome to the vLLM Batch Server documentation!

## 📚 Getting Started

New to vLLM Batch Server? Start here:

1. **[Getting Started Guide](GETTING_STARTED.md)** - Installation and first batch job
2. **[Docker Quick Start](DOCKER_QUICKSTART.md)** - One-command Docker setup (< 5 minutes)
3. **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## 📖 Core Documentation

### API & Usage

- **[API Reference](API.md)** - Complete API documentation
  - Endpoints, request/response formats
  - Error codes and handling
  - Rate limiting and quotas

- **[Examples](../examples/README.md)** - Code examples
  - Python examples
  - TypeScript examples
  - curl examples
  - Integration patterns

### System Design

- **[Architecture](ARCHITECTURE.md)** - System architecture
  - High-level architecture diagrams
  - Data flow diagrams
  - Component descriptions
  - Design decisions

- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment
  - System requirements
  - Installation steps
  - Configuration options
  - Monitoring setup
  - Security best practices

### Model Management

- **[Add Model Guide](ADD_MODEL_GUIDE.md)** - Adding new models
  - Model installation
  - Configuration
  - Benchmarking
  - Troubleshooting

## 🚀 Release Information

- **[Release Notes v1.0.0](RELEASE_NOTES_v1.0.0.md)** - What's new in v1.0.0
- **[Changelog](../CHANGELOG.md)** - Version history
- **[Roadmap](../ROADMAP.md)** - Future plans

## 🛠️ Development

- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute
- **[Security Policy](../SECURITY.md)** - Security and vulnerability reporting

## 📊 Performance & Optimization

### GPU-Specific Guides

**RTX 3060 12GB** (Budget Option)
- Recommended models: Gemma 3 2B, Llama 3.2 1B
- GPU_MEMORY_UTILIZATION=0.85
- CHUNK_SIZE=50
- Expected throughput: 300-400 tok/s

**RTX 3090 24GB**
- Recommended models: Gemma 3 4B, Llama 3.2 3B, Gemma 3 7B
- GPU_MEMORY_UTILIZATION=0.90
- CHUNK_SIZE=150
- Expected throughput: 400-500 tok/s

**RTX 4080 16GB**
- Recommended models: Gemma 3 4B, Llama 3.2 3B, Qwen 2.5 3B
- GPU_MEMORY_UTILIZATION=0.90
- CHUNK_SIZE=100
- Expected throughput: 450-520 tok/s

**RTX 4090 24GB**
- Recommended models: Gemma 3 7B, Llama 3.1 8B
- GPU_MEMORY_UTILIZATION=0.92
- CHUNK_SIZE=200
- Expected throughput: 550-620 tok/s

See [Troubleshooting Guide](TROUBLESHOOTING.md#performance-tuning) for detailed optimization tips.

## 🔍 Quick Reference

### Common Tasks

**Start the server:**
```bash
# Docker (recommended)
docker compose up -d

# From source
./scripts/start_all.sh
```

**Submit a batch job:**
```bash
# Upload file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@batch.jsonl" \
  -F "purpose=batch"

# Create batch
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{"input_file_id": "file-xxx", "endpoint": "/v1/chat/completions"}'
```

**Check job status:**
```bash
curl http://localhost:4080/v1/batches/{batch_id}
```

**Monitor in real-time:**
- Queue Monitor: http://localhost:4080/queue-monitor.html
- Grafana: http://localhost:4220

### File Formats

**Input file (JSONL):**
```json
{"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "google/gemma-3-4b-it", "messages": [{"role": "user", "content": "Hello!"}]}}
```

**Output file (JSONL):**
```json
{"id": "batch_req_xxx", "custom_id": "request-1", "response": {"status_code": 200, "body": {"id": "chatcmpl-xxx", "choices": [{"message": {"content": "Hi there!"}}]}}}
```

## 🆘 Getting Help

### Documentation

1. Check [Troubleshooting Guide](TROUBLESHOOTING.md) first
2. Search [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
3. Read [API Reference](API.md) for endpoint details

### Community Support

- **GitHub Discussions**: [Ask questions](https://github.com/zisaacson/vllm-batch-server/discussions)
- **GitHub Issues**: [Report bugs](https://github.com/zisaacson/vllm-batch-server/issues/new?template=bug_report.md)
- **Feature Requests**: [Suggest features](https://github.com/zisaacson/vllm-batch-server/issues/new?template=feature_request.md)

### Diagnostic Information

When reporting issues, include:

```bash
# System info
uname -a
python --version
nvidia-smi

# Service status
docker compose ps
curl http://localhost:4080/health

# Logs
docker compose logs api-server
docker compose logs worker
```

## 📁 Documentation Structure

```
docs/
├── README.md                    # This file
├── GETTING_STARTED.md          # Installation guide
├── DOCKER_QUICKSTART.md        # Docker setup
├── API.md                      # API reference
├── ARCHITECTURE.md             # System design
├── DEPLOYMENT.md               # Production deployment
├── TROUBLESHOOTING.md          # Common issues
├── ADD_MODEL_GUIDE.md          # Adding models
├── RELEASE_NOTES_v1.0.0.md    # Release notes
├── archive/                    # Archived docs
└── integrations/               # Integration guides
    └── aris/                   # Example integration
```

## 🔗 External Resources

### vLLM

- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [Supported Models](https://docs.vllm.ai/en/latest/models/supported_models.html)

### OpenAI Batch API

- [OpenAI Batch API Guide](https://platform.openai.com/docs/guides/batch)
- [Batch API Reference](https://platform.openai.com/docs/api-reference/batch)

### Monitoring

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/)

## 📝 Contributing to Documentation

Found a typo? Want to improve the docs? We welcome contributions!

1. Fork the repository
2. Edit the documentation
3. Submit a pull request

See [Contributing Guide](../CONTRIBUTING.md) for details.

## 📄 License

All documentation is licensed under [Apache License 2.0](../LICENSE).

---

**Need help?** Start with [Getting Started](GETTING_STARTED.md) or ask in [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)!

