# 🏗️ Open Source Architecture Plan

## 🎯 Goal
Create a clean, extensible open source version that:
1. ✅ Showcases our innovation (chunking, monitoring, production-ready)
2. ✅ Provides value to general users (not just Aris-specific)
3. ✅ Impresses Parasail team (complementary, not competitive)
4. ✅ Demonstrates AI-assisted development quality

---

## 📊 New Repo vs Feature Branch?

**Decision: NEW REPO** ✅

**Reasons:**
1. Clean slate (no internal commit history)
2. Different audience (general public vs internal)
3. Separate branding (open source vs internal)
4. Easier maintenance (cherry-pick features)
5. Better optics (polished, professional)

**Repo Name:** `vllm-batch-server`  
**GitHub:** `parasail-ai/vllm-batch-server` (if they want to host it) OR `your-org/vllm-batch-server`

---

## 🔧 Core Architecture

### **What vLLM Actually Requires (Correcting Misconception)**

**NOT TRUE:** "vLLM requires 24GB VRAM"

**ACTUALLY TRUE:**
- vLLM VRAM = Model size + KV cache + overhead
- Llama 3.1 8B (FP16) = ~16GB
- Gemma 3 4B (FP16) = ~8GB
- **Problem**: Large batches cause OOM even with small models

**OUR INNOVATION:**
- ✅ Intelligent chunking (5K requests per chunk)
- ✅ Dynamic memory management
- ✅ Incremental saves (resume from crashes)
- ✅ GPU health monitoring

**VALUE PROP (CORRECTED):**
> "Process large batches (50K+ requests) on consumer GPUs without OOM crashes"

---

## 🧩 Component Breakdown

### **TIER 1: Core (Always Included)** ✅

```
batch_app/
├── api_server.py          # OpenAI-compatible Batch API
├── worker.py              # vLLM worker with chunking
├── database.py            # PostgreSQL job queue
├── webhooks.py            # Webhook callbacks
└── gpu_monitor.py         # GPU health checks
```

**Features:**
- OpenAI Batch API compatibility
- Intelligent chunking (5K per chunk)
- Incremental saves
- Webhook notifications
- GPU health monitoring
- PostgreSQL job queue

**This alone is valuable!**

---

### **TIER 2: Monitoring (Optional via Docker Profile)** ✅

```
monitoring/
├── prometheus.yml         # Metrics collection
├── grafana/              # Dashboards
└── docker-compose.monitoring.yml
```

**Usage:**
```bash
# Without monitoring
docker-compose up

# With monitoring
docker-compose --profile monitoring up
```

**Why optional:**
- Some users just want batch processing
- Monitoring adds complexity
- Easy to enable when needed

---

### **TIER 3: Result Handlers (Plugin System)** ✅

**This is the key innovation for abstracting Aris integration!**

```
result_handlers/
├── base.py                # Abstract base class
├── webhook.py             # Webhook handler (always enabled)
├── label_studio.py        # Label Studio auto-import (optional)
├── postgres.py            # PostgreSQL auto-insert (optional)
├── s3.py                  # S3 auto-upload (optional)
└── custom.py              # User-defined handlers
```

**Base Handler Interface:**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ResultHandler(ABC):
    """
    Base class for result handlers.
    
    Result handlers are called when a batch job completes,
    allowing you to automatically process results.
    
    Examples:
    - Import to Label Studio for curation
    - Insert into your database
    - Upload to S3
    - Send to your ML pipeline
    """
    
    @abstractmethod
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Process batch results.
        
        Args:
            batch_id: Unique batch identifier
            results: List of result objects (JSONL format)
            metadata: User-provided metadata from batch submission
            
        Returns:
            True if handled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def enabled(self) -> bool:
        """Check if this handler is enabled."""
        pass
```

**Example: Label Studio Handler**

```python
class LabelStudioHandler(ResultHandler):
    """
    Auto-import batch results to Label Studio for curation.
    
    Configuration (optional):
    - LABEL_STUDIO_URL: Label Studio server URL
    - LABEL_STUDIO_API_KEY: API key
    - LABEL_STUDIO_PROJECT_ID: Project ID
    """
    
    def enabled(self) -> bool:
        return bool(
            os.getenv('LABEL_STUDIO_URL') and
            os.getenv('LABEL_STUDIO_API_KEY')
        )
    
    def handle(self, batch_id, results, metadata):
        if not self.enabled():
            return True  # Skip if not configured
        
        # Import to Label Studio
        # ... (implementation)
        
        return True
```

**Example: Custom Handler (User-Defined)**

```python
class MyCustomHandler(ResultHandler):
    """
    Example: Insert results into your application database.
    """
    
    def enabled(self) -> bool:
        return True  # Always enabled
    
    def handle(self, batch_id, results, metadata):
        # Your custom logic here
        # Example: Insert into your database
        for result in results:
            db.insert('ml_results', {
                'batch_id': batch_id,
                'custom_id': result['custom_id'],
                'response': result['response']['body'],
                'created_at': datetime.now()
            })
        
        return True
```

**Configuration:**

```yaml
# config.yml
result_handlers:
  enabled:
    - webhook          # Always enabled (built-in)
    - label_studio     # Optional (if configured)
    - custom           # User-defined
  
  label_studio:
    url: ${LABEL_STUDIO_URL}
    api_key: ${LABEL_STUDIO_API_KEY}
    project_id: ${LABEL_STUDIO_PROJECT_ID}
```

**Why This Works:**
- ✅ Abstracts Aris integration (Label Studio is just one handler)
- ✅ Users can write custom handlers for their pipelines
- ✅ Optional (doesn't complicate simple use cases)
- ✅ Extensible (plugin architecture)
- ✅ Shows off your innovation (data pipeline integration)

---

## 🎨 What to Strip Out

### **Remove (Too Specific to Aris):**

```
❌ conquest_schemas/candidate_evaluation.json
❌ conquest_schemas/cartographer.json
❌ conquest_schemas/email_evaluation.json
   → These are YOUR business logic

❌ curation_app/conquest-specific UI
   → Too specific to your use case

❌ Aris integration docs
   → Internal documentation

❌ Internal benchmarks/results
   → Your internal data
```

### **Generalize (Make Reusable):**

```
✅ conquest_schemas/ → schemas/
   - Keep as "example schemas"
   - Show how to define custom schemas
   - Provide template for users

✅ curation_app/ → result_handlers/label_studio.py
   - Make it a plugin
   - Optional, not required
   - Generic, not conquest-specific

✅ Auto-import logic → ResultHandler plugin system
   - Extensible architecture
   - Users can write custom handlers
```

---

## 📦 Final Structure

```
vllm-batch-server/  (NEW REPO)
├── batch_app/                    # Core batch processing
│   ├── api_server.py             # OpenAI-compatible API
│   ├── worker.py                 # vLLM worker with chunking
│   ├── database.py               # PostgreSQL models
│   ├── webhooks.py               # Webhook notifications
│   └── gpu_monitor.py            # GPU health checks
│
├── result_handlers/              # Plugin system (NEW!)
│   ├── base.py                   # Abstract base class
│   ├── webhook.py                # Webhook handler (built-in)
│   ├── label_studio.py           # Label Studio (optional)
│   └── examples/
│       ├── postgres_insert.py    # Example: DB insert
│       ├── s3_upload.py          # Example: S3 upload
│       └── custom_handler.py     # Template for users
│
├── schemas/                      # Schema system (generalized)
│   ├── base_schema.json          # Schema template
│   └── examples/                 # Example schemas
│       ├── chat_completion.json  # Generic chat
│       ├── classification.json   # Generic classification
│       └── candidate_eval.json   # Your example (as demo)
│
├── monitoring/                   # Optional monitoring
│   ├── prometheus.yml
│   └── grafana/
│
├── docker/
│   ├── docker-compose.yml        # Core services
│   ├── docker-compose.monitoring.yml  # Optional monitoring
│   └── docker-compose.curation.yml    # Optional Label Studio
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/
│   ├── QUICKSTART.md             # 5-minute setup
│   ├── ARCHITECTURE.md           # System design
│   ├── API.md                    # API reference
│   ├── RESULT_HANDLERS.md        # Plugin system guide
│   ├── SCHEMAS.md                # Schema system guide
│   └── DEPLOYMENT.md             # Production deployment
│
├── examples/
│   ├── basic_batch.py            # Simple batch processing
│   ├── with_webhooks.py          # Webhook callbacks
│   ├── custom_handler.py         # Custom result handler
│   └── label_studio_integration.py  # Label Studio example
│
├── README.md                     # Main documentation
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                       # Apache 2.0
└── pyproject.toml                # Python packaging
```

---

## 🎯 Key Messages for Parasail

### **1. We Built the Server for Your Client**

```markdown
Parasail's openai-batch is an excellent CLIENT library.
We built the SERVER that it can connect to.

Your library → Our server → Local GPU processing
```

### **2. Solves Real Problems**

```markdown
Three innovations:

1. **Large Batch Processing on Consumer GPUs**
   - Process 50K+ requests without OOM
   - Intelligent chunking (5K per chunk)
   - Incremental saves (resume from crashes)

2. **Production Infrastructure**
   - GPU health monitoring
   - Webhook notifications
   - Prometheus + Grafana
   - PostgreSQL job queue

3. **Extensible Result Handling** (NEW!)
   - Plugin system for custom pipelines
   - Label Studio integration (example)
   - Users can write custom handlers
```

### **3. Expands Your Ecosystem**

```markdown
Now your users can choose:

☁️  Cloud: OpenAI/Parasail (your library → cloud API)
🏠 Self-hosted: vLLM Batch Server (your library → local server)

Same client library, different backends!
```

---

## ✅ Recommendation

**YES, include result handler plugin system!**

**Why:**
1. ✅ Abstracts Aris integration (Label Studio is just one plugin)
2. ✅ Provides value to general users (custom pipelines)
3. ✅ Shows off innovation (extensible architecture)
4. ✅ Doesn't complicate simple use cases (optional)
5. ✅ Demonstrates AI-assisted development quality

**Make it optional:**
```bash
# Basic batch processing (no handlers)
docker-compose up

# With Label Studio integration
docker-compose --profile curation up

# With custom handlers
# Users write their own plugins
```

---

## 🚀 Next Steps

1. **Create new repo** - `vllm-batch-server`
2. **Copy core components** - batch_app/, monitoring/, tests/
3. **Build plugin system** - result_handlers/ (NEW!)
4. **Generalize schemas** - schemas/examples/
5. **Write documentation** - README, QUICKSTART, ARCHITECTURE
6. **Polish examples** - Show different use cases
7. **Test thoroughly** - Make sure it works out of the box
8. **Reach out to Parasail** - Show them what we built!

---

**This is your coming-out party. Let's make it impressive!** 🎉

