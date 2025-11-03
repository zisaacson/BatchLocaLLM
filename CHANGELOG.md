# Changelog

All notable changes to vLLM Batch Server will be documented in this file.

## [1.0.0] - 2025-01-15

### 🎉 Initial Open Source Release

First public release of vLLM Batch Server - a production-ready OpenAI-compatible batch inference server for local LLMs.

### ✨ Core Features

#### Batch Processing
- OpenAI-Compatible API - Drop-in replacement for OpenAI Batch API
- Model Hot-Swapping - Automatic model loading/unloading between jobs
- Crash-Resistant Processing - Incremental saves every 100 requests
- Queue Management - Priority queue with position and ETA visibility

#### Real-Time Inference
- Single Inference Endpoint (/v1/inference) - Real-time predictions
- Supports both simple prompts and chat format
- Low latency (<2s) with model caching
- Used by Label Studio ML Backend

#### Label Studio Integration
- ML Backend Server (Port 4082) - 50-70% faster labeling
- Webhook Automation - 8 event types with automatic triggers
- Ground Truth Tracking - Mark and track high-quality annotations
- Accuracy Calculation - Compare predictions vs human annotations

#### Monitoring & Observability
- Real-Time Monitoring - Grafana, Prometheus, Loki
- Worker Heartbeat - Health monitoring with auto-recovery
- Log Rotation - Prevent disk fill (10MB max, 7 backups)

#### Model Management
- Model Registry - Database-driven model configs
- Model Installer - Automated HuggingFace downloads
- GGUF Support - Quantized models for consumer GPUs

#### Benchmarking & Comparison
- Dataset Workbench - Interactive result exploration
- Benchmark Runner - Scientific model comparison
- Quality vs speed vs cost analysis

#### Developer Experience
- CLI Tool (vllm-batch) - Command-line interface
- Startup Scripts - Easy service management
- Docker Compose - One-command setup

### 📚 Documentation
- README.md - Quick start, features, architecture
- docs/ML_BACKEND_SETUP.md - Label Studio integration guide
- docs/API.md - Complete API reference
- docs/WEBHOOKS.md - Webhook configuration guide

### 🐛 Bug Fixes
- Fixed validation errors preventing job submission
- Fixed progress tracking not updating
- Fixed crash recovery not resuming from checkpoint
- Fixed missing import causing API server crash
- Fixed Pydantic deprecation warning
- Fixed log rotation not preventing disk fill

### 📦 Dependencies
- Python 3.10+
- vLLM 0.11.0
- FastAPI 0.104.1
- SQLAlchemy 2.0.23
- PostgreSQL 16
- Label Studio (latest)

---

## [Unreleased]

### Planned Features
- v1.1.0 - Multi-GPU Support
- v1.2.0 - Advanced Model Support (GGUF, llama.cpp)
- v1.3.0 - Enhanced Monitoring
- v1.4.0 - Multi-stage Pipelines

---

## License

Apache 2.0 - See LICENSE for details.
