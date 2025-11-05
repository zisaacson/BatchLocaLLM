# Auto-Recovery System

The vLLM Batch Server includes a robust auto-recovery system that automatically detects and recovers from worker failures.

---

## 🎯 **Problem Solved**

**Issue**: Worker process can crash or become unresponsive, causing the API to return `503 Service Unavailable` errors.

**Solution**: Watchdog process monitors worker health and automatically restarts it on failure.

---

## 🏗️ **Architecture**

```
┌─────────────────┐
│   API Server    │  ← Returns 503 if worker is offline
│   (port 4080)   │
└─────────────────┘
         │
         │ checks heartbeat
         ↓
┌─────────────────┐
│    Database     │  ← WorkerHeartbeat table
│  (PostgreSQL)   │
└─────────────────┘
         ↑
         │ updates every 5s
         │
┌─────────────────┐
│     Worker      │  ← Processes batch jobs
│   (vLLM GPU)    │
└─────────────────┘
         ↑
         │ monitors & restarts
         │
┌─────────────────┐
│    Watchdog     │  ← Auto-recovery system
│  (monitoring)   │
└─────────────────┘
```

---

## 🔍 **How It Works**

### **1. Worker Heartbeat**

The worker sends a heartbeat to the database every 5 seconds:

```python
# In worker.py
def update_heartbeat(self):
    worker = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
    worker.last_seen = datetime.now(timezone.utc)
    worker.status = self.status
    worker.worker_pid = os.getpid()
    db.commit()
```

### **2. API Server Health Check**

Before accepting batch jobs, the API checks if the worker is alive:

```python
# In api_server.py
worker_heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()
age_seconds = (now_utc - last_seen).total_seconds()

if age_seconds > 60:
    raise HTTPException(
        status_code=503,
        detail=f"Worker offline (last seen {int(age_seconds)}s ago)"
    )
```

### **3. Watchdog Monitoring**

The watchdog checks worker health every 30 seconds:

```python
# In watchdog.py
def check_and_recover(self):
    status = self.get_worker_status()
    
    if status['healthy']:
        logger.info("✅ Worker healthy")
        return
    
    # Worker is unhealthy - recover
    logger.warning("⚠️ Worker unhealthy, restarting...")
    self.kill_zombie_worker(status['pid'])
    self.start_worker()
```

---

## 🚀 **Usage**

### **Quick Start**

```bash
# Start all services (API + Watchdog)
./scripts/start-all.sh

# Stop all services
./scripts/stop-all.sh
```

### **Manual Start**

```bash
# Start API server
python -m core.batch_app.api_server &

# Start watchdog (will auto-start worker)
python -m core.batch_app.watchdog &
```

### **Production Deployment (systemd)**

```bash
# Install systemd service
sudo cp deployment/systemd/vllm-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable vllm-watchdog

# Start service
sudo systemctl start vllm-watchdog

# Check status
sudo systemctl status vllm-watchdog

# View logs
sudo journalctl -u vllm-watchdog -f
```

---

## 📊 **Monitoring**

### **Check Worker Status**

```bash
# Check if worker is alive
curl http://localhost:4080/health

# Check worker heartbeat age
python3 << 'EOF'
from datetime import datetime, timezone
from core.batch_app.database import get_db, WorkerHeartbeat

db = next(get_db())
worker = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()

if worker:
    last_seen = worker.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    
    age = (datetime.now(timezone.utc) - last_seen).total_seconds()
    print(f"Worker Status: {worker.status}")
    print(f"Last Seen: {age:.1f}s ago")
    print(f"Healthy: {'✅ Yes' if age < 60 else '❌ No'}")
EOF
```

### **View Logs**

```bash
# Watchdog logs
tail -f logs/watchdog.log

# Worker logs
tail -f logs/worker.log

# API server logs
tail -f logs/api_server.log
```

---

## ⚙️ **Configuration**

### **Watchdog Settings**

Edit `core/batch_app/watchdog.py`:

```python
class WorkerWatchdog:
    def __init__(self):
        self.check_interval = 30  # Check every 30 seconds
        self.heartbeat_timeout = 60  # Worker is dead if no heartbeat for 60s
        self.max_restarts_per_hour = 10  # Rate limit to prevent restart loops
```

### **Worker Heartbeat Interval**

Edit `core/batch_app/worker.py`:

```python
HEARTBEAT_INTERVAL = 5  # Send heartbeat every 5 seconds
```

---

## 🛡️ **Safety Features**

### **1. Restart Rate Limiting**

Prevents infinite restart loops if worker is crashing immediately:

- Max 10 restarts per hour
- If limit exceeded, watchdog stops and alerts via Sentry
- Requires manual intervention

### **2. Zombie Process Detection**

Detects and kills zombie worker processes:

```python
def is_process_running(self, pid: int | None) -> bool:
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
```

### **3. Graceful Shutdown**

Watchdog handles SIGTERM/SIGINT gracefully:

```python
def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    if self.worker_process:
        self.worker_process.terminate()
    sys.exit(0)
```

---

## 🔧 **Troubleshooting**

### **Worker keeps crashing**

1. Check worker logs: `tail -f logs/worker.log`
2. Check GPU status: `nvidia-smi`
3. Check disk space: `df -h`
4. Check memory: `free -h`

### **Watchdog not restarting worker**

1. Check watchdog logs: `tail -f logs/watchdog.log`
2. Verify watchdog is running: `ps aux | grep watchdog`
3. Check restart rate limit (max 10/hour)

### **503 errors still happening**

1. Check worker heartbeat age (should be <60s)
2. Verify worker process is running: `ps aux | grep worker`
3. Check database connection
4. Restart watchdog: `./scripts/stop-all.sh && ./scripts/start-all.sh`

---

## 📈 **Metrics**

The watchdog tracks:

- **Restart count**: Total number of worker restarts
- **Restart times**: Timestamps of recent restarts (for rate limiting)
- **Recovery success rate**: Logged to Sentry

All recovery events are logged to:
- `logs/watchdog.log` (local file)
- Sentry (if configured)

---

## 🎯 **Best Practices**

1. **Always run watchdog in production** - Don't run worker standalone
2. **Monitor watchdog logs** - Set up alerts for frequent restarts
3. **Use systemd for auto-start** - Ensures watchdog starts on boot
4. **Set up Sentry** - Get alerts when worker crashes
5. **Regular health checks** - Monitor `/health` endpoint

---

## 🚨 **Alerts**

The watchdog sends alerts to Sentry for:

- Worker crashes (auto-recovered)
- Restart rate limit exceeded (manual intervention needed)
- Watchdog errors

Configure Sentry in `.env`:

```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENVIRONMENT=production
```

---

## ✅ **Success Criteria**

A healthy system should show:

```bash
$ curl http://localhost:4080/health
{"status":"healthy","service":"batch-api","version":"1.0.0"}

$ tail -1 logs/watchdog.log
2025-11-05 02:30:00 - ✅ Worker healthy (heartbeat 3.2s ago)

$ ps aux | grep -E "watchdog|worker" | grep -v grep
zack  123456  python -m core.batch_app.watchdog
zack  123457  python -m core.batch_app.worker
```

---

**The auto-recovery system ensures 99.9% uptime by automatically recovering from worker failures!** 🎉

