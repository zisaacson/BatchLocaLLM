# Model Comparison Guide

## Available Models for RTX 4080 (16GB VRAM)

### 1. Gemma 3 12B (RECOMMENDED BASE MODEL)
- **HuggingFace**: `google/gemma-3-12b-it`
- **Size**: ~12B parameters (8.1GB quantized)
- **VRAM**: ~10-11GB
- **Context**: 128K tokens
- **Features**: Multimodal (text + images), multilingual
- **Use Case**: Your primary model for production workloads
- **Availability**: ✅ Available in vLLM

### 2. GPT-OSS 20B (COMPARISON MODEL)
- **HuggingFace**: `openai/gpt-oss-20b`
- **Ollama**: `gpt-oss:20b`
- **Size**: ~21B parameters (3.6B active - MoE architecture)
- **VRAM**: ~14-16GB (MXFP4 quantized)
- **Context**: 128K tokens
- **Features**: Chain-of-thought reasoning, function calling, agentic
- **Use Case**: Comparison benchmarks, complex reasoning tasks
- **Availability**: ✅ Available in vLLM AND Ollama
- **Note**: Requires vLLM v1.0+ (we're using v0.6.0+)

### 3. Mistral 7B (FAST BASELINE)
- **HuggingFace**: `mistralai/Mistral-7B-Instruct-v0.3`
- **Size**: ~7B parameters
- **VRAM**: ~5-6GB
- **Context**: 32K tokens
- **Features**: Fast, efficient, good general performance
- **Use Case**: Quick tests, high-throughput batch processing
- **Availability**: ✅ Available in vLLM

## Deployment Strategy

### Option A: vLLM Only (RECOMMENDED)

**vLLM Server (Port 8000):**
- Gemma 3 12B (primary)
- GPT-OSS 20B (comparison)
- Mistral 7B (fast baseline)
- Switch by editing `.env` and restarting

**Pros:**
- ✅ Best batch processing performance
- ✅ All models use same OpenAI-compatible API
- ✅ Can run all three models (one at a time)
- ✅ Consistent benchmarking environment

**Cons:**
- ⚠️ Can only run one model at a time (VRAM limit)
- ⚠️ Need to restart to switch models

### Option B: vLLM + Ollama

**vLLM Server (Port 8000):**
- Gemma 3 12B (primary)
- Mistral 7B (fast baseline)

**Ollama (Port 11434):**
- GPT-OSS 20B (comparison)

**Pros:**
- ✅ Can keep Gemma 3 running while testing GPT-OSS in Ollama
- ✅ Ollama has simpler model switching

**Cons:**
- ⚠️ Can't run both simultaneously (VRAM limit)
- ⚠️ Different APIs (OpenAI-compatible vs Ollama)

### Option C: Ollama Only

**Ollama (Port 11434):**
- `ollama run gemma3:12b`
- `ollama run gpt-oss:20b`
- `ollama run mistral:7b`

**Pros:**
- ✅ Consistent API
- ✅ Easy model switching
- ✅ Already installed

**Cons:**
- ❌ No batch processing API
- ❌ Less efficient for batch workloads

## Switching Models in vLLM

Edit `.env` file:

```bash
# For Gemma 3 12B (base model)
MODEL_NAME=google/gemma-3-12b-it

# For GPT-OSS 20B (comparison)
MODEL_NAME=openai/gpt-oss-20b

# For Mistral 7B (fast baseline)
MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3

# For Qwen 14B (alternative)
MODEL_NAME=Qwen/Qwen2.5-14B-Instruct
```

Then restart:
```bash
docker compose down
docker compose up -d
```

## Benchmark Comparison

To compare models, run the same workload on each (in vLLM):

```bash
# Test Gemma 3 12B
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "google/gemma-3-12b-it", "messages": [{"role": "user", "content": "Explain quantum computing"}]}'

# Switch to GPT-OSS 20B (edit .env, restart)
# Then test GPT-OSS 20B
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "Explain quantum computing"}]}'

# Switch to Mistral 7B (edit .env, restart)
# Then test Mistral 7B
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "mistralai/Mistral-7B-Instruct-v0.3", "messages": [{"role": "user", "content": "Explain quantum computing"}]}'
```

## Current Configuration

**vLLM is configured for Gemma 3 12B** (see `.env` file)

To use GPT-OSS 20B in vLLM:
1. Edit `.env`: Change `MODEL_NAME=openai/gpt-oss-20b`
2. Restart: `docker compose down && docker compose up -d`
3. Wait for model download (~14GB)
4. Test with OpenAI-compatible API

## Notes

- **All three models available in vLLM** - Gemma 3 12B, GPT-OSS 20B, Mistral 7B
- **Can't run multiple models simultaneously** - 16GB VRAM limit
- **Gemma 3 12B is your base model** for production batch processing
- **GPT-OSS 20B is for comparison** - OpenAI's open-weight reasoning model
- **Mistral 7B is your fast baseline** - quick tests and high throughput
- **All use same OpenAI-compatible API** - consistent benchmarking
