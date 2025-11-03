# Environment Variables Reference

Complete reference for all environment variables used by vLLM Batch Server.

---

## 🔧 Core Configuration

### **Database**

#### `DATABASE_URL`
- **Type:** String (PostgreSQL connection URL)
- **Required:** Yes
- **Default:** `postgresql://postgres:postgres@localhost:4332/vllm_batch`
- **Description:** PostgreSQL database connection string
- **Example:**
  ```bash
  DATABASE_URL=postgresql://user:password@localhost:4332/dbname
  ```

---

### **API Server**

#### `API_HOST`
- **Type:** String
- **Required:** No
- **Default:** `0.0.0.0`
- **Description:** Host address for the API server
- **Example:**
  ```bash
  API_HOST=127.0.0.1
  ```

#### `API_PORT`
- **Type:** Integer
- **Required:** No
- **Default:** `4080`
- **Description:** Port for the API server
- **Example:**
  ```bash
  API_PORT=8080
  ```

#### `API_WORKERS`
- **Type:** Integer
- **Required:** No
- **Default:** `1`
- **Description:** Number of API worker processes
- **Example:**
  ```bash
  API_WORKERS=4
  ```

---

### **Worker Configuration**

#### `WORKER_POLL_INTERVAL`
- **Type:** Integer (seconds)
- **Required:** No
- **Default:** `5`
- **Description:** How often the worker checks for new jobs
- **Example:**
  ```bash
  WORKER_POLL_INTERVAL=10
  ```

#### `WORKER_MAX_RETRIES`
- **Type:** Integer
- **Required:** No
- **Default:** `3`
- **Description:** Maximum retries for failed jobs
- **Example:**
  ```bash
  WORKER_MAX_RETRIES=5
  ```

---

## 🤖 vLLM Configuration

### **Model Settings**

#### `DEFAULT_MODEL`
- **Type:** String (HuggingFace model ID)
- **Required:** No
- **Default:** `google/gemma-3-4b-it`
- **Description:** Default model to use if not specified
- **Example:**
  ```bash
  DEFAULT_MODEL=meta-llama/Llama-3.2-3B-Instruct
  ```

#### `VLLM_TENSOR_PARALLEL_SIZE`
- **Type:** Integer
- **Required:** No
- **Default:** `1`
- **Description:** Number of GPUs for tensor parallelism
- **Example:**
  ```bash
  VLLM_TENSOR_PARALLEL_SIZE=2
  ```

#### `VLLM_GPU_MEMORY_UTILIZATION`
- **Type:** Float (0.0-1.0)
- **Required:** No
- **Default:** `0.9`
- **Description:** Fraction of GPU memory to use
- **Example:**
  ```bash
  VLLM_GPU_MEMORY_UTILIZATION=0.85
  ```

#### `VLLM_MAX_MODEL_LEN`
- **Type:** Integer
- **Required:** No
- **Default:** `8192`
- **Description:** Maximum context length
- **Example:**
  ```bash
  VLLM_MAX_MODEL_LEN=16384
  ```

---

## 🔗 Label Studio Integration

### **Label Studio Configuration**

#### `LABEL_STUDIO_URL`
- **Type:** String (URL)
- **Required:** No (if using Label Studio)
- **Default:** `http://localhost:4115`
- **Description:** Label Studio server URL
- **Example:**
  ```bash
  LABEL_STUDIO_URL=https://labelstudio.example.com
  ```

#### `LABEL_STUDIO_API_KEY`
- **Type:** String
- **Required:** No (if using Label Studio)
- **Default:** None
- **Description:** Label Studio API authentication token
- **Example:**
  ```bash
  LABEL_STUDIO_API_KEY=your-api-key-here
  ```

#### `LABEL_STUDIO_PROJECT_ID`
- **Type:** Integer
- **Required:** No
- **Default:** None
- **Description:** Default Label Studio project ID
- **Example:**
  ```bash
  LABEL_STUDIO_PROJECT_ID=1
  ```

---

### **ML Backend Configuration**

#### `ML_BACKEND_HOST`
- **Type:** String
- **Required:** No
- **Default:** `0.0.0.0`
- **Description:** ML Backend server host
- **Example:**
  ```bash
  ML_BACKEND_HOST=127.0.0.1
  ```

#### `ML_BACKEND_PORT`
- **Type:** Integer
- **Required:** No
- **Default:** `4082`
- **Description:** ML Backend server port
- **Example:**
  ```bash
  ML_BACKEND_PORT=9090
  ```

---

## 📊 Monitoring

### **Grafana**

#### `GRAFANA_PORT`
- **Type:** Integer
- **Required:** No
- **Default:** `4220`
- **Description:** Grafana dashboard port
- **Example:**
  ```bash
  GRAFANA_PORT=3000
  ```

### **Prometheus**

#### `PROMETHEUS_PORT`
- **Type:** Integer
- **Required:** No
- **Default:** `4222`
- **Description:** Prometheus metrics port
- **Example:**
  ```bash
  PROMETHEUS_PORT=9090
  ```

### **Loki**

#### `LOKI_PORT`
- **Type:** Integer
- **Required:** No
- **Default:** `4221`
- **Description:** Loki log aggregation port
- **Example:**
  ```bash
  LOKI_PORT=3100
  ```

---

## 🔐 Security

### **Webhook Configuration**

#### `WEBHOOK_SECRET`
- **Type:** String
- **Required:** No (if using webhooks)
- **Default:** None
- **Description:** Secret key for webhook signature verification
- **Example:**
  ```bash
  WEBHOOK_SECRET=your-secret-key-here
  ```

#### `WEBHOOK_MAX_RETRIES`
- **Type:** Integer
- **Required:** No
- **Default:** `3`
- **Description:** Maximum webhook delivery retries
- **Example:**
  ```bash
  WEBHOOK_MAX_RETRIES=5
  ```

#### `WEBHOOK_TIMEOUT`
- **Type:** Integer (seconds)
- **Required:** No
- **Default:** `30`
- **Description:** Webhook request timeout
- **Example:**
  ```bash
  WEBHOOK_TIMEOUT=60
  ```

---

## 🗄️ Storage

### **File Storage**

#### `STORAGE_PATH`
- **Type:** String (directory path)
- **Required:** No
- **Default:** `./storage`
- **Description:** Directory for uploaded files
- **Example:**
  ```bash
  STORAGE_PATH=/var/lib/vllm-batch/storage
  ```

#### `MAX_FILE_SIZE`
- **Type:** Integer (bytes)
- **Required:** No
- **Default:** `104857600` (100MB)
- **Description:** Maximum upload file size
- **Example:**
  ```bash
  MAX_FILE_SIZE=524288000  # 500MB
  ```

---

## 🔍 Logging

### **Log Configuration**

#### `LOG_LEVEL`
- **Type:** String
- **Required:** No
- **Default:** `INFO`
- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description:** Logging verbosity level
- **Example:**
  ```bash
  LOG_LEVEL=DEBUG
  ```

#### `LOG_FORMAT`
- **Type:** String
- **Required:** No
- **Default:** `json`
- **Options:** `json`, `text`
- **Description:** Log output format
- **Example:**
  ```bash
  LOG_FORMAT=text
  ```

---

## 🌐 CORS

### **CORS Configuration**

#### `CORS_ORIGINS`
- **Type:** String (comma-separated URLs)
- **Required:** No
- **Default:** `*`
- **Description:** Allowed CORS origins
- **Example:**
  ```bash
  CORS_ORIGINS=http://localhost:3000,https://app.example.com
  ```

---

## 📝 Example .env File

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:4332/vllm_batch

# API Server
API_HOST=0.0.0.0
API_PORT=4080
API_WORKERS=1

# Worker
WORKER_POLL_INTERVAL=5
WORKER_MAX_RETRIES=3

# vLLM
DEFAULT_MODEL=google/gemma-3-4b-it
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=8192

# Label Studio
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_API_KEY=your-api-key-here
LABEL_STUDIO_PROJECT_ID=1

# ML Backend
ML_BACKEND_HOST=0.0.0.0
ML_BACKEND_PORT=4082

# Monitoring
GRAFANA_PORT=4220
PROMETHEUS_PORT=4222
LOKI_PORT=4221

# Security
WEBHOOK_SECRET=your-secret-key-here
WEBHOOK_MAX_RETRIES=3
WEBHOOK_TIMEOUT=30

# Storage
STORAGE_PATH=./storage
MAX_FILE_SIZE=104857600

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# CORS
CORS_ORIGINS=*
```

---

## 🔗 Related Documentation

- [Getting Started Guide](../guides/getting-started.md)
- [Deployment Guide](../guides/deployment.md)
- [API Reference](api.md)

---

**Need help?** Open an issue or ask in discussions!

