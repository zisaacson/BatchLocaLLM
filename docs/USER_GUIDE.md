# vLLM Batch Server - User Guide

Welcome to the vLLM Batch Server! This guide will help you get started with batch LLM inference, fine-tuning, and data curation.

---

## 📚 **Table of Contents**

1. [What is vLLM Batch Server?](#what-is-vllm-batch-server)
2. [Getting Started](#getting-started)
3. [Batch Inference](#batch-inference)
4. [Fine-Tuning Models](#fine-tuning-models)
5. [Data Curation with Label Studio](#data-curation-with-label-studio)
6. [Conquest Viewer](#conquest-viewer)
7. [Model Management](#model-management)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 **What is vLLM Batch Server?**

vLLM Batch Server is an open-source platform for:

- **Batch LLM Inference**: Process thousands of requests efficiently using OpenAI-compatible batch APIs
- **Fine-Tuning**: Train custom models on your data using Unsloth, Axolotl, or other frameworks
- **Data Curation**: Annotate and curate LLM outputs using Label Studio integration
- **Model Management**: Hot-swap models, compare performance, and deploy fine-tuned models

**Key Features**:
- ✅ OpenAI-compatible batch API
- ✅ Multiple model support (Gemma, Llama, GPT, etc.)
- ✅ Fine-tuning with LoRA/QLoRA
- ✅ Label Studio integration for data annotation
- ✅ Web UI for monitoring and management
- ✅ 100% open source (Apache 2.0, MIT)

---

## 🚀 **Getting Started**

### **Prerequisites**

- **GPU**: NVIDIA GPU with 16GB+ VRAM (RTX 4080, A100, H100, etc.)
- **Docker**: Docker and Docker Compose installed
- **Python**: Python 3.10+ (for local development)

### **Installation**

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/vllm-batch-server.git
   cd vllm-batch-server
   ```

2. **Start the services**:
   ```bash
   cd docker
   docker compose up -d
   ```

3. **Verify services are running**:
   ```bash
   # vLLM Batch Server
   curl http://localhost:4000/health
   
   # Label Studio
   curl http://localhost:4115/api/health
   ```

4. **Open the web UI**:
   - vLLM Batch Server: http://localhost:4000
   - Label Studio: http://localhost:4115
   - Conquest Viewer: http://localhost:4000/static/conquest-viewer.html

---

## 📦 **Batch Inference**

### **What is Batch Inference?**

Batch inference allows you to process thousands of LLM requests efficiently:
- **50% cost savings** compared to sequential requests (OpenAI/Parasail)
- **Parallel processing** for faster completion
- **Automatic retries** for failed requests

### **How to Submit a Batch**

1. **Prepare your JSONL file**:
   ```jsonl
   {"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma-3-12b", "messages": [{"role": "user", "content": "Hello!"}]}}
   {"custom_id": "request-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma-3-12b", "messages": [{"role": "user", "content": "How are you?"}]}}
   ```

2. **Upload the file**:
   ```bash
   curl -X POST http://localhost:4000/v1/files \
     -F "file=@batch_requests.jsonl" \
     -F "purpose=batch"
   ```

3. **Create a batch job**:
   ```bash
   curl -X POST http://localhost:4000/v1/batches \
     -H "Content-Type: application/json" \
     -d '{
       "input_file_id": "file_abc123",
       "endpoint": "/v1/chat/completions",
       "completion_window": "24h"
     }'
   ```

4. **Check batch status**:
   ```bash
   curl http://localhost:4000/v1/batches/batch_abc123
   ```

5. **Download results**:
   ```bash
   curl http://localhost:4000/v1/files/file_xyz789/content > results.jsonl
   ```

### **Using the Web UI**

1. Navigate to http://localhost:4000/static/queue-monitor.html
2. View active batches and their progress
3. Download results when complete

---

## 🎓 **Fine-Tuning Models**

### **What is Fine-Tuning?**

Fine-tuning adapts a pre-trained model to your specific use case:
- **Improve accuracy** on domain-specific tasks
- **Reduce hallucinations** with curated examples
- **Customize behavior** for your application

### **How to Fine-Tune a Model**

1. **Export training data**:
   - Go to http://localhost:4000/static/fine-tuning.html
   - Click "Export Gold Star Data"
   - Select dataset format (ChatML, Alpaca, OpenAI)
   - Download the dataset

2. **Configure training**:
   - Select backend (Unsloth, Axolotl, OpenAI, HuggingFace)
   - Choose base model (e.g., `gemma-3-12b`)
   - Set LoRA parameters (rank, alpha, dropout)
   - Configure training hyperparameters

3. **Start training**:
   - Click "Start Training"
   - Monitor progress in the dashboard
   - Training typically takes 1-4 hours depending on dataset size

4. **Deploy the model**:
   - Once training completes, click "Deploy to vLLM"
   - The model will be loaded into vLLM for inference
   - Use the model in batch jobs or conquests

### **Best Practices**

- **Start with 50-100 examples** for initial fine-tuning
- **Use Gold Star annotations** for high-quality training data
- **Compare models** using the Model Comparison tool
- **Iterate** based on performance metrics

---

## 🏷️ **Data Curation with Label Studio**

### **What is Label Studio?**

Label Studio is an open-source data annotation platform integrated with vLLM Batch Server:
- **Annotate LLM outputs** with ratings, feedback, and gold stars
- **Bidirectional sync** with Aristotle database
- **Webhook integration** for real-time updates

### **How to Annotate Data**

1. **Export conquests to Label Studio**:
   - Conquests are automatically exported after batch completion
   - Or manually export from Aristotle UI

2. **Open Label Studio**:
   - Navigate to http://localhost:4115
   - Login with your credentials
   - Select your project

3. **Annotate tasks**:
   - Review the LLM output
   - Rate quality (1-5 stars)
   - Check "Use for training" for gold star examples
   - Add feedback and improvement notes
   - Click "Submit"

4. **Sync back to Aristotle**:
   - Annotations automatically sync via webhook
   - Gold star annotations set conquest result to VICTORY
   - Data is available for fine-tuning

### **Annotation Guidelines**

**Quality Rating**:
- ⭐ (1 star): Completely wrong or unusable
- ⭐⭐ (2 stars): Mostly wrong with some correct elements
- ⭐⭐⭐ (3 stars): Partially correct but needs improvement
- ⭐⭐⭐⭐ (4 stars): Mostly correct with minor issues
- ⭐⭐⭐⭐⭐ (5 stars): Perfect or near-perfect output

**Gold Star** (Use for training):
- Check this for examples you want to use for fine-tuning
- Only select high-quality outputs (4-5 stars)
- Aim for diverse examples covering different scenarios

---

## 🏆 **Conquest Viewer**

### **What is the Conquest Viewer?**

The Conquest Viewer is a web UI for viewing and annotating conquests directly from the vLLM Batch Server.

### **How to Use**

1. **Open the viewer**:
   - Navigate to http://localhost:4000/static/conquest-viewer.html

2. **Filter conquests**:
   - Filter by status (Completed, Analyzing, Failed)
   - Filter by result (Victory, Defeat, Pending)
   - Filter by type (Candidate, Cartographer, etc.)
   - Filter by gold star status

3. **View conquest details**:
   - Click on a conquest to view full details
   - See prompt, completion, metadata, and execution time

4. **Annotate conquests**:
   - Click "Annotate Conquest"
   - Set quality rating (1-5 stars)
   - Check "Mark as Gold Star" for training examples
   - Add feedback and improvement notes
   - Click "Submit Annotation"

---

## 🔧 **Model Management**

### **Adding Models**

1. **Open Model Management**:
   - Navigate to http://localhost:4000/static/model-management.html

2. **Add a model**:
   - Enter model name (e.g., `gemma-3-12b`)
   - Enter HuggingFace model ID (e.g., `google/gemma-3-12b`)
   - Select quantization (none, 4-bit, 8-bit)
   - Click "Add Model"

3. **Wait for download**:
   - Model will be downloaded from HuggingFace
   - Progress shown in the UI
   - Model will be loaded into vLLM when ready

### **Switching Models**

1. **View active models**:
   - See currently loaded models in Model Management

2. **Load a different model**:
   - Click "Load" next to the model you want to use
   - Previous model will be unloaded
   - New model will be loaded (hot-swap)

3. **Use in batch jobs**:
   - Specify model name in batch requests
   - Model will be used for inference

---

## 🐛 **Troubleshooting**

### **Common Issues**

**1. Services not starting**

```bash
# Check Docker logs
docker compose logs -f

# Restart services
docker compose down
docker compose up -d
```

**2. GPU not detected**

```bash
# Verify NVIDIA drivers
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**3. Batch job stuck in "validating" status**

- Check vLLM server logs: `docker logs vllm-server`
- Verify model is loaded: `curl http://localhost:4000/v1/models`
- Restart vLLM server: `docker restart vllm-server`

**4. Label Studio webhook not working**

- Verify webhook URL is correct: `http://localhost:4000/api/webhooks/label-studio`
- Check webhook secret matches environment variable
- See [Label Studio Webhook Setup](LABEL_STUDIO_WEBHOOK_SETUP.md)

**5. Fine-tuning fails**

- Check GPU memory: `nvidia-smi`
- Reduce batch size or LoRA rank
- Check training logs: `docker logs vllm-batch-server`

### **Getting Help**

- **Documentation**: See [docs/](../docs/) folder
- **GitHub Issues**: https://github.com/your-org/vllm-batch-server/issues
- **Discord**: Join our community server

---

## 📖 **Next Steps**

- **Read the Developer Guide**: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Explore the API**: [API_REFERENCE.md](API_REFERENCE.md)
- **Join the Community**: Contribute to the project!

---

**Happy batching!** 🚀

