#!/bin/bash
# =============================================================================
# Start vLLM Batch Server Services
# =============================================================================
#
# This script starts all native Python services that need GPU access:
# - API Server (port 4080)
# - Worker (background)
# - ML Backend (port 4082)
#
# Usage:
#   ./scripts/start-services.sh
#   ./scripts/start-services.sh --no-worker  # Skip worker (for testing)
#   ./scripts/start-services.sh --no-ml      # Skip ML Backend
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
START_WORKER=true
START_ML_BACKEND=true

for arg in "$@"; do
    case $arg in
        --no-worker)
            START_WORKER=false
            shift
            ;;
        --no-ml)
            START_ML_BACKEND=false
            shift
            ;;
        --help)
            echo "Usage: $0 [--no-worker] [--no-ml]"
            echo ""
            echo "Options:"
            echo "  --no-worker    Skip starting the worker"
            echo "  --no-ml        Skip starting the ML Backend"
            echo "  --help         Show this help message"
            exit 0
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found at venv/bin/activate${NC}"
    echo -e "${YELLOW}Run: python -m venv venv && source venv/bin/activate && pip install -e .${NC}"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Check if services are already running
echo -e "${BLUE}Checking for existing services...${NC}"

API_PID=$(pgrep -f "python -m core.batch_app.api_server" || true)
WORKER_PID=$(pgrep -f "python -m core.batch_app.worker" || true)
ML_PID=$(pgrep -f "python -m core.label_studio_ml_backend" || true)

if [ -n "$API_PID" ]; then
    echo -e "${YELLOW}API Server already running (PID: $API_PID)${NC}"
    echo -e "${YELLOW}Kill it with: kill $API_PID${NC}"
    exit 1
fi

if [ -n "$WORKER_PID" ] && [ "$START_WORKER" = true ]; then
    echo -e "${YELLOW}Worker already running (PID: $WORKER_PID)${NC}"
    echo -e "${YELLOW}Kill it with: kill $WORKER_PID${NC}"
    exit 1
fi

if [ -n "$ML_PID" ] && [ "$START_ML_BACKEND" = true ]; then
    echo -e "${YELLOW}ML Backend already running (PID: $ML_PID)${NC}"
    echo -e "${YELLOW}Kill it with: kill $ML_PID${NC}"
    exit 1
fi

# Wait for PostgreSQL to be ready
echo -e "${BLUE}Waiting for PostgreSQL to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:4080/health > /dev/null 2>&1; then
        echo -e "${GREEN}PostgreSQL is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}PostgreSQL not ready after 30 seconds${NC}"
        echo -e "${YELLOW}Make sure Docker services are running: docker compose -f docker/docker-compose.yml up -d${NC}"
        exit 1
    fi
    sleep 1
done

# Start API Server
echo -e "${BLUE}Starting API Server (port 4080)...${NC}"
PYTHONPATH="$PROJECT_ROOT" nohup python -m core.batch_app.api_server > logs/api_server.log 2>&1 &
API_PID=$!
echo -e "${GREEN}API Server started (PID: $API_PID)${NC}"

# Wait for API Server to be ready
echo -e "${BLUE}Waiting for API Server to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:4080/health > /dev/null 2>&1; then
        echo -e "${GREEN}API Server is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}API Server not ready after 30 seconds${NC}"
        echo -e "${YELLOW}Check logs: tail -f logs/api_server.log${NC}"
        exit 1
    fi
    sleep 1
done

# Start Worker
if [ "$START_WORKER" = true ]; then
    echo -e "${BLUE}Starting Worker...${NC}"
    PYTHONPATH="$PROJECT_ROOT" nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
    WORKER_PID=$!
    echo -e "${GREEN}Worker started (PID: $WORKER_PID)${NC}"
    
    # Wait for worker to be ready
    echo -e "${BLUE}Waiting for Worker to be ready...${NC}"
    sleep 5
    
    # Check worker heartbeat
    HEARTBEAT=$(curl -s http://localhost:4080/health | jq -r '.worker_heartbeat // "unknown"')
    if [ "$HEARTBEAT" != "unknown" ]; then
        echo -e "${GREEN}Worker is ready!${NC}"
    else
        echo -e "${YELLOW}Worker may still be starting up...${NC}"
        echo -e "${YELLOW}Check logs: tail -f logs/worker.log${NC}"
    fi
fi

# Start ML Backend
if [ "$START_ML_BACKEND" = true ]; then
    echo -e "${BLUE}Starting ML Backend (port 4082)...${NC}"
    PYTHONPATH="$PROJECT_ROOT" nohup python -m core.label_studio_ml_backend > logs/ml_backend.log 2>&1 &
    ML_PID=$!
    echo -e "${GREEN}ML Backend started (PID: $ML_PID)${NC}"
    
    # Wait for ML Backend to be ready
    echo -e "${BLUE}Waiting for ML Backend to be ready...${NC}"
    for i in {1..30}; do
        if curl -s http://localhost:4082/ > /dev/null 2>&1; then
            echo -e "${GREEN}ML Backend is ready!${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${YELLOW}ML Backend not ready after 30 seconds${NC}"
            echo -e "${YELLOW}Check logs: tail -f logs/ml_backend.log${NC}"
        fi
        sleep 1
    done
fi

# Print summary
echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}vLLM Batch Server Services Started!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  API Server:  http://localhost:4080 (PID: $API_PID)"
if [ "$START_WORKER" = true ]; then
    echo -e "  Worker:      Running in background (PID: $WORKER_PID)"
fi
if [ "$START_ML_BACKEND" = true ]; then
    echo -e "  ML Backend:  http://localhost:4082 (PID: $ML_PID)"
fi
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  tail -f logs/api_server.log"
if [ "$START_WORKER" = true ]; then
    echo -e "  tail -f logs/worker.log"
fi
if [ "$START_ML_BACKEND" = true ]; then
    echo -e "  tail -f logs/ml_backend.log"
fi
echo ""
echo -e "${BLUE}Stop services:${NC}"
echo -e "  kill $API_PID"
if [ "$START_WORKER" = true ]; then
    echo -e "  kill $WORKER_PID"
fi
if [ "$START_ML_BACKEND" = true ]; then
    echo -e "  kill $ML_PID"
fi
echo ""
echo -e "${BLUE}Or use:${NC}"
echo -e "  ./scripts/stop-services.sh"
echo ""
echo -e "${GREEN}==============================================================================${NC}"

