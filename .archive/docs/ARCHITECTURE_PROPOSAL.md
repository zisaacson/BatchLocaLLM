# 🏗️ Architecture Proposal: Core vs Integrations

## 🎯 The Problem

**Current state:** Everything is bundled together
- Core batch processing + Label Studio + webhooks + monitoring all mixed
- Can't use the system without installing everything
- Skeptics see bloat, power users see value

**Goal:** Separate concerns so:
- Skeptics get a lean, fast batch processor
- Power users get optional integrations
- Both groups are happy

---

## 📦 Proposed Structure

```
vllm-batch-server/
│
├── core/                           # CORE: Skeptic-approved minimal system
│   ├── batch_processor.py          # Pure vLLM batch processing
│   ├── api_server.py               # REST API (optional but recommended)
│   ├── worker.py                   # Job worker
│   ├── database.py                 # Job queue (PostgreSQL)
│   ├── config.py                   # Configuration
│   └── models.py                   # Data models
│
├── integrations/                   # OPTIONAL: Power user features
│   │
│   ├── monitoring/                 # Grafana + Prometheus + Loki
│   │   ├── __init__.py
│   │   ├── prometheus_exporter.py
│   │   ├── grafana_dashboards/
│   │   └── README.md
│   │
│   ├── curation/                   # Label Studio integration
│   │   ├── __init__.py
│   │   ├── label_studio_client.py
│   │   ├── curation_api.py
│   │   ├── ui/
│   │   └── README.md
│   │
│   ├── webhooks/                   # Webhook notifications
│   │   ├── __init__.py
│   │   ├── webhook_handler.py
│   │   └── README.md
│   │
│   ├── result_handlers/            # Custom result processing
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── s3_handler.py
│   │   ├── gcs_handler.py
│   │   └── README.md
│   │
│   ├── aris/                       # Private: Your specific use case
│   │   ├── conquest_schemas/
│   │   ├── curation_app/
│   │   └── README.md
│   │
│   └── examples/                   # Example integrations
│       ├── slack_notifications/
│       ├── discord_bot/
│       └── custom_metrics/
│
├── cli/                            # Command-line interface
│   └── vllm_batch.py
│
├── sdk/                            # Python SDK (future)
│   └── client.py
│
├── docker/
│   ├── docker-compose.core.yml     # Core only
│   ├── docker-compose.full.yml     # Core + all integrations
│   └── docker-compose.custom.yml   # Mix and match
│
├── docs/
│   ├── GETTING_STARTED.md          # Core system
│   ├── API.md
│   ├── INTEGRATIONS.md             # How to use integrations
│   └── CUSTOM_INTEGRATIONS.md      # How to build your own
│
└── examples/
    ├── simple_batch.py             # 80-line skeptic version
    ├── with_monitoring.py          # Core + monitoring
    └── full_stack.py               # Everything enabled
```

---

## 🎯 Core System (Skeptic-Approved)

### **What's Included**

**Minimal dependencies:**
```txt
vllm==0.11.0
fastapi>=0.115.0
uvicorn>=0.32.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
pydantic>=2.10.0
```

**Core features:**
- ✅ vLLM batch processing with chunking
- ✅ OpenAI-compatible API
- ✅ PostgreSQL job queue (durable, crash-resistant)
- ✅ Incremental saves (checkpoint every N requests)
- ✅ Model hot-swapping (for consumer GPUs)
- ✅ Sequential processing (prevent OOM)
- ✅ Basic file storage
- ✅ Job status tracking

**What's NOT included:**
- ❌ Monitoring (Grafana/Prometheus)
- ❌ Label Studio
- ❌ Webhooks
- ❌ Sentry
- ❌ Rate limiting
- ❌ Custom result handlers

### **Installation**

```bash
# Core only
pip install vllm-batch-server

# Start server
vllm-batch start

# Submit job
vllm-batch submit input.jsonl --model gemma-3-4b
```

### **What Skeptics Get**

**80-line equivalent, but with:**
- ✅ Crash recovery (PostgreSQL queue)
- ✅ Incremental saves (don't lose work)
- ✅ Model hot-swapping (RTX 4080 friendly)
- ✅ REST API (optional, can use CLI)
- ✅ Job tracking (know what's running)

**No bloat:**
- ❌ No monitoring stack
- ❌ No data curation
- ❌ No webhooks
- ❌ No error tracking

---

## 🔌 Integration System (Power Users)

### **How It Works**

**Integrations are plugins:**

```python
# core/config.py
class Settings(BaseSettings):
    # Core settings
    DATABASE_URL: str
    VLLM_MODEL: str
    
    # Integration flags (all default to False)
    ENABLE_MONITORING: bool = False
    ENABLE_CURATION: bool = False
    ENABLE_WEBHOOKS: bool = False
```

**Enable via environment:**

```bash
# .env
ENABLE_MONITORING=true
ENABLE_CURATION=true
```

**Or via pip extras:**

```bash
# Install with monitoring
pip install vllm-batch-server[monitoring]

# Install with curation
pip install vllm-batch-server[curation]

# Install everything
pip install vllm-batch-server[all]
```

### **Integration: Monitoring**

**Location:** `integrations/monitoring/`

**Dependencies:**
```txt
prometheus-client>=0.21.0
grafana (Docker)
loki (Docker)
```

**Usage:**
```bash
# Install
pip install vllm-batch-server[monitoring]

# Enable
export ENABLE_MONITORING=true

# Start with monitoring
docker compose -f docker-compose.monitoring.yml up -d
vllm-batch start
```

**What you get:**
- Grafana dashboards (port 4020)
- Prometheus metrics (port 4022)
- Loki logs (port 4021)
- GPU utilization tracking
- Throughput metrics
- Job duration histograms

---

### **Integration: Curation (Label Studio)**

**Location:** `integrations/curation/`

**Dependencies:**
```txt
label-studio (Docker)
```

**Usage:**
```bash
# Install
pip install vllm-batch-server[curation]

# Enable
export ENABLE_CURATION=true

# Start with curation
docker compose -f docker-compose.curation.yml up -d
vllm-batch start --with-curation
```

**What you get:**
- Label Studio UI (port 4015)
- Curation API (port 4082)
- Result review interface
- Training data export
- Quality scoring

---

### **Integration: Webhooks**

**Location:** `integrations/webhooks/`

**Dependencies:**
```txt
httpx>=0.28.0
```

**Usage:**
```bash
# Install (included in core, just enable)
export ENABLE_WEBHOOKS=true
export WEBHOOK_URL=https://your-app.com/batch-complete

# Start
vllm-batch start
```

**What you get:**
- POST to webhook on job completion
- Configurable retry logic
- Payload customization

---

### **Integration: Result Handlers**

**Location:** `integrations/result_handlers/`

**Purpose:** Custom post-processing of results

**Built-in handlers:**
- `S3Handler` - Upload results to S3
- `GCSHandler` - Upload to Google Cloud Storage
- `WebhookHandler` - POST to webhook
- `LabelStudioHandler` - Send to Label Studio

**Usage:**
```python
# integrations/result_handlers/custom.py
from integrations.result_handlers.base import ResultHandler

class MyCustomHandler(ResultHandler):
    def handle(self, batch_id: str, results: list, metadata: dict):
        # Your custom logic
        send_to_slack(f"Batch {batch_id} complete!")
        upload_to_s3(results)
```

**Register:**
```python
# config.py
RESULT_HANDLERS = [
    "integrations.result_handlers.s3_handler.S3Handler",
    "integrations.result_handlers.custom.MyCustomHandler",
]
```

---

## 📊 Comparison: Core vs Full

| Feature | Core | + Monitoring | + Curation | Full |
|---------|------|--------------|------------|------|
| **vLLM batch processing** | ✅ | ✅ | ✅ | ✅ |
| **OpenAI API** | ✅ | ✅ | ✅ | ✅ |
| **Job queue (PostgreSQL)** | ✅ | ✅ | ✅ | ✅ |
| **Incremental saves** | ✅ | ✅ | ✅ | ✅ |
| **Model hot-swapping** | ✅ | ✅ | ✅ | ✅ |
| **Grafana dashboards** | ❌ | ✅ | ❌ | ✅ |
| **Prometheus metrics** | ❌ | ✅ | ❌ | ✅ |
| **Label Studio** | ❌ | ❌ | ✅ | ✅ |
| **Curation UI** | ❌ | ❌ | ✅ | ✅ |
| **Webhooks** | ❌ | ❌ | ❌ | ✅ |
| **Result handlers** | ❌ | ❌ | ❌ | ✅ |
| | | | | |
| **Install time** | 2 min | 5 min | 8 min | 10 min |
| **Docker containers** | 1 | 4 | 3 | 6 |
| **Dependencies** | 6 | 8 | 8 | 12 |
| **Use case** | Simple batch | Production | Data curation | Full platform |

---

## 🎯 Migration Plan

### **Phase 1: Restructure (Now)**

1. ✅ Move monitoring to `integrations/monitoring/`
2. ✅ Move Label Studio to `integrations/curation/`
3. ✅ Move webhooks to `integrations/webhooks/`
4. ✅ Move result handlers to `integrations/result_handlers/`
5. ✅ Keep Aris in `integrations/aris/` (private)

### **Phase 2: Make Optional (v1.1)**

6. ⚠️ Add feature flags to config
7. ⚠️ Create separate docker-compose files
8. ⚠️ Update pyproject.toml with extras
9. ⚠️ Update documentation

### **Phase 3: CLI Tool (v1.2)**

10. 💡 Create `vllm-batch` CLI
11. 💡 Add `--enable-monitoring` flag
12. 💡 Add `--enable-curation` flag

---

## 📝 Updated README Structure

```markdown
# vLLM Batch Server

Process 50,000+ LLM requests on consumer GPUs with crash recovery and model hot-swapping.

## Quick Start (Core)

```bash
pip install vllm-batch-server
vllm-batch submit input.jsonl --model gemma-3-4b
```

## Optional Integrations

### Monitoring (Grafana + Prometheus)
```bash
pip install vllm-batch-server[monitoring]
```

### Data Curation (Label Studio)
```bash
pip install vllm-batch-server[curation]
```

### Everything
```bash
pip install vllm-batch-server[all]
```

## When to Use What

**Core only:** Simple batch processing, one-off jobs  
**+ Monitoring:** Long-running jobs, production use  
**+ Curation:** Building training datasets, quality review  
**Full:** Complete platform for LLM operations
```

---

## ✅ Benefits

### **For Skeptics**
- ✅ Lean core (6 dependencies)
- ✅ Fast install (2 minutes)
- ✅ No bloat
- ✅ Still get crash recovery + incremental saves
- ✅ Can upgrade later if needed

### **For Power Users**
- ✅ All features available
- ✅ Mix and match integrations
- ✅ Build custom integrations
- ✅ Production-grade monitoring
- ✅ Data curation built-in

### **For You (Aris)**
- ✅ Keep everything you built
- ✅ Clean separation of concerns
- ✅ Easy to maintain
- ✅ Easy to extend
- ✅ Better for open source

---

## 🎓 Key Insight

**The skeptic was right about ONE thing:**

> "Most people just need simple batch processing"

**But you were ALSO right:**

> "Some people need production features"

**Solution:** Make it modular. Everyone wins.

---

**Next step:** Should I start restructuring the codebase to match this architecture?

