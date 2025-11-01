# Google Cloud Secret Manager - Complete Guide

**Project:** windows4080  
**Region:** us-central1  
**Status:** ✅ Configured and ready

---

## 📋 Current Secrets

| Secret Name | Description | Status |
|-------------|-------------|--------|
| `database-url` | PostgreSQL connection string | ✅ Uploaded |
| `huggingface-token` | HuggingFace API token | ⏳ Pending (add when you have it) |
| `openai-api-key` | OpenAI API key | ⏳ Pending (add when you have it) |
| `label-studio-token` | Label Studio access token | ⏳ Pending (add when you have it) |
| `grafana-token` | Grafana API token | ⏳ Pending (add when you have it) |
| `google-application-credentials` | GCP service account JSON | ⏳ Pending (add when you have it) |

---

## 🚀 Quick Start

### **List all secrets:**
```bash
./scripts/manage_gcp_secrets.sh list
```

### **Add a new secret:**
```bash
# From command line
./scripts/manage_gcp_secrets.sh add openai-api-key "sk-proj-xxxxx"

# From file (for service account JSON, etc.)
./scripts/manage_gcp_secrets.sh add-from-file google-credentials service-account.json
```

### **Get a secret value:**
```bash
./scripts/manage_gcp_secrets.sh get database-url
```

### **Upload all secrets from .env:**
```bash
./scripts/manage_gcp_secrets.sh upload-all
```

### **Download secrets to .env.production:**
```bash
./scripts/manage_gcp_secrets.sh download-env
```

---

## 📝 Adding Secrets

### **Method 1: Using the helper script (Recommended)**

```bash
# Add HuggingFace token
./scripts/manage_gcp_secrets.sh add huggingface-token "hf_xxxxxxxxxxxxx"

# Add OpenAI API key
./scripts/manage_gcp_secrets.sh add openai-api-key "sk-proj-xxxxxxxxxxxxx"

# Add Label Studio token
./scripts/manage_gcp_secrets.sh add label-studio-token "xxxxxxxxxxxxx"

# Add Grafana token
./scripts/manage_gcp_secrets.sh add grafana-token "xxxxxxxxxxxxx"

# Add service account JSON from file
./scripts/manage_gcp_secrets.sh add-from-file google-application-credentials service-account.json
```

### **Method 2: Using gcloud directly**

```bash
# Create a new secret
echo "my-secret-value" | gcloud secrets create my-secret-name \
    --project=windows4080 \
    --replication-policy="automatic" \
    --data-file=-

# Update existing secret (add new version)
echo "new-secret-value" | gcloud secrets versions add my-secret-name \
    --project=windows4080 \
    --data-file=-
```

### **Method 3: Update .env and upload all**

1. Edit your `.env` file and add the secret values
2. Run: `./scripts/manage_gcp_secrets.sh upload-all`

---

## 🔍 Viewing Secrets

### **List all secrets:**
```bash
gcloud secrets list --project=windows4080
```

### **Get secret value:**
```bash
gcloud secrets versions access latest --secret=database-url --project=windows4080
```

### **Get secret metadata:**
```bash
gcloud secrets describe database-url --project=windows4080
```

### **List all versions of a secret:**
```bash
gcloud secrets versions list database-url --project=windows4080
```

---

## 🗑️ Deleting Secrets

### **Using helper script:**
```bash
./scripts/manage_gcp_secrets.sh delete my-secret-name
```

### **Using gcloud:**
```bash
gcloud secrets delete my-secret-name --project=windows4080
```

---

## 🔐 Accessing Secrets in Production

### **Option 1: Using gcloud in startup script**

```bash
#!/bin/bash
# startup.sh

# Fetch secrets from Secret Manager
export DATABASE_URL=$(gcloud secrets versions access latest --secret=database-url --project=windows4080)
export HF_TOKEN=$(gcloud secrets versions access latest --secret=huggingface-token --project=windows4080)
export OPENAI_API_KEY=$(gcloud secrets versions access latest --secret=openai-api-key --project=windows4080)

# Start your application
python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080
```

### **Option 2: Using Python Secret Manager client**

```python
from google.cloud import secretmanager

def get_secret(secret_name: str, project_id: str = "windows4080") -> str:
    """Fetch secret from Google Cloud Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Usage
database_url = get_secret("database-url")
hf_token = get_secret("huggingface-token")
```

### **Option 3: Using environment variables in Cloud Run/Compute Engine**

When deploying to Cloud Run or Compute Engine, you can mount secrets as environment variables:

```bash
# Cloud Run deployment
gcloud run deploy vllm-batch-server \
    --image gcr.io/windows4080/vllm-batch-server \
    --set-secrets DATABASE_URL=database-url:latest,HF_TOKEN=huggingface-token:latest \
    --project windows4080
```

---

## 🔒 Security Best Practices

### **1. Grant minimal permissions**

Only grant access to secrets that are needed:

```bash
# Grant service account access to specific secret
gcloud secrets add-iam-policy-binding database-url \
    --member="serviceAccount:my-service@windows4080.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=windows4080
```

### **2. Use automatic replication**

All secrets are configured with automatic replication for high availability.

### **3. Rotate secrets regularly**

```bash
# Add new version (old versions are kept)
echo "new-password" | gcloud secrets versions add database-url \
    --project=windows4080 \
    --data-file=-

# Disable old version
gcloud secrets versions disable 1 --secret=database-url --project=windows4080
```

### **4. Never commit secrets to git**

- ✅ Use `.env` for local development (already in `.gitignore`)
- ✅ Use Secret Manager for production
- ❌ Never commit `.env` files with real secrets

---

## 📊 Monitoring & Auditing

### **View secret access logs:**

```bash
# View audit logs for secret access
gcloud logging read "resource.type=secretmanager.googleapis.com/Secret" \
    --project=windows4080 \
    --limit=50
```

### **Set up alerts:**

You can set up Cloud Monitoring alerts for:
- Secret access attempts
- Failed access attempts
- Secret modifications

---

## 💰 Pricing

**Secret Manager Pricing (as of 2024):**
- **Active secret versions:** $0.06 per secret version per month
- **Access operations:** $0.03 per 10,000 access operations
- **First 6 active secret versions:** FREE
- **First 10,000 access operations per month:** FREE

**Your current usage:**
- Secrets: 1 (database-url)
- Cost: **$0/month** (within free tier)

Even with all 6 secrets, you'd still be in the free tier!

---

## 🚀 Next Steps

### **1. Add your API tokens when you have them:**

```bash
# When you get your HuggingFace token
./scripts/manage_gcp_secrets.sh add huggingface-token "hf_xxxxx"

# When you get your OpenAI API key
./scripts/manage_gcp_secrets.sh add openai-api-key "sk-proj-xxxxx"

# When you set up Label Studio
./scripts/manage_gcp_secrets.sh add label-studio-token "xxxxx"

# When you set up Grafana
./scripts/manage_gcp_secrets.sh add grafana-token "xxxxx"
```

### **2. Create a service account for production:**

```bash
# Create service account
gcloud iam service-accounts create vllm-batch-server \
    --display-name="vLLM Batch Server" \
    --project=windows4080

# Grant secret access
gcloud projects add-iam-policy-binding windows4080 \
    --member="serviceAccount:vllm-batch-server@windows4080.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Create key (download JSON)
gcloud iam service-accounts keys create service-account.json \
    --iam-account=vllm-batch-server@windows4080.iam.gserviceaccount.com \
    --project=windows4080
```

### **3. Update your production deployment to use secrets:**

See the "Accessing Secrets in Production" section above.

---

## 📚 Resources

- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Secret Manager Pricing](https://cloud.google.com/secret-manager/pricing)
- [Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [Python Client Library](https://cloud.google.com/python/docs/reference/secretmanager/latest)

---

## ✅ Summary

**What's Done:**
- ✅ Secret Manager API enabled
- ✅ `database-url` secret uploaded
- ✅ Helper scripts created (`manage_gcp_secrets.sh`, `upload_secrets_to_gcp.sh`)
- ✅ Project configured: windows4080

**What's Next:**
- ⏳ Add remaining secrets when you have the tokens
- ⏳ Create service account for production
- ⏳ Update production deployment to fetch secrets

**Your secrets are now safely stored in Google Cloud Secret Manager!** 🎉

