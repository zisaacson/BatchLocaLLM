# Label Studio Integration Status

**Date:** 2025-11-03  
**Status:** ⚠️ **PARTIALLY CONFIGURED - NEEDS FIX**

---

## 🔍 Current Situation

Your vLLM Batch Server has **TWO different Label Studio integration systems**, and they're not properly connected:

### **System 1: Direct Integration** (Simple, Recommended)
- **Handler:** `core/result_handlers/label_studio.py`
- **Flow:** Worker → Label Studio (port 4115)
- **Status:** ✅ Code exists, ❌ Not configured

### **System 2: Curation API Middleware** (Complex, Aris-specific)
- **Handler:** `integrations/aris/curation_app/api.py`
- **Flow:** Worker → Curation API (port 8001) → Label Studio (port 4115)
- **Status:** ✅ Code exists, ❌ Server not running

---

## ❌ The Problem

The worker is configured to use **System 2** (Curation API), but:
1. The Curation API server is **not running** (port 8001 is empty)
2. The Curation API is **not in docker-compose.yml**
3. Auto-import tries to send data to `http://localhost:8001` and **fails silently**

**Result:** Batch jobs complete successfully, but **data never reaches Label Studio** for curation.

---

## ✅ The Solution

You have **two options**:

### **Option A: Simple Direct Integration** (Recommended for Open Source)
Use the built-in Label Studio handler to send data directly.

**Pros:**
- ✅ Simpler architecture
- ✅ Fewer moving parts
- ✅ Better for open source release
- ✅ No extra server needed

**Cons:**
- ❌ No conquest-specific schemas
- ❌ No custom UI templates

### **Option B: Full Curation System** (For Aris Production)
Run the Curation API middleware for advanced features.

**Pros:**
- ✅ Conquest-specific schemas
- ✅ Custom UI templates
- ✅ Advanced curation features

**Cons:**
- ❌ More complex
- ❌ Extra server to manage
- ❌ Aris-specific (not generic)

---

## 🛠️ How to Fix (Option A - Recommended)

### **Step 1: Update Environment Variables**

Edit `.env`:
```bash
# Change this:
AUTO_IMPORT_TO_CURATION=true
CURATION_API_URL=http://localhost:8001

# To this:
AUTO_IMPORT_TO_CURATION=false  # Disable Curation API
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_API_KEY=<your-token-from-label-studio>
LABEL_STUDIO_PROJECT_ID=1
```

### **Step 2: Get Label Studio API Key**

1. Open Label Studio: `http://localhost:4115`
2. Login with:
   - Username: `admin@vllm-batch.local`
   - Password: `vllm_batch_2024`
3. Go to: **Account & Settings** → **Access Token**
4. Copy the token
5. Paste it into `.env` as `LABEL_STUDIO_API_KEY`

### **Step 3: Create a Project in Label Studio**

1. Click **Create Project**
2. Name it: "vLLM Batch Results"
3. Note the project ID (usually `1` for first project)
4. Update `.env` with `LABEL_STUDIO_PROJECT_ID=1`

### **Step 4: Configure Labeling Interface**

In Label Studio project settings, add this XML:

```xml
<View>
  <Header value="Batch Result Review"/>
  
  <Text name="custom_id" value="$custom_id"/>
  <Text name="batch_id" value="$batch_id"/>
  <Text name="model" value="$model"/>
  
  <Header value="Input Messages"/>
  <Text name="input" value="$input_messages"/>
  
  <Header value="LLM Response"/>
  <TextArea name="response" value="$llm_response" editable="true"/>
  
  <Choices name="quality" toName="response" choice="single">
    <Choice value="excellent"/>
    <Choice value="good"/>
    <Choice value="needs_correction"/>
    <Choice value="poor"/>
  </Choices>
  
  <Checkbox name="gold_star" toName="response">
    <Choice value="Use for training"/>
  </Checkbox>
</View>
```

### **Step 5: Update Worker to Use Direct Handler**

The worker needs to be modified to use `LabelStudioHandler` instead of the Curation API.

**Current code** (`core/batch_app/worker.py` line 697-757):
```python
def auto_import_to_curation(self, job: BatchJob, db: Session, log_file: str | None):
    # Sends to CURATION_API_URL (port 8001) - BROKEN
    response = requests.post(
        f"{settings.CURATION_API_URL}/api/tasks/bulk-import",
        ...
    )
```

**Should be:**
```python
def auto_import_to_label_studio(self, job: BatchJob, db: Session, log_file: str | None):
    from core.result_handlers.label_studio import LabelStudioHandler
    
    handler = LabelStudioHandler(config={
        'url': settings.LABEL_STUDIO_URL,
        'api_key': settings.LABEL_STUDIO_API_KEY,
        'project_id': settings.LABEL_STUDIO_PROJECT_ID
    })
    
    # Read results and send to Label Studio
    handler.handle(job.batch_id, results, metadata)
```

### **Step 6: Restart Worker**

```bash
# If running in Docker
cd docker
docker compose restart worker

# If running locally
pkill -f "python -m core.batch_app.worker"
python -m core.batch_app.worker
```

---

## 🛠️ How to Fix (Option B - Full System)

### **Step 1: Add Curation API to Docker Compose**

Edit `docker/docker-compose.yml`:

```yaml
  curation-api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.curation
    container_name: vllm-curation-api
    restart: unless-stopped
    ports:
      - "8001:8001"
    environment:
      LABEL_STUDIO_URL: http://label-studio:8080
      LABEL_STUDIO_API_KEY: ${LABEL_STUDIO_TOKEN}
    depends_on:
      - label-studio
    networks:
      - vllm-network
```

### **Step 2: Update Dockerfile.curation**

Make sure it copies the right files:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3 \
    requests==2.31.0

# Copy application code
COPY integrations/aris/curation_app/ /app/curation_app/
COPY core/config.py /app/core/config.py
COPY static/ /app/static/

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "-m", "uvicorn", "curation_app.api:app", "--host", "0.0.0.0", "--port", "8001"]
```

### **Step 3: Start the Curation API**

```bash
cd docker
docker compose up -d curation-api
```

### **Step 4: Verify It's Working**

```bash
curl http://localhost:8001/health
# Should return: {"status": "healthy", ...}

curl http://localhost:8001/ready
# Should return: {"status": "ready", "label_studio": "connected", ...}
```

---

## 📊 Current Configuration

**From `.env`:**
```bash
LABEL_STUDIO_URL=http://localhost:4115  ✅ Correct
LABEL_STUDIO_TOKEN=eyJhbGci...  ✅ Has token
LABEL_STUDIO_PROJECT_ID=1  ✅ Has project

AUTO_IMPORT_TO_CURATION=true  ⚠️ Enabled but server not running
CURATION_API_URL=http://localhost:8001  ❌ Server doesn't exist
```

**From `core/config.py`:**
```python
LABEL_STUDIO_URL: str = "http://localhost:8080"  ❌ Wrong port (should be 4115)
AUTO_IMPORT_TO_CURATION: bool = True  ⚠️ Enabled
CURATION_API_URL: str = "http://localhost:8001"  ❌ Server doesn't exist
```

---

## 🎯 Recommendation

**For Open Source Release:** Use **Option A** (Direct Integration)
- Simpler
- Fewer dependencies
- Easier for users to understand
- Generic (not Aris-specific)

**For Your Internal Use:** Use **Option B** (Full System) if you need:
- Conquest-specific schemas
- Custom UI templates
- Advanced curation features

---

## 🧪 Testing the Integration

After fixing, test with a small batch:

```bash
# 1. Submit a test batch
curl -X POST http://localhost:4080/v1/batches \
  -F "file=@test_batch.jsonl" \
  -F "model=gemma-3-4b-it"

# 2. Wait for completion
# 3. Check Label Studio at http://localhost:4115
# 4. You should see tasks imported automatically
```

---

## 📝 Summary

**Current State:**
- ❌ Auto-import enabled but broken (sends to non-existent port 8001)
- ✅ Label Studio running and persistent (port 4115)
- ✅ Direct handler code exists
- ❌ Not actually integrated

**Next Steps:**
1. Choose Option A or Option B
2. Follow the fix steps
3. Test with a small batch
4. Verify data appears in Label Studio

**Estimated Time:** 15-30 minutes

---

**Need help deciding?** Ask yourself:
- Do you need conquest-specific schemas? → Option B
- Do you want simplicity for open source? → Option A
- Are you unsure? → Start with Option A, upgrade to B later if needed

