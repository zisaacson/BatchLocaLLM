# Implementation Plan - Correct Abstraction

**Date**: 2025-11-05  
**Goal**: Build correct two-layer architecture (Core OSS + Aris Extensions)

---

## 📋 **CURRENT STATE ANALYSIS**

### **What We Have (Good)**
✅ `core/batch_app/` - Batch processing engine (working)
✅ `core/result_handlers/` - Plugin system (working)
✅ `core/training/base.py` - Generic training interfaces
✅ `core/training/dataset_exporter.py` - Generic dataset export
✅ `static/` - Web UI files (5000+ lines, feature-rich)
✅ `integrations/aris/curation_app/api.py` - Curation API (mostly generic)
✅ `integrations/aris/static/` - Conquest-specific UI

### **What's Broken/Missing**
❌ Curation API is in `integrations/aris/` (should be in `core/`)
❌ Fine-tuning system moved to `integrations/aris/` (should be in `core/`)
❌ Unsloth backend moved to `integrations/aris/` (should be in `core/`)
❌ Static UI not connected to curation API
❌ No clear separation between generic and Aris-specific code
❌ Bidirectional sync endpoints removed from core

---

## 🎯 **IMPLEMENTATION STRATEGY**

### **Approach: Surgical Refactor**
Instead of rewriting everything, we'll:
1. Move generic code from `integrations/aris/` → `core/`
2. Keep Aris-specific code in `integrations/aris/`
3. Wire everything together with plugin system
4. Test both OSS and Aris flows

**Why this works:**
- Most code is already written and tested
- Just needs to be reorganized
- Minimizes risk of breaking things
- Can validate incrementally

---

## 📦 **PHASE 1: CORE OSS (Generic Platform)**

### **Step 1.1: Create Generic Curation API**

**Action**: Move and genericize curation API

**Files to create/modify:**
```
core/curation/
├── __init__.py          # ← UPDATE: Export CurationAPI
├── api.py               # ← CREATE: Generic curation API
├── dataset_manager.py   # ← CREATE: Upload/manage datasets
├── model_installer.py   # ← CREATE: Install models from HuggingFace
├── annotation_sync.py   # ← CREATE: Sync with Label Studio
├── schemas.py           # ← UPDATE: Generic schema system
└── registry.py          # ← UPDATE: Schema registry
```

**Source files:**
- Copy from: `integrations/aris/curation_app/api.py`
- Remove: Conquest-specific terminology
- Replace: `conquest_type` → `schema_type`
- Replace: `conquest` → `request` or `task`
- Keep: All the good generic functionality

**Changes needed:**
```python
# BEFORE (Aris-specific)
class CreateTaskRequest(BaseModel):
    conquest_type: str
    data: dict[str, Any]
    llm_prediction: dict[str, Any] | None = None

# AFTER (Generic)
class CreateTaskRequest(BaseModel):
    schema_type: str  # Generic: could be "candidate_eval", "text_classification", etc.
    data: dict[str, Any]
    llm_prediction: dict[str, Any] | None = None
```

**Endpoints to keep (generic):**
- `GET /api/schemas` - List all schemas
- `GET /api/schemas/{schema_type}` - Get schema details
- `POST /api/tasks` - Create task
- `GET /api/tasks` - List tasks
- `GET /api/tasks/{id}` - Get task details
- `POST /api/annotations` - Submit annotation
- `POST /api/tasks/{id}/gold-star` - Mark as high-quality
- `POST /api/export` - Export curated dataset

---

### **Step 1.2: Restore Fine-Tuning to Core**

**Action**: Move fine-tuning system back to core

**Files to move:**
```
integrations/aris/fine_tuning/fine_tuning.py → core/batch_app/fine_tuning.py
integrations/aris/training/unsloth_backend.py → core/training/unsloth_backend.py
integrations/aris/training/metrics.py → core/training/metrics.py
```

**Changes needed:**
```python
# In core/batch_app/fine_tuning.py
# BEFORE (Aris-specific)
philosopher: str
conquest_types: list[str]

# AFTER (Generic)
user_email: str
schema_types: list[str]  # or dataset_types
```

**Endpoints to restore in `api_server.py`:**
- `GET /v1/fine-tuning/models` - List fine-tuned models
- `POST /v1/fine-tuning/jobs` - Create training job
- `GET /v1/fine-tuning/jobs` - List training jobs
- `GET /v1/fine-tuning/jobs/{id}` - Get job status
- `POST /v1/fine-tuning/export` - Export training dataset
- `POST /v1/fine-tuning/deploy` - Deploy fine-tuned model

---

### **Step 1.3: Connect Static UI to Curation API**

**Action**: Wire static UI to generic curation API

**Files to update:**
```
static/workbench.html       # ← UPDATE: Point to curation API
static/js/workbench.js      # ← UPDATE: Use generic endpoints
static/fine-tuning.html     # ← ALREADY UPDATED (uses user_email)
static/js/fine-tuning.js    # ← ALREADY UPDATED
```

**Changes needed:**
```javascript
// In static/js/workbench.js
// BEFORE
const API_BASE = 'http://localhost:4080/admin';

// AFTER
const CURATION_API = 'http://localhost:8001/api';  // Generic curation API
const BATCH_API = 'http://localhost:4080';         // Batch processing API
```

---

### **Step 1.4: Create Landing Page**

**Action**: Create main landing page for port 8001

**File to create:**
```
static/index.html  # ← CREATE: Landing page with navigation
```

**Content:**
- Welcome message
- Links to:
  - Model Management (install models)
  - Dataset Workbench (upload & curate)
  - Model Comparison (compare results)
  - Fine-Tuning Dashboard (train models)
  - Queue Monitor (batch progress)
- Quick start guide
- Documentation links

---

## 📦 **PHASE 2: ARIS INTEGRATION (Extensions)**

### **Step 2.1: Create Aris Result Handlers**

**Action**: Implement Aris-specific result handlers

**Files to create:**
```
integrations/aris/result_handlers/
├── __init__.py                  # ← CREATE: Auto-register handlers
├── aristotle_sync.py            # ← CREATE: Sync to Aristotle DB
├── conquest_metadata.py         # ← KEEP: Parse conquest data
└── eidos_export.py              # ← CREATE: Export to Eidos
```

**Example:**
```python
# integrations/aris/result_handlers/aristotle_sync.py
from core.result_handlers.base import ResultHandler
from integrations.aris.aristotle_db import sync_gold_star_to_aristotle

class AristotleGoldStarHandler(ResultHandler):
    """Syncs gold stars to Aristotle database."""
    
    def name(self) -> str:
        return "aristotle_gold_star"
    
    def enabled(self) -> bool:
        return os.getenv("ENABLE_ARISTOTLE_SYNC") == "true"
    
    def handle(self, batch_id: str, results: list, metadata: dict) -> bool:
        # Only process if this is a conquest
        if 'conquest_id' not in metadata:
            return True  # Not a conquest, skip
        
        # Extract conquest data
        conquest_id = metadata['conquest_id']
        philosopher = metadata.get('philosopher')
        domain = metadata.get('domain')
        
        # Sync to Aristotle
        success = sync_gold_star_to_aristotle(
            conquest_id=conquest_id,
            philosopher=philosopher,
            domain=domain,
            rating=5,
            feedback=metadata.get('feedback'),
            label_studio_task_id=metadata.get('task_id')
        )
        
        return success
```

---

### **Step 2.2: Create Aris API Extensions**

**Action**: Add conquest-specific endpoints

**Files to create:**
```
integrations/aris/
├── conquest_api.py              # ← CREATE: Conquest endpoints
└── bidirectional_sync.py        # ← CREATE: VICTORY ↔ Gold Star
```

**Endpoints to add:**
```python
# integrations/aris/conquest_api.py
from fastapi import APIRouter

router = APIRouter(prefix="/v1/conquests", tags=["conquests"])

@router.post("/sync/victory-to-gold-star")
async def sync_victory_to_gold_star(request: VictoryRequest):
    """Sync VICTORY conquest from Aristotle to Label Studio gold star."""
    # Find task in Label Studio by conquest_id
    # Update task metadata: gold_star = true
    # Return success
    ...

@router.post("/sync/gold-star-to-victory")
async def sync_gold_star_to_victory(request: GoldStarRequest):
    """Sync Label Studio gold star to Aristotle VICTORY."""
    # Update Aristotle database
    # Set conquest.result = 'VICTORY'
    # Create ml_analysis_rating record
    # Return success
    ...
```

**Wire into core:**
```python
# In core/batch_app/api_server.py
# Add at the end of file:

# ============================================================================
# Aris Integration (Optional)
# ============================================================================
if os.getenv("ENABLE_ARIS_INTEGRATION") == "true":
    try:
        from integrations.aris.conquest_api import router as conquest_router
        app.include_router(conquest_router)
        logger.info("✅ Aris conquest API enabled")
    except ImportError:
        logger.warning("⚠️ Aris integration not found")
```

---

### **Step 2.3: Create Conquest Viewer Extensions**

**Action**: Extend curation UI with conquest-specific features

**Files to keep:**
```
integrations/aris/static/
├── conquest-viewer.html         # ← KEEP: Conquest-specific UI
├── conquest-curation.html       # ← KEEP: Conquest curation UI
└── js/
    ├── conquest-viewer.js       # ← KEEP
    └── curation.js              # ← KEEP
```

**Wire into curation API:**
```python
# In integrations/aris/curation_app/conquest_viewer.py
from core.curation.api import app as core_app
from fastapi import APIRouter

router = APIRouter(prefix="/api/conquests", tags=["conquests"])

@router.get("/by-type/{conquest_type}")
async def get_conquests_by_type(conquest_type: str):
    """Get conquests filtered by type (Aris-specific)."""
    ...

# Mount Aris routes
if os.getenv("ENABLE_ARIS_INTEGRATION") == "true":
    core_app.include_router(router)
```

---

## 📦 **PHASE 3: WIRING & TESTING**

### **Step 3.1: Environment Configuration**

**Action**: Create clear env var controls

**File to update:**
```
.env.example  # ← UPDATE: Add Aris flags
```

**Variables:**
```bash
# Core (always enabled)
BATCH_API_PORT=4080
CURATION_API_PORT=8001
LABEL_STUDIO_URL=http://localhost:4115

# Aris Integration (optional)
ENABLE_ARIS_INTEGRATION=false
ENABLE_ARISTOTLE_SYNC=false
ENABLE_EIDOS_EXPORT=false

# Aristotle Database (only if Aris enabled)
ARISTOTLE_DB_HOST=localhost
ARISTOTLE_DB_PORT=4002
ARISTOTLE_DB_NAME=aristotle
ARISTOTLE_DB_USER=postgres
ARISTOTLE_DB_PASSWORD=secret
```

---

### **Step 3.2: Auto-Registration**

**Action**: Auto-register Aris handlers when enabled

**File to create:**
```
integrations/aris/__init__.py  # ← CREATE: Auto-registration
```

**Content:**
```python
"""
Aris Integration for vLLM Batch Server

Automatically registers Aris-specific result handlers and API routes
when ENABLE_ARIS_INTEGRATION=true.
"""
import os
import logging

logger = logging.getLogger(__name__)

def register_aris_integration():
    """Register Aris result handlers and API extensions."""
    if os.getenv("ENABLE_ARIS_INTEGRATION") != "true":
        logger.info("Aris integration disabled")
        return
    
    logger.info("Registering Aris integration...")
    
    # Register result handlers
    from core.result_handlers import get_registry
    from .result_handlers.aristotle_sync import AristotleGoldStarHandler
    from .result_handlers.eidos_export import EidosExportHandler
    
    registry = get_registry()
    registry.register(AristotleGoldStarHandler())
    registry.register(EidosExportHandler())
    
    logger.info("✅ Aris result handlers registered")

# Auto-register on import
register_aris_integration()
```

---

### **Step 3.3: Testing**

**OSS Flow Test:**
```bash
# 1. Start core services (no Aris)
export ENABLE_ARIS_INTEGRATION=false
make start-core

# 2. Open web UI
open http://localhost:8001

# 3. Install a model
# - Go to Model Management
# - Paste HuggingFace URL
# - Click Install

# 4. Upload dataset
# - Go to Dataset Workbench
# - Upload JSONL file
# - Select models to run

# 5. View results
# - See results appear
# - Mark high-quality examples
# - Export curated dataset

# 6. Fine-tune
# - Go to Fine-Tuning Dashboard
# - Export gold stars
# - Start training job
# - Deploy fine-tuned model
```

**Aris Flow Test:**
```bash
# 1. Start with Aris enabled
export ENABLE_ARIS_INTEGRATION=true
export ENABLE_ARISTOTLE_SYNC=true
make start-all

# 2. Create conquest in Aristotle
# - Aristotle web app creates conquest
# - Sent to batch API

# 3. Process conquest
# - Worker processes with vLLM
# - Results synced to Label Studio
# - Aris handler parses conquest metadata

# 4. Mark as VICTORY
# - Mark conquest as VICTORY in Aristotle
# - Webhook triggers sync
# - Gold star created in Label Studio

# 5. Verify bidirectional sync
# - Mark gold star in Label Studio
# - Check Aristotle: conquest.result = 'VICTORY'
# - Check ml_analysis_rating: is_gold_star = true
```

---

## ✅ **SUCCESS CRITERIA**

### **Core OSS**
- [ ] Curation API runs on port 8001
- [ ] Can install models from HuggingFace
- [ ] Can upload datasets and run inference
- [ ] Can view results in web UI
- [ ] Can mark gold stars
- [ ] Can export curated datasets
- [ ] Can fine-tune with Unsloth
- [ ] Can deploy fine-tuned models
- [ ] Works without any Aris dependencies

### **Aris Integration**
- [ ] Conquest endpoints work when enabled
- [ ] Bidirectional sync works (VICTORY ↔ Gold Star)
- [ ] Aristotle database sync works
- [ ] Eidos export works
- [ ] Conquest viewer UI works
- [ ] Can disable with env vars
- [ ] Doesn't break core when disabled

---

**Next**: Start implementing Phase 1

