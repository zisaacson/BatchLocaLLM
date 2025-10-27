# Ollama Batch Server - OpenAI-Compatible Batch Processing

**Branch**: `ollama`  
**Purpose**: OpenAI-compatible batch processing wrapper for Ollama (consumer GPUs)  
**Target Hardware**: RTX 4080 16GB, RTX 3080, RTX 3090, etc.

---

## 🎯 What This Does

This branch provides an **OpenAI Batch API-compatible** wrapper around Ollama, enabling:

1. **Batch Processing** - Submit 100s-1000s of requests in JSONL format
2. **Async Processing** - Jobs run in background, check status via API
3. **Cost Savings** - Reduces tokenization overhead vs individual requests
4. **OpenAI Compatibility** - Drop-in replacement for OpenAI Batch API
5. **Local Inference** - No API costs, full privacy

---

## 🚀 Quick Start

### 1. Start Ollama
```bash
ollama serve &
ollama pull gemma3:12b
```

### 2. Start Batch Server
```bash
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

### 3. Submit a Batch Job

**Create batch file** (`batch_requests.jsonl`):
```jsonl
{"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma3:12b", "messages": [{"role": "user", "content": "What is 2+2?"}]}}
{"custom_id": "request-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma3:12b", "messages": [{"role": "user", "content": "What is the capital of France?"}]}}
```

**Upload and submit**:
```bash
# Upload batch file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@batch_requests.jsonl" \
  -F "purpose=batch"

# Create batch job (use file_id from above)
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-abc123",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'

# Check status (use batch_id from above)
curl http://localhost:4080/v1/batches/batch-xyz789

# Download results when complete
curl http://localhost:4080/v1/files/file-output123/content
```

---

## 📊 How Batching Reduces Tokenization Overhead

### Individual Requests (No Batching)
```
Request 1: Tokenize prompt → Inference → Detokenize
Request 2: Tokenize prompt → Inference → Detokenize
Request 3: Tokenize prompt → Inference → Detokenize
...
Total tokenization: N requests × tokenization time
```

### Batch Processing (This Server)
```
Batch: Load all requests → Process sequentially → Write results
- Ollama model stays loaded in memory
- No repeated model loading/unloading
- Efficient memory usage
- Single tokenizer initialization
```

**Savings**:
- ✅ Model stays warm (no reload overhead)
- ✅ Tokenizer initialized once
- ✅ Efficient memory management
- ✅ Background processing (async)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   Client Application                │
│   - Submits batch JSONL file       │
│   - Polls for completion            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   FastAPI Batch Server (Port 4080)  │
│   - /v1/files (upload)              │
│   - /v1/batches (create/status)     │
│   - Batch job queue                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Ollama Backend                    │
│   - Sequential processing           │
│   - Model: gemma3:12b               │
│   - Port: 11434                     │
└─────────────────────────────────────┘
```

---

## 🔧 Configuration

Edit `.env`:
```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=gemma3:12b

# Batch Processing
MAX_CONCURRENT_BATCHES=1  # Ollama processes sequentially

# Server
HOST=0.0.0.0
PORT=4080
```

---

## 📝 API Endpoints

### Upload File
```bash
POST /v1/files
Content-Type: multipart/form-data

file: <JSONL file>
purpose: "batch"
```

### Create Batch
```bash
POST /v1/batches
Content-Type: application/json

{
  "input_file_id": "file-abc123",
  "endpoint": "/v1/chat/completions",
  "completion_window": "24h"
}
```

### Get Batch Status
```bash
GET /v1/batches/{batch_id}
```

### List Batches
```bash
GET /v1/batches
```

### Download Results
```bash
GET /v1/files/{file_id}/content
```

---

## 🎓 Batch Request Format

Each line in the JSONL file:
```json
{
  "custom_id": "unique-request-id",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "gemma3:12b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Your question here"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }
}
```

---

## 🎯 Batch Response Format

Each line in the output JSONL file:
```json
{
  "id": "batch-result-123",
  "custom_id": "unique-request-id",
  "response": {
    "status_code": 200,
    "request_id": "req-abc123",
    "body": {
      "id": "chatcmpl-xyz",
      "object": "chat.completion",
      "created": 1234567890,
      "model": "gemma3:12b",
      "choices": [{
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "The answer is..."
        },
        "finish_reason": "stop"
      }],
      "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 50,
        "total_tokens": 70
      }
    }
  },
  "error": null
}
```

---

## 🔍 Monitoring

### Health Check
```bash
curl http://localhost:4080/health
```

### Metrics (Prometheus)
```bash
curl http://localhost:4080/metrics
```

---

## 🆚 Comparison: Ollama Branch vs vLLM Branch

| Feature | Ollama Branch | vLLM Branch |
|---------|---------------|-------------|
| **Target Hardware** | Consumer GPUs (16GB) | Cloud GPUs (24GB+) |
| **Backend** | Ollama | vLLM |
| **Batch Processing** | Sequential wrapper | Native batching |
| **Model Hot-Swapping** | ❌ No | ✅ Yes |
| **Memory Efficiency** | ✅ High | ⚠️ Medium |
| **Throughput** | Medium | High |
| **Use Case** | Local dev, A/B testing | Production inference |

---

## 🐛 Troubleshooting

See `TROUBLESHOOTING_CHECKLIST.md` for comprehensive troubleshooting guide.

**Common Issues**:

1. **"Ollama server is not running"**
   ```bash
   ollama serve &
   ```

2. **"Model not found"**
   ```bash
   ollama pull gemma3:12b
   ```

3. **Port 4080 already in use**
   ```bash
   ps aux | grep uvicorn
   kill -9 <PID>
   ```

---

## 📚 Next Steps

1. ✅ Server is running
2. ⏳ **Build batch processing workflow** (current task)
3. ⏳ Test end-to-end with sample batch
4. ⏳ Measure throughput and cost savings
5. ⏳ Document performance benchmarks

---

**Branch**: `ollama`  
**Status**: Active development  
**Last Updated**: 2025-10-27

