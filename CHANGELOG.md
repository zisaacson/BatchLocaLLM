# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-26

### Added

#### Core Features
- OpenAI-compatible batch processing API
- vLLM engine integration with continuous batching
- Automatic prefix caching support (vLLM APC)
- SQLite-based job metadata storage
- Local file storage for batch inputs/outputs
- Async batch processing with background workers

#### API Endpoints
- `POST /v1/files` - Upload batch input files
- `GET /v1/files/{file_id}/content` - Download file content
- `POST /v1/batches` - Create batch jobs
- `GET /v1/batches/{batch_id}` - Get batch status
- `POST /v1/batches/{batch_id}/cancel` - Cancel batch jobs
- `GET /health` - Health check with GPU metrics
- `GET /readiness` - Kubernetes readiness probe
- `GET /liveness` - Kubernetes liveness probe

#### Infrastructure
- Docker support with CUDA 12.1
- Docker Compose configuration
- Multi-stage Dockerfile for optimized image size
- GPU resource management
- Environment-based configuration
- Structured JSON logging

#### Documentation
- Comprehensive README with quick start
- ARIS integration guide
- Complete API documentation
- Contributing guidelines
- Apache 2.0 license

#### Examples
- Simple batch processing example with OpenAI SDK
- Quick start script for easy deployment

#### Testing
- Unit tests for API endpoints
- Mock-based testing infrastructure
- GitHub Actions CI/CD workflow
- Code quality tools (Black, Ruff, mypy)

#### Configuration
- 40+ environment variables for customization
- GPU memory management settings
- Batch processing limits
- Prefix caching configuration
- Performance tuning options
- Monitoring and observability settings

### Technical Details

#### Dependencies
- FastAPI 0.115.0+ (web framework)
- vLLM 0.6.0+ (inference engine)
- Pydantic 2.9.0+ (data validation)
- SQLAlchemy 2.0.0+ (database ORM)
- aiofiles 24.1.0+ (async file I/O)
- python-json-logger 3.2.0+ (structured logging)

#### Architecture
- Async/await throughout
- Background task processing
- Concurrent batch job support
- Graceful shutdown handling
- Health check integration

#### Performance
- Continuous batching for high throughput
- Automatic prefix caching for cost savings
- CUDA graph optimization
- PagedAttention memory management
- Configurable batch sizes

### Known Limitations

- Single-node deployment only (no distributed processing yet)
- Local file storage only (no S3/cloud storage yet)
- Basic chat template (model-specific templates not implemented)
- No streaming support for batch results
- No web UI for job monitoring

### Future Roadmap

See [README.md](README.md#roadmap) for planned features.

---

## [Unreleased]

### Planned for 0.2.0
- Redis-based job queue for multi-instance deployments
- S3-compatible storage backend
- Prometheus metrics export
- Model-specific chat templates
- Streaming batch results
- Web UI for job monitoring

---

[0.1.0]: https://github.com/YOUR_ORG/vllm-batch-server/releases/tag/v0.1.0

