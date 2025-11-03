# 🚀 5-Minute Quick Start

Get vLLM Batch Server running in **5 minutes** with a single command.

---

## What You'll Build

By the end of this guide, you'll have:
- ✅ vLLM Batch Server running locally
- ✅ PostgreSQL database configured
- ✅ Interactive API documentation (Swagger UI)
- ✅ Your first batch job submitted and completed
- ✅ Real-time queue monitor

**Time:** 5 minutes  
**Difficulty:** Easy  
**Prerequisites:** Docker, Docker Compose, NVIDIA GPU

---

## Step 1: Clone and Start (2 minutes)

```bash
# Clone the repository
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server

# Start all services with one command
docker compose up -d

# Wait for services to start (30 seconds)
sleep 30
```

**What just happened?**
- ✅ PostgreSQL database started (port 4332)
- ✅ Label Studio started (port 4115)
- ✅ Monitoring stack started (Grafana on 4220)

---

## Step 2: Start the Batch Server (1 minute)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (this takes ~5-10 minutes for vLLM)
pip install -r requirements.txt

# Start the API server
./scripts/start-services.sh
```

**What just happened?**
- ✅ API Server started (port 4080)
- ✅ Worker started (processing jobs)
- ✅ ML Backend started (port 4082)

---

## Step 3: Explore the API (1 minute)

Open your browser and visit:

**🔗 Interactive API Documentation:**
```
http://localhost:4080/docs
```

You'll see the Swagger UI with all available endpoints:

![Swagger UI](../screenshots/swagger-ui/api-docs.png)

**Try it out:**
1. Click on `GET /health`
2. Click "Try it out"
3. Click "Execute"
4. See the response:

```json
{
  "status": "healthy",
  "service": "batch-api",
  "version": "1.0.0",
  "timestamp": "2025-11-03T14:59:51.586534+00:00"
}
```

---

## Step 4: Submit Your First Batch Job (1 minute)

### Option A: Using Swagger UI (Easiest)

1. In Swagger UI, find `POST /v1/batches`
2. Click "Try it out"
3. Paste this example:

```json
{
  "input_file_id": "file-example-001",
  "endpoint": "/v1/chat/completions",
  "completion_window": "24h",
  "metadata": {
    "description": "My first batch job",
    "model": "google/gemma-3-4b-it"
  }
}
```

4. Click "Execute"
5. Copy the `batch_id` from the response

### Option B: Using curl

```bash
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-example-001",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h",
    "metadata": {
      "description": "My first batch job",
      "model": "google/gemma-3-4b-it"
    }
  }'
```

**Response:**
```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "status": "validating",
  "created_at": 1234567890,
  "request_counts": {
    "total": 0,
    "completed": 0,
    "failed": 0
  }
}
```

---

## Step 5: Monitor Your Job (30 seconds)

### Option A: Queue Monitor UI

Open the queue monitor:
```
http://localhost:4080/queue
```

You'll see:
- 📊 All jobs in the queue
- ⏱️ Queue position and ETA
- 📈 Progress (completed/total requests)
- 🎯 Current model loaded

![Queue Monitor](../screenshots/queue-monitor/with-jobs.png)

### Option B: Check Status via API

```bash
# Replace batch_abc123 with your batch ID
curl http://localhost:4080/v1/batches/batch_abc123 | jq
```

**Response:**
```json
{
  "id": "batch_abc123",
  "status": "completed",
  "request_counts": {
    "total": 100,
    "completed": 100,
    "failed": 0
  },
  "output_file_id": "file-output-abc123"
}
```

---

## 🎉 Success!

You now have a fully functional vLLM Batch Server!

**What you can do next:**

### 1. **View Results**
```bash
# Download results
curl http://localhost:4080/v1/files/file-output-abc123/content > results.jsonl

# View first result
head -1 results.jsonl | jq
```

### 2. **Monitor with Grafana**
```
http://localhost:4220
```
- Username: `admin`
- Password: `admin`

![Grafana Dashboard](../screenshots/grafana/main-dashboard.png)

### 3. **Try Label Studio Integration**
```
http://localhost:4115
```

Create a project and connect the ML Backend for real-time predictions!

### 4. **Compare Multiple Models**

Submit the same dataset to different models:
```bash
# Gemma 3 4B
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{"input_file_id": "file-example-001", "metadata": {"model": "google/gemma-3-4b-it"}}'

# Llama 3.2 3B
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{"input_file_id": "file-example-001", "metadata": {"model": "meta-llama/Llama-3.2-3B-Instruct"}}'
```

Then compare results in the Dataset Workbench!

---

## 📚 Next Steps

Now that you have the basics working, explore:

- **[Full Setup Guide](../guides/getting-started.md)** - Complete installation and configuration
- **[API Reference](../reference/api.md)** - All endpoints and parameters
- **[Label Studio Integration](../guides/label-studio.md)** - Set up data labeling
- **[Benchmarking Guide](../guides/benchmarking.md)** - Compare models scientifically
- **[Deployment Guide](../guides/deployment.md)** - Deploy to production

---

## 🐛 Troubleshooting

### Services won't start

```bash
# Check if ports are already in use
sudo lsof -i :4080  # API Server
sudo lsof -i :4332  # PostgreSQL
sudo lsof -i :4115  # Label Studio

# Kill existing processes
pkill -f "python -m core.batch_app.api_server"
docker compose down
```

### GPU not detected

```bash
# Check GPU
nvidia-smi

# Verify CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

### vLLM installation fails

```bash
# Make sure you have CUDA 12.1+
nvcc --version

# Try installing with specific CUDA version
pip install vllm==0.11.0 --extra-index-url https://download.pytorch.org/whl/cu121
```

### Need help?

- 📖 [Full Troubleshooting Guide](../TROUBLESHOOTING.md)
- 💬 [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)
- 🐛 [Report a Bug](https://github.com/zisaacson/vllm-batch-server/issues)

---

## 🎯 What's Different from OpenAI?

| Feature | OpenAI Batch API | vLLM Batch Server |
|---------|------------------|-------------------|
| **Cost** | $$ per request | Free (local) |
| **Privacy** | Cloud (data leaves your network) | Local (data stays on your machine) |
| **Models** | OpenAI models only | Any HuggingFace model |
| **Customization** | Limited | Full control (open source) |
| **Training Data** | No curation tools | Label Studio integration |
| **Monitoring** | Basic | Grafana + Prometheus + Loki |
| **Queue Visibility** | Limited | Real-time queue monitor |

---

**Ready to build?** 🚀

Start processing thousands of requests on your local GPU!

