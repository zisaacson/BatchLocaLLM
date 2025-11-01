# Deployment & Durability Strategy

**Date:** 2025-10-31  
**Issue:** Processes getting killed, need more durable deployment  
**Question:** Should we run in Docker?

---

## 🔍 Root Cause Analysis: Why Are Processes Getting Killed?

### **Current Observations:**
1. ✅ **Worker running natively** - `python -m core.batch_app.worker` (1.4GB RAM, running Gemma 3 4B)
2. ✅ **API running natively** - `uvicorn` on port 4080
3. ✅ **Systemd services exist** - But not being used for tests
4. ⚠️ **Test scripts run directly** - No process management, no restart on failure
5. ⚠️ **4.8GB swap used** - System under memory pressure
6. ❌ **OOM killer likely active** - Processes getting killed when memory runs out

### **Why Test Processes Get Killed:**

**Scenario:**
```
1. Worker has Gemma 3 4B loaded (11GB GPU + 1.4GB RAM)
2. You run: python test_olmo2_7b_single.py
3. Script tries to load OLMo 2 7B (14GB GPU + 2GB RAM)
4. System runs out of RAM (30GB total, 14GB used, need 2GB more)
5. Linux OOM killer: "Kill the newest process" → test script dies
```

**Evidence:**
- ✅ Swap usage (4.8GB) - System swapping heavily
- ✅ Process killed with no error message - Classic OOM behavior
- ✅ Worker still running - OOM kills newest/largest process first

---

## 🎯 Solution: Hybrid Deployment Strategy

### **Recommendation: Native + Docker Hybrid (Current Architecture is CORRECT)**

Your current architecture is actually **excellent** for a single-GPU system:

```
┌─────────────────────────────────────────────────────────┐
│                    RTX 4080 16GB                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  vLLM Worker (Native, Systemd)                   │  │
│  │  - Direct GPU access (no Docker overhead)        │  │
│  │  - Fast model loading                            │  │
│  │  - Systemd auto-restart                          │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Supporting Services (Docker)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Label    │  │ Grafana  │  │Prometheus│             │
│  │ Studio   │  │          │  │          │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

**Why This Is Right:**
- ✅ **vLLM native** - No Docker GPU passthrough overhead
- ✅ **Systemd management** - Auto-restart, logging, resource limits
- ✅ **Docker for services** - Easy deployment of monitoring stack
- ✅ **Best of both worlds** - Performance + convenience

---

## 🛠️ Fixes Needed

### **Problem 1: Test Scripts Not Managed**

**Current:**
```bash
# Run test directly (no process management)
python core/tests/manual/test_olmo2_7b_single.py
# Gets killed by OOM, no restart, no logging
```

**Solution: Use Systemd for Tests Too**

Create temporary systemd service for model testing:

```ini
# /tmp/test-olmo2-7b.service
[Unit]
Description=OLMo 2 7B Model Test
After=network.target

[Service]
Type=oneshot
User=zack
WorkingDirectory=/home/zack/Documents/augment-projects/Local/vllm-batch-server
Environment="PATH=/home/zack/.../venv/bin:..."
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/zack/.../venv/bin/python core/tests/manual/test_olmo2_7b_single.py

# Resource limits (prevent OOM)
MemoryMax=20G
MemoryHigh=18G

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Usage:**
```bash
# Run test as systemd service
sudo systemctl start test-olmo2-7b

# Watch logs in real-time
journalctl -u test-olmo2-7b -f

# Check status
systemctl status test-olmo2-7b
```

---

### **Problem 2: Worker Doesn't Unload Model Before Tests**

**Current:**
- Worker has Gemma 3 4B loaded (11GB GPU)
- Test tries to load OLMo 2 7B (14GB GPU)
- GPU runs out of memory

**Solution: Stop Worker Before Testing**

```bash
# scripts/test_model_safely.sh
#!/bin/bash
set -e

MODEL_NAME=$1
TEST_SCRIPT=$2

echo "🛑 Stopping worker to free GPU..."
sudo systemctl stop aristotle-batch-worker

echo "⏳ Waiting for GPU to clear..."
sleep 5

echo "🧪 Running test: $TEST_SCRIPT"
python "$TEST_SCRIPT"

echo "✅ Test complete, restarting worker..."
sudo systemctl start aristotle-batch-worker

echo "✅ Worker restarted"
```

**Usage:**
```bash
bash scripts/test_model_safely.sh "OLMo 2 7B" core/tests/manual/test_olmo2_7b_single.py
```

---

### **Problem 3: No Memory Limits on Services**

**Current systemd services have no memory limits** - Can consume all RAM and trigger OOM

**Solution: Add Resource Limits**

Update `systemd/aristotle-batch-worker.service`:
```ini
[Service]
# ... existing config ...

# Memory limits (prevent OOM)
MemoryMax=24G        # Hard limit (kill if exceeded)
MemoryHigh=20G       # Soft limit (throttle if exceeded)

# CPU limits (prevent CPU starvation)
CPUQuota=400%        # Max 4 cores (adjust based on system)

# Restart on OOM
Restart=on-failure
RestartSec=30
```

Update `systemd/aristotle-batch-api.service`:
```ini
[Service]
# ... existing config ...

# Memory limits
MemoryMax=4G
MemoryHigh=3G

# Restart on failure
Restart=on-failure
RestartSec=10
```

---

### **Problem 4: No Monitoring of System Resources**

**Solution: Add Pre-Flight Checks**

Create `scripts/check_resources.sh`:
```bash
#!/bin/bash

# Check available RAM
AVAILABLE_RAM=$(free -g | awk '/^Mem:/{print $7}')
if [ "$AVAILABLE_RAM" -lt 10 ]; then
    echo "❌ Insufficient RAM: ${AVAILABLE_RAM}GB available (need 10GB+)"
    exit 1
fi

# Check GPU memory
GPU_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
if [ "$GPU_FREE" -lt 14000 ]; then
    echo "❌ Insufficient GPU memory: ${GPU_FREE}MB available (need 14GB+)"
    exit 1
fi

echo "✅ Resources OK: ${AVAILABLE_RAM}GB RAM, ${GPU_FREE}MB GPU"
```

Use in test scripts:
```python
# At start of test
import subprocess
result = subprocess.run(['bash', 'scripts/check_resources.sh'])
if result.returncode != 0:
    print("❌ Pre-flight check failed")
    sys.exit(1)
```

---

## 📋 Deployment Modes

### **Mode 1: Development (Current)**

**Use Case:** Local development, testing, experimentation

**Setup:**
```bash
# Start services manually
python -m core.batch_app.worker &
python -m uvicorn core.batch_app.api_server:app --port 4080 &

# Or use scripts
bash scripts/start_worker.sh
bash scripts/start_api_server.sh
```

**Pros:**
- ✅ Fast iteration
- ✅ Easy debugging
- ✅ No systemd setup needed

**Cons:**
- ❌ No auto-restart
- ❌ No resource limits
- ❌ Processes die on terminal close

---

### **Mode 2: Production (Systemd - RECOMMENDED)**

**Use Case:** Long-running server, production deployments, open source users

**Setup:**
```bash
# Install services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable aristotle-batch-worker
sudo systemctl enable aristotle-batch-api

# Start services
sudo systemctl start aristotle-batch-worker
sudo systemctl start aristotle-batch-api

# Check status
systemctl status aristotle-batch-worker
systemctl status aristotle-batch-api

# View logs
journalctl -u aristotle-batch-worker -f
journalctl -u aristotle-batch-api -f
```

**Pros:**
- ✅ Auto-restart on failure
- ✅ Auto-start on boot
- ✅ Resource limits (memory, CPU)
- ✅ Centralized logging (journald)
- ✅ Process isolation
- ✅ Standard Linux deployment

**Cons:**
- ⚠️ Requires sudo for management
- ⚠️ Slightly slower iteration (need to restart service)

---

### **Mode 3: Docker (NOT RECOMMENDED for vLLM)**

**Use Case:** Multi-GPU cloud deployments, Kubernetes

**Why NOT for single-GPU:**
- ❌ **GPU passthrough overhead** - Docker adds latency
- ❌ **Complex setup** - Need nvidia-docker, runtime config
- ❌ **Harder debugging** - Logs inside container
- ❌ **No benefit** - Systemd already provides isolation

**When to use Docker:**
- ✅ Multi-GPU cloud (Kubernetes, ECS)
- ✅ Horizontal scaling (multiple workers)
- ✅ Complex dependencies (many services)

---

## 🚀 Recommended Implementation Plan

### **Phase 1: Fix Immediate Issues (30 min)**

1. **Add resource limits to systemd services**
   ```bash
   # Edit systemd/aristotle-batch-worker.service
   # Add MemoryMax, MemoryHigh, CPUQuota
   
   sudo cp systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl restart aristotle-batch-worker
   ```

2. **Create safe test script**
   ```bash
   # Create scripts/test_model_safely.sh
   # Stops worker, runs test, restarts worker
   ```

3. **Add pre-flight checks**
   ```bash
   # Create scripts/check_resources.sh
   # Check RAM and GPU before tests
   ```

### **Phase 2: Improve Durability (1-2 hours)**

4. **Add maintenance mode API** (from MODEL_TESTING_ARCHITECTURE.md)
   - Pause job acceptance during tests
   - Clear user communication

5. **Add priority queue** (from MODEL_TESTING_ARCHITECTURE.md)
   - Test jobs don't block production

6. **Improve monitoring**
   - Add alerts for OOM conditions
   - Dashboard for resource usage

### **Phase 3: Documentation (1 hour)**

7. **Update README with deployment modes**
8. **Create TESTING.md guide**
9. **Add troubleshooting section**

---

## 🎯 Answer: Should We Use Docker?

**NO** - Your current architecture is correct!

**Keep:**
- ✅ vLLM worker native (systemd)
- ✅ API server native (systemd)
- ✅ Supporting services in Docker (Label Studio, Grafana, etc.)

**Fix:**
- ⚠️ Add resource limits to systemd services
- ⚠️ Stop worker before running tests
- ⚠️ Add pre-flight resource checks
- ⚠️ Use systemd for test execution (optional)

**Result:**
- ✅ Durable (systemd auto-restart)
- ✅ Fast (no Docker overhead)
- ✅ Manageable (systemd + journald)
- ✅ Production-ready (resource limits)

---

## 📝 Next Steps

1. **Implement safe test script** (10 min)
2. **Add resource limits to systemd** (10 min)
3. **Test OLMo 2 7B safely** (30 min)
4. **Add maintenance mode API** (1-2 hours)
5. **Document deployment modes** (30 min)

**Total time:** ~3 hours to production-grade durability

