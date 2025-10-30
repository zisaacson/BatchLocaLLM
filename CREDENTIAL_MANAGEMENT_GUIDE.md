# Credential Management Guide: Local to Production

## 🎯 Current State

**You already have:**
- ✅ `.env` file for local configuration
- ✅ `.env` in `.gitignore` (not committed to Git)
- ✅ `.env.example` as template

**What's missing:**
- ❌ Label Studio API token
- ❌ Grafana API token
- ❌ Production secret management (GCP Secret Manager)

---

## 🔐 Local Development: `.env` File

### **Current `.env` Structure**

Your `.env` file has vLLM configuration but is missing monitoring/integration tokens.

### **Updated `.env` Template**

Add these sections to your `.env` file:

```bash
# =============================================================================
# Monitoring & Integration Tokens
# =============================================================================

# Label Studio
# Get token from: http://localhost:4015 → Account & Settings → Access Token
LABEL_STUDIO_URL=http://localhost:4015
LABEL_STUDIO_TOKEN=your_token_here
LABEL_STUDIO_PROJECT_ID=1

# Grafana
# Get token from: http://localhost:4020 → Configuration → API Keys
GRAFANA_URL=http://localhost:4020
GRAFANA_TOKEN=your_token_here

# Prometheus
PROMETHEUS_URL=http://localhost:4022

# Loki
LOKI_URL=http://localhost:4021

# =============================================================================
# External Services (Production)
# =============================================================================

# Hugging Face
# Get token from: https://huggingface.co/settings/tokens
HF_TOKEN=your_hf_token_here

# Google Cloud Platform
# Service account key path (for local development)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1

# OpenAI (for comparison benchmarks)
OPENAI_API_KEY=your_openai_key_here

# =============================================================================
# Security
# =============================================================================

# API authentication (optional)
# Generate with: openssl rand -hex 32
API_KEY=

# JWT secret (for multi-user auth)
# Generate with: openssl rand -hex 64
JWT_SECRET=

# =============================================================================
# Database (if using PostgreSQL instead of SQLite)
# =============================================================================

# PostgreSQL connection string
DATABASE_URL=postgresql://user:password@localhost:5432/vllm_batch

# Redis (for distributed queue)
REDIS_URL=redis://localhost:6379/0
```

### **How to Get Tokens**

**Label Studio:**
```bash
# 1. Open Label Studio
open http://localhost:4015

# 2. Click user icon (top right) → Account & Settings
# 3. Copy "Access Token"
# 4. Add to .env:
LABEL_STUDIO_TOKEN=abc123...
```

**Grafana:**
```bash
# 1. Open Grafana
open http://localhost:4020

# 2. Login (admin/admin)
# 3. Configuration (gear icon) → API Keys
# 4. Click "New API Key"
#    - Name: "vllm-batch-server"
#    - Role: "Admin"
#    - Time to live: "Never" (or 1 year)
# 5. Copy token
# 6. Add to .env:
GRAFANA_TOKEN=eyJrIjoi...
```

**Hugging Face:**
```bash
# 1. Go to https://huggingface.co/settings/tokens
# 2. Create new token (Read access)
# 3. Add to .env:
HF_TOKEN=hf_...
```

### **Loading `.env` in Python**

```python
# serve_results.py or any Python script
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access tokens
LABEL_STUDIO_TOKEN = os.getenv('LABEL_STUDIO_TOKEN')
GRAFANA_TOKEN = os.getenv('GRAFANA_TOKEN')
HF_TOKEN = os.getenv('HF_TOKEN')

# Use in API calls
from label_studio_sdk import Client

ls = Client(
    url=os.getenv('LABEL_STUDIO_URL'),
    api_key=LABEL_STUDIO_TOKEN
)
```

### **Install python-dotenv**

```bash
pip install python-dotenv
```

---

## ☁️ Production: GCP Secret Manager

### **Why Use Secret Manager?**

**Local `.env` is fine for development, but production needs:**
- ✅ **Centralized** - one place for all secrets
- ✅ **Versioned** - track changes, rollback if needed
- ✅ **Audited** - who accessed what when
- ✅ **Encrypted** - at rest and in transit
- ✅ **IAM-controlled** - fine-grained access control
- ✅ **No files** - no risk of committing secrets to Git

### **Setup GCP Secret Manager**

**1. Create GCP Project**

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Create project
gcloud projects create vllm-batch-server --name="vLLM Batch Server"

# Set as default
gcloud config set project vllm-batch-server

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com
```

**2. Create Secrets**

```bash
# Label Studio token
echo -n "your_label_studio_token" | \
  gcloud secrets create label-studio-token \
  --data-file=- \
  --replication-policy="automatic"

# Grafana token
echo -n "your_grafana_token" | \
  gcloud secrets create grafana-token \
  --data-file=- \
  --replication-policy="automatic"

# Hugging Face token
echo -n "your_hf_token" | \
  gcloud secrets create hf-token \
  --data-file=- \
  --replication-policy="automatic"

# OpenAI API key (for benchmarks)
echo -n "your_openai_key" | \
  gcloud secrets create openai-api-key \
  --data-file=- \
  --replication-policy="automatic"

# Database password
echo -n "your_db_password" | \
  gcloud secrets create db-password \
  --data-file=- \
  --replication-policy="automatic"
```

**3. Grant Access to Service Account**

```bash
# Create service account
gcloud iam service-accounts create vllm-batch-server \
  --display-name="vLLM Batch Server"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding vllm-batch-server \
  --member="serviceAccount:vllm-batch-server@vllm-batch-server.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Create key for local development
gcloud iam service-accounts keys create ~/vllm-batch-server-key.json \
  --iam-account=vllm-batch-server@vllm-batch-server.iam.gserviceaccount.com
```

**4. Access Secrets in Python**

```python
# secret_manager.py
from google.cloud import secretmanager
import os

class SecretManager:
    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = os.getenv('GCP_PROJECT_ID', 'vllm-batch-server')
    
    def get_secret(self, secret_id, version='latest'):
        """Get secret from GCP Secret Manager."""
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode('UTF-8')
    
    def get_all_secrets(self):
        """Get all secrets for the application."""
        return {
            'label_studio_token': self.get_secret('label-studio-token'),
            'grafana_token': self.get_secret('grafana-token'),
            'hf_token': self.get_secret('hf-token'),
            'openai_api_key': self.get_secret('openai-api-key'),
            'db_password': self.get_secret('db-password'),
        }

# Usage
if os.getenv('ENV') == 'production':
    # Production: use GCP Secret Manager
    sm = SecretManager()
    secrets = sm.get_all_secrets()
    LABEL_STUDIO_TOKEN = secrets['label_studio_token']
else:
    # Local: use .env file
    from dotenv import load_dotenv
    load_dotenv()
    LABEL_STUDIO_TOKEN = os.getenv('LABEL_STUDIO_TOKEN')
```

**5. Install Dependencies**

```bash
pip install google-cloud-secret-manager
```

---

## 🔒 Security Best Practices

### **1. Never Commit Secrets to Git**

```bash
# Check .gitignore includes:
.env
.env.local
.env.*.local
*.json  # Service account keys
```

### **2. Rotate Tokens Regularly**

```bash
# Rotate every 90 days
# Label Studio: Generate new token, update secret
# Grafana: Generate new API key, update secret
# HF: Generate new token, update secret
```

### **3. Use Least Privilege**

```bash
# Label Studio: Read-only token if only reading data
# Grafana: Viewer role if only viewing dashboards
# GCP: Only grant secretAccessor, not secretAdmin
```

### **4. Audit Access**

```bash
# GCP Secret Manager logs all access
gcloud logging read "resource.type=secretmanager.googleapis.com/Secret" \
  --limit 50 \
  --format json
```

### **5. Encrypt at Rest**

```bash
# GCP Secret Manager encrypts by default
# For local .env, use encrypted disk (LUKS, FileVault, BitLocker)
```

---

## 📋 Credential Checklist

### **Local Development**

- [ ] Create `.env` file
- [ ] Add to `.gitignore`
- [ ] Get Label Studio token
- [ ] Get Grafana token
- [ ] Get Hugging Face token
- [ ] Install `python-dotenv`
- [ ] Test loading secrets in Python

### **Production (GCP)**

- [ ] Create GCP project
- [ ] Enable Secret Manager API
- [ ] Create service account
- [ ] Grant Secret Manager access
- [ ] Create secrets (Label Studio, Grafana, HF, etc.)
- [ ] Download service account key
- [ ] Install `google-cloud-secret-manager`
- [ ] Test accessing secrets in Python
- [ ] Set up secret rotation schedule
- [ ] Enable audit logging

---

## 🚀 Quick Start

### **Local Development**

```bash
# 1. Copy .env.example to .env
cp .env.example .env

# 2. Get tokens
# - Label Studio: http://localhost:4015 → Account & Settings
# - Grafana: http://localhost:4020 → Configuration → API Keys
# - Hugging Face: https://huggingface.co/settings/tokens

# 3. Add tokens to .env
nano .env

# 4. Install python-dotenv
pip install python-dotenv

# 5. Test
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('LABEL_STUDIO_TOKEN'))"
```

### **Production (GCP)**

```bash
# 1. Create GCP project
gcloud projects create vllm-batch-server

# 2. Enable Secret Manager
gcloud services enable secretmanager.googleapis.com

# 3. Create secrets
echo -n "your_token" | gcloud secrets create label-studio-token --data-file=-

# 4. Create service account
gcloud iam service-accounts create vllm-batch-server

# 5. Grant access
gcloud projects add-iam-policy-binding vllm-batch-server \
  --member="serviceAccount:vllm-batch-server@vllm-batch-server.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# 6. Install SDK
pip install google-cloud-secret-manager

# 7. Test
python3 secret_manager.py
```

---

## 💡 Recommendations

### **For Your Current Setup (Local Workstation)**

1. ✅ **Use `.env` file** - simple, works great for local development
2. ✅ **Add Label Studio + Grafana tokens** - enable integrations
3. ✅ **Keep `.env` in `.gitignore`** - already done!
4. ❌ **Don't use GCP Secret Manager yet** - overkill for local-only

### **When to Move to GCP Secret Manager**

1. **Multi-user team** - need centralized secret management
2. **Production deployment** - running on GCP Compute Engine / Cloud Run
3. **Compliance requirements** - need audit logs, encryption, rotation
4. **Multiple environments** - dev, staging, prod with different secrets

### **Hybrid Approach (Best of Both Worlds)**

```python
# config.py
import os
from dotenv import load_dotenv

# Determine environment
ENV = os.getenv('ENV', 'local')

if ENV == 'production':
    # Use GCP Secret Manager
    from secret_manager import SecretManager
    sm = SecretManager()
    secrets = sm.get_all_secrets()
else:
    # Use .env file
    load_dotenv()
    secrets = {
        'label_studio_token': os.getenv('LABEL_STUDIO_TOKEN'),
        'grafana_token': os.getenv('GRAFANA_TOKEN'),
        'hf_token': os.getenv('HF_TOKEN'),
    }

# Export for use in other modules
LABEL_STUDIO_TOKEN = secrets['label_studio_token']
GRAFANA_TOKEN = secrets['grafana_token']
HF_TOKEN = secrets['hf_token']
```

---

## 📚 Resources

- **python-dotenv**: https://github.com/theskumar/python-dotenv
- **GCP Secret Manager**: https://cloud.google.com/secret-manager/docs
- **Label Studio API**: https://labelstud.io/guide/api
- **Grafana API**: https://grafana.com/docs/grafana/latest/developers/http_api/

