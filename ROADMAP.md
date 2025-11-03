# Roadmap

This document outlines the planned features and improvements for vLLM Batch Server.

## Current Version: 1.0.0

**Status:** Production Ready ✅

The current release includes:
- OpenAI-compatible batch API
- Model hot-swapping for consumer GPUs
- Real-time monitoring with Grafana
- Incremental saves and error recovery
- Web UI for queue monitoring and model management
- Support for 50,000+ requests per batch

---

## Short-Term (Next 3 Months)

### Performance Optimizations

- [ ] **Quantization Support** (Q8, Q4 GGUF formats)
  - Reduce memory usage by 50-75%
  - Enable larger models on consumer GPUs
  - Support for llama.cpp integration

- [ ] **KV Cache Optimization**
  - KV cache quantization to Q8
  - Double effective context length
  - Reduce memory footprint

- [ ] **Batch Size Auto-Tuning**
  - Automatically adjust batch size based on GPU memory
  - Prevent OOM crashes
  - Maximize throughput

### Model Support

- [ ] **More Model Families**
  - OLMo 2 (7B, 13B)
  - IBM Granite (3B, 8B)
  - DeepSeek (7B, 33B)
  - Mistral (7B, 8x7B MoE)

- [ ] **Multi-Modal Support**
  - Vision models (LLaVA, Qwen-VL)
  - Audio models (Whisper integration)
  - Document understanding

### Developer Experience

- [ ] **Python SDK**
  - Official Python client library
  - Async/await support
  - Type hints and autocomplete

- [ ] **TypeScript SDK**
  - Official TypeScript/JavaScript client
  - React hooks for web integration
  - Node.js examples

- [ ] **CLI Tool**
  - Command-line interface for batch operations
  - Interactive mode
  - Progress bars and status updates

---

## Mid-Term (3-6 Months)

### Scalability

- [ ] **Multi-GPU Support**
  - Tensor parallelism across multiple GPUs
  - Pipeline parallelism for large models
  - Automatic GPU selection

- [ ] **Distributed Processing**
  - Multiple worker nodes
  - Load balancing across machines
  - Fault tolerance and failover

- [ ] **Priority Queue**
  - Job prioritization
  - SLA-based scheduling
  - Fair queuing algorithms

### Advanced Features

- [ ] **Streaming Responses**
  - Real-time token streaming
  - Server-Sent Events (SSE)
  - WebSocket support

- [ ] **Caching Layer**
  - Response caching for identical requests
  - Semantic caching for similar prompts
  - Cache invalidation strategies

- [ ] **A/B Testing Framework**
  - Compare model outputs side-by-side
  - Statistical significance testing
  - Automated quality metrics

### Training Data Curation

- [ ] **Label Studio Integration** (Optional)
  - Visual annotation interface
  - Multi-user collaboration
  - Export to common formats (JSONL, Parquet)

- [ ] **Quality Scoring**
  - Automated quality metrics
  - Human feedback collection
  - Active learning for dataset improvement

- [ ] **Dataset Management**
  - Version control for datasets
  - Dataset statistics and analysis
  - Deduplication and cleaning

---

## Long-Term (6-12 Months)

### Enterprise Features

- [ ] **Authentication & Authorization**
  - API key management
  - Role-based access control (RBAC)
  - OAuth2 integration

- [ ] **Multi-Tenancy**
  - Isolated workspaces per user/team
  - Resource quotas and limits
  - Usage tracking and billing

- [ ] **Audit Logging**
  - Comprehensive audit trails
  - Compliance reporting
  - Data retention policies

### Cloud Integration

- [ ] **Cloud Provider Support**
  - AWS (EC2, SageMaker)
  - GCP (Compute Engine, Vertex AI)
  - Azure (VM, ML)

- [ ] **Kubernetes Deployment**
  - Helm charts
  - Auto-scaling
  - Service mesh integration

- [ ] **Serverless Mode**
  - On-demand model loading
  - Pay-per-request pricing
  - Cold start optimization

### Advanced Inference

- [ ] **Speculative Decoding**
  - 2-3x faster inference
  - Draft model + verification
  - Automatic draft model selection

- [ ] **Continuous Batching**
  - Dynamic batching during generation
  - Improved GPU utilization
  - Lower latency for mixed workloads

- [ ] **Model Merging**
  - Merge multiple fine-tuned models
  - Task-specific routing
  - Ensemble predictions

---

## Research & Experimental

These features are under investigation and may or may not be implemented:

- **Mixture of Experts (MoE) Optimization**
  - CPU offloading for expert layers
  - Sparse activation patterns
  - Dynamic expert selection

- **Quantization-Aware Training**
  - Train models specifically for quantized inference
  - Maintain quality at lower precision
  - Custom quantization schemes

- **Prompt Optimization**
  - Automatic prompt engineering
  - Few-shot example selection
  - Prompt compression

- **Model Distillation**
  - Distill large models to smaller ones
  - Maintain quality with reduced size
  - On-device deployment

---

## Community Requests

Features requested by the community (vote on GitHub Discussions):

- [ ] **Windows Support** (WSL2 compatibility)
- [ ] **macOS Support** (Metal GPU acceleration)
- [ ] **AMD GPU Support** (ROCm)
- [ ] **Intel GPU Support** (oneAPI)
- [ ] **ARM Support** (Apple Silicon, Raspberry Pi)

---

## How to Contribute

We welcome contributions! Here's how you can help:

### Vote on Features

- 👍 Upvote features you want on [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)
- 💬 Comment with your use case
- 📝 Suggest new features

### Implement Features

1. Check the roadmap for features marked as "Help Wanted"
2. Comment on the issue to claim it
3. Submit a PR with your implementation
4. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines

### Report Issues

- 🐛 [Report bugs](https://github.com/zisaacson/vllm-batch-server/issues/new?template=bug_report.md)
- 💡 [Request features](https://github.com/zisaacson/vllm-batch-server/issues/new?template=feature_request.md)
- 📖 Improve documentation

---

## Version History

### v1.0.0 (Current)
- Initial public release
- OpenAI-compatible batch API
- Model hot-swapping
- Real-time monitoring
- Web UI

### Planned Releases

- **v1.1.0** - Quantization support, Python SDK
- **v1.2.0** - Multi-GPU support, streaming responses
- **v2.0.0** - Distributed processing, enterprise features

---

## Feedback

We'd love to hear from you! Share your thoughts:

- **GitHub Discussions**: [Start a discussion](https://github.com/zisaacson/vllm-batch-server/discussions)
- **GitHub Issues**: [Open an issue](https://github.com/zisaacson/vllm-batch-server/issues)
- **GitHub Issues**: [Report bugs or request features](https://github.com/zisaacson/vllm-batch-server/issues)

---

**Last Updated:** 2025-01-01

This roadmap is subject to change based on community feedback and project priorities.

