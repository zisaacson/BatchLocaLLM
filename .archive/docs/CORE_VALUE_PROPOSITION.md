# 🎯 Core Value Proposition

## What Even Skeptics Would Appreciate

---

## ❌ The Skeptic's "Simple" Solution

```python
# simple_batch.py (80 lines)
from vllm import LLM

llm = LLM("google/gemma-3-4b-it")
outputs = llm.generate(prompts)
```

**Problems:**
1. ❌ **Crash = lose everything** - No checkpointing
2. ❌ **Can't switch models** - Locked to one model per run
3. ❌ **No progress tracking** - Is it working? How long left?
4. ❌ **No job queue** - Can't queue multiple jobs
5. ❌ **No API** - Can't integrate with other apps
6. ❌ **Memory management** - Will it OOM? Who knows!

---

## ✅ The Core System (Skeptic-Approved)

**Same simplicity, but production-grade:**

```bash
vllm-batch submit input.jsonl --model gemma-3-4b
```

**What you get:**

### **1. Crash Recovery** 🛡️

**Problem:** Your GPU crashes after 8 hours of processing 40,000 requests.

**Simple script:** Start over. Lose 8 hours.

**Core system:**
```
✅ Checkpoint saved at request 40,000
✅ Resume from checkpoint
✅ Only lost ~5 minutes of work
```

**How it works:**
- PostgreSQL job queue (survives crashes)
- Incremental saves every 100 requests
- Automatic resume on restart

---

### **2. Model Hot-Swapping** 🔄

**Problem:** You want to compare 3 models on the same data.

**Simple script:**
```bash
python simple_batch.py --model gemma-3-4b input.jsonl > output1.jsonl
# Wait 2 hours...

python simple_batch.py --model llama-3.2-3b input.jsonl > output2.jsonl
# Wait 2 hours...

python simple_batch.py --model qwen-2.5-3b input.jsonl > output3.jsonl
# Wait 2 hours...

# Total: 6 hours
```

**Core system:**
```bash
vllm-batch submit input.jsonl --models gemma-3-4b,llama-3.2-3b,qwen-2.5-3b

# Automatically:
# 1. Process with gemma-3-4b
# 2. Unload gemma, load llama
# 3. Process with llama-3.2-3b
# 4. Unload llama, load qwen
# 5. Process with qwen-2.5-3b

# Total: 6 hours (same time, but automated)
# Bonus: Results are aligned (same request order)
```

**Why this matters:**
- RTX 4080 16GB can only hold ONE 4B model at a time
- Manual model switching is error-prone
- Automatic switching ensures fair comparison

---

### **3. Memory Management** 🧠

**Problem:** Will this batch fit in GPU memory?

**Simple script:**
```python
llm = LLM("google/gemma-3-4b-it")
outputs = llm.generate(prompts)  # 🤞 Hope it doesn't OOM
```

**Core system:**
```python
# Automatic chunking based on GPU memory
CHUNK_SIZE = auto_calculate_chunk_size(
    model="gemma-3-4b",
    gpu_memory_gb=16,
    safety_margin=0.1
)

# Process in safe chunks
for chunk in chunks(prompts, CHUNK_SIZE):
    outputs = llm.generate(chunk)
    save_checkpoint(outputs)
```

**GPU-specific defaults:**
- RTX 3060 12GB: CHUNK_SIZE=50
- RTX 4080 16GB: CHUNK_SIZE=100
- RTX 3090 24GB: CHUNK_SIZE=150
- RTX 4090 24GB: CHUNK_SIZE=200

**Result:** Never OOM, maximize throughput

---

### **4. Progress Tracking** 📊

**Problem:** Is it working? How long will it take?

**Simple script:**
```
Processing...
(no output for 2 hours)
(is it frozen? who knows!)
```

**Core system:**
```
✅ Batch job started: batch_abc123
✅ Model loaded: gemma-3-4b (2.3 GB VRAM)
✅ Processing: 1,247 / 50,000 requests (2.5%)
✅ Throughput: 487 tok/s
✅ ETA: 2h 34m
✅ Checkpoint saved: 1,200 requests
✅ Processing: 2,491 / 50,000 requests (5.0%)
...
```

**Access via:**
- CLI: `vllm-batch status batch_abc123`
- API: `GET /v1/batches/batch_abc123`
- Web UI: `http://localhost:4080/queue-monitor.html`

---

### **5. Job Queue** 📋

**Problem:** You have 3 datasets to process.

**Simple script:**
```bash
python simple_batch.py dataset1.jsonl > output1.jsonl
# Wait 2 hours, then manually start next one
python simple_batch.py dataset2.jsonl > output2.jsonl
# Wait 2 hours, then manually start next one
python simple_batch.py dataset3.jsonl > output3.jsonl
```

**Core system:**
```bash
# Submit all 3 jobs
vllm-batch submit dataset1.jsonl --model gemma-3-4b
vllm-batch submit dataset2.jsonl --model llama-3.2-3b
vllm-batch submit dataset3.jsonl --model qwen-2.5-3b

# Go to bed. Wake up. All done.
```

**Queue automatically:**
- Processes jobs sequentially (prevent OOM)
- Switches models between jobs
- Tracks progress for each job
- Survives crashes (PostgreSQL queue)

---

### **6. API Integration** 🔌

**Problem:** Your web app needs to submit batch jobs.

**Simple script:**
```python
# Your web app
import subprocess

# Ugly hack
subprocess.run(["python", "simple_batch.py", "input.jsonl"])

# How do you check status? Parse stdout?
# How do you get results? Read files?
# How do you handle errors? 🤷
```

**Core system:**
```python
# Your web app
import httpx

client = httpx.Client(base_url="http://localhost:4080")

# Submit job
response = client.post("/v1/files", files={"file": open("input.jsonl")})
file_id = response.json()["id"]

response = client.post("/v1/batches", json={
    "input_file_id": file_id,
    "endpoint": "/v1/chat/completions",
    "metadata": {"user_id": "123", "dataset": "candidates"}
})
batch_id = response.json()["id"]

# Check status
status = client.get(f"/v1/batches/{batch_id}").json()
print(f"Status: {status['status']}")  # queued, processing, completed

# Get results when done
if status["status"] == "completed":
    results = client.get(f"/v1/files/{status['output_file_id']}/content").text
```

**OpenAI-compatible:** Drop-in replacement for OpenAI Batch API

---

## 📊 Core System: What's Included

### **Minimal Dependencies** (6 packages)
```txt
vllm==0.11.0              # Inference engine
fastapi>=0.115.0          # REST API
uvicorn>=0.32.0           # ASGI server
sqlalchemy>=2.0.0         # ORM
psycopg2-binary>=2.9.0    # PostgreSQL driver
pydantic>=2.10.0          # Data validation
```

### **Core Features**
- ✅ vLLM batch processing with automatic chunking
- ✅ OpenAI-compatible REST API
- ✅ PostgreSQL job queue (crash-resistant)
- ✅ Incremental saves (checkpoint every 100 requests)
- ✅ Model hot-swapping (consumer GPU friendly)
- ✅ Sequential processing (prevent OOM)
- ✅ Progress tracking (CLI, API, Web UI)
- ✅ Job queue (submit multiple jobs)
- ✅ File storage (input/output management)

### **What's NOT Included** (Optional Integrations)
- ❌ Grafana/Prometheus monitoring
- ❌ Label Studio data curation
- ❌ Webhooks
- ❌ Sentry error tracking
- ❌ Rate limiting
- ❌ Custom result handlers

---

## 🎯 The Value Proposition

### **For the Skeptic:**

**You said:** "Just use an 80-line script"

**We say:** "Here's an 80-line script that doesn't lose your work when it crashes"

**Core system = Simple script + Production features**

| Feature | Simple Script | Core System |
|---------|--------------|-------------|
| Lines of code to use | 5 | 1 |
| Crash recovery | ❌ | ✅ |
| Progress tracking | ❌ | ✅ |
| Model switching | Manual | Automatic |
| Memory management | Hope | Guaranteed |
| Job queue | ❌ | ✅ |
| API integration | Hacky | Clean |
| Dependencies | 1 | 6 |
| Install time | 30s | 2min |

**Trade-off:** 90 seconds of install time for production reliability

**Worth it?** If you're processing 50,000 requests over 3 hours, YES.

---

## 🎓 When to Use What

### **Use Simple Script When:**
- ✅ One-off job (< 1,000 requests)
- ✅ Don't care about crashes
- ✅ Single model
- ✅ No integration needed
- ✅ Experimenting/testing

### **Use Core System When:**
- ✅ Long-running jobs (> 1 hour)
- ✅ Can't afford to lose work
- ✅ Comparing multiple models
- ✅ Need progress tracking
- ✅ Integrating with other apps
- ✅ Processing regularly

---

## 💡 The Skeptic's Rebuttal

**Skeptic:** "But I can add checkpointing to my script!"

**Us:** "Sure! You'll end up rebuilding our core system. We already did that work."

**Skeptic:** "But I don't need PostgreSQL!"

**Us:** "SQLite works too. But PostgreSQL is more reliable for long jobs."

**Skeptic:** "But I don't need an API!"

**Us:** "Use the CLI then. API is there if you need it."

**Skeptic:** "This is still more complex than I need!"

**Us:** "Then use the simple script. We're not stopping you. But when your 8-hour job crashes at 95%, you'll be back."

---

## ✅ Bottom Line

**Core system is the MINIMUM viable production system.**

**It's what you'd build yourself after:**
1. Your first crash loses 8 hours of work
2. You manually switch models 3 times
3. You wonder "is it frozen or just slow?"
4. You want to integrate with your web app
5. You need to queue multiple jobs

**We just saved you 2 weeks of development.**

**And we made it optional - use what you need, ignore the rest.**

---

**That's the core value proposition. Everything else (monitoring, curation, webhooks) is gravy.**

