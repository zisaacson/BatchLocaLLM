# FastAPI Integration Guide

Learn how to integrate vLLM Batch Server with your FastAPI application.

---

## 🎯 Overview

This guide shows you how to:
- Submit batch jobs from FastAPI endpoints
- Check batch status asynchronously
- Receive webhook notifications
- Handle results in your FastAPI app

---

## 🚀 Quick Start

### **1. Install Dependencies**

```bash
pip install fastapi uvicorn httpx
```

### **2. Basic Integration**

```python
# app.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import httpx
import asyncio

app = FastAPI()

# vLLM Batch Server configuration
BATCH_API_URL = "http://localhost:4080"

class BatchRequest(BaseModel):
    input_file_id: str
    model: str = "google/gemma-3-4b-it"

class BatchResponse(BaseModel):
    batch_id: str
    status: str

@app.post("/submit-batch", response_model=BatchResponse)
async def submit_batch(request: BatchRequest):
    """Submit a batch job to vLLM Batch Server"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BATCH_API_URL}/v1/batches",
            json={
                "input_file_id": request.input_file_id,
                "metadata": {"model": request.model}
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return BatchResponse(
            batch_id=data["id"],
            status=data["status"]
        )

@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Check batch job status"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BATCH_API_URL}/v1/batches/{batch_id}"
        )
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### **3. Run Your App**

```bash
python app.py
```

### **4. Test It**

```bash
# Submit a batch
curl -X POST http://localhost:8000/submit-batch \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-test-data",
    "model": "google/gemma-3-4b-it"
  }'

# Check status
curl http://localhost:8000/batch/batch_abc123
```

---

## 📚 Advanced Examples

### **Example 1: Upload File and Submit Batch**

```python
from fastapi import FastAPI, UploadFile, File
import httpx
import json

app = FastAPI()
BATCH_API_URL = "http://localhost:4080"

@app.post("/process-file")
async def process_file(file: UploadFile = File(...)):
    """Upload JSONL file and submit batch job"""
    
    # Read file content
    content = await file.read()
    
    # Upload to vLLM Batch Server
    async with httpx.AsyncClient() as client:
        # Upload file
        files = {"file": (file.filename, content, "application/jsonl")}
        upload_response = await client.post(
            f"{BATCH_API_URL}/v1/files",
            files=files,
            data={"purpose": "batch"}
        )
        upload_response.raise_for_status()
        file_id = upload_response.json()["id"]
        
        # Submit batch
        batch_response = await client.post(
            f"{BATCH_API_URL}/v1/batches",
            json={
                "input_file_id": file_id,
                "metadata": {"model": "google/gemma-3-4b-it"}
            }
        )
        batch_response.raise_for_status()
        
        return {
            "file_id": file_id,
            "batch_id": batch_response.json()["id"],
            "status": "submitted"
        }
```

### **Example 2: Webhook Receiver**

```python
from fastapi import FastAPI, Request
import hmac
import hashlib

app = FastAPI()

# Your webhook secret (set in vLLM Batch Server)
WEBHOOK_SECRET = "your-secret-key"

@app.post("/webhooks/batch-complete")
async def batch_webhook(request: Request):
    """Receive webhook notifications from vLLM Batch Server"""
    
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature")
    body = await request.body()
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return {"error": "Invalid signature"}, 401
    
    # Process webhook
    data = await request.json()
    
    if data["event"] == "batch.completed":
        batch_id = data["batch_id"]
        output_file_id = data["output_file_id"]
        
        # Download results
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BATCH_API_URL}/v1/files/{output_file_id}/content"
            )
            results = response.text
            
            # Process results
            await process_batch_results(batch_id, results)
    
    return {"status": "received"}

async def process_batch_results(batch_id: str, results: str):
    """Process completed batch results"""
    # Your custom logic here
    for line in results.strip().split("\n"):
        result = json.loads(line)
        # Store in database, send notifications, etc.
        print(f"Processed result: {result['custom_id']}")
```

### **Example 3: Background Job Polling**

```python
from fastapi import FastAPI, BackgroundTasks
import httpx
import asyncio

app = FastAPI()
BATCH_API_URL = "http://localhost:4080"

async def poll_batch_status(batch_id: str):
    """Poll batch status until complete"""
    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"{BATCH_API_URL}/v1/batches/{batch_id}"
            )
            data = response.json()
            
            if data["status"] in ["completed", "failed", "cancelled"]:
                # Process final results
                await handle_batch_completion(batch_id, data)
                break
            
            # Wait before next poll
            await asyncio.sleep(10)

async def handle_batch_completion(batch_id: str, data: dict):
    """Handle completed batch"""
    if data["status"] == "completed":
        # Download results
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BATCH_API_URL}/v1/files/{data['output_file_id']}/content"
            )
            results = response.text
            
            # Process results
            print(f"Batch {batch_id} completed with {len(results.split())} results")
    else:
        print(f"Batch {batch_id} failed: {data.get('error')}")

@app.post("/submit-and-poll")
async def submit_and_poll(
    input_file_id: str,
    background_tasks: BackgroundTasks
):
    """Submit batch and poll in background"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BATCH_API_URL}/v1/batches",
            json={
                "input_file_id": input_file_id,
                "metadata": {"model": "google/gemma-3-4b-it"}
            }
        )
        data = response.json()
        batch_id = data["id"]
    
    # Start background polling
    background_tasks.add_task(poll_batch_status, batch_id)
    
    return {"batch_id": batch_id, "status": "polling_started"}
```

---

## 🔧 Configuration

### **Environment Variables**

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    batch_api_url: str = "http://localhost:4080"
    webhook_secret: str
    default_model: str = "google/gemma-3-4b-it"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

```bash
# .env
BATCH_API_URL=http://localhost:4080
WEBHOOK_SECRET=your-secret-key
DEFAULT_MODEL=google/gemma-3-4b-it
```

---

## 🎯 Best Practices

### **1. Use Async HTTP Client**
```python
# ✅ Good - Async
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# ❌ Bad - Blocking
import requests
response = requests.get(url)  # Blocks event loop
```

### **2. Handle Errors Gracefully**
```python
from fastapi import HTTPException

try:
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
except httpx.HTTPError as e:
    raise HTTPException(status_code=500, detail=f"Batch API error: {e}")
```

### **3. Use Background Tasks for Long Operations**
```python
@app.post("/submit")
async def submit(background_tasks: BackgroundTasks):
    background_tasks.add_task(poll_batch_status, batch_id)
    return {"status": "submitted"}
```

### **4. Verify Webhook Signatures**
```python
def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

## 📖 Full Example Application

See `examples/integrations/fastapi/` for a complete FastAPI application with:
- File upload and batch submission
- Webhook receiver with signature verification
- Background job polling
- Result storage in database
- Error handling and logging

---

## 🔗 Related Documentation

- [API Reference](../../reference/api.md)
- [Webhook Events](../../reference/webhooks.md)
- [Getting Started Guide](../getting-started.md)

---

## 💡 Tips

- Use `httpx.AsyncClient` for non-blocking HTTP requests
- Implement webhook receivers for real-time notifications
- Use background tasks for long-running operations
- Always verify webhook signatures for security
- Handle errors gracefully with proper HTTP status codes

---

**Need help?** Open an issue or ask in discussions!

