# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### 🎉 Initial Public Release

First production-ready release of vLLM Batch Server!

### Added

#### Core Features
- **OpenAI-Compatible Batch API** - Drop-in replacement for OpenAI Batch API
  - `/v1/batches` - Create and manage batch jobs
  - `/v1/files` - Upload and manage batch files
  - `/v1/models` - List and manage models
  - JSONL format support matching OpenAI specification

- **Model Hot-Swapping** - Automatic model loading/unloading
  - Queue jobs for different models
  - Worker automatically switches models between jobs
  - Prevents OOM on consumer GPUs (RTX 3060, 3090, 4080, 4090)

- **Incremental Saves** - Checkpoint every 100 requests
  - Prevents data loss from crashes
  - Resume from last checkpoint
  - Configurable save interval

- **Real-Time Monitoring** - Grafana + Prometheus + Loki
  - Pre-configured dashboards for batch processing
  - GPU metrics (utilization, memory, temperature)
  - System health monitoring
  - Log aggregation and search

#### Web UI
- **Queue Monitor** - Real-time job status and progress
- **Model Management** - Add, remove, and configure models
- **Workbench** - Interactive prompt testing
- **Benchmark Runner** - Compare models on test datasets

#### Developer Experience
- **Docker Support** - One-command setup with docker-compose
- **Python Examples** - Simple batch processing examples
- **TypeScript Examples** - Integration examples for web apps
- **Comprehensive Documentation** - Getting started, API reference, troubleshooting

#### Testing & Quality
- **Unit Tests** - Core functionality coverage
- **Integration Tests** - End-to-end workflow testing
- **CI/CD Pipeline** - GitHub Actions for automated testing
- **Pre-commit Hooks** - Code quality checks (black, ruff, mypy)
- **Makefile** - Common development tasks

#### Documentation
- **README.md** - Project overview and quick start
- **GETTING_STARTED.md** - Step-by-step installation guide
- **API.md** - Complete API reference
- **ARCHITECTURE.md** - System design and architecture
- **DEPLOYMENT.md** - Production deployment guide
- **TROUBLESHOOTING.md** - Common issues and solutions
- **DOCKER_QUICKSTART.md** - Docker setup in under 5 minutes
- **CONTRIBUTING.md** - Contribution guidelines
- **SECURITY.md** - Security policy and best practices
- **ROADMAP.md** - Future plans and feature requests

### Performance

- **Throughput**: 450-620 tok/s on RTX 4080 16GB (model-dependent)
- **Batch Size**: Support for 50,000+ requests per batch
- **Memory Efficiency**: 90% GPU memory utilization
- **Reliability**: Automatic error recovery and retry logic

### Supported Models

Out-of-the-box support for:
- **Gemma 3** (2B, 4B, 7B, 12B)
- **Llama 3.2** (1B, 3B)
- **Llama 3.1** (8B)
- **Qwen 2.5** (3B, 7B)
- **OLMo 2** (7B, 13B)
- **IBM Granite** (3B, 8B)

### Supported GPUs

Tested and optimized for:
- **RTX 3060** 12GB (budget option)
- **RTX 3090** 24GB
- **RTX 4080** 16GB
- **RTX 4090** 24GB

### Infrastructure

- **PostgreSQL** - Durable job queue and model registry
- **FastAPI** - High-performance async API server
- **vLLM 0.11.0** - State-of-the-art inference engine
- **SQLAlchemy 2.0** - Type-safe ORM
- **Prometheus** - Metrics collection
- **Grafana** - Visualization and dashboards
- **Loki** - Log aggregation

### Security

- **Apache 2.0 License** - Open source and permissive
- **Security Policy** - Vulnerability reporting process
- **Input Validation** - Comprehensive request validation
- **Error Handling** - Secure error messages (no sensitive data leaks)
- **Dependency Scanning** - Automated security checks in CI

### Community

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Community support and Q&A
- **Contributing Guidelines** - Clear contribution process
- **Code of Conduct** - Inclusive community standards

---

## [Unreleased]

### Planned for v1.1.0

- Quantization support (Q8, Q4 GGUF)
- Python SDK
- TypeScript SDK
- CLI tool
- Batch size auto-tuning
- More model families (OLMo 2, IBM Granite, DeepSeek)

See [ROADMAP.md](ROADMAP.md) for full roadmap.

---

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backwards compatible manner
- **PATCH** version for backwards compatible bug fixes

---

## How to Upgrade

### From Source

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python -c "from core.batch_app.database import init_db; init_db()"
```

### With Docker

```bash
docker compose pull
docker compose up -d
```

---

## Migration Guides

### Migrating to v1.0.0

This is the initial release, no migration needed.

---

## Deprecation Notices

None yet.

---

## Breaking Changes

None yet.

---

## Contributors

Thank you to all contributors who made this release possible!

- [@zisaacson](https://github.com/zisaacson) - Project creator and maintainer

Want to contribute? See [CONTRIBUTING.md](CONTRIBUTING.md)!

---

## Links

- **GitHub Repository**: https://github.com/zisaacson/vllm-batch-server
- **Documentation**: [docs/](docs/)
- **Issue Tracker**: https://github.com/zisaacson/vllm-batch-server/issues
- **Discussions**: https://github.com/zisaacson/vllm-batch-server/discussions

---

**Note**: This changelog is automatically updated with each release. For the latest changes, see the [commit history](https://github.com/zisaacson/vllm-batch-server/commits/main).

