# vLLM Batch Server - Correct Architecture

**Date**: 2025-11-05  
**Status**: Architecture Design (Starting from Scratch)

---

## 🎯 **CORE PRINCIPLE**

> **The OSS project should be feature-complete and valuable on its own.**  
> **Aris is an extension that adds domain-specific features, not a replacement.**

---

## 📦 **TWO-LAYER ARCHITECTURE**

### **Layer 1: Core (OSS) - Feature-Complete Batch Processing Platform**

**What it does:**
- Accept batch inference requests (OpenAI-compatible API)
- Process batches with vLLM (model hot-swapping, GPU optimization)
- Store results in PostgreSQL
- Provide web UI for model management, dataset curation, fine-tuning
- Export curated datasets for training
- Fine-tune models with Unsloth
- Deploy fine-tuned models back to vLLM
- Plugin system for extensibility

**Who uses it:**
- Anyone who wants to run batch inference on local GPUs
- Researchers curating training datasets
- Teams fine-tuning models for specific tasks
- Companies building AI applications on consumer hardware

**Key Features:**
1. **Model Management** (port 8001)
   - Install models from HuggingFace (paste URL)
   - Test models with sample prompts
   - View benchmark results
   - Delete models

2. **Dataset Workbench** (port 8001)
   - Upload JSONL datasets
   - Run multiple models on same dataset
   - View results side-by-side
   - Mark high-quality examples (gold stars)
   - Export curated datasets

3. **Fine-Tuning System** (port 8001)
   - Export gold star examples
   - Fine-tune with Unsloth (LoRA, QLoRA)
   - Track training progress
   - Deploy fine-tuned models
   - Serve fine-tuned models via vLLM

4. **Label Studio Integration**
   - Auto-export results to Label Studio
   - Annotate and curate data
   - Sync annotations back to batch server
   - Export annotated datasets

5. **Monitoring & Metrics**
   - Live batch progress (WebSocket)
   - GPU utilization
   - Cost tracking
   - Throughput metrics

---

### **Layer 2: Aris Integration - Domain-Specific Extensions**

**What it adds:**
- Conquest schemas (candidate evaluation, CV parsing, etc.)
- Aristotle database integration
- Bidirectional sync (VICTORY ↔ Gold Star)
- Eidos ICL integration
- Conquest-specific UI

**Who uses it:**
- Aris production system only

**Key Features:**
1. **Conquest Processing**
   - Accept conquests from Aristotle web app
   - Parse conquest metadata
   - Route to appropriate schema handlers

2. **Bidirectional Sync**
   - Aristotle VICTORY → Label Studio Gold Star
   - Label Studio Gold Star → Aristotle VICTORY
   - Automatic sync via webhooks

3. **Eidos Integration**
   - Export gold star conquests to Eidos
   - Format for in-context learning
   - Track which examples are used

4. **Conquest Viewer UI**
   - View conquests by type
   - See candidate information
   - Mark as VICTORY
   - Edit and improve responses

---

## 🏗️ **DIRECTORY STRUCTURE**

```
vllm-batch-server/
├── core/                           # OSS - Feature-complete platform
│   ├── batch_app/                  # Batch processing engine
│   │   ├── api_server.py           # OpenAI-compatible API (port 4080)
│   │   ├── worker.py               # vLLM batch processor
│   │   ├── database.py             # Generic database schema
│   │   ├── fine_tuning.py          # Fine-tuning endpoints
│   │   └── static/                 # Admin UI (queue, logs, config)
│   │
│   ├── curation/                   # Curation web app (port 8001)
│   │   ├── api.py                  # Curation API server
│   │   ├── dataset_manager.py      # Upload/manage datasets
│   │   ├── model_installer.py      # Install models from HuggingFace
│   │   ├── annotation_sync.py      # Sync with Label Studio
│   │   └── schemas.py              # Generic schemas
│   │
│   ├── training/                   # Fine-tuning system
│   │   ├── base.py                 # Training interfaces
│   │   ├── dataset_exporter.py     # Export curated data
│   │   ├── unsloth_backend.py      # Unsloth integration
│   │   └── metrics.py              # Training metrics
│   │
│   ├── result_handlers/            # Plugin system
│   │   ├── base.py                 # ResultHandler interface
│   │   ├── label_studio.py         # Generic Label Studio handler
│   │   ├── webhook.py              # Generic webhook handler
│   │   └── database_sync.py        # Generic DB sync handler
│   │
│   └── config.py                   # Core configuration
│
├── static/                         # OSS web UI (port 8001)
│   ├── index.html                  # Landing page
│   ├── model-management.html       # Install/test models
│   ├── workbench.html              # Dataset curation
│   ├── model-comparison.html       # Compare model results
│   ├── fine-tuning.html            # Fine-tuning dashboard
│   ├── js/                         # Frontend JavaScript
│   └── css/                        # Styles
│
├── integrations/aris/              # Aris-specific extensions
│   ├── config_aris.py              # Aris configuration
│   ├── aristotle_db.py             # Aristotle database models
│   ├── conquest_api.py             # Conquest endpoints
│   │
│   ├── conquest_schemas/           # Conquest type definitions
│   │   ├── candidate_evaluation.json
│   │   ├── cv_parsing.json
│   │   └── ...
│   │
│   ├── result_handlers/            # Aris result handlers
│   │   ├── aristotle_sync.py       # Sync to Aristotle DB
│   │   ├── conquest_metadata.py    # Parse conquest data
│   │   └── eidos_export.py         # Export to Eidos
│   │
│   ├── curation_app/               # Aris curation extensions
│   │   ├── conquest_viewer.py      # Conquest-specific UI logic
│   │   └── bidirectional_sync.py   # VICTORY ↔ Gold Star sync
│   │
│   └── static/                     # Aris-specific UI
│       └── conquest-viewer.html    # Conquest viewer
│
├── docs/                           # Documentation
├── examples/                       # Example code
├── scripts/                        # Deployment scripts
└── tests/                          # Tests
```

---

## 🔌 **PLUGIN SYSTEM - THE BRIDGE**

### **How Aris Extends Core**

**1. Result Handlers**
```python
# integrations/aris/result_handlers/aristotle_sync.py
from core.result_handlers.base import ResultHandler

class AristotleGoldStarHandler(ResultHandler):
    """Syncs gold stars to Aristotle database."""
    
    def name(self) -> str:
        return "aristotle_gold_star"
    
    def enabled(self) -> bool:
        return os.getenv("ENABLE_ARISTOTLE_SYNC") == "true"
    
    def handle(self, batch_id: str, results: list, metadata: dict) -> bool:
        # Extract conquest data
        conquest_id = metadata.get('conquest_id')
        if not conquest_id:
            return True  # Not a conquest, skip
        
        # Sync to Aristotle
        sync_gold_star_to_aristotle(
            conquest_id=conquest_id,
            philosopher=metadata.get('philosopher'),
            domain=metadata.get('domain'),
            ...
        )
        return True
```

**2. API Extensions**
```python
# integrations/aris/conquest_api.py
from fastapi import APIRouter

router = APIRouter(prefix="/v1/conquests", tags=["conquests"])

@router.post("/sync/victory-to-gold-star")
async def sync_victory_to_gold_star(request: VictoryRequest):
    """Sync VICTORY conquest to Label Studio gold star."""
    # Find task in Label Studio
    # Update metadata
    # Return success
    ...

# In core/batch_app/api_server.py:
# if os.getenv("ENABLE_ARIS_INTEGRATION") == "true":
#     from integrations.aris.conquest_api import router as conquest_router
#     app.include_router(conquest_router)
```

**3. UI Extensions**
```python
# integrations/aris/curation_app/conquest_viewer.py
from core.curation.api import app as core_app
from fastapi import APIRouter

router = APIRouter(prefix="/api/conquests", tags=["conquests"])

@router.get("/by-type/{conquest_type}")
async def get_conquests_by_type(conquest_type: str):
    """Get conquests filtered by type."""
    ...

# Mount Aris routes
core_app.include_router(router)
```

---

## 🔄 **DATA FLOWS**

### **OSS Flow (Generic)**
```
1. User uploads dataset (JSONL) via web UI (port 8001)
2. User selects models to run
3. Batch API (port 4080) processes requests
4. Worker runs vLLM inference
5. Results stored in PostgreSQL
6. Results auto-exported to Label Studio
7. User views results in web UI
8. User marks high-quality examples (gold stars)
9. User exports curated dataset
10. User fine-tunes model with Unsloth
11. User deploys fine-tuned model to vLLM
```

### **Aris Flow (Extended)**
```
1. Aristotle web app creates conquest
2. Conquest sent to Batch API (port 4080)
3. Aris result handler parses conquest metadata
4. Worker runs vLLM inference
5. Results stored in PostgreSQL
6. Aris result handler syncs to Label Studio
7. User views conquest in Conquest Viewer UI
8. User marks as VICTORY in Aristotle
9. Webhook triggers: VICTORY → Gold Star sync
10. Gold star marked in Label Studio
11. Aris result handler exports to Eidos
12. Eidos uses gold star for in-context learning
```

---

## 🎯 **IMPLEMENTATION PLAN**

### **Phase 1: Core OSS (Feature-Complete)**
1. ✅ Batch API (port 4080) - Already working
2. ✅ Worker with vLLM - Already working
3. ✅ PostgreSQL database - Already working
4. ✅ Result handler plugin system - Already working
5. **TODO**: Curation API (port 8001) - Needs to be generic
6. **TODO**: Model management UI - Move from static/ to core
7. **TODO**: Fine-tuning system - Make generic
8. **TODO**: Label Studio integration - Make generic

### **Phase 2: Aris Integration (Extensions)**
1. **TODO**: Conquest result handlers
2. **TODO**: Aristotle database sync
3. **TODO**: Bidirectional sync endpoints
4. **TODO**: Conquest viewer UI
5. **TODO**: Eidos export handler

### **Phase 3: Testing & Documentation**
1. **TODO**: Test OSS standalone
2. **TODO**: Test Aris extended
3. **TODO**: Update documentation
4. **TODO**: Create examples

---

## ✅ **SUCCESS CRITERIA**

### **OSS Project**
- [ ] Can install and run without any Aris dependencies
- [ ] Web UI on port 8001 works standalone
- [ ] Can install models from HuggingFace
- [ ] Can upload datasets and run inference
- [ ] Can mark gold stars and export datasets
- [ ] Can fine-tune models with Unsloth
- [ ] Can deploy fine-tuned models
- [ ] Documentation is clear for OSS users

### **Aris Integration**
- [ ] All Aris features work when enabled
- [ ] Bidirectional sync works (VICTORY ↔ Gold Star)
- [ ] Conquest viewer UI works
- [ ] Eidos integration works
- [ ] Can disable Aris features with env vars
- [ ] Aris code is cleanly separated in integrations/

---

**Next Steps**: Implement Phase 1 - Core OSS

