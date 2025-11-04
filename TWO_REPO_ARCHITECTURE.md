# Two-Repo Architecture Plan

**Status**: 🚧 IN PROGRESS  
**Date**: 2025-11-04  
**Goal**: Split vLLM Batch Server into OSS (public) and Aris (private) repos

---

## 📋 Executive Summary

We're splitting the vLLM Batch Server into two repositories:

1. **`vllm-batch-server`** (Public OSS) - Generic batch processing system
2. **`vllm-batch-server-aris`** (Private) - Aris-specific integrations

This enables:
- ✅ Clean OSS release without proprietary code
- ✅ Keep all Aris functionality working
- ✅ Independent evolution of both repos
- ✅ Plugin architecture for extensibility

---

## 🏗️ Architecture

### **Repo 1: `vllm-batch-server` (Public OSS)**

**Purpose**: Generic vLLM batch processing server

**What it includes**:
```
vllm-batch-server/
├── core/
│   ├── batch_app/
│   │   ├── api_server.py          # Generic batch API (NO Aristotle code)
│   │   ├── worker.py               # Generic worker (NO conquest code)
│   │   ├── database.py             # Core models only
│   │   └── model_manager.py        # Model registry
│   ├── result_handlers/            # Plugin system
│   │   ├── base.py                 # ✅ DONE: Abstract base class
│   │   ├── webhook.py              # ✅ EXISTS: Generic webhook
│   │   └── label_studio.py         # ✅ EXISTS: Generic LS integration
│   └── config.py                   # Generic config (NO Aristotle vars)
├── integrations/
│   └── examples/                   # Generic examples
│       ├── simple_client.py
│       ├── webhook_receiver.py
│       ├── postgres_insert.py
│       └── s3_upload.py
├── docs/                           # Generic docs
├── tests/                          # Generic tests
├── README.md                       # OSS README
├── LICENSE                         # Apache 2.0
└── CONTRIBUTING.md                 # Contribution guide
```

**What it does NOT include**:
- ❌ `core/integrations/aristotle_db.py`
- ❌ `core/batch_app/conquest_api.py`
- ❌ Aristotle webhook handlers in `api_server.py`
- ❌ Conquest references in `worker.py`
- ❌ `integrations/aris/` directory
- ❌ Hardcoded Aristotle credentials
- ❌ Aris-specific terminology

---

### **Repo 2: `vllm-batch-server-aris` (Private)**

**Purpose**: Aris-specific integrations

**What it includes**:
```
vllm-batch-server-aris/
├── core/                           # Git submodule → vllm-batch-server
├── integrations/
│   └── aris/
│       ├── conquest_schemas/       # ✅ EXISTS: Conquest schemas
│       ├── curation_app/           # ✅ EXISTS: Curation UI
│       ├── result_handlers/        # ✅ DONE: Aris handlers
│       │   ├── __init__.py
│       │   ├── aristotle_gold_star.py
│       │   └── conquest_metadata.py
│       ├── config_aris.py          # ✅ DONE: Aris configuration
│       ├── aristotle_db.py         # Moved from core/integrations/
│       ├── conquest_api.py         # Moved from core/batch_app/
│       └── tests/                  # Aris-specific tests
├── config/
│   └── .env.aris                   # Aris-specific env vars
├── docker-compose.aris.yml         # Aris-specific Docker setup
└── README.md                       # Private repo docs
```

---

## ✅ Progress

### **Phase 1: Create Plugin System** ✅ COMPLETE

- [x] `core/result_handlers/base.py` - Already exists
- [x] `core/result_handlers/webhook.py` - Already exists
- [x] `core/result_handlers/label_studio.py` - Already exists

### **Phase 2: Create Aris Handlers** ✅ COMPLETE

- [x] `integrations/aris/result_handlers/__init__.py`
- [x] `integrations/aris/result_handlers/aristotle_gold_star.py`
- [x] `integrations/aris/result_handlers/conquest_metadata.py`
- [x] `integrations/aris/config_aris.py`

### **Phase 3: Refactor Core Code** 🚧 IN PROGRESS

Need to remove Aris-specific code from core:

#### **Files to Modify**:

1. **`core/batch_app/api_server.py`** ❌ TODO
   - Remove lines 3950-3996 (gold star sync to Aristotle)
   - Remove lines 4025-4064 (gold star update sync)
   - Remove lines 4159-4166 (Aristotle DB connection)
   - Remove lines 4221-4290 (VICTORY conquest sync endpoint)
   - Replace with generic result handler calls

2. **`core/batch_app/worker.py`** ❌ TODO
   - Remove lines 760-800 (conquest metadata extraction)
   - Replace with generic result handler registry
   - Remove hardcoded Label Studio handler instantiation
   - Use plugin system instead

3. **`core/config.py`** ❌ TODO
   - Remove ARISTOTLE_DB_* environment variables
   - Keep only generic configuration

#### **Files to Delete** (move to Aris repo):

4. **`core/integrations/aristotle_db.py`** ❌ TODO
   - Move to `integrations/aris/aristotle_db.py`

5. **`core/batch_app/conquest_api.py`** ❌ TODO
   - Move to `integrations/aris/conquest_api.py`

### **Phase 4: Update Tests** ❌ TODO

- [ ] Ensure 90 unit tests still pass
- [ ] Update integration tests to use plugin system
- [ ] Create Aris-specific tests in private repo

### **Phase 5: Type Safety** ❌ TODO

- [ ] Run `mypy --strict` on core/
- [ ] Fix all type errors
- [ ] Add type hints to plugin interfaces

### **Phase 6: Documentation** ❌ TODO

- [ ] Update README.md (remove Aris references)
- [ ] Update docs/ (genericize examples)
- [ ] Create plugin development guide
- [ ] Update CONTRIBUTING.md

### **Phase 7: Create Repos** ❌ TODO

- [ ] Create `vllm-batch-server` public repo
- [ ] Create `vllm-batch-server-aris` private repo
- [ ] Set up git submodule
- [ ] Migrate code
- [ ] Test both repos independently

---

## 🔧 Implementation Details

### **How Plugin System Works**

**1. Base Class** (in OSS repo):

```python
# core/result_handlers/base.py
from abc import ABC, abstractmethod

class ResultHandler(ABC):
    @abstractmethod
    def name(self) -> str:
        """Return handler name."""
        pass
    
    @abstractmethod
    def enabled(self, metadata: dict) -> bool:
        """Check if handler should run."""
        pass
    
    @abstractmethod
    def handle(self, batch_id: str, results: list, metadata: dict) -> bool:
        """Process batch results."""
        pass
```

**2. Generic Handler** (in OSS repo):

```python
# core/result_handlers/webhook.py
class WebhookHandler(ResultHandler):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def handle(self, batch_id: str, results: list, metadata: dict) -> bool:
        requests.post(self.webhook_url, json={
            "batch_id": batch_id,
            "results": results
        })
        return True
```

**3. Aris Handler** (in private repo):

```python
# integrations/aris/result_handlers/aristotle_gold_star.py
from core.result_handlers.base import ResultHandler
from integrations.aris.aristotle_db import sync_gold_star_to_aristotle

class AristotleGoldStarHandler(ResultHandler):
    def handle(self, batch_id: str, results: list, metadata: dict) -> bool:
        conquest_id = metadata['conquest_id']
        sync_gold_star_to_aristotle(conquest_id, ...)
        return True
```

**4. Worker Registration** (in OSS repo):

```python
# core/batch_app/worker.py
from core.result_handlers.base import get_registry

class Worker:
    def __init__(self):
        self.registry = get_registry()
    
    def process_batch(self, batch_id: str):
        # ... process batch ...
        
        # Execute all registered handlers
        self.registry.process_results(batch_id, results, metadata)
```

**5. Aris Startup** (in private repo):

```python
# startup.py
from core.result_handlers.base import get_registry
from integrations.aris.config_aris import register_aris_handlers

registry = get_registry()
register_aris_handlers(registry)  # Registers Aris handlers

# Now worker will use Aris handlers
worker = Worker()
worker.run()
```

---

## 📊 Code Changes Required

### **Deletions** (move to Aris repo):

| File | Lines | Action |
|------|-------|--------|
| `core/integrations/aristotle_db.py` | 336 | Move to Aris repo |
| `core/batch_app/conquest_api.py` | ~200 | Move to Aris repo |
| `core/batch_app/api_server.py` | ~150 | Remove Aristotle sync code |
| `core/batch_app/worker.py` | ~40 | Remove conquest metadata code |
| `core/config.py` | ~10 | Remove Aristotle env vars |

**Total**: ~736 lines to remove/move

### **Additions** (already done):

| File | Lines | Status |
|------|-------|--------|
| `integrations/aris/result_handlers/__init__.py` | 17 | ✅ DONE |
| `integrations/aris/result_handlers/aristotle_gold_star.py` | 260 | ✅ DONE |
| `integrations/aris/result_handlers/conquest_metadata.py` | 240 | ✅ DONE |
| `integrations/aris/config_aris.py` | 170 | ✅ DONE |

**Total**: ~687 lines added (in Aris repo)

---

## 🎯 Next Steps

### **Immediate** (Today):

1. ✅ Create Aris handlers (DONE)
2. ❌ Refactor `api_server.py` to remove Aristotle code
3. ❌ Refactor `worker.py` to use plugin registry
4. ❌ Update `config.py` to remove Aristotle vars
5. ❌ Run tests to ensure nothing breaks

### **Short-term** (This Week):

6. ❌ Move `aristotle_db.py` to Aris repo
7. ❌ Move `conquest_api.py` to Aris repo
8. ❌ Update all documentation
9. ❌ Run type checking (`mypy --strict`)
10. ❌ Create OSS README

### **Medium-term** (Next Week):

11. ❌ Create public `vllm-batch-server` repo
12. ❌ Create private `vllm-batch-server-aris` repo
13. ❌ Set up git submodule
14. ❌ Migrate code to both repos
15. ❌ Test both repos independently
16. ❌ Publish OSS repo

---

## 📝 Notes

- **Aris handlers are gitignored** - They won't accidentally leak to OSS
- **Plugin system is type-safe** - Uses abstract base classes
- **No breaking changes** - Aris functionality stays the same
- **Independent evolution** - OSS and Aris can evolve separately
- **Easy to sync** - Core updates can be pulled via git submodule

---

## 🔗 Related Documents

- `OSS_RELEASE_AUDIT_2025.md` - Comprehensive OSS readiness audit
- `integrations/aris/README.md` - Aris integration documentation
- `core/result_handlers/base.py` - Plugin system base class
- `CONTRIBUTING.md` - Contribution guidelines

---

**Ready to proceed with refactoring core code?**

