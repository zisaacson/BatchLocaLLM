# Enterprise Architecture Guide - Training Data Collection System

**Date:** 2025-10-29  
**Purpose:** Scalable, durable architecture for collecting high-quality training data from candidate evaluations

---

## 🎯 **Your Use Case: Training Data Collection**

You have:
- **Main Web App (Aris)** - Evaluates 170K+ candidates for recruiting
- **vLLM Batch Server** - Processes evaluations with local LLMs
- **Goal:** Create high-quality training data from these evaluations

**Key Questions:**
1. Should we store results in the batch server?
2. Should training data be created in the web app or batch server?
3. What's the enterprise best practice?
4. How do agents know how to interact with the system?

---

## 📊 **Enterprise Architecture: Separation of Concerns**

### **Best Practice: Microservices Pattern**

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIS Web App                             │
│              (Business Logic Layer)                         │
│                                                             │
│  - Candidate management                                     │
│  - User interface                                           │
│  - Training data curation                                   │
│  - Quality control & labeling                               │
│  - Data export for fine-tuning                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP POST (submit batch)
                     │ HTTP GET (poll status)
                     │ HTTP GET (download results)
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              vLLM Batch Server (Port 4080)                  │
│              (Inference Service Layer)                      │
│                                                             │
│  - Accept batch inference requests                          │
│  - Queue management                                         │
│  - GPU resource management                                  │
│  - Run LLM inference                                        │
│  - Return raw results                                       │
│  - Store results temporarily (7-30 days)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  RTX 4080 16GB GPU                          │
│              (Compute Resource)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ **Answers to Your Questions**

### **1. Should we store results in the batch server?**

**YES - Temporarily (7-30 days)**

**Reasons:**
- ✅ **Reliability:** Results available if web app fails to download
- ✅ **Retry Logic:** Web app can re-download if needed
- ✅ **Debugging:** Audit trail for troubleshooting
- ✅ **Async Processing:** Web app doesn't need to stay connected

**Storage Strategy:**
```
batch_server/
├── data/
│   ├── batches/
│   │   ├── input/          # Original JSONL requests (7 days)
│   │   ├── output/         # Results JSONL (30 days)
│   │   └── failed/         # Failed requests (30 days)
│   └── database/
│       └── batches.db      # Job metadata (permanent)
```

**Retention Policy:**
- Input files: 7 days (can be re-submitted if needed)
- Output files: 30 days (web app should download within this window)
- Failed requests: 30 days (for debugging)
- Job metadata: Permanent (for analytics)

---

### **2. Should training data be created in web app or batch server?**

**WEB APP - Definitely!**

**Reasons:**

#### **Batch Server Should:**
- ✅ Run inference (what it's good at)
- ✅ Return raw LLM outputs
- ✅ Be stateless and reusable
- ✅ Not know about your business logic

#### **Web App Should:**
- ✅ **Curate training data** (business logic)
- ✅ **Label quality** (human-in-the-loop)
- ✅ **Filter bad examples** (quality control)
- ✅ **Add metadata** (candidate context, recruiter feedback)
- ✅ **Export for fine-tuning** (format conversion)
- ✅ **Store long-term** (permanent database)

**Why?**

1. **Separation of Concerns**
   - Batch server = inference engine (reusable)
   - Web app = business logic (specific to recruiting)

2. **Quality Control**
   - You need human review before training data is finalized
   - Web app has the UI for this
   - Batch server is headless

3. **Flexibility**
   - You might want to combine multiple LLM outputs
   - You might want to add recruiter feedback
   - You might want to filter by candidate quality
   - All of this is business logic → belongs in web app

4. **Data Governance**
   - Training data is a strategic asset
   - Should be in your main database, not inference server
   - Easier to backup, version, and audit

---

### **3. What's the enterprise best practice?**

**Pattern: Inference Service + Data Lake**

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIS Web App                             │
│                                                             │
│  1. Submit batch to inference service                       │
│  2. Poll for completion                                     │
│  3. Download raw results                                    │
│  4. Curate training data (filter, label, enrich)            │
│  5. Store in permanent database                             │
│  6. Export for fine-tuning                                  │
└─────────────────────────────────────────────────────────────┘
                     │                          │
                     │                          │
                     ↓                          ↓
┌──────────────────────────────┐  ┌──────────────────────────┐
│  vLLM Batch Server           │  │  Training Data Lake      │
│  (Temporary Storage)         │  │  (Permanent Storage)     │
│                              │  │                          │
│  - Raw inference results     │  │  - Curated examples      │
│  - 30-day retention          │  │  - Quality labels        │
│  - No business logic         │  │  - Metadata enriched     │
└──────────────────────────────┘  │  - Version controlled    │
                                  │  - Backed up             │
                                  └──────────────────────────┘
```

**Enterprise Principles:**

1. **Single Responsibility**
   - Each service does ONE thing well
   - Batch server = inference
   - Web app = business logic

2. **Loose Coupling**
   - Services communicate via HTTP API
   - Can swap batch server implementation
   - Can add more inference services

3. **Data Ownership**
   - Web app owns training data
   - Batch server owns inference results (temporarily)
   - Clear boundaries

4. **Scalability**
   - Can run multiple batch servers
   - Can run batch server on different hardware
   - Can add GPU nodes without changing web app

5. **Observability**
   - Each service has its own monitoring
   - Clear API contracts
   - Easy to debug

---

## 🔧 **Recommended Implementation**

### **Batch Server Responsibilities**

```python
# batch_app/api_server.py

@app.post("/v1/batches")
async def create_batch(file: UploadFile, model: str):
    """
    Accept batch job, run inference, return results.
    NO business logic about training data.
    """
    # 1. Validate request
    # 2. Check GPU health
    # 3. Queue job
    # 4. Return batch_id
    
@app.get("/v1/batches/{batch_id}/results")
async def get_results(batch_id: str):
    """
    Return raw LLM outputs.
    Web app decides what to do with them.
    """
    # Return JSONL with raw inference results
```

### **Web App Responsibilities**

```python
# aris_app/training_data_service.py

class TrainingDataService:
    """
    Curate high-quality training data from LLM evaluations.
    """
    
    async def create_training_data_from_batch(self, batch_id: str):
        """
        1. Download results from batch server
        2. Parse LLM outputs
        3. Filter low-quality examples
        4. Add metadata (candidate info, recruiter feedback)
        5. Store in training_data table
        6. Mark for human review
        """
        
        # Download from batch server
        results = await self.batch_client.get_results(batch_id)
        
        # Parse and filter
        for result in results:
            llm_output = result['response']['body']['choices'][0]['message']['content']
            candidate_id = result['custom_id']
            
            # Get candidate context
            candidate = await self.db.get_candidate(candidate_id)
            
            # Quality filter
            if self.is_high_quality(llm_output, candidate):
                # Store as training example
                await self.db.training_data.insert({
                    'candidate_id': candidate_id,
                    'llm_output': llm_output,
                    'candidate_context': candidate.to_dict(),
                    'model': result['model'],
                    'created_at': datetime.now(),
                    'quality_score': self.calculate_quality(llm_output),
                    'needs_review': True,  # Human-in-the-loop
                    'batch_id': batch_id
                })
    
    async def export_for_finetuning(self, min_quality: float = 0.8):
        """
        Export curated training data for fine-tuning.
        """
        examples = await self.db.training_data.find({
            'quality_score': {'$gte': min_quality},
            'needs_review': False,  # Already reviewed
            'approved': True
        })
        
        # Convert to fine-tuning format
        return self.format_for_finetuning(examples)
```

---

## 📋 **Data Flow: End-to-End**

### **Step 1: Submit Batch (Aris → Batch Server)**

```python
# In Aris web app
batch_id = await batch_client.submit_batch(
    file='candidates_170k.jsonl',
    model='google/gemma-3-4b-it'
)
```

### **Step 2: Process (Batch Server)**

```
Batch Server:
1. Queue job
2. Worker picks up job
3. Chunk into 5K pieces
4. Run vLLM inference
5. Save results incrementally
6. Mark as completed
```

### **Step 3: Download Results (Aris)**

```python
# Poll for completion
while True:
    status = await batch_client.get_status(batch_id)
    if status['status'] == 'completed':
        break
    await asyncio.sleep(10)

# Download results
results = await batch_client.get_results(batch_id)
```

### **Step 4: Curate Training Data (Aris)**

```python
# In Aris web app
await training_data_service.create_training_data_from_batch(batch_id)

# This:
# - Parses LLM outputs
# - Filters low-quality
# - Adds candidate metadata
# - Stores in permanent DB
# - Marks for human review
```

### **Step 5: Human Review (Aris UI)**

```
Recruiter reviews training examples:
- ✅ Approve good examples
- ❌ Reject bad examples
- ✏️ Edit/improve examples
- 🏷️ Add labels (positive/negative)
```

### **Step 6: Export for Fine-Tuning (Aris)**

```python
# Export approved training data
training_data = await training_data_service.export_for_finetuning(
    min_quality=0.8,
    approved_only=True
)

# Format: OpenAI fine-tuning JSONL
# {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

---

## 🌐 **Web-Based Instructions for Agents**

### **4. How do agents know how to interact?**

**Answer: OpenAPI/Swagger Documentation + Health Page**

#### **Option A: OpenAPI Spec (Recommended)**

```python
# batch_app/api_server.py

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="vLLM Batch Processing API",
    description="Enterprise-grade batch inference service for LLMs",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# Agents can access:
# http://localhost:4080/docs - Interactive API docs
# http://localhost:4080/openapi.json - Machine-readable spec
```

#### **Option B: Enhanced Health Page**

Let me create an interactive health page with API instructions...

---

## 📊 **Storage Recommendations**

### **Batch Server (Temporary)**

```yaml
Storage:
  Input Files: 7 days
  Output Files: 30 days
  Failed Requests: 30 days
  Job Metadata: Permanent (for analytics)
  
Database:
  SQLite (current) - Good for single server
  PostgreSQL (future) - Better for multi-server
  
Backup:
  Not critical (temporary data)
  Web app should download within 30 days
```

### **Web App (Permanent)**

```yaml
Training Data Storage:
  Database: PostgreSQL (ACID compliance)
  Backup: Daily (critical business asset)
  Retention: Permanent
  Version Control: Track changes to examples
  
Schema:
  training_examples:
    - id
    - candidate_id
    - llm_output
    - candidate_context (JSON)
    - quality_score
    - approved (boolean)
    - reviewed_by (user_id)
    - created_at
    - updated_at
    - batch_id (reference to batch server)
```

---

## 🚀 **Next Steps**

1. ✅ **Keep batch server simple** - Just inference
2. ✅ **Build training data service in Aris** - Business logic
3. ✅ **Add retention policy** - Auto-delete old batch results
4. ✅ **Create OpenAPI docs** - For agent integration
5. ✅ **Build human review UI** - Quality control
6. ✅ **Export pipeline** - Fine-tuning format

---

## 📝 **Summary**

**Best Practice: Separation of Concerns**

| Component | Responsibility | Storage | Retention |
|-----------|---------------|---------|-----------|
| **Batch Server** | Inference only | Temporary (30 days) | Auto-delete |
| **Web App** | Training data curation | Permanent | Forever |
| **Human Review** | Quality control | In web app | Forever |
| **Fine-Tuning Export** | Format conversion | In web app | Forever |

**This is the enterprise way:** Clean separation, clear responsibilities, scalable architecture! 🎯

