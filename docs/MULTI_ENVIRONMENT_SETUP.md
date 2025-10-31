# Multi-Environment Setup Guide

**How to manage multiple machines/environments with vLLM Batch Server**

---

## 🎯 Overview

This guide shows how to run the vLLM Batch Server on multiple machines with different configurations:

- **Home RTX 4080** - Development with 4B models
- **Office RTX 4080** - Second development machine
- **Cloud A100** - Production with 27B models
- **Custom Setups** - Any other configuration

---

## 📦 Architecture

### **Environment-Specific `.env` Files**

```
vllm-batch-server/
├── .env.example              ← Template (committed to git)
├── .env                      ← Active config (gitignored)
├── .env.rtx4080-home         ← Home machine (gitignored)
├── .env.rtx4080-office       ← Office machine (gitignored)
├── .env.a100-cloud           ← Cloud production (gitignored)
└── core/config.py            ← Reads from .env
```

**Key Principle:** One codebase, multiple configs via `.env` files

---

## 🚀 Quick Start

### **1. Clone Repo on New Machine**

```bash
git clone https://github.com/zisaacson/vllm-batch-server.git
cd vllm-batch-server
```

### **2. Choose Your Environment**

```bash
# Option A: Copy existing config
cp .env.rtx4080-home .env

# Option B: Create from template
cp .env.example .env
vim .env  # Edit for your machine
```

### **3. Start Server**

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -e core/

# Start services
python -m core.batch_app.api_server
python -m core.batch_app.worker
```

---

## 🔧 Environment Configs

### **RTX 4080 16GB (Home)**

**File:** `.env.rtx4080-home`

**Key Settings:**
```bash
ENVIRONMENT=development
DEFAULT_MODEL=google/gemma-3-4b-it  # 4B model
GPU_MEMORY_UTILIZATION=0.90  # Conservative
MAX_MODEL_LEN=8192  # Safe context
CHUNK_SIZE=5000  # Memory limit
```

**Use Case:** Local development, testing, benchmarking

---

### **RTX 4080 16GB (Office)**

**File:** `.env.rtx4080-office`

**Key Settings:**
```bash
ENVIRONMENT=development
DEFAULT_MODEL=google/gemma-3-4b-it
GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=8192
CHUNK_SIZE=5000

# Different paths
DATA_DIR=/mnt/ssd/vllm-data
MODELS_DIR=/mnt/ssd/models

# Different network
ARIS_APP_URL=http://192.168.1.100:4000
```

**Use Case:** Second development machine, different network/storage

---

### **A100 80GB (Cloud Production)**

**File:** `.env.a100-cloud`

**Key Settings:**
```bash
ENVIRONMENT=production
DEFAULT_MODEL=google/gemma-3-27b-it  # 27B model!
GPU_MEMORY_UTILIZATION=0.95  # Aggressive
MAX_MODEL_LEN=32768  # Large context
CHUNK_SIZE=10000  # Bigger batches

# Production settings
BATCH_API_RELOAD=false
LOG_LEVEL=WARNING
LOG_FILE=/var/log/vllm/app.log
API_KEY=your-secret-key
```

**Use Case:** Production deployment, customer-facing

---

## 📝 Creating Custom Configs

### **Step 1: Copy Template**

```bash
cp .env.example .env.my-machine
```

### **Step 2: Customize Key Settings**

```bash
# GPU Configuration
DEFAULT_MODEL=your-model-here
GPU_MEMORY_UTILIZATION=0.90  # Adjust for your GPU
MAX_MODEL_LEN=8192  # Adjust for your needs
CHUNK_SIZE=5000  # Adjust for your VRAM

# Paths
DATA_DIR=/your/data/path
MODELS_DIR=/your/models/path

# Network
BATCH_API_HOST=0.0.0.0
BATCH_API_PORT=4080
ARIS_APP_URL=http://your-aris-url
```

### **Step 3: Activate**

```bash
cp .env.my-machine .env
```

---

## 🔄 Switching Environments

### **Method 1: Copy Files**

```bash
# Switch to home config
cp .env.rtx4080-home .env

# Switch to office config
cp .env.rtx4080-office .env

# Switch to production
cp .env.a100-cloud .env
```

### **Method 2: Symlinks**

```bash
# Create symlink
ln -sf .env.rtx4080-home .env

# Switch
ln -sf .env.a100-cloud .env
```

### **Method 3: Environment Variable**

```bash
# Use specific config without copying
ENV_FILE=.env.a100-cloud python -m core.batch_app.worker
```

---

## 🎯 Common Scenarios

### **Scenario 1: Adding Second RTX 4080**

1. **Clone repo on new machine**
2. **Create config:** `cp .env.rtx4080-home .env.rtx4080-office`
3. **Edit paths/network:** `vim .env.rtx4080-office`
4. **Activate:** `cp .env.rtx4080-office .env`
5. **Start:** `python -m core.batch_app.worker`

### **Scenario 2: Upgrading to Cloud A100**

1. **SSH to cloud machine**
2. **Clone repo:** `git clone ...`
3. **Use production config:** `cp .env.a100-cloud .env`
4. **Edit secrets:** `vim .env` (add API keys)
5. **Deploy:** `docker-compose up -d`

### **Scenario 3: Testing Different Models**

```bash
# Create test config
cp .env .env.test-llama
vim .env.test-llama  # Change DEFAULT_MODEL

# Switch
cp .env.test-llama .env

# Test
python -m core.batch_app.worker
```

---

## 🔒 Security Best Practices

### **1. Never Commit `.env` Files**

```bash
# .gitignore already includes:
.env
.env.*
!.env.example
```

### **2. Use Different API Keys Per Environment**

```bash
# Development
API_KEY=  # Empty = no auth

# Production
API_KEY=your-secret-production-key
```

### **3. Restrict CORS in Production**

```bash
# Development
CORS_ORIGINS=["*"]

# Production
CORS_ORIGINS=["https://your-domain.com"]
```

---

## 📊 Monitoring Per Environment

### **Development (Local)**

```bash
ENABLE_PROMETHEUS=true
PROMETHEUS_URL=http://localhost:4022
GRAFANA_URL=http://localhost:3000
LOG_LEVEL=INFO
```

### **Production (Cloud)**

```bash
ENABLE_PROMETHEUS=true
PROMETHEUS_URL=http://prometheus.internal:9090
GRAFANA_URL=http://grafana.internal:3000
LOG_LEVEL=WARNING
LOG_FILE=/var/log/vllm/app.log
```

---

## 🚨 Troubleshooting

### **Problem: Config not loading**

```bash
# Check .env exists
ls -la .env

# Check syntax
cat .env | grep -v "^#" | grep "="

# Test loading
python -c "from core.config import settings; print(settings.DEFAULT_MODEL)"
```

### **Problem: Wrong environment active**

```bash
# Check which config is active
cat .env | head -5

# Verify settings
python -c "from core.config import settings; print(f'ENV: {settings.ENVIRONMENT}, MODEL: {settings.DEFAULT_MODEL}')"
```

### **Problem: Paths don't exist**

```bash
# Create directories
mkdir -p data/batches/{input,output,logs}
mkdir -p data/files
mkdir -p models
```

---

## 📚 Best Practices

### **1. Name Configs Descriptively**

```bash
✅ Good:
.env.rtx4080-home
.env.a100-cloud-prod
.env.test-gemma3-12b

❌ Bad:
.env.1
.env.backup
.env.old
```

### **2. Document Custom Configs**

Add comments to your `.env` files:

```bash
# ============================================================================
# RTX 4080 16GB - Home Development Setup
# ============================================================================
# This is Zack's home machine configuration
# Last updated: 2025-10-31
```

### **3. Keep Configs in Sync**

When adding new settings to `.env.example`, update all environment configs:

```bash
# Add new setting to all configs
for f in .env.*; do
    echo "NEW_SETTING=value" >> $f
done
```

---

## ✅ Checklist for New Environment

- [ ] Clone repo
- [ ] Create `.env` file (copy from template or existing)
- [ ] Update `DEFAULT_MODEL` for your GPU
- [ ] Update `GPU_MEMORY_UTILIZATION` for your VRAM
- [ ] Update `CHUNK_SIZE` for your memory
- [ ] Update paths (`DATA_DIR`, `MODELS_DIR`)
- [ ] Update network settings (`ARIS_APP_URL`, etc.)
- [ ] Test config loads: `python -c "from core.config import settings; print(settings.DEFAULT_MODEL)"`
- [ ] Start server: `python -m core.batch_app.api_server`
- [ ] Start worker: `python -m core.batch_app.worker`
- [ ] Verify monitoring: Open `http://localhost:3000` (Grafana)

---

**Questions?** See `core/README.md` or `.env.example` for all available settings.

