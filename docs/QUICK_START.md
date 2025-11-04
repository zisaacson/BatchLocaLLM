# Quick Start Guide

Get up and running with vLLM Batch Server in **5 minutes**.

---

## 📋 **Prerequisites**

### **Hardware**
- **GPU**: NVIDIA GPU with 16GB+ VRAM (tested on RTX 4080)
- **RAM**: 32GB+ recommended
- **Storage**: 50GB+ free space for models

### **Software**
- **OS**: Linux (Ubuntu 22.04+ recommended)
- **Python**: 3.10-3.12
- **Docker**: 20.10+ (optional, for monitoring stack)
- **CUDA**: 12.1+ (for vLLM)

---

## 🚀 **Installation**

### **Option 1: Quick Install (Recommended)**

```bash
# Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
python -m core.batch_app.init_db

# Start server
python -m core.batch_app.api_server
```

Server will start on `http://localhost:4080` 🎉

### **Option 2: Docker Compose (Full Stack)**

```bash
# Clone repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

This starts:
- **vLLM Batch Server** (port 4080)
- **PostgreSQL** (port 4332)
- **Grafana** (port 4333) - Monitoring dashboards
- **Prometheus** (port 4334) - Metrics
- **Loki** (port 4335) - Logs
- **Label Studio** (port 4115) - Data annotation

---

## 🎯 **Your First Batch Job**

### **Step 1: Add a Model**

Open the web UI: `http://localhost:8001`

1. Click **"Model Management"**
2. Enter HuggingFace model ID: `google/gemma-3-4b-it`
3. Click outside the field → model info auto-fills
4. Click **"Add Model"**

The model will download automatically (may take 5-10 minutes).

### **Step 2: Create a Batch File**

Create `my_batch.jsonl`:

```jsonl
{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "google/gemma-3-4b-it", "messages": [{"role": "user", "content": "What is the capital of France?"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "google/gemma-3-4b-it", "messages": [{"role": "user", "content": "Explain quantum computing in simple terms."}]}}
{"custom_id": "req-3", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "google/gemma-3-4b-it", "messages": [{"role": "user", "content": "Write a haiku about coding."}]}}
```

### **Step 3: Submit Batch Job**

```bash
# Upload file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@my_batch.jsonl" \
  -F "purpose=batch"

# Response: {"id": "file-abc123", ...}

# Create batch job
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-abc123",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'

# Response: {"id": "batch-xyz789", "status": "validating", ...}
```

### **Step 4: Check Status**

```bash
# Check batch status
curl http://localhost:4080/v1/batches/batch-xyz789

# Response:
# {
#   "id": "batch-xyz789",
#   "status": "completed",
#   "request_counts": {
#     "total": 3,
#     "completed": 3,
#     "failed": 0
#   },
#   "output_file_id": "file-output-123"
# }
```

### **Step 5: Download Results**

```bash
# Download results
curl http://localhost:4080/v1/files/file-output-123/content > results.jsonl

# View results
cat results.jsonl | jq .
```

**Example output**:
```json
{
  "custom_id": "req-1",
  "response": {
    "status_code": 200,
    "body": {
      "id": "chatcmpl-123",
      "choices": [{
        "message": {
          "content": "The capital of France is Paris."
        }
      }]
    }
  }
}
```

---

## 🎨 **Using the Web UI**

### **Dataset Workbench** (`http://localhost:8001`)

1. **Upload Dataset**
   - Click "Upload Dataset"
   - Select your JSONL file
   - Choose models to compare

2. **View Results**
   - See all model responses side-by-side
   - Compare quality, speed, cost
   - Mark high-quality examples

3. **Export Curated Data**
   - Select gold star examples
   - Export for fine-tuning
   - Use in-context learning

### **Model Management** (`http://localhost:8001/model-management.html`)

- Add models from HuggingFace
- Test models with sample requests
- View benchmark results
- Delete unused models

### **Monitoring** (`http://localhost:4333`)

- GPU utilization and memory
- Request throughput
- Queue depth
- Error rates

---

## 📚 **Next Steps**

### **Learn More**

- **[Plugin Development](PLUGIN_DEVELOPMENT.md)** - Create custom result handlers
- **[Examples](../examples/README.md)** - Code examples and use cases
- **[API Reference](reference/api.md)** - Complete API documentation
- **[Architecture](architecture/system-design.md)** - System design and internals

### **Common Use Cases**

1. **Model Comparison**
   ```bash
   python examples/compare_models.py \
     --dataset examples/datasets/synthetic_100.jsonl \
     --models gemma-3-4b llama-3.2-3b qwen-3-4b
   ```

2. **Training Data Curation**
   - Process 1000s of examples
   - Review in web UI
   - Mark gold stars
   - Export for fine-tuning

3. **Production Inference**
   - Submit large batches (50K+ requests)
   - Automatic chunking and incremental saves
   - Monitor progress in Grafana
   - Webhook notifications on completion

### **Troubleshooting**

**GPU Out of Memory?**
- Use smaller models (4B instead of 7B)
- Enable CPU offload in model config
- Reduce `max_model_len` in model settings

**Model Download Slow?**
- Check HuggingFace status
- Use a mirror if available
- Download manually and place in `models/` directory

**Worker Not Processing Jobs?**
- Check worker logs: `docker-compose logs worker`
- Verify model is downloaded: `ls models/`
- Check GPU availability: `nvidia-smi`

**Database Connection Failed?**
- Ensure PostgreSQL is running: `docker-compose ps postgres`
- Check `.env` database settings
- Verify port 4332 is not in use

---

## 🤝 **Getting Help**

- **Issues**: [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)
- **Documentation**: [docs/](.)

---

## 📝 **What's Next?**

Now that you have the basics working:

1. **Try the examples** in `examples/` directory
2. **Create a custom result handler** (see [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md))
3. **Set up monitoring** with Grafana dashboards
4. **Fine-tune a model** using curated data
5. **Deploy to production** with systemd services

Happy batching! 🚀

