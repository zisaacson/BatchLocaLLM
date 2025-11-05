#!/bin/bash
#
# Start all vLLM Batch Server services
#
# This script starts:
# 1. API Server (port 4080)
# 2. Worker Watchdog (auto-restarts worker on failure)
# 3. Curation Web App (port 8001)
#
# The watchdog will automatically start and monitor the worker process.
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${GREEN}🚀 Starting vLLM Batch Server...${NC}"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if services are already running
if pgrep -f "core.batch_app.api_server" > /dev/null; then
    echo -e "${YELLOW}⚠️  API Server already running${NC}"
else
    echo -e "${GREEN}📡 Starting API Server (port 4080)...${NC}"
    nohup python -m core.batch_app.api_server > logs/api_server.log 2>&1 &
    API_PID=$!
    echo "   PID: $API_PID"
    sleep 2
    
    # Verify it started
    if ps -p $API_PID > /dev/null; then
        echo -e "${GREEN}   ✅ API Server started successfully${NC}"
    else
        echo -e "${RED}   ❌ API Server failed to start${NC}"
        echo "   Check logs/api_server.log for details"
        exit 1
    fi
fi

echo ""

# Check if watchdog is already running
if pgrep -f "core.batch_app.watchdog" > /dev/null; then
    echo -e "${YELLOW}⚠️  Watchdog already running${NC}"
else
    echo -e "${GREEN}🐕 Starting Worker Watchdog...${NC}"
    nohup python -m core.batch_app.watchdog > logs/watchdog.log 2>&1 &
    WATCHDOG_PID=$!
    echo "   PID: $WATCHDOG_PID"
    sleep 2
    
    # Verify it started
    if ps -p $WATCHDOG_PID > /dev/null; then
        echo -e "${GREEN}   ✅ Watchdog started successfully${NC}"
        echo "   The watchdog will automatically start and monitor the worker"
    else
        echo -e "${RED}   ❌ Watchdog failed to start${NC}"
        echo "   Check logs/watchdog.log for details"
        exit 1
    fi
fi

echo ""

# Check if curation API is already running
if pgrep -f "core.curation.api" > /dev/null; then
    echo -e "${YELLOW}⚠️  Curation Web App already running${NC}"
else
    echo -e "${GREEN}🌐 Starting Curation Web App (port 8001)...${NC}"
    nohup python -m core.curation.api > logs/curation_api.log 2>&1 &
    CURATION_PID=$!
    echo "   PID: $CURATION_PID"
    sleep 3

    # Verify it started
    if ps -p $CURATION_PID > /dev/null; then
        echo -e "${GREEN}   ✅ Curation Web App started successfully${NC}"
    else
        echo -e "${RED}   ❌ Curation Web App failed to start${NC}"
        echo "   Check logs/curation_api.log for details"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ All services started!${NC}"
echo ""
echo "Services:"
echo "  - Main UI:         http://localhost:8001"
echo "  - API Server:      http://localhost:4080"
echo "  - Health:          http://localhost:4080/health"
echo "  - Label Studio:    http://localhost:4115"
echo ""
echo "Logs:"
echo "  - API Server:      tail -f logs/api_server.log"
echo "  - Watchdog:        tail -f logs/watchdog.log"
echo "  - Worker:          tail -f logs/worker.log"
echo "  - Curation API:    tail -f logs/curation_api.log"
echo ""
echo "To stop all services:"
echo "  ./scripts/stop-all.sh"
echo ""

