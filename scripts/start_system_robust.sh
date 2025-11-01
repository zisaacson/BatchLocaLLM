#!/bin/bash
set -e

# Robust system startup script with full health checks
# This script ensures all prerequisites are met before starting services

echo "============================================================"
echo "🚀 STARTING vLLM BATCH SERVER (ROBUST MODE)"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "📁 Project root: $PROJECT_ROOT"
echo ""

# ============================================================
# STEP 1: Kill zombie processes
# ============================================================
echo "🔪 STEP 1: Killing zombie processes..."
pkill -9 -f "vllm" 2>/dev/null || true
pkill -9 -f "worker.py" 2>/dev/null || true
pkill -9 -f "uvicorn.*api_server" 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ Zombie processes killed${NC}"
echo ""

# ============================================================
# STEP 2: Check GPU is free
# ============================================================
echo "🎮 STEP 2: Checking GPU status..."
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}❌ nvidia-smi not found - GPU not available${NC}"
    exit 1
fi

GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
if [ "$GPU_MEM" -gt 1000 ]; then
    echo -e "${YELLOW}⚠️  GPU has ${GPU_MEM}MB in use - may have zombie processes${NC}"
    echo "Run: nvidia-smi to check"
else
    echo -e "${GREEN}✅ GPU is free (${GPU_MEM}MB used)${NC}"
fi
echo ""

# ============================================================
# STEP 3: Start PostgreSQL
# ============================================================
echo "🐘 STEP 3: Starting PostgreSQL..."

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    exit 1
fi

# Start PostgreSQL container
docker compose -f docker-compose.postgres.yml up -d

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker exec vllm-batch-postgres pg_isready -U vllm_batch_user > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    echo -n "."
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ PostgreSQL failed to start after ${MAX_WAIT}s${NC}"
    exit 1
fi
echo ""

# ============================================================
# STEP 4: Run database migrations
# ============================================================
echo "🔄 STEP 4: Running database migrations..."

source venv/bin/activate

# Run migrations
python3 -c "
from sqlalchemy import text
from core.batch_app.database import engine

try:
    with engine.connect() as conn:
        # Worker heartbeat columns
        try:
            conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS loaded_model VARCHAR(256)'))
            conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS model_loaded_at TIMESTAMP'))
            conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS worker_pid INTEGER'))
            conn.execute(text('ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS worker_started_at TIMESTAMP'))
        except Exception as e:
            if 'already exists' not in str(e):
                print(f'Warning: {e}')
        
        # Batch jobs progress tracking
        try:
            conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS tokens_processed BIGINT DEFAULT 0'))
            conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS current_throughput FLOAT DEFAULT 0.0'))
            conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS queue_position INTEGER'))
            conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS last_progress_update TIMESTAMP'))
            conn.execute(text('ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS estimated_completion_time TIMESTAMP'))
        except Exception as e:
            if 'already exists' not in str(e):
                print(f'Warning: {e}')
        
        conn.commit()
        print('✅ Database migrations complete')
except Exception as e:
    print(f'❌ Migration failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Database migrations failed${NC}"
    exit 1
fi
echo ""

# ============================================================
# STEP 5: Start API server
# ============================================================
echo "🌐 STEP 5: Starting API server..."

nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080 > logs/api_server.log 2>&1 &
API_PID=$!
echo "API server started with PID: $API_PID"

# Wait for API server to be ready
echo "Waiting for API server to be ready..."
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:4080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API server is ready${NC}"
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    echo -n "."
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ API server failed to start after ${MAX_WAIT}s${NC}"
    echo "Check logs: tail -f logs/api_server.log"
    exit 1
fi
echo ""

# ============================================================
# STEP 6: Start worker
# ============================================================
echo "⚙️  STEP 6: Starting worker..."

nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
WORKER_PID=$!
echo "Worker started with PID: $WORKER_PID"

# Wait for worker to register heartbeat
echo "Waiting for worker to register..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    QUEUE_STATUS=$(curl -s http://localhost:4080/v1/queue 2>/dev/null || echo '{"worker":{"status":"offline"}}')
    WORKER_STATUS=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('worker', {}).get('status', 'offline'))" 2>/dev/null || echo "offline")
    
    if [ "$WORKER_STATUS" = "online" ]; then
        echo -e "${GREEN}✅ Worker is online${NC}"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}⚠️  Worker did not come online after ${MAX_WAIT}s${NC}"
    echo "Check logs: tail -f logs/worker.log"
    echo "Worker may still be loading model..."
fi
echo ""

# ============================================================
# STEP 7: Verify system health
# ============================================================
echo "🏥 STEP 7: Verifying system health..."

# Check API server
API_HEALTH=$(curl -s http://localhost:4080/health 2>/dev/null || echo '{"status":"error"}')
API_STATUS=$(echo "$API_HEALTH" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

if [ "$API_STATUS" = "healthy" ]; then
    echo -e "${GREEN}✅ API server: healthy${NC}"
else
    echo -e "${RED}❌ API server: $API_STATUS${NC}"
fi

# Check worker
QUEUE_STATUS=$(curl -s http://localhost:4080/v1/queue 2>/dev/null || echo '{"worker":{"status":"offline"}}')
WORKER_STATUS=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('worker', {}).get('status', 'offline'))" 2>/dev/null || echo "offline")

if [ "$WORKER_STATUS" = "online" ]; then
    echo -e "${GREEN}✅ Worker: online${NC}"
else
    echo -e "${YELLOW}⚠️  Worker: $WORKER_STATUS${NC}"
fi

# Check PostgreSQL
if docker exec vllm-batch-postgres pg_isready -U vllm_batch_user > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL: ready${NC}"
else
    echo -e "${RED}❌ PostgreSQL: not ready${NC}"
fi

echo ""

# ============================================================
# SUMMARY
# ============================================================
echo "============================================================"
echo "📊 SYSTEM STATUS"
echo "============================================================"
echo ""
echo "API Server:   http://localhost:4080"
echo "Queue Monitor: http://localhost:4080/queue-monitor.html"
echo "Workbench:    http://localhost:4080/workbench.html"
echo ""
echo "Logs:"
echo "  API:    tail -f logs/api_server.log"
echo "  Worker: tail -f logs/worker.log"
echo ""
echo "Health Check:"
echo "  curl -s http://localhost:4080/health | python3 -m json.tool"
echo "  curl -s http://localhost:4080/v1/queue | python3 -m json.tool"
echo ""
echo "============================================================"
echo -e "${GREEN}✅ SYSTEM STARTUP COMPLETE${NC}"
echo "============================================================"

