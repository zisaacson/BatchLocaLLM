#!/bin/bash
# Start all vLLM Batch Server services
# This script starts the complete system in the correct order

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         vLLM Batch Server - Starting All Services         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Create logs directory
mkdir -p logs

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local name=$2
    local max_wait=30
    local count=0
    
    echo -n "   Waiting for $name to be ready..."
    while [ $count -lt $max_wait ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo -e " ${RED}✗ (timeout)${NC}"
    return 1
}

# ============================================================================
# 1. Check PostgreSQL
# ============================================================================
echo -e "${GREEN}[1/5] Checking PostgreSQL...${NC}"

if ! docker ps | grep -q postgres; then
    echo -e "${YELLOW}   PostgreSQL not running, starting...${NC}"
    docker-compose -f docker-compose.postgres.yml up -d
    sleep 5
else
    echo -e "${GREEN}   ✓ PostgreSQL already running${NC}"
fi

# ============================================================================
# 2. Start API Server
# ============================================================================
echo -e "${GREEN}[2/5] Starting API Server (port 4080)...${NC}"

if is_running "core.batch_app.api_server"; then
    echo -e "${YELLOW}   ⚠️  API Server already running${NC}"
    API_PID=$(pgrep -f "core.batch_app.api_server")
    echo -e "${YELLOW}   PID: $API_PID${NC}"
else
    nohup python -m core.batch_app.api_server > logs/api_server.log 2>&1 &
    API_PID=$!
    echo -e "${GREEN}   ✓ API Server started (PID: $API_PID)${NC}"
    wait_for_service "http://localhost:4080/health" "API Server"
fi

# ============================================================================
# 3. Start Worker (if not already running)
# ============================================================================
echo -e "${GREEN}[3/5] Checking Worker Process...${NC}"

# Check if worker is sending heartbeats
WORKER_ALIVE=$(python3 << 'EOF'
from datetime import datetime, timezone
from core.batch_app.database import get_db, WorkerHeartbeat

db = next(get_db())
worker = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()

if worker:
    last_seen = worker.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    
    now_utc = datetime.now(timezone.utc)
    age_seconds = (now_utc - last_seen).total_seconds()
    
    if age_seconds < 60:
        print("ALIVE")
    else:
        print("STALE")
else:
    print("MISSING")
EOF
)

if [ "$WORKER_ALIVE" = "ALIVE" ]; then
    echo -e "${GREEN}   ✓ Worker is alive and sending heartbeats${NC}"
else
    echo -e "${YELLOW}   ⚠️  Worker heartbeat is stale or missing${NC}"
    echo -e "${YELLOW}   Note: Worker should be running in a separate terminal${NC}"
    echo -e "${YELLOW}   To start worker: python -m core.batch_app.worker${NC}"
fi

# ============================================================================
# 4. Start Watchdog
# ============================================================================
echo -e "${GREEN}[4/5] Starting Watchdog (auto-recovery)...${NC}"

if is_running "core.batch_app.watchdog"; then
    echo -e "${YELLOW}   ⚠️  Watchdog already running${NC}"
    WATCHDOG_PID=$(pgrep -f "core.batch_app.watchdog")
    echo -e "${YELLOW}   PID: $WATCHDOG_PID${NC}"
else
    nohup python -m core.batch_app.watchdog > logs/watchdog.log 2>&1 &
    WATCHDOG_PID=$!
    echo -e "${GREEN}   ✓ Watchdog started (PID: $WATCHDOG_PID)${NC}"
    sleep 2
fi

# ============================================================================
# 5. Start Curation Web App
# ============================================================================
echo -e "${GREEN}[5/5] Starting Curation Web App (port 8001)...${NC}"

if is_running "core.curation.api"; then
    echo -e "${YELLOW}   ⚠️  Curation Web App already running${NC}"
    CURATION_PID=$(pgrep -f "core.curation.api")
    echo -e "${YELLOW}   PID: $CURATION_PID${NC}"
else
    nohup python -m core.curation.api > logs/curation_api.log 2>&1 &
    CURATION_PID=$!
    echo -e "${GREEN}   ✓ Curation Web App started (PID: $CURATION_PID)${NC}"
    wait_for_service "http://localhost:8001/health" "Curation Web App"
fi

# ============================================================================
# 6. Start Label Studio (if not running)
# ============================================================================
echo -e "${GREEN}[6/6] Checking Label Studio (port 4115)...${NC}"

if curl -s http://localhost:4115 > /dev/null 2>&1; then
    echo -e "${GREEN}   ✓ Label Studio already running${NC}"
else
    echo -e "${YELLOW}   ⚠️  Label Studio not running${NC}"
    echo -e "${YELLOW}   To start: docker-compose up -d label-studio${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    System Status                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check each service
check_service() {
    local url=$1
    local name=$2
    local port=$3
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (port $port) - ${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}✗${NC} $name (port $port) - ${RED}DOWN${NC}"
    fi
}

check_service "http://localhost:4080/health" "API Server" "4080"
check_service "http://localhost:8001/health" "Curation Web App" "8001"
check_service "http://localhost:4115" "Label Studio" "4115"

# Check worker heartbeat
WORKER_STATUS=$(python3 << 'EOF'
from datetime import datetime, timezone
from core.batch_app.database import get_db, WorkerHeartbeat

db = next(get_db())
worker = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == 1).first()

if worker:
    last_seen = worker.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    
    now_utc = datetime.now(timezone.utc)
    age_seconds = (now_utc - last_seen).total_seconds()
    
    if age_seconds < 60:
        print(f"ALIVE ({age_seconds:.1f}s ago)")
    else:
        print(f"STALE ({age_seconds:.0f}s ago)")
else:
    print("MISSING")
EOF
)

if [[ "$WORKER_STATUS" == ALIVE* ]]; then
    echo -e "${GREEN}✓${NC} Worker Process - ${GREEN}$WORKER_STATUS${NC}"
else
    echo -e "${RED}✗${NC} Worker Process - ${RED}$WORKER_STATUS${NC}"
fi

# Check watchdog
if is_running "core.batch_app.watchdog"; then
    echo -e "${GREEN}✓${NC} Watchdog - ${GREEN}RUNNING${NC}"
else
    echo -e "${RED}✗${NC} Watchdog - ${RED}DOWN${NC}"
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Access URLs                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}•${NC} API Server:        http://localhost:4080"
echo -e "  ${GREEN}•${NC} Curation Web App:  http://localhost:8001"
echo -e "  ${GREEN}•${NC} Label Studio:      http://localhost:4115"
echo -e "  ${GREEN}•${NC} Model Management:  http://localhost:8001/model-management.html"
echo -e "  ${GREEN}•${NC} Dataset Workbench: http://localhost:8001/workbench.html"
echo -e "  ${GREEN}•${NC} Fine-Tuning:       http://localhost:8001/fine-tuning.html"
echo -e "  ${GREEN}•${NC} Settings:          http://localhost:8001/settings.html"
echo ""
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo -e "  • API Server:      tail -f logs/api_server.log"
echo -e "  • Watchdog:        tail -f logs/watchdog.log"
echo -e "  • Curation API:    tail -f logs/curation_api.log"
echo -e "  • Worker:          tail -f logs/worker.log"
echo ""

