# Troubleshooting Checklist - vLLM Batch Server Project

**CRITICAL**: This document captures EVERY issue we encountered. Use this as a pre-flight checklist before starting ANY server.

---

## 🎯 Project Architecture

### Two Independent Branches (NEVER MERGE)

1. **`master` branch** - Ollama + Batch Wrapper
   - **Target**: Consumer GPUs (RTX 4080 16GB)
   - **Backend**: Ollama
   - **Capability**: Batch processing wrapper (sequential)
   - **Model Format**: Ollama format (e.g., `gemma3:12b`)

2. **`vllm` branch** - vLLM + Model Hot-Swapping
   - **Target**: Production/Cloud GPUs (24GB+ VRAM)
   - **Backend**: vLLM
   - **Capability**: Native batch processing + model hot-swapping
   - **Model Format**: HuggingFace format (e.g., `google/gemma-3-12b-it`)

---

## ⚠️ CRITICAL ISSUES ENCOUNTERED

### 1. Memory & GPU Issues

#### Issue: vLLM V1 Engine Memory Overhead
- **Problem**: vLLM V1 engine requires 16+ GB VRAM just to LOAD 7-9B models
- **Impact**: RTX 4080 16GB cannot run even small models with V1 engine
- **Root Cause**: V1 engine has massive memory overhead for KV cache initialization
- **Solution**: Use Ollama for consumer GPUs OR use cloud GPUs with 24GB+ VRAM for vLLM

#### Issue: vLLM V0 Engine Removed
- **Problem**: vLLM 0.11.0 (Oct 2024) completely removed V0 engine
- **Impact**: Cannot use older, more memory-efficient V0 engine
- **Workaround**: Would require downgrading to vLLM 0.9.2 + Python 3.9-3.12 (incompatible with Python 3.13.3)
- **Decision**: Abandoned vLLM for consumer GPUs, using Ollama instead

#### Issue: Gemma 3 Compatibility
- **Problem**: Gemma 3 has known issues with vLLM (both V0 and V1)
- **Impact**: Cannot reliably use Gemma 3 with vLLM
- **Solution**: Use Gemma 3 with Ollama (works perfectly)

---

### 2. Zombie Process Issues

#### Issue: Old Server Processes Blocking Ports
- **Problem**: Old vLLM/Ollama servers continue running after crashes/stops
- **Impact**: 
  - Port 4080 blocked (cannot start new server)
  - Port 11434 blocked (Ollama conflicts)
  - GPU memory consumed by zombie processes
- **Detection**:
  ```bash
  ps aux | grep -E "python|vllm|ollama" | grep -v grep
  nvidia-smi  # Check GPU memory usage
  ```
- **Solution**:
  ```bash
  # Kill specific process
  kill -9 <PID>
  
  # Nuclear option - kill all Python processes (USE WITH CAUTION)
  pkill -9 python
  
  # Kill all Ollama processes
  pkill -9 ollama
  ```

#### Issue: Multiple Ollama Instances
- **Problem**: Multiple `ollama serve` processes running simultaneously
- **Impact**: Port conflicts, unpredictable behavior
- **Detection**: `ps aux | grep ollama | grep -v grep`
- **Solution**: Kill all but one, or kill all and restart fresh

---

### 3. Configuration Issues

#### Issue: Model Name Format Mismatch
- **Problem**: `.env` file has wrong model name format for backend
- **Examples**:
  - vLLM expects: `google/gemma-3-12b-it` (HuggingFace format)
  - Ollama expects: `gemma3:12b` (Ollama format)
- **Impact**: Server fails to start with "Model not found" error
- **Solution**: Update `.env` file when switching branches:
  ```bash
  # For Ollama (master branch)
  MODEL_NAME=gemma3:12b
  OLLAMA_BASE_URL=http://localhost:11434
  
  # For vLLM (vllm branch)
  MODEL_NAME=google/gemma-3-12b-it
  HF_TOKEN=hf_...
  ```

#### Issue: Obsolete Config Validators
- **Problem**: Pydantic validators reference deleted fields (e.g., `dtype` validator after removing vLLM config)
- **Impact**: Server crashes on startup with `PydanticUserError: Decorators defined with incorrect fields`
- **Solution**: Remove validators when removing their corresponding fields

#### Issue: vLLM-Specific Settings in Ollama Branch
- **Problem**: Config has vLLM-specific fields (tensor_parallel_size, gpu_memory_utilization, etc.)
- **Impact**: Confusion, unnecessary complexity
- **Solution**: Clean up config when switching backends

---

### 4. Dependency Issues

#### Issue: Wrong Dependencies for Backend
- **Problem**: `pyproject.toml` has `vllm>=0.6.0` when using Ollama
- **Impact**: Unnecessary heavy dependencies, potential conflicts
- **Solution**: Update dependencies per branch:
  ```toml
  # Ollama branch
  dependencies = [
      "httpx>=0.28.0",  # For Ollama API calls
      "fastapi>=0.115.0",
      ...
  ]
  
  # vLLM branch
  dependencies = [
      "vllm>=0.6.0",
      "fastapi>=0.115.0",
      ...
  ]
  ```

---

### 5. Python Version Issues

#### Issue: Python 3.13 Incompatibility with vLLM 0.9.2
- **Problem**: vLLM 0.9.2 (last V0 version) requires Python 3.9-3.12
- **Impact**: Cannot use V0 engine on Python 3.13.3
- **Solution**: Accept limitation, use Ollama for consumer GPUs

---

## 🔍 Pre-Flight Checklist

### Before Starting ANY Server

```bash
# 1. Check for zombie processes
ps aux | grep -E "python|vllm|ollama" | grep -v grep

# 2. Check GPU memory
nvidia-smi

# 3. Check port availability
lsof -i :4080  # FastAPI server
lsof -i :11434 # Ollama server

# 4. Verify correct branch
git branch

# 5. Verify .env matches branch
cat .env | grep MODEL_NAME

# 6. Kill zombies if needed
pkill -9 python  # CAUTION: Kills ALL Python processes
pkill -9 ollama

# 7. Verify Ollama is running (if using Ollama branch)
curl -s http://localhost:11434/api/tags | head -10

# 8. Verify model is downloaded (if using Ollama)
ollama list
```

---

## 🚀 Startup Procedures

### Master Branch (Ollama + Batch Wrapper)

```bash
# 1. Switch to master
git checkout master

# 2. Kill zombies
ps aux | grep -E "python|ollama" | grep -v grep
# Kill any found processes

# 3. Start Ollama (if not running)
ollama serve &

# 4. Verify Ollama health
curl http://localhost:11434/api/tags

# 5. Pull model if needed
ollama pull gemma3:12b

# 6. Verify .env
cat .env | grep MODEL_NAME  # Should be: gemma3:12b

# 7. Start server
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

### vLLM Branch (vLLM + Model Hot-Swapping)

```bash
# 1. Switch to vllm
git checkout vllm

# 2. Kill zombies
ps aux | grep python | grep -v grep
# Kill any found processes

# 3. Verify GPU memory is clear
nvidia-smi  # Should show minimal usage

# 4. Verify .env
cat .env | grep MODEL_NAME  # Should be: google/gemma-3-12b-it

# 5. Start server (requires 24GB+ VRAM)
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

---

## 🐛 Common Error Messages & Solutions

### "CUDA out of memory"
- **Cause**: vLLM V1 engine on RTX 4080 16GB
- **Solution**: Switch to Ollama branch OR use cloud GPU with 24GB+ VRAM

### "Model not found"
- **Cause**: Wrong model name format in `.env`
- **Solution**: 
  - Ollama: Use `gemma3:12b`
  - vLLM: Use `google/gemma-3-12b-it`

### "Address already in use" (Port 4080)
- **Cause**: Old server still running
- **Solution**: `ps aux | grep uvicorn`, then `kill -9 <PID>`

### "Ollama server is not running"
- **Cause**: Ollama not started
- **Solution**: `ollama serve &`

### "PydanticUserError: Decorators defined with incorrect fields"
- **Cause**: Validator references deleted field
- **Solution**: Remove obsolete validators from `src/config.py`

---

## 📊 Memory Usage Guidelines

### RTX 4080 16GB Breakdown

```
Total VRAM: 16,376 MiB

Desktop/System: ~500-600 MiB
Available for Models: ~15,800 MiB

Model Memory Requirements:
- Gemma 3 12B (Ollama Q4_K_M): ~8.1 GB ✅ FITS
- Gemma 2 9B (vLLM FP16): ~16 GB ❌ BARELY FITS (no room for KV cache)
- Gemma 2 9B (vLLM V1): ~20+ GB ❌ DOES NOT FIT
- Llama 3.2 3B (Ollama): ~2 GB ✅ FITS
```

### Cloud GPU Requirements (vLLM Branch)

```
Minimum: 24 GB VRAM (e.g., RTX 3090, RTX 4090, A5000)
Recommended: 40 GB VRAM (e.g., A100)
```

---

## 🎓 Lessons Learned

1. **Always check for zombie processes** - They WILL block ports and consume memory
2. **GPU memory is precious** - vLLM V1 is a memory hog, Ollama is efficient
3. **Model name formats matter** - HuggingFace vs Ollama naming conventions
4. **Config validators must match fields** - Remove validators when removing fields
5. **Two branches, two products** - Don't try to merge them, they serve different purposes
6. **Python version matters** - vLLM 0.9.2 won't work on Python 3.13
7. **Gemma 3 + vLLM = Problems** - Use Ollama for Gemma 3
8. **Port conflicts are silent killers** - Always check `lsof -i :PORT`

---

## 📝 Quick Reference Commands

```bash
# Process management
ps aux | grep -E "python|vllm|ollama" | grep -v grep
kill -9 <PID>
pkill -9 python
pkill -9 ollama

# GPU monitoring
nvidia-smi
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
watch -n 1 nvidia-smi  # Real-time monitoring

# Port checking
lsof -i :4080
lsof -i :11434
netstat -tulpn | grep :4080

# Ollama management
ollama serve &
ollama list
ollama pull gemma3:12b
curl http://localhost:11434/api/tags

# Git branch management
git branch
git checkout master
git checkout vllm

# Server startup
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

---

**Last Updated**: 2025-10-27
**Status**: Living document - update as new issues are discovered

