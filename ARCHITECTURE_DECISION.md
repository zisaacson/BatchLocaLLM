# 🏗️ Architecture Decision: Monorepo vs Separate Open Source

**Date:** 2025-10-31  
**Decision Maker:** AI Agent (First Principles Analysis)  
**Context:** "there probably won't be that much more work done on this thing"

---

## 🎯 The Question

Should we:
1. **Maintain separate repos** (current: vllm-batch-server + vllm-batch-server-opensource)
2. **Refactor to use open source as dependency** (Aris imports vllm-batch-server package)
3. **Monorepo with public/private split** (single repo, different directories)

---

## 🧠 First Principles Analysis

### **Key Constraints**

1. **Low Future Development:** "probably won't be that much more work done on this thing"
2. **Engineering Resources Available:** Can do either approach
3. **Current State:** Two repos with ~95% code overlap
4. **Aris-Specific Code:** conquest_schemas/, curation_app/, Aris integration

### **Core Principles**

1. **Minimize Maintenance Burden** - Less work to keep in sync
2. **Maximize Code Reuse** - Don't duplicate fixes
3. **Clear Separation** - Public vs private code
4. **Easy to Understand** - Future developers can navigate
5. **Low Friction** - Easy to contribute to open source

---

## 📊 Option Analysis

### **Option 1: Separate Repos (Current State)**

```
vllm-batch-server/              (Private - Aris internal)
├── batch_app/                  ✅ Core (duplicated)
├── result_handlers/            ❌ Missing
├── conquest_schemas/           ✅ Aris-specific
├── curation_app/               ✅ Aris-specific
└── config.py                   ✅ Core (duplicated)

vllm-batch-server-opensource/   (Public)
├── batch_app/                  ✅ Core
├── result_handlers/            ✅ Core
├── config.py                   ✅ Core
└── docs/                       ✅ Public docs
```

**Pros:**
- ✅ Clean separation (public vs private)
- ✅ No risk of leaking Aris code
- ✅ Can customize each independently

**Cons:**
- ❌ **CRITICAL:** Bug fixes must be applied twice
- ❌ **CRITICAL:** Features must be implemented twice
- ❌ **CRITICAL:** Code drift over time (already happening)
- ❌ Maintenance burden (2x work)
- ❌ Confusing (which is source of truth?)

**Verdict:** ❌ **BAD CHOICE** - Violates "minimize maintenance burden"

---

### **Option 2: Open Source as Dependency**

```
vllm-batch-server/              (Public PyPI package)
├── batch_app/                  ✅ Core
├── result_handlers/            ✅ Core
├── config.py                   ✅ Core
└── setup.py                    ✅ Package config

aris-vllm-integration/          (Private - Aris internal)
├── conquest_schemas/           ✅ Aris-specific
├── curation_app/               ✅ Aris-specific
├── aris_config.py              ✅ Extends base config
└── requirements.txt            → vllm-batch-server==1.0.0
```

**Usage:**
```python
# In Aris codebase
from vllm_batch_server import BatchWorker, ResultHandler
from vllm_batch_server.config import settings

# Extend with Aris-specific handlers
class ConquestHandler(ResultHandler):
    def handle(self, batch_id, results, metadata):
        # Aris-specific logic
        pass
```

**Pros:**
- ✅ Single source of truth (open source repo)
- ✅ Bug fixes automatically available to Aris
- ✅ Clear separation (package vs integration)
- ✅ Can version and pin (vllm-batch-server==1.0.0)
- ✅ Forces good API design

**Cons:**
- ❌ Requires packaging (setup.py, PyPI/GitHub releases)
- ❌ Aris changes require open source PR first
- ❌ More complex deployment (install package)
- ❌ Overhead for "probably won't be much more work"

**Verdict:** ⚠️ **OVERKILL** - Too much process for low-activity project

---

### **Option 3: Monorepo with Public/Private Split** ⭐

```
vllm-batch-server/              (Single repo, public on GitHub)
├── core/                       ✅ Public (open source)
│   ├── batch_app/
│   ├── result_handlers/
│   ├── config.py
│   ├── README.md
│   └── LICENSE
│
├── integrations/               ✅ Private (gitignored)
│   └── aris/
│       ├── conquest_schemas/
│       ├── curation_app/
│       ├── aris_config.py
│       └── README.md
│
├── .gitignore                  → integrations/
├── README.md                   → Points to core/
└── docker-compose.yml          → Uses core/ + integrations/
```

**.gitignore:**
```
integrations/
!integrations/README.md
!integrations/examples/
```

**Pros:**
- ✅ **Single source of truth** (one repo)
- ✅ **Zero duplication** (fixes apply once)
- ✅ **Clear separation** (core/ vs integrations/)
- ✅ **Easy to contribute** (just edit core/)
- ✅ **Low maintenance** (one codebase)
- ✅ **Flexible** (can extract to package later if needed)
- ✅ **Simple deployment** (just clone repo)

**Cons:**
- ⚠️ Must be careful not to commit integrations/
- ⚠️ Slightly less "pure" open source (has private folder)

**Verdict:** ✅ **BEST CHOICE** - Balances all constraints

---

## 🎯 RECOMMENDATION: Monorepo with Public/Private Split

### **Why This is the Right Choice**

**Given your constraints:**
1. ✅ "Probably won't be much more work" → Minimize process overhead
2. ✅ "Engineering resources available" → Can do refactor once
3. ✅ "Pick a direction" → Clear, simple architecture

**First Principles:**
1. ✅ **Minimize Maintenance:** Single codebase, zero duplication
2. ✅ **Maximize Reuse:** All fixes/features apply once
3. ✅ **Clear Separation:** core/ (public) vs integrations/ (private)
4. ✅ **Easy to Understand:** Obvious structure
5. ✅ **Low Friction:** Just edit core/ to contribute

**Future-Proof:**
- If project grows → Extract core/ to PyPI package (Option 2)
- If project dies → Archive repo, core/ is already open source
- If Aris changes → Just edit integrations/aris/

---

## 📋 Implementation Plan

### **Phase 1: Restructure Current Repo** (2 hours)

```bash
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server

# 1. Create new structure
mkdir -p core integrations/aris integrations/examples

# 2. Move core code to core/
mv batch_app core/
mv result_handlers core/
mv config.py core/
mv requirements.txt core/
mv pyproject.toml core/
mv LICENSE core/
mv tests core/

# 3. Move Aris-specific code to integrations/aris/
mv conquest_schemas integrations/aris/
mv curation_app integrations/aris/

# 4. Update .gitignore
echo "integrations/aris/" >> .gitignore
echo "!integrations/examples/" >> .gitignore

# 5. Create README files
# core/README.md → Open source documentation
# integrations/aris/README.md → Aris integration guide
# integrations/examples/README.md → Example integrations
```

### **Phase 2: Update Imports** (1 hour)

```python
# Before (old structure)
from batch_app import api_server
from config import settings

# After (new structure)
from core.batch_app import api_server
from core.config import settings
```

**Files to update:**
- All Python files in integrations/aris/
- docker-compose.yml
- scripts/*.sh

### **Phase 3: Update Documentation** (30 min)

**Root README.md:**
```markdown
# vLLM Batch Server

Self-hosted OpenAI-compatible batch processing for local GPUs.

## 📦 Structure

- **core/** - Open source batch server (Apache 2.0)
- **integrations/** - Private integrations (gitignored)
  - **aris/** - Aris-specific code (conquest schemas, curation)
  - **examples/** - Example integrations (public)

## 🚀 Quick Start

See [core/README.md](core/README.md) for open source documentation.

For Aris integration, see [integrations/aris/README.md](integrations/aris/README.md).
```

**core/README.md:**
- Copy from vllm-batch-server-opensource/README.md
- This is the public-facing documentation

**integrations/aris/README.md:**
```markdown
# Aris Integration

Private integration code for Aris candidate evaluation system.

## Structure

- **conquest_schemas/** - Conquest-specific schemas
- **curation_app/** - Curation UI and API
- **aris_config.py** - Aris-specific configuration

## Usage

This code extends the core vLLM batch server with Aris-specific functionality.
```

### **Phase 4: Test Everything** (1 hour)

```bash
# Test core functionality
cd core
python -m batch_app.api_server &
python -m batch_app.worker &

# Test Aris integration
cd ../integrations/aris
python -m curation_app.api &

# Run tests
cd ../../core
pytest tests/
```

### **Phase 5: Commit and Push** (15 min)

```bash
git add .
git commit -m "Refactor: Monorepo with core/ (public) and integrations/ (private)

STRUCTURE:
- core/ → Open source batch server (Apache 2.0)
- integrations/aris/ → Aris-specific code (gitignored)
- integrations/examples/ → Example integrations (public)

BENEFITS:
✅ Single source of truth
✅ Zero code duplication
✅ Clear public/private separation
✅ Easy to contribute to open source
✅ Low maintenance burden

MIGRATION:
- Moved batch_app, result_handlers, config to core/
- Moved conquest_schemas, curation_app to integrations/aris/
- Updated all imports
- Updated documentation"

git push
```

---

## 🔄 Migration from Separate Repos

### **What to Do with vllm-batch-server-opensource/**

**Option A: Delete it** ✅ RECOMMENDED
```bash
# It's now redundant - core/ is the open source version
rm -rf /home/zack/Documents/augment-projects/Local/vllm-batch-server-opensource
```

**Option B: Keep as reference**
```bash
# Rename to indicate it's archived
mv vllm-batch-server-opensource vllm-batch-server-opensource-ARCHIVED
```

### **GitHub Strategy**

**Current repo:** `github.com/zisaacson/vllm-batch-server`

**After refactor:**
- Root README.md → Points to core/
- core/ → Open source documentation
- integrations/aris/ → Gitignored (not pushed)
- GitHub sees only core/ + examples

**Result:** Same repo, now properly structured for open source

---

## 📊 Comparison Summary

| Aspect | Separate Repos | As Dependency | Monorepo ⭐ |
|--------|---------------|---------------|-------------|
| **Maintenance** | 2x work | Medium | 1x work |
| **Code Duplication** | High | None | None |
| **Complexity** | Low | High | Low |
| **Future Flexibility** | Low | High | Medium |
| **Time to Implement** | 0 (current) | 4 hours | 2 hours |
| **Ongoing Effort** | High | Medium | Low |
| **Fits Constraints** | ❌ No | ⚠️ Overkill | ✅ Yes |

---

## ✅ DECISION: Monorepo with Public/Private Split

### **Rationale**

1. **"Probably won't be much more work"** → Don't over-engineer
2. **"Engineering resources available"** → Can do refactor once
3. **"Pick a direction"** → Clear, simple, maintainable

### **Action Items**

- [ ] Restructure repo (core/ + integrations/)
- [ ] Update imports
- [ ] Update documentation
- [ ] Test everything
- [ ] Commit and push
- [ ] Delete vllm-batch-server-opensource/

### **Timeline**

- **Total Time:** ~4-5 hours
- **Benefit:** Zero ongoing duplication
- **Risk:** Low (can revert if needed)

---

## 🎯 Long-Term Strategy

### **If Project Grows** (Unlikely but possible)

Extract core/ to PyPI package:
```bash
cd core
python setup.py sdist bdist_wheel
twine upload dist/*
```

Then Aris becomes:
```python
# requirements.txt
vllm-batch-server==1.0.0
```

### **If Project Dies** (More likely)

Archive repo:
- core/ is already open source
- integrations/aris/ is already gitignored
- Nothing to clean up

### **If Aris Changes** (Most likely)

Just edit integrations/aris/:
- No need to sync with open source
- No need to maintain two repos
- Changes are local and isolated

---

**RECOMMENDATION: Implement Monorepo Structure** ✅

**Estimated Time:** 4-5 hours  
**Ongoing Savings:** Infinite (zero duplication)  
**Risk:** Low  
**Complexity:** Low  

**This is the right choice.** 🎯

