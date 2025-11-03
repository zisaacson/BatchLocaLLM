# API Documentation

Complete API reference for vLLM Batch Server.

## Base URL

```
http://localhost:4080/v1
```

**Note:** The API server runs on port **4080** (not 8000). For interactive API documentation, visit:
- Swagger UI: http://localhost:4080/docs
- ReDoc: http://localhost:4080/redoc

## Authentication

Optional. Set `API_KEY` in `.env` to enable authentication.

```bash
# In requests
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### Health & Status

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1234567890.123,
  "version": "0.1.0",
  "model_loaded": true,
  "active_batches": 2,
  "gpu_available": true,
  "gpu_memory_used_gb": 12.5,
  "gpu_memory_total_gb": 16.0
}
```

#### GET /readiness

Kubernetes readiness probe.

**Response:**
```json
{"status": "ready"}
```

#### GET /liveness

Kubernetes liveness probe.

**Response:**
```json
{"status": "alive"}
```

---

### Files

#### POST /v1/files

Upload a file for batch processing.

**Request:**
- Content-Type: `multipart/form-data`
- Body:
  - `file`: File to upload (JSONL format)
  - `purpose`: `"batch"` | `"batch_output"` | `"batch_error"`

**Response:**
```json
{
  "id": "file-abc123",
  "object": "file",
  "bytes": 1024,
  "created_at": 1234567890,
  "filename": "batch_input.jsonl",
  "purpose": "batch"
}
```

#### GET /v1/files/{file_id}/content

Download file content.

**Response:**
- Content-Type: `text/plain`
- Body: File content (JSONL)

---

### Batches

#### POST /v1/batches

Create a new batch job.

**Request:**
```json
{
  "input_file_id": "file-abc123",
  "endpoint": "/v1/chat/completions",
  "completion_window": "24h",
  "priority": 0,
  "metadata": {
    "description": "My batch job",
    "webhook_url": "https://myapp.com/batch-complete"
  }
}
```

**Request Fields:**
- `input_file_id` (required): ID of uploaded input file
- `endpoint` (required): API endpoint (only `/v1/chat/completions` supported)
- `completion_window` (required): Completion window (only `"24h"` supported)
- `priority` (optional): Job priority
  - `-1` = Low priority (testing/benchmarking)
  - `0` = Normal priority (default)
  - `1` = High priority (production)
- `metadata` (optional): Custom metadata
  - `webhook_url`: URL to receive completion notification (see [Webhooks](WEBHOOKS.md))

**Response:**
```json
{
  "id": "batch_xyz789",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "errors": null,
  "input_file_id": "file-abc123",
  "completion_window": "24h",
  "status": "validating",
  "output_file_id": null,
  "error_file_id": null,
  "created_at": 1234567890,
  "in_progress_at": null,
  "expires_at": null,
  "finalizing_at": null,
  "completed_at": null,
  "failed_at": null,
  "expired_at": null,
  "cancelling_at": null,
  "cancelled_at": null,
  "request_counts": {
    "total": 0,
    "completed": 0,
    "failed": 0
  },
  "metadata": {
    "description": "My batch job"
  }
}
```

#### GET /v1/batches/{batch_id}

Get batch job status.

**Response:**
```json
{
  "id": "batch_xyz789",
  "object": "batch",
  "status": "completed",
  "output_file_id": "file-output123",
  "request_counts": {
    "total": 100,
    "completed": 98,
    "failed": 2
  },
  "queue_position": 0,
  "estimated_start_time": "2025-11-02T01:30:00Z",
  "estimated_completion_time": "2025-11-02T02:00:00Z",
  ...
}
```

**Extended Fields (Queue Visibility):**
- `queue_position`: Position in queue (only for `status: "validating"`)
  - `1` = Next to process
  - `2+` = Position in queue
  - `0` = Currently processing (for `status: "in_progress"`)
- `estimated_start_time`: When job is expected to start (ISO 8601)
- `estimated_completion_time`: When job is expected to complete (ISO 8601)

**Status Values:**
- `validating` - Validating input file
- `in_progress` - Processing requests
- `completed` - All requests processed
- `failed` - Batch processing failed
- `cancelled` - Batch was cancelled
- `expired` - Batch expired (not implemented)

#### POST /v1/batches/{batch_id}/cancel

Cancel a batch job.

**Response:**
```json
{
  "id": "batch_xyz789",
  "status": "cancelled",
  "cancelled_at": 1234567890,
  ...
}
```

---

## Batch File Format

### Input File (JSONL)

Each line is a JSON object:

```jsonl
{"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "meta-llama/Llama-3.1-8B-Instruct", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 100}}
{"custom_id": "request-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "meta-llama/Llama-3.1-8B-Instruct", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 100}}
```

**Fields:**
- `custom_id` (string, required): Unique identifier for this request
- `method` (string, required): Must be `"POST"`
- `url` (string, required): Must be `"/v1/chat/completions"`
- `body` (object, required): Chat completion request body

**Body Fields:**
- `model` (string, required): Model name
- `messages` (array, required): Chat messages
- `max_tokens` (integer, optional): Maximum tokens to generate
- `temperature` (float, optional): Sampling temperature (0.0-2.0)
- `top_p` (float, optional): Nucleus sampling (0.0-1.0)
- `frequency_penalty` (float, optional): Frequency penalty (-2.0-2.0)
- `presence_penalty` (float, optional): Presence penalty (-2.0-2.0)
- `stop` (array, optional): Stop sequences
- `n` (integer, optional): Number of completions per request

### Output File (JSONL)

Each line is a JSON object:

```jsonl
{"id": "batch-abc", "custom_id": "request-1", "response": {"status_code": 200, "request_id": "req-123", "body": {"id": "chatcmpl-xyz", "object": "chat.completion", "created": 1234567890, "model": "meta-llama/Llama-3.1-8B-Instruct", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello! How can I help?"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}}}, "error": null}
```

**Fields:**
- `id` (string): Result ID
- `custom_id` (string): Matches input `custom_id`
- `response` (object, optional): Response if successful
  - `status_code` (integer): HTTP status code (200 for success)
  - `request_id` (string): Request ID
  - `body` (object): Chat completion response
- `error` (object, optional): Error if failed
  - `message` (string): Error message
  - `type` (string): Error type
  - `code` (string): Error code

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "message": "Error description",
    "type": "invalid_request_error",
    "code": "400"
  }
}
```

**Common Error Codes:**
- `400` - Bad request (invalid input)
- `404` - Resource not found
- `500` - Internal server error
- `503` - Service unavailable (model not loaded)

---

## Rate Limits

No rate limits by default. Configure in production as needed.

---

## Examples

See [examples/simple_batch.py](../examples/simple_batch.py) for a complete example using the OpenAI Python SDK.

