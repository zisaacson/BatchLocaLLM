# 🛠️ System Management Guide

Quick reference for managing the vLLM Batch Server when things go wrong.

---

## 🚨 Common Issues

### **Issue: Models won't load / Worker is stuck**

**Symptoms:**
- Jobs stay in "queued" status
- Worker logs show errors
- GPU memory is full

**Solution:**
```bash
# Option 1: Use the restart script
./scripts/restart_server.sh

# Option 2: Use the admin panel
# Open http://localhost:4080/admin
# Click "Clear GPU Memory"
```

---

### **Issue: Server is not responding**

**Symptoms:**
- Can't access http://localhost:4080
- API returns connection errors

**Solution:**
```bash
# Check if processes are running
./scripts/status_server.sh

# If not running, start them
./scripts/restart_server.sh
```

---

### **Issue: Multiple workers running (causes OOM)**

**Symptoms:**
- GPU runs out of memory
- Worker crashes repeatedly
- Multiple worker processes in `ps aux`

**Solution:**
```bash
# Stop all processes
./scripts/stop_server.sh

# Wait 5 seconds
sleep 5

# Start fresh
./scripts/restart_server.sh
```

---

## 🎯 Quick Commands

### **Check Status**
```bash
./scripts/status_server.sh
```

Shows:
- ✅/❌ API Server status
- ✅/❌ Worker status
- GPU memory usage
- Current jobs in queue
- Available models

---

### **Restart Everything**
```bash
./scripts/restart_server.sh
```

This will:
1. Kill all existing processes
2. Clear GPU memory
3. Start API server
4. Start worker
5. Verify everything is healthy

**Takes ~15 seconds**

---

### **Stop Everything**
```bash
./scripts/stop_server.sh
```

Stops all vLLM Batch Server processes.

---

### **View Logs**
```bash
# API server logs
tail -f logs/api_server.log

# Worker logs
tail -f logs/worker.log

# Last 50 lines of worker logs
tail -50 logs/worker.log
```

---

## 🌐 Web Interfaces

### **Admin Panel** (NEW!)
```
http://localhost:4080/admin
```

Features:
- ✅ View process status (API server, worker)
- ✅ View GPU status (memory, temperature, utilization)
- ✅ View job queue
- ✅ **Restart worker** (one click)
- ✅ **Clear GPU memory** (one click)
- ✅ Auto-refreshes every 5 seconds

**Use this when models fail to load!**

---

### **Queue Monitor**
```
http://localhost:4080/queue-monitor.html
```

Features:
- View all jobs in queue
- See job progress
- Check job status
- View throughput metrics

---

### **API Documentation**
```
http://localhost:4080/docs
```

Interactive API documentation (Swagger UI)

---

## 🔧 API Endpoints for Remote Management

### **Restart Worker**
```bash
curl -X POST http://localhost:4080/admin/system/restart-worker
```

Response:
```json
{
  "status": "success",
  "message": "Killed 1 worker process(es). Process manager should restart it.",
  "pids": ["12345"]
}
```

---

### **Clear GPU Memory**
```bash
curl -X POST http://localhost:4080/admin/system/clear-gpu-memory
```

Response:
```json
{
  "status": "success",
  "message": "GPU memory cleared. Worker will restart automatically.",
  "pids": ["12345"],
  "note": "Wait 10-15 seconds for worker to restart and load models"
}
```

**Wait 15 seconds after calling this before submitting new jobs!**

---

### **Get System Status**
```bash
curl http://localhost:4080/admin/system/status | jq
```

Response:
```json
{
  "processes": {
    "api_server": {
      "running": true,
      "pids": ["99174"]
    },
    "worker": {
      "running": true,
      "pids": ["99374"]
    }
  },
  "gpu": {
    "memory_used_mb": 14302,
    "memory_total_mb": 16376,
    "memory_percent": 87.3,
    "temperature_c": 65,
    "utilization_percent": 45
  },
  "timestamp": "2025-11-01T20:30:00Z"
}
```

---

## 🚀 Integration with Your App

### **Python Example**

```python
import httpx

client = httpx.Client(base_url="http://localhost:4080")

# Check if server is healthy
health = client.get("/health").json()
if health["status"] != "healthy":
    # Restart worker
    result = client.post("/admin/system/restart-worker").json()
    print(f"Restarted worker: {result['message']}")
    
    # Wait for worker to come back
    import time
    time.sleep(15)

# Now submit your job
response = client.post("/v1/batches", json={
    "input_file_id": "file-xxx",
    "endpoint": "/v1/chat/completions"
})
```

---

### **TypeScript Example**

```typescript
const client = axios.create({
  baseURL: 'http://localhost:4080'
});

// Check health
const health = await client.get('/health');
if (health.data.status !== 'healthy') {
  // Restart worker
  await client.post('/admin/system/restart-worker');
  
  // Wait for worker
  await new Promise(resolve => setTimeout(resolve, 15000));
}

// Submit job
const batch = await client.post('/v1/batches', {
  input_file_id: 'file-xxx',
  endpoint: '/v1/chat/completions'
});
```

---

## 📊 Monitoring GPU Health

### **Check GPU Memory**
```bash
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits
```

Output: `14302, 16376` (used MB, total MB)

---

### **Check GPU Temperature**
```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

Output: `65` (degrees Celsius)

---

### **Watch GPU in Real-Time**
```bash
watch -n 1 nvidia-smi
```

Updates every second.

---

## 🔥 Emergency Procedures

### **Server is completely frozen**

```bash
# Nuclear option: kill everything
pkill -9 -f "python -m uvicorn core.batch_app.api_server"
pkill -9 -f "python -m core.batch_app.worker"

# Wait for GPU to clear
sleep 5

# Restart
./scripts/restart_server.sh
```

---

### **GPU is out of memory**

```bash
# Check what's using GPU
nvidia-smi

# Kill all Python processes
pkill -9 python

# Wait for GPU to clear
sleep 5

# Restart server
./scripts/restart_server.sh
```

---

### **Database is locked**

```bash
# Stop server
./scripts/stop_server.sh

# Check for zombie connections
ps aux | grep postgres

# Restart PostgreSQL (if using Docker)
docker restart aristotle-postgres

# Restart server
./scripts/restart_server.sh
```

---

## 📞 Getting Help

### **Check Logs First**

```bash
# Worker logs (most common issues)
tail -100 logs/worker.log

# API server logs
tail -100 logs/api_server.log

# System logs (if using systemd)
journalctl -u aristotle-batch-api -n 100
```

---

### **Common Error Messages**

**"CUDA out of memory"**
- Solution: Clear GPU memory via admin panel or restart worker

**"Model not found"**
- Solution: Check available models at http://localhost:4080/v1/models

**"Database connection failed"**
- Solution: Check if PostgreSQL is running

**"Worker not responding"**
- Solution: Restart worker via admin panel

---

## ✅ Health Check Checklist

Before submitting a job, verify:

1. ✅ API server is running: `curl http://localhost:4080/health`
2. ✅ Worker is running: `./scripts/status_server.sh`
3. ✅ GPU has free memory: `nvidia-smi`
4. ✅ Models are loaded: `curl http://localhost:4080/v1/models`
5. ✅ Database is accessible: Check `/health` endpoint

---

## 🎓 Best Practices

1. **Use the admin panel** - Easiest way to restart worker when models fail
2. **Check logs** - Always check logs before restarting
3. **Wait after restart** - Give worker 15 seconds to load models
4. **Monitor GPU** - Keep an eye on GPU memory usage
5. **One worker only** - Never run multiple workers (causes OOM)

---

## 📝 Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│  vLLM Batch Server - Quick Reference           │
├─────────────────────────────────────────────────┤
│  Admin Panel:    http://localhost:4080/admin   │
│  Queue Monitor:  http://localhost:4080/queue   │
│  API Docs:       http://localhost:4080/docs    │
├─────────────────────────────────────────────────┤
│  Restart:        ./scripts/restart_server.sh   │
│  Status:         ./scripts/status_server.sh    │
│  Stop:           ./scripts/stop_server.sh      │
├─────────────────────────────────────────────────┤
│  API Restart:    POST /admin/system/restart-worker │
│  Clear GPU:      POST /admin/system/clear-gpu-memory │
│  System Status:  GET /admin/system/status      │
└─────────────────────────────────────────────────┘
```

---

**For your main engineer:** Bookmark http://localhost:4080/admin and use it when models fail to load!

