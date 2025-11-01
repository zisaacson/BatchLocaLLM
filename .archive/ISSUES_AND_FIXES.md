# Issues and Fixes - vLLM Batch Server

## Critical Issues Encountered

### 1. **PostgreSQL Not Running**
**Symptom**: All database operations hang indefinitely
- `psql` commands hang
- `docker ps` hangs
- Python database connections timeout
- API server hangs on startup
- Worker hangs on startup

**Root Cause**: PostgreSQL Docker container not started

**Fix**:
```bash
# Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d

# Verify it's running
docker ps | grep postgres

# Test connection
psql postgresql://vllm_batch_user:vllm_batch_password_dev@localhost:5432/vllm_batch -c "SELECT 1"
```

**Prevention**: Add PostgreSQL health check to startup scripts

---

### 2. **Missing Database Columns**
**Symptom**: `/v1/queue` endpoint returns 500 error with `AttributeError: 'WorkerHeartbeat' object has no attribute 'loaded_model'`

**Root Cause**: Database schema out of sync with code - missing columns:
- `worker_heartbeat.loaded_model`
- `worker_heartbeat.model_loaded_at`
- `worker_heartbeat.worker_pid`
- `worker_heartbeat.worker_started_at`
- `batch_jobs.tokens_processed`
- `batch_jobs.current_throughput`
- `batch_jobs.queue_position`
- `batch_jobs.last_progress_update`
- `batch_jobs.estimated_completion_time`

**Fix**:
```bash
# Run migrations
python3 scripts/migrate_worker_heartbeat.py
python3 scripts/migrate_add_progress_tracking.py

# Or manually add columns
python3 -c "
from sqlalchemy import text
from core.batch_app.database import engine

with engine.connect() as conn:
    # Worker heartbeat columns
    conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS loaded_model VARCHAR(256)'))
    conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS model_loaded_at TIMESTAMP'))
    conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS worker_pid INTEGER'))
    conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS worker_started_at TIMESTAMP'))
    
    # Batch jobs progress tracking
    conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS tokens_processed BIGINT DEFAULT 0'))
    conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS current_throughput FLOAT DEFAULT 0.0'))
    conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS queue_position INTEGER'))
    conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS last_progress_update TIMESTAMP'))
    conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS estimated_completion_time TIMESTAMP'))
    
    conn.commit()
    print('✅ All columns added')
"
```

**Prevention**: 
- Add database schema version tracking
- Run migrations automatically on startup
- Add health check that validates schema

---

### 3. **API Server Not Starting**
**Symptom**: 
- Port 4080 not responding
- `curl http://localhost:4080/health` hangs
- Queue monitor shows "Error fetching data"

**Root Cause**: API server not running OR hanging on PostgreSQL connection

**Fix**:
```bash
# Kill any existing API server
pkill -f "uvicorn.*api_server"

# Start API server (after PostgreSQL is running!)
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server
source venv/bin/activate
nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080 > logs/api_server.log 2>&1 &

# Wait and verify
sleep 5
curl -s http://localhost:4080/health | python3 -m json.tool
```

**Prevention**: 
- Add startup script that checks PostgreSQL first
- Add timeout to database connections
- Add health check endpoint that doesn't require database

---

### 4. **Worker Offline / Not Updating Heartbeat**
**Symptom**: API returns "Worker offline (last seen 677s ago). Cannot accept jobs."

**Root Cause**: 
- Worker not running
- Worker crashed
- Worker heartbeat not updating (database connection issue)

**Fix**:
```bash
# Check if worker is running
ps aux | grep "python.*worker" | grep -v grep

# Kill zombie workers
pkill -9 -f "worker.py"

# Start worker (after PostgreSQL is running!)
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server
source venv/bin/activate
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &

# Monitor startup
tail -f logs/worker.log
```

**Prevention**:
- Add worker process monitoring
- Add automatic restart on crash
- Add heartbeat failure alerts

---

### 5. **GGUF Models Not Supported**
**Symptom**: 
- OLMo 2 7B GGUF: "GGUF model with architecture olmo2 is not supported yet"
- GPT-OSS 20B GGUF: "np.uint32(39) is not a valid GGMLQuantizationType"

**Root Cause**: vLLM 0.11.0 has limited GGUF support
- OLMo2 architecture not implemented in GGUF loader
- GPT-OSS GGUF file uses unsupported quantization type

**Fix**: Use FP16 models with CPU offload instead
```python
# OLMo 2 7B FP16 with 8GB CPU offload
model_id = "allenai/OLMo-2-1124-7B-Instruct"
cpu_offload_gb = 8.0

# GPT-OSS 20B FP16 with 25GB CPU offload
model_id = "openai/gpt-oss-20b"
cpu_offload_gb = 25.0
```

**Alternative**: Use llama.cpp for GGUF models (better GGUF support)

**Prevention**: Test GGUF compatibility before downloading large models

---

### 6. **Benchmark Jobs Blocking Conquest System**
**Symptom**: Can't test conquest system because worker is processing 5K benchmark

**Root Cause**: Worker processes jobs sequentially - benchmark blocks all other requests

**Fix**:
```bash
# Cancel all running/queued batches
curl -s http://localhost:4080/v1/batches | python3 -c "
import sys, json
data = json.load(sys)
for batch in data['data']:
    if batch['status'] in ['in_progress', 'queued', 'validating']:
        batch_id = batch['id']
        print(f'Cancelling {batch_id}...')
        import subprocess
        subprocess.run(['curl', '-s', '-X', 'POST', f'http://localhost:4080/v1/batches/{batch_id}/cancel'])
"

# Kill worker to stop current job
pkill -9 -f "worker.py|vllm"

# Restart worker
python -m core.batch_app.worker > logs/worker.log 2>&1 &
```

**Prevention**:
- Add priority queue (conquest requests > benchmarks)
- Add job cancellation UI
- Add "pause benchmarks" mode

---

## System Startup Checklist

**Before starting the system, verify:**

1. ✅ **PostgreSQL is running**
   ```bash
   docker compose -f docker-compose.postgres.yml up -d
   docker ps | grep postgres
   ```

2. ✅ **Database schema is up to date**
   ```bash
   python3 scripts/migrate_worker_heartbeat.py
   python3 scripts/migrate_add_progress_tracking.py
   ```

3. ✅ **No zombie processes**
   ```bash
   pkill -9 -f "vllm|worker.py|uvicorn.*api_server"
   nvidia-smi  # Verify GPU is free
   ```

4. ✅ **Start API server**
   ```bash
   nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080 > logs/api_server.log 2>&1 &
   sleep 5
   curl -s http://localhost:4080/health
   ```

5. ✅ **Start worker**
   ```bash
   nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
   sleep 10
   tail -f logs/worker.log  # Verify startup
   ```

6. ✅ **Verify system is ready**
   ```bash
   curl -s http://localhost:4080/v1/queue | python3 -m json.tool
   # Should show worker online, no jobs running
   ```

---

## Quick Recovery Commands

**System completely broken? Start fresh:**
```bash
# 1. Kill everything
pkill -9 -f "vllm|worker|uvicorn|postgres"
docker compose -f docker-compose.postgres.yml down

# 2. Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d
sleep 5

# 3. Run migrations
python3 scripts/migrate_worker_heartbeat.py
python3 scripts/migrate_add_progress_tracking.py

# 4. Start services
./scripts/start_all.sh

# 5. Verify
curl -s http://localhost:4080/health
curl -s http://localhost:4080/v1/queue
```

---

## Known Limitations

1. **No horizontal scaling** - Single worker, single GPU
2. **No authentication** - Local development only
3. **Sequential job processing** - One job at a time
4. **Limited GGUF support** - Use FP16 models instead
5. **No automatic recovery** - Manual restart required on crashes
6. **Database migrations manual** - No automatic schema updates

---

## Future Improvements

1. **Add PostgreSQL health check to startup**
2. **Add automatic database migrations**
3. **Add worker process monitoring/restart**
4. **Add priority queue for conquest vs benchmark jobs**
5. **Add job cancellation UI**
6. **Add "pause benchmarks" mode**
7. **Add better error messages when PostgreSQL is down**
8. **Add timeout to database connections**
9. **Add schema version tracking**
10. **Add integration tests for full system startup**

