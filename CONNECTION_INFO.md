# 🔗 Connection Information for Lead Engineer

**Date:** 2025-11-01  
**Server:** RTX 4080 @ 10.0.0.223

---

## ✅ Both Services Are UP and Running

### **vLLM Batch Server**
```
✅ Status: Running
✅ API Port: 4080
✅ Docs Port: 4081
✅ Worker: Active (processing jobs)
✅ GPU: 87% utilized
```

### **Label Studio**
```
✅ Status: Running
✅ Port: 4115
✅ Health: {"status": "UP"}
✅ Token: Configured
```

---

## 🌐 Connection URLs

### **From Remote Machine (10.0.0.185)**

**vLLM Batch API:**
```
http://10.0.0.223:4080
```

**Label Studio:**
```
http://10.0.0.223:4115
```

**Health Checks:**
```bash
# Test vLLM API
curl http://10.0.0.223:4080/health

# Test Label Studio
curl http://10.0.0.223:4115/health/
```

---

### **From Local Machine (10.0.0.223)**

**vLLM Batch API:**
```
http://localhost:4080
```

**Label Studio:**
```
http://localhost:4115
```

---

## 📝 Example Code (Python)

```python
from openai import OpenAI

# Connect to vLLM Batch Server
client = OpenAI(
    base_url="http://10.0.0.223:4080/v1",  # ← Use this URL
    api_key="not-needed"
)

# Upload file
with open("batch_input.jsonl", "rb") as f:
    file = client.files.create(file=f, purpose="batch")

# Create batch job
batch = client.batches.create(
    input_file_id=file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h"
)

print(f"Batch ID: {batch.id}")
```

---

## 🔧 Available Models

```
✅ meta-llama/Llama-3.2-1B-Instruct
✅ meta-llama/Llama-3.2-3B-Instruct
✅ google/gemma-3-4b-it
✅ Qwen/Qwen3-4B-Instruct-2507
```

---

## 📊 Current Status

**Active Batches:**
```
batch_a2afa4cbe2394ec2 - validating
batch_8976e3171ac74157 - completed
batch_bb40d2afce0e491f - completed
batch_3eb07a89bc7e4ab6 - completed
```

**Worker Status:**
```
✅ Processing jobs
✅ Model loaded: Gemma 3 4B
✅ GPU Memory: 14.3 GB / 16.4 GB (87%)
✅ Temperature: 33°C
```

---

## ⚠️ Common Issues

### **Issue: Connection Refused**

**Symptom:**
```
httpcore.ConnectError: [Errno 111] Connection refused
```

**Cause:** Wrong port (8000 instead of 4080)

**Fix:**
```python
# WRONG
base_url="http://10.0.0.223:8000/v1"

# CORRECT
base_url="http://10.0.0.223:4080/v1"
```

---

### **Issue: Label Studio 401 Unauthorized**

**Symptom:**
```json
{"status_code":401,"detail":"Authentication credentials were not provided."}
```

**Cause:** Missing API token

**Fix:**
```bash
# Get token from Label Studio UI
# http://10.0.0.223:4115 → Account & Settings → Access Token

# Use in API calls
curl -H "Authorization: Token YOUR_TOKEN" \
  http://10.0.0.223:4115/api/projects
```

**Token is now configured in .env file!**

---

## 🚀 Quick Test

```bash
# From remote machine (10.0.0.185)
curl http://10.0.0.223:4080/health
curl http://10.0.0.223:4115/health/

# Should both return healthy status
```

---

## 📚 Documentation

**Full API Docs:**
```
http://10.0.0.223:4081
```

**Admin Panel:**
```
http://10.0.0.223:4081/admin
```

**Grafana Monitoring:**
```
http://10.0.0.223:4220
```

---

## ✅ Summary

**Everything is working!** The lead engineer just needs to:

1. ✅ Use port **4080** (not 8000) for vLLM API
2. ✅ Use port **4115** (not 4015) for Label Studio
3. ✅ Use IP **10.0.0.223** when connecting remotely
4. ✅ Label Studio token is now configured

**Both services are healthy and ready to accept requests!**

