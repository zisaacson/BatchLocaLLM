# 🔧 OpenAI/Parasail Batch API Compatibility Implementation Plan

**Goal:** Make our vLLM batch server 100% compatible with OpenAI/Parasail Batch API  
**Priority:** CRITICAL - This was the entire point of the project  
**Estimated Effort:** 8-12 hours  

---

## 📋 **What We Need to Implement:**

### **1. Files API (NEW - 4 hours)**

#### **POST /v1/files**
Upload a file for batch processing.

**Request:**
```
POST /v1/files
Content-Type: multipart/form-data

file: <binary JSONL file>
purpose: "batch"
```

**Response:**
```json
{
  "id": "file-abc123",
  "object": "file",
  "bytes": 120000,
  "created_at": 1677610602,
  "filename": "mydata.jsonl",
  "purpose": "batch"
}
```

**Implementation:**
- Store uploaded files in `data/files/`
- Generate file_id: `file-{uuid}`
- Track in new `File` database table
- Return file metadata

---

#### **GET /v1/files/{file_id}**
Get file metadata.

**Response:**
```json
{
  "id": "file-abc123",
  "object": "file",
  "bytes": 120000,
  "created_at": 1677610602,
  "filename": "mydata.jsonl",
  "purpose": "batch"
}
```

---

#### **GET /v1/files/{file_id}/content**
Download file content.

**Response:**
```
Content-Type: application/x-ndjson

<JSONL file content>
```

---

#### **DELETE /v1/files/{file_id}**
Delete a file.

**Response:**
```json
{
  "id": "file-abc123",
  "object": "file.deleted",
  "deleted": true
}
```

---

#### **GET /v1/files**
List all files.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "file-abc123",
      "object": "file",
      "bytes": 120000,
      "created_at": 1677610602,
      "filename": "mydata.jsonl",
      "purpose": "batch"
    }
  ]
}
```

---

### **2. Fix Batch API (3 hours)**

#### **POST /v1/batches** (BREAKING CHANGE)

**OLD (Current - WRONG):**
```
POST /v1/batches
Content-Type: multipart/form-data

file: <binary>
model: "Qwen/Qwen2.5-3B-Instruct"
webhook_url: "https://..."
```

**NEW (OpenAI Compatible):**
```json
POST /v1/batches
Content-Type: application/json

{
  "input_file_id": "file-abc123",
  "endpoint": "/v1/chat/completions",
  "completion_window": "24h",
  "metadata": {
    "description": "My batch job"
  }
}
```

**Response (NEW):**
```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "errors": null,
  "input_file_id": "file-abc123",
  "completion_window": "24h",
  "status": "validating",
  "output_file_id": null,
  "error_file_id": null,
  "created_at": 1711471533,
  "in_progress_at": null,
  "expires_at": 1711557933,
  "finalizing_at": null,
  "completed_at": null,
  "failed_at": null,
  "expired_at": null,
  "cancelling_at": null,
  "cancelled_at": null,
  "request_counts": {
    "total": 100,
    "completed": 95,
    "failed": 5
  },
  "metadata": {
    "description": "My batch job"
  }
}
```

**Changes:**
- Accept `input_file_id` instead of direct file upload
- Add `endpoint` field (always "/v1/chat/completions")
- Add `completion_window` field (always "24h")
- Add `object` field (always "batch")
- Add `output_file_id` and `error_file_id` fields
- Add timestamp fields: `in_progress_at`, `expires_at`, `finalizing_at`, etc
- Change `metadata` from JSON string to object
- Remove `model` field (extracted from input file)

---

#### **GET /v1/batches/{batch_id}**

**Response (NEW):**
```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "errors": null,
  "input_file_id": "file-abc123",
  "completion_window": "24h",
  "status": "completed",
  "output_file_id": "file-xyz789",
  "error_file_id": "file-err456",
  "created_at": 1711471533,
  "in_progress_at": 1711471538,
  "expires_at": 1711557933,
  "finalizing_at": 1711493133,
  "completed_at": 1711493163,
  "failed_at": null,
  "expired_at": null,
  "cancelling_at": null,
  "cancelled_at": null,
  "request_counts": {
    "total": 100,
    "completed": 95,
    "failed": 5
  },
  "metadata": {}
}
```

---

#### **GET /v1/batches**
List all batches.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "batch_abc123",
      "object": "batch",
      ...
    }
  ],
  "first_id": "batch_abc123",
  "last_id": "batch_xyz789",
  "has_more": false
}
```

---

#### **POST /v1/batches/{batch_id}/cancel**
Cancel a batch.

**Response:**
```json
{
  "id": "batch_abc123",
  "object": "batch",
  "status": "cancelling",
  ...
}
```

---

### **3. Fix Status Values (1 hour)**

**OLD (Current):**
- `pending`
- `running`
- `completed`
- `failed`

**NEW (OpenAI Compatible):**
- `validating` - Checking input file format
- `failed` - Validation failed
- `in_progress` - Processing requests
- `finalizing` - Writing output file
- `completed` - Done successfully
- `failed` - Processing failed
- `expired` - Took too long (>24h)
- `cancelling` - Cancel requested
- `cancelled` - Cancelled successfully

---

### **4. Database Schema Changes (2 hours)**

#### **New Table: `files`**
```sql
CREATE TABLE files (
    file_id VARCHAR(64) PRIMARY KEY,
    object VARCHAR(32) DEFAULT 'file',
    bytes INTEGER,
    created_at DATETIME,
    filename VARCHAR(512),
    purpose VARCHAR(32),
    file_path VARCHAR(512),
    deleted BOOLEAN DEFAULT FALSE
);
```

#### **Update Table: `batch_jobs`**
```sql
ALTER TABLE batch_jobs ADD COLUMN object VARCHAR(32) DEFAULT 'batch';
ALTER TABLE batch_jobs ADD COLUMN endpoint VARCHAR(128) DEFAULT '/v1/chat/completions';
ALTER TABLE batch_jobs ADD COLUMN input_file_id VARCHAR(64);
ALTER TABLE batch_jobs ADD COLUMN output_file_id VARCHAR(64);
ALTER TABLE batch_jobs ADD COLUMN error_file_id VARCHAR(64);
ALTER TABLE batch_jobs ADD COLUMN completion_window VARCHAR(16) DEFAULT '24h';
ALTER TABLE batch_jobs ADD COLUMN in_progress_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN expires_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN finalizing_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN failed_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN expired_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN cancelling_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN cancelled_at DATETIME;
ALTER TABLE batch_jobs ADD COLUMN errors TEXT;

-- Remove old fields
ALTER TABLE batch_jobs DROP COLUMN model;  -- Extracted from input file
ALTER TABLE batch_jobs DROP COLUMN input_file;  -- Use input_file_id
ALTER TABLE batch_jobs DROP COLUMN output_file;  -- Use output_file_id
```

---

### **5. Worker Changes (2 hours)**

**Changes:**
1. Read input file using `input_file_id` from files table
2. Extract model from first request in JSONL file
3. Create output file and register as `output_file_id`
4. Create error file and register as `error_file_id`
5. Update status transitions: `validating` → `in_progress` → `finalizing` → `completed`
6. Set timestamp fields correctly

---

## 📝 **Implementation Checklist:**

### **Phase 1: Database (2 hours)**
- [ ] Create `File` model in `database.py`
- [ ] Add migration script for schema changes
- [ ] Update `BatchJob` model with new fields
- [ ] Test database migrations

### **Phase 2: Files API (4 hours)**
- [ ] Implement `POST /v1/files` endpoint
- [ ] Implement `GET /v1/files/{file_id}` endpoint
- [ ] Implement `GET /v1/files/{file_id}/content` endpoint
- [ ] Implement `DELETE /v1/files/{file_id}` endpoint
- [ ] Implement `GET /v1/files` endpoint
- [ ] Add file storage in `data/files/`
- [ ] Test all Files API endpoints

### **Phase 3: Batch API Updates (3 hours)**
- [ ] Update `POST /v1/batches` to accept JSON body with `input_file_id`
- [ ] Update response format to match OpenAI
- [ ] Update `GET /v1/batches/{batch_id}` response format
- [ ] Implement `POST /v1/batches/{batch_id}/cancel`
- [ ] Update `GET /v1/batches` list format
- [ ] Test all Batch API endpoints

### **Phase 4: Worker Updates (2 hours)**
- [ ] Update worker to read from `input_file_id`
- [ ] Extract model from input file
- [ ] Create and register output/error files
- [ ] Update status transitions
- [ ] Set all timestamp fields
- [ ] Test worker with new format

### **Phase 5: Testing (1 hour)**
- [ ] Test with OpenAI Python SDK
- [ ] Verify drop-in replacement works
- [ ] Test full workflow: upload → create → poll → download
- [ ] Test error cases

### **Phase 6: Documentation (1 hour)**
- [ ] Update README with correct API format
- [ ] Update ARIS_INTEGRATION.md
- [ ] Add OpenAI SDK examples
- [ ] Remove "custom API" warnings

---

## 🧪 **Testing with OpenAI SDK:**

```python
from openai import OpenAI

# Point to our local server
client = OpenAI(
    base_url="http://localhost:4080/v1",
    api_key="dummy-key"  # We don't have auth yet
)

# Step 1: Upload file
with open("requests.jsonl", "rb") as f:
    file = client.files.create(
        file=f,
        purpose="batch"
    )

print(f"File uploaded: {file.id}")

# Step 2: Create batch
batch = client.batches.create(
    input_file_id=file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h"
)

print(f"Batch created: {batch.id}")
print(f"Status: {batch.status}")

# Step 3: Poll for completion
import time
while batch.status not in ["completed", "failed", "expired", "cancelled"]:
    time.sleep(5)
    batch = client.batches.retrieve(batch.id)
    print(f"Status: {batch.status} - {batch.request_counts}")

# Step 4: Download results
if batch.status == "completed":
    content = client.files.content(batch.output_file_id)
    with open("results.jsonl", "wb") as f:
        f.write(content.read())
    print("Results downloaded!")
```

**This MUST work without any errors.**

---

## ⚠️ **Breaking Changes:**

### **For Existing Users:**

**OLD API (will break):**
```python
import requests
response = requests.post(
    "http://localhost:4080/v1/batches",
    files={"file": open("requests.jsonl", "rb")},
    data={"model": "Qwen/Qwen2.5-3B-Instruct"}
)
```

**NEW API (OpenAI compatible):**
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:4080/v1")

file = client.files.create(file=open("requests.jsonl", "rb"), purpose="batch")
batch = client.batches.create(input_file_id=file.id, endpoint="/v1/chat/completions", completion_window="24h")
```

---

## 🎯 **Success Criteria:**

1. ✅ OpenAI Python SDK works without modification
2. ✅ Can switch between local vLLM and Parasail by changing `base_url` only
3. ✅ All response formats match OpenAI exactly
4. ✅ All status values match OpenAI
5. ✅ Files API fully functional
6. ✅ No custom client code needed

---

**Total Estimated Time:** 12 hours  
**Priority:** CRITICAL  
**Blocking:** Everything - this was the entire goal


