# Webhook Notifications

The vLLM Batch Server supports webhook notifications for batch job completion. This allows your application to receive real-time notifications when jobs complete, instead of polling for status updates.

---

## 📋 Overview

**What are webhooks?**
- HTTP POST callbacks sent when a batch job completes or fails
- Eliminates the need for polling `/v1/batches/{batch_id}` for status
- Compatible with Parasail/OpenAI batch API format

**When are webhooks sent?**
- ✅ When a job completes successfully (`status: "completed"`)
- ❌ When a job fails (`status: "failed"`)

---

## 🚀 Quick Start

### **Basic Webhook (Simple)**

```python
import requests

# Submit batch job with webhook URL in metadata
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "metadata": {
            "webhook_url": "https://myapp.com/batch-complete"
        }
    }
)

batch_id = response.json()["id"]
print(f"Batch submitted: {batch_id}")
```

### **Advanced Webhook (With Security & Configuration)**

```python
import requests

# Submit batch job with full webhook configuration
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "webhook": {
            "url": "https://myapp.com/batch-complete",
            "secret": "your_hmac_secret_key",  # For signature verification
            "max_retries": 5,  # Custom retry count (default: 3)
            "timeout": 60,  # Custom timeout in seconds (default: 30)
            "events": ["completed", "failed"]  # Subscribe to specific events
        }
    }
)

batch_id = response.json()["id"]
print(f"Batch submitted: {batch_id}")
```

### **2. Receive webhook notification**

Your webhook endpoint will receive a POST request when the job completes:

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/batch-complete", methods=["POST"])
def batch_complete():
    payload = request.json
    
    print(f"Batch {payload['id']} completed!")
    print(f"Status: {payload['status']}")
    print(f"Total requests: {payload['request_counts']['total']}")
    print(f"Completed: {payload['request_counts']['completed']}")
    print(f"Failed: {payload['request_counts']['failed']}")
    
    # Download results
    if payload['status'] == 'completed':
        output_url = f"http://localhost:4080{payload['output_file_url']}"
        # ... download and process results
    
    return {"status": "ok"}, 200
```

---

## 📦 Webhook Payload Format

The webhook payload follows the OpenAI Batch API format:

```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "status": "completed",
  "created_at": 1699564800,
  "completed_at": 1699568400,
  "request_counts": {
    "total": 100,
    "completed": 98,
    "failed": 2
  },
  "metadata": {
    "webhook_url": "https://myapp.com/batch-complete",
    "custom_field": "custom_value"
  },
  "output_file_url": "/v1/batches/batch_abc123/results",
  "error_file_url": "/v1/batches/batch_abc123/errors"
}
```

### **Fields**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Batch job ID |
| `object` | string | Always `"batch"` |
| `endpoint` | string | Always `"/v1/chat/completions"` |
| `status` | string | `"completed"` or `"failed"` |
| `created_at` | integer | Unix timestamp (seconds) |
| `completed_at` | integer | Unix timestamp (seconds) |
| `request_counts.total` | integer | Total requests in batch |
| `request_counts.completed` | integer | Successfully completed requests |
| `request_counts.failed` | integer | Failed requests |
| `metadata` | object | Custom metadata from job submission |
| `output_file_url` | string | Relative URL to download results (if completed) |
| `error_file_url` | string | Relative URL to download errors (if any failed) |

---

## 🔐 Security: HMAC Signatures

Webhooks can be signed with HMAC-SHA256 to verify authenticity and prevent tampering.

### **Enable Signatures**

```python
# Submit batch with webhook secret
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "webhook": {
            "url": "https://myapp.com/batch-complete",
            "secret": "your_secret_key_here"  # HMAC secret
        }
    }
)
```

### **Verify Signatures**

When a webhook is sent with a secret, it includes two headers:

- `X-Webhook-Signature`: HMAC-SHA256 signature (format: `sha256=<hex>`)
- `X-Webhook-Timestamp`: Unix timestamp when webhook was sent

**Python verification example:**

```python
import hmac
import hashlib
import json
from flask import Flask, request, abort

app = Flask(__name__)

WEBHOOK_SECRET = "your_secret_key_here"

@app.route("/batch-complete", methods=["POST"])
def batch_complete():
    # Get headers
    signature_header = request.headers.get("X-Webhook-Signature")
    timestamp_header = request.headers.get("X-Webhook-Timestamp")

    if not signature_header:
        abort(401, "Missing signature")

    # Get payload
    payload = request.json

    # Generate expected signature
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    # Extract received signature
    received_signature = signature_header.replace("sha256=", "")

    # Constant-time comparison
    if not hmac.compare_digest(received_signature, expected_signature):
        abort(401, "Invalid signature")

    # Verify timestamp (prevent replay attacks)
    import time
    current_time = int(time.time())
    webhook_time = int(timestamp_header)

    if abs(current_time - webhook_time) > 300:  # 5 minutes
        abort(401, "Webhook too old")

    # Process webhook
    print(f"✅ Verified webhook for batch {payload['id']}")
    return {"status": "ok"}, 200
```

---

## 🔄 Retry Logic

The webhook system includes automatic retry with exponential backoff:

- **Max retries:** 3 attempts (configurable per webhook)
- **Timeout:** 30 seconds per attempt (configurable per webhook)
- **Backoff:** 1s, 2s, 4s between retries
- **Success codes:** 200, 201, 202, 204

**Example retry sequence:**
```
Attempt 1: POST webhook → HTTP 500 → Wait 1s
Attempt 2: POST webhook → Timeout → Wait 2s
Attempt 3: POST webhook → HTTP 200 → Success ✅
```

If all retries fail, the webhook is added to the **Dead Letter Queue** for manual inspection and retry.

---

## 📬 Dead Letter Queue (DLQ)

Failed webhooks are automatically added to a Dead Letter Queue for manual inspection and retry.

### **List Failed Webhooks**

```bash
curl http://localhost:4080/v1/webhooks/dead-letter
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": 1,
      "batch_id": "batch_abc123",
      "webhook_url": "https://myapp.com/batch-complete",
      "error_message": "HTTP 500: Internal Server Error",
      "attempts": 3,
      "last_attempt_at": "2025-11-02T01:30:00Z",
      "created_at": "2025-11-02T01:25:00Z",
      "retried_at": null,
      "retry_success": null
    }
  ],
  "has_more": false,
  "total": 1
}
```

### **Retry Failed Webhook**

```bash
curl -X POST http://localhost:4080/v1/webhooks/dead-letter/1/retry
```

**Response:**
```json
{
  "id": 1,
  "batch_id": "batch_abc123",
  "retry_success": true,
  "retried_at": "2025-11-02T02:00:00Z"
}
```

### **Delete Failed Webhook**

```bash
curl -X DELETE http://localhost:4080/v1/webhooks/dead-letter/1
```

---

## 🎯 Event Filtering

Subscribe to specific webhook events instead of receiving all notifications.

### **Available Events**

- `completed` - Job completed successfully
- `failed` - Job failed
- `progress` - Progress updates (future feature)

### **Example: Only Success Notifications**

```python
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "webhook": {
            "url": "https://myapp.com/batch-complete",
            "events": ["completed"]  # Only send on success
        }
    }
)
```

### **Example: Only Failure Notifications**

```python
response = requests.post(
    "http://localhost:4080/v1/batches",
    json={
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "webhook": {
            "url": "https://myapp.com/error-handler",
            "events": ["failed"]  # Only send on failure
        }
    }
)
```

---

## 🧪 Testing Webhooks Locally

### **Option 1: Use ngrok (Recommended)**

```bash
# 1. Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# 2. Start your local webhook server
python webhook_server.py  # Listens on port 5000

# 3. Expose it with ngrok
ngrok http 5000

# 4. Use the ngrok URL in your batch job
# Example: https://abc123.ngrok.io/batch-complete
```

### **Option 2: Use webhook.site**

```bash
# 1. Go to https://webhook.site
# 2. Copy the unique URL (e.g., https://webhook.site/abc123)
# 3. Use it in your batch job metadata
# 4. View webhook payloads in the webhook.site UI
```

### **Option 3: Local testing with requestbin**

```bash
# 1. Run requestbin locally
docker run -p 8080:8080 -it --rm redthing/requestbin

# 2. Open http://localhost:8080
# 3. Create a bin and use the URL
```

---

## 📊 Webhook Status Tracking

You can check webhook delivery status in the batch job response:

```python
response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}")
job = response.json()

# Webhook fields (not in OpenAI API, custom extension)
print(f"Webhook URL: {job.get('webhook_url')}")
print(f"Webhook status: {job.get('webhook_status')}")  # "sent", "failed", or None
print(f"Webhook attempts: {job.get('webhook_attempts')}")
print(f"Webhook error: {job.get('webhook_error')}")
```

---

## 🔒 Security Best Practices

### **1. Validate webhook signatures (TODO)**

Currently, webhooks are sent without signatures. In production, you should:
- Add HMAC signatures to webhook payloads
- Verify signatures in your webhook handler
- Use a shared secret key

### **2. Use HTTPS**

Always use HTTPS URLs for webhooks in production:
```python
# ✅ Good
"webhook_url": "https://myapp.com/batch-complete"

# ❌ Bad (insecure)
"webhook_url": "http://myapp.com/batch-complete"
```

### **3. Implement idempotency**

Your webhook handler should be idempotent (safe to call multiple times):
```python
@app.route("/batch-complete", methods=["POST"])
def batch_complete():
    payload = request.json
    batch_id = payload["id"]
    
    # Check if already processed
    if already_processed(batch_id):
        return {"status": "already_processed"}, 200
    
    # Process webhook
    process_batch_results(batch_id)
    mark_as_processed(batch_id)
    
    return {"status": "ok"}, 200
```

---

## 🐛 Troubleshooting

### **Webhook not received**

1. **Check webhook URL is accessible**
   ```bash
   curl -X POST https://myapp.com/batch-complete \
     -H "Content-Type: application/json" \
     -d '{"test": "payload"}'
   ```

2. **Check webhook status in batch job**
   ```python
   response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}")
   print(response.json().get("webhook_error"))
   ```

3. **Check worker logs**
   ```bash
   tail -f logs/worker.log | grep webhook
   ```

### **Webhook timeout**

If your webhook handler is slow (>30s), the webhook will timeout. Solutions:
- Return 202 Accepted immediately, process asynchronously
- Increase timeout in `core/batch_app/webhooks.py` (not recommended)

### **Webhook retries exhausted**

If all 3 retries fail, check:
- Is your webhook endpoint returning 200/201/202/204?
- Is it timing out (>30s)?
- Is it returning an error (4xx/5xx)?

---

## 📚 Examples

### **Example: Flask webhook handler**

```python
from flask import Flask, request
import requests

app = Flask(__name__)

@app.route("/batch-complete", methods=["POST"])
def batch_complete():
    payload = request.json
    batch_id = payload["id"]
    status = payload["status"]
    
    if status == "completed":
        # Download results
        output_url = f"http://localhost:4080{payload['output_file_url']}"
        results = requests.get(output_url).text
        
        # Process results
        for line in results.strip().split("\n"):
            result = json.loads(line)
            print(f"Request {result['custom_id']}: {result['response']['body']}")
    
    elif status == "failed":
        print(f"Batch {batch_id} failed!")
    
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(port=5000)
```

### **Example: FastAPI webhook handler**

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/batch-complete")
async def batch_complete(request: Request):
    payload = await request.json()
    batch_id = payload["id"]
    
    # Process asynchronously
    import asyncio
    asyncio.create_task(process_batch_results(batch_id))
    
    # Return immediately
    return {"status": "accepted"}

async def process_batch_results(batch_id: str):
    # Download and process results
    pass
```

---

## 🔮 Future Enhancements

- [ ] HMAC signature verification
- [ ] Webhook retry configuration (max_retries, timeout)
- [ ] Webhook event filtering (only success, only failure, etc.)
- [ ] Webhook headers customization
- [ ] Webhook payload customization
- [ ] Dead letter queue for failed webhooks

---

## 📖 Related Documentation

- [API Reference](API.md) - Full API documentation
- [Getting Started](GETTING_STARTED.md) - Quick start guide
- [Batch Processing](BATCH_PROCESSING.md) - Batch job workflow

