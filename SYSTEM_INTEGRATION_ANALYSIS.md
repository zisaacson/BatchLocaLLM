# 🔍 SYSTEM INTEGRATION ANALYSIS

**Date:** November 4, 2025  
**Status:** Analyzing complete data flow architecture

---

## 🎯 **REQUIRED SYSTEM ARCHITECTURE**

### **The 7 Requirements**

1. **Aristotle Web App** → Conquests declared as VICTORY should sync to Label Studio as Gold Stars
2. **vLLM Batch Server (4080)** → OpenAI-compatible batch inference
3. **Integration Server (4081)** → Documentation and client downloads
4. **Curation Web App (8001)** → View conquests, edit responses, mark gold stars
5. **Label Studio (4115)** → Persistent annotation storage
6. **Bidirectional Sync** → Gold Stars ↔ VICTORY conquests
7. **Eidos ICL** → Gold stars available as training data for in-context learning

---

## ✅ **WHAT EXISTS (Current Implementation)**

### **1. vLLM Batch Server (Port 4080)** ✅
**Location:** `core/batch_app/api_server.py`

**Status:** ✅ COMPLETE
- OpenAI-compatible batch API
- Model hot-swapping
- Crash-resistant processing
- Webhook support
- Label Studio webhook receiver at `/v1/webhooks/label-studio`

### **2. Integration Server (Port 4081)** ✅
**Location:** `core/batch_app/static_server.py`

**Status:** ✅ COMPLETE
- Serves documentation
- Provides TypeScript client download
- Model management UI

### **3. Curation Web App (Port 8001)** ✅
**Location:** `integrations/aris/curation_app/api.py`

**Status:** ✅ COMPLETE
- FastAPI backend with Label Studio integration
- Web UI at `integrations/aris/static/conquest-curation.html`
- Endpoints for viewing conquests, marking gold stars, exporting datasets
- Schema-driven conquest rendering

**Key Endpoints:**
```
GET  /api/schemas                    # List conquest types
GET  /api/tasks?page=1&page_size=20  # List tasks
GET  /api/tasks/{id}                 # Get task details
GET  /api/stats                      # Statistics
POST /api/annotations                # Submit annotation
POST /api/tasks/{id}/gold-star       # Mark/unmark gold star
POST /api/export                     # Export gold star dataset
```

### **4. Label Studio Integration** ✅
**Location:** `core/result_handlers/label_studio.py`

**Status:** ✅ COMPLETE
- Auto-import batch results to Label Studio
- Ground truth tracking
- Accuracy calculation

### **5. Fine-Tuning System** ✅
**Location:** `core/training/dataset_exporter.py`

**Status:** ✅ COMPLETE
- Exports gold star conquests from Aristotle database
- Supports ChatML, Alpaca, OpenAI formats
- Connects to Aristotle PostgreSQL (localhost:4002)
- Queries `ml_analysis_rating` table for `is_gold_star = true`

### **6. Conquest API** ✅
**Location:** `core/batch_app/conquest_api.py`

**Status:** ✅ COMPLETE
- Read-only access to Aristotle conquest data
- Annotation sync to Label Studio
- Connects to Aristotle PostgreSQL (localhost:4002)

---

## ❌ **WHAT'S MISSING (Gaps)**

### **Gap #1: Aristotle → Label Studio Sync (VICTORY → Gold Star)**
**Problem:** When a conquest is marked as VICTORY in Aristotle, it doesn't automatically create a Gold Star in Label Studio

**Required:**
- Aristotle webhook/trigger when `conquest.result = 'VICTORY'`
- POST to vLLM batch server or curation API
- Create/update Label Studio task with `is_gold_star: true`

**Current State:** ❌ NOT IMPLEMENTED
- No webhook from Aristotle to vLLM batch server
- No automatic sync of VICTORY → Gold Star

### **Gap #2: Label Studio → Aristotle Sync (Gold Star → VICTORY)**
**Problem:** When a conquest is marked as Gold Star in Label Studio, it doesn't automatically update Aristotle

**Required:**
- Label Studio webhook to Aristotle
- Update `conquest.result = 'VICTORY'`
- Create `ml_analysis_rating` record with `is_gold_star: true`

**Current State:** ⚠️ PARTIALLY IMPLEMENTED
- Label Studio webhook receiver exists at `/v1/webhooks/label-studio` (vLLM batch server)
- But it only logs events, doesn't update Aristotle database
- Documentation claims it works (PHASE_5_WEB_UI_COMPLETE.md line 144) but code doesn't implement it

### **Gap #3: Curation Web App → Aristotle Sync**
**Problem:** When user marks gold star in curation web app (8001), it doesn't sync to Aristotle

**Required:**
- POST `/api/tasks/{id}/gold-star` should:
  1. Update Label Studio task metadata
  2. Trigger webhook to Aristotle
  3. Update `conquest.result = 'VICTORY'`
  4. Create `ml_analysis_rating` record

**Current State:** ⚠️ PARTIALLY IMPLEMENTED
- Curation API has `/api/tasks/{id}/gold-star` endpoint
- Updates Label Studio task metadata
- But doesn't trigger Aristotle update

### **Gap #4: Eidos ICL Integration**
**Problem:** Gold star data not accessible for Eidos in-context learning

**Required:**
- API endpoint to fetch gold star examples for ICL
- Format: Prompt + Response pairs
- Filter by conquest type, philosopher, domain

**Current State:** ✅ MOSTLY COMPLETE
- `DatasetExporter.fetch_gold_star_conquests()` exists
- Connects to Aristotle database
- Exports in ChatML, Alpaca, OpenAI formats
- **Missing:** REST API endpoint to fetch ICL examples on-demand

### **Gap #5: Label Studio Persistence**
**Problem:** Label Studio data needs to be persistent across restarts

**Required:**
- PostgreSQL backend for Label Studio
- Proper volume mounts in Docker

**Current State:** ✅ COMPLETE
- `docker/docker-compose.yml` has `label-studio-db` (PostgreSQL)
- Volume: `label-studio-db-data:/var/lib/postgresql/data`

---

## 🔧 **ABSTRACTION REQUIREMENTS**

### **Core vs Integration Separation**

**Core (Open Source):**
- vLLM batch server (4080)
- Model hot-swapping
- Crash-resistant processing
- Generic result handlers (webhook, Label Studio)
- Generic curation system (`core/curation/`)

**Integration (Aris-Specific):**
- Conquest schemas (`integrations/aris/conquest_schemas/`)
- Curation web app (`integrations/aris/curation_app/`)
- Aristotle database connection
- Fine-tuning dataset export from Aristotle

**Current State:** ✅ MOSTLY COMPLETE
- Core curation system exists (`core/curation/`)
- Aris integration exists (`integrations/aris/`)
- **Missing:** Clear documentation on how to create custom integrations

---

## 📋 **ACTION PLAN**

### **Priority 1: Fix Bidirectional Sync** 🔴

**Task 1.1: Implement Label Studio → Aristotle Webhook Handler**
- Location: `core/batch_app/api_server.py` (update `/v1/webhooks/label-studio`)
- When: `ANNOTATION_CREATED` with `is_gold_star: true`
- Action:
  1. Connect to Aristotle PostgreSQL
  2. Update `conquest.result = 'VICTORY'`
  3. Create `ml_analysis_rating` record with `is_gold_star: true`

**Task 1.2: Implement Aristotle → Label Studio Sync**
- Location: New endpoint in Aristotle web app
- When: `conquest.result` changes to `'VICTORY'`
- Action:
  1. POST to `/api/tasks/{conquest_id}/gold-star` (curation API)
  2. Update Label Studio task metadata

**Task 1.3: Update Curation API Gold Star Endpoint**
- Location: `integrations/aris/curation_app/api.py`
- Endpoint: `POST /api/tasks/{id}/gold-star`
- Action:
  1. Update Label Studio task
  2. POST webhook to Aristotle (if configured)
  3. Update Aristotle database directly (if no webhook)

### **Priority 2: Add Eidos ICL API** 🟡

**Task 2.1: Create ICL Examples Endpoint**
- Location: `core/batch_app/api_server.py` or `integrations/aris/curation_app/api.py`
- Endpoint: `GET /v1/icl/examples`
- Query params: `conquest_type`, `philosopher`, `domain`, `limit`
- Response: List of prompt/response pairs in ChatML format

**Task 2.2: Integrate with Eidos**
- Update Eidos to fetch ICL examples from this endpoint
- Cache examples for performance

### **Priority 3: Documentation & Abstraction** 🟢

**Task 3.1: Create Integration Guide**
- Document how to create custom integrations
- Example: Sentiment analysis integration
- Show how to use `core/curation/` abstractions

**Task 3.2: Update README**
- Clarify core vs integration separation
- Document data flow architecture
- Add diagrams

---

## 🎯 **RECOMMENDED APPROACH**

### **Option A: Full Bidirectional Sync (Recommended)**

**Pros:**
- Complete data consistency
- Real-time updates
- Best user experience

**Cons:**
- More complex implementation
- Requires Aristotle webhook support

**Implementation:**
1. Add webhook endpoint to Aristotle: `POST /api/webhooks/vllm-batch`
2. Trigger on `conquest.result` changes
3. Update Label Studio via curation API
4. Update vLLM batch server webhook handler to write to Aristotle

### **Option B: One-Way Sync (Label Studio → Aristotle)**

**Pros:**
- Simpler implementation
- No changes to Aristotle needed

**Cons:**
- Manual VICTORY marking in Aristotle doesn't sync
- Inconsistent data

**Implementation:**
1. Update `/v1/webhooks/label-studio` to write to Aristotle
2. Document that gold stars must be marked in Label Studio/Curation UI

### **Option C: Database-Level Sync**

**Pros:**
- No webhook complexity
- Guaranteed consistency

**Cons:**
- Tight coupling
- Harder to maintain

**Implementation:**
1. Curation API writes directly to Aristotle database
2. Aristotle reads from Label Studio database
3. Use database triggers for sync

---

## 💡 **RECOMMENDATION**

**Implement Option A (Full Bidirectional Sync)** for production use.

**For v1.0.0 open source release:**
- Document current state clearly
- Provide webhook examples
- Show how integrations can implement sync
- Keep core generic, make Aris integration a reference implementation

---

## 📊 **CURRENT SYSTEM DIAGRAM**

```
┌─────────────────────────────────────────────────────────────┐
│ ARISTOTLE WEB APP (Port 4000)                               │
│ - Conquests database (PostgreSQL 4002)                      │
│ - ml_analysis_rating table (gold stars)                     │
│ - conquest.result = 'VICTORY'                               │
│                                                             │
│ ❌ MISSING: Webhook to vLLM when VICTORY marked            │
└─────────────────────────────────────────────────────────────┘
                    ↓ (batch jobs)
┌─────────────────────────────────────────────────────────────┐
│ vLLM BATCH SERVER (Port 4080)                               │
│ - OpenAI-compatible batch API                               │
│ - Model hot-swapping                                        │
│ - Webhook receiver: /v1/webhooks/label-studio               │
│                                                             │
│ ⚠️  PARTIAL: Webhook logs events but doesn't update Aristotle│
└─────────────────────────────────────────────────────────────┘
                    ↓ (auto-import results)
┌─────────────────────────────────────────────────────────────┐
│ LABEL STUDIO (Port 4115)                                    │
│ - PostgreSQL backend (4118) ✅                              │
│ - Task storage                                              │
│ - Annotation storage                                        │
│                                                             │
│ ⚠️  PARTIAL: Sends webhooks but Aristotle doesn't receive  │
└─────────────────────────────────────────────────────────────┘
                    ↕ (API calls)
┌─────────────────────────────────────────────────────────────┐
│ CURATION WEB APP (Port 8001)                                │
│ - View conquests                                            │
│ - Edit responses                                            │
│ - Mark gold stars                                           │
│ - Export datasets                                           │
│                                                             │
│ ⚠️  PARTIAL: Marks gold stars but doesn't sync to Aristotle│
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ **NEXT STEPS**

1. **Decide on sync strategy** (Option A, B, or C)
2. **Implement bidirectional sync** (Priority 1)
3. **Add Eidos ICL API** (Priority 2)
4. **Update documentation** (Priority 3)
5. **Test end-to-end data flow**
6. **Release v1.1.0** with complete integration

---

**Would you like me to implement the bidirectional sync now?**

