# Codebase Reorganization Plan

**Goal:** Reorganize from Ollama-focused to vLLM native batch processing with multi-model support.

---

## 🎯 Current State vs Target State

### **Current State (Messy):**
```
vllm-batch-server/
├── src/                    # Ollama-specific code (DEPRECATED)
│   ├── ollama_backend.py
│   ├── batch_processor.py
│   └── ...
├── batch_app/              # NEW vLLM web app (KEEP)
├── benchmarks/             # Benchmark data (KEEP)
├── tools/                  # Various scripts (REORGANIZE)
├── tests/                  # Old tests (UPDATE)
└── 50+ markdown files      # Documentation (CONSOLIDATE)
```

### **Target State (Clean):**
```
vllm-batch-server/
├── batch_api/              # Web API for batch processing
│   ├── server.py           # FastAPI server
│   ├── worker.py           # Background worker
│   ├── database.py         # Database models
│   └── benchmarks.py       # Benchmark integration
├── models/                 # Model configurations
│   ├── gemma3_4b.py
│   ├── llama32_1b.py
│   ├── qwen3_4b.py
│   └── registry.py         # Model registry
├── benchmarks/             # Benchmark data and tools
│   ├── data/               # Benchmark results
│   ├── tools/              # Benchmark scripts
│   └── reports/            # Analysis reports
├── tests/                  # Test suite
│   ├── test_api.py
│   ├── test_worker.py
│   └── test_models.py
├── docs/                   # Documentation
│   ├── README.md           # Main docs
│   ├── API.md              # API reference
│   ├── BENCHMARKING.md     # Benchmark guide
│   └── MODELS.md           # Model guide
├── scripts/                # Utility scripts
│   ├── start_server.sh
│   ├── start_worker.sh
│   └── run_benchmark.sh
└── examples/               # Example usage
    ├── submit_batch.py
    └── monitor_job.py
```

---

## 📋 Migration Steps

### **Step 1: Rename and Reorganize Core**
```bash
# Rename batch_app to batch_api
mv batch_app batch_api

# Update imports in all files
# batch_app.api_server -> batch_api.server
# batch_app.worker -> batch_api.worker
```

### **Step 2: Archive Ollama Code**
```bash
# Move deprecated Ollama code to archive
mkdir -p archive/ollama
mv src/ archive/ollama/
mv README_OLLAMA_BATCH.md archive/ollama/
```

### **Step 3: Create Models Directory**
```bash
mkdir -p models
# Create model configuration files
```

### **Step 4: Consolidate Documentation**
```bash
mkdir -p docs
# Move key docs to docs/
# Archive old docs
```

### **Step 5: Clean Up Root**
```bash
# Keep only essential files in root:
# - README.md (new, comprehensive)
# - pyproject.toml
# - .gitignore
# - LICENSE
```

---

## 📁 New File Structure

### **batch_api/** (Core Application)
```
batch_api/
├── __init__.py
├── server.py               # FastAPI server (renamed from api_server.py)
├── worker.py               # Background worker
├── database.py             # Database models
├── benchmarks.py           # Benchmark integration
└── config.py               # Configuration management
```

### **models/** (Model Configurations)
```
models/
├── __init__.py
├── registry.py             # Model registry and loader
├── base.py                 # Base model configuration
├── gemma3_4b.py           # Gemma 3 4B config
├── gemma3_12b.py          # Gemma 3 12B config
├── llama32_1b.py          # Llama 3.2 1B config
├── llama32_3b.py          # Llama 3.2 3B config
├── qwen3_4b.py            # Qwen 3 4B config
├── qwen3_7b.py            # Qwen 3 7B config
└── olmo_1b.py             # OLMo 1B config
```

### **benchmarks/** (Benchmark System)
```
benchmarks/
├── data/                   # Benchmark results
│   ├── metadata/           # JSON metadata files
│   └── raw/                # Raw JSONL results
├── tools/                  # Benchmark scripts
│   ├── run_benchmark.py
│   ├── analyze_results.py
│   └── compare_models.py
└── reports/                # Analysis reports
    └── BENCHMARKING_JOURNEY.md
```

### **docs/** (Documentation)
```
docs/
├── README.md               # Main documentation
├── API.md                  # API reference
├── BENCHMARKING.md         # Benchmark guide
├── MODELS.md               # Model guide
├── DEPLOYMENT.md           # Deployment guide
└── ARCHITECTURE.md         # System architecture
```

### **scripts/** (Utility Scripts)
```
scripts/
├── start_server.sh         # Start API server
├── start_worker.sh         # Start worker
├── run_benchmark.sh        # Run benchmark
└── setup.sh                # Initial setup
```

### **tests/** (Test Suite)
```
tests/
├── __init__.py
├── test_api.py             # API tests
├── test_worker.py          # Worker tests
├── test_models.py          # Model tests
└── test_benchmarks.py      # Benchmark tests
```

---

## 🔧 Implementation Plan

### **Phase 1: Core Reorganization** (30 minutes)
1. ✅ Rename `batch_app` → `batch_api`
2. ✅ Update all imports
3. ✅ Create `models/` directory
4. ✅ Create model configuration files
5. ✅ Update startup scripts

### **Phase 2: Documentation Consolidation** (20 minutes)
1. ✅ Create new comprehensive README.md
2. ✅ Move key docs to `docs/`
3. ✅ Archive old docs to `archive/docs/`
4. ✅ Update all doc links

### **Phase 3: Archive Ollama Code** (10 minutes)
1. ✅ Create `archive/ollama/`
2. ✅ Move `src/` to archive
3. ✅ Move Ollama-specific docs to archive
4. ✅ Update .gitignore

### **Phase 4: Clean Up Root** (10 minutes)
1. ✅ Remove unnecessary files
2. ✅ Keep only essential files
3. ✅ Update pyproject.toml
4. ✅ Update .gitignore

### **Phase 5: Update Tests** (20 minutes)
1. ✅ Update test imports
2. ✅ Add new model tests
3. ✅ Add API tests
4. ✅ Run test suite

---

## 📝 New README.md Structure

```markdown
# vLLM Batch Processing Server

**Production-ready batch inference system for large-scale LLM processing on consumer GPUs.**

## Features
- ✅ Native vLLM batch processing
- ✅ Multi-model support (Gemma, Llama, Qwen, OLMo)
- ✅ Web API for job submission
- ✅ Automatic benchmarking
- ✅ Progress tracking
- ✅ Optimized for RTX 4080 16GB

## Quick Start
[Installation, usage, examples]

## Supported Models
[Model list with benchmarks]

## API Reference
[API documentation]

## Benchmarking
[Benchmark results and guide]

## Architecture
[System architecture]
```

---

## 🎯 Benefits of Reorganization

### **Before:**
- ❌ Mixed Ollama and vLLM code
- ❌ 50+ markdown files in root
- ❌ Unclear project structure
- ❌ Hard to find relevant code
- ❌ Model configs scattered

### **After:**
- ✅ Pure vLLM native batch processing
- ✅ Clean, organized structure
- ✅ Clear separation of concerns
- ✅ Easy to add new models
- ✅ Professional, maintainable codebase

---

## 🚀 Next Steps

1. **Execute reorganization** (1-2 hours)
2. **Update GitHub repo** (30 minutes)
3. **Test everything works** (30 minutes)
4. **Update documentation** (30 minutes)
5. **Commit and push** (10 minutes)

**Total Time:** ~3 hours

---

**Ready to execute?** This will transform the codebase into a professional, production-ready system.

