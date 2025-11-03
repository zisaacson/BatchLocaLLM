#!/bin/bash
# =============================================================================
# Stop vLLM Batch Server Services
# =============================================================================
#
# This script stops all native Python services:
# - API Server
# - Worker
# - ML Backend
#
# Usage:
#   ./scripts/stop-services.sh
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping vLLM Batch Server Services...${NC}"
echo ""

# Find and kill API Server
API_PID=$(pgrep -f "python -m core.batch_app.api_server" || true)
if [ -n "$API_PID" ]; then
    echo -e "${YELLOW}Stopping API Server (PID: $API_PID)...${NC}"
    kill $API_PID
    echo -e "${GREEN}API Server stopped${NC}"
else
    echo -e "${BLUE}API Server not running${NC}"
fi

# Find and kill Worker
WORKER_PID=$(pgrep -f "python -m core.batch_app.worker" || true)
if [ -n "$WORKER_PID" ]; then
    echo -e "${YELLOW}Stopping Worker (PID: $WORKER_PID)...${NC}"
    kill $WORKER_PID
    echo -e "${GREEN}Worker stopped${NC}"
else
    echo -e "${BLUE}Worker not running${NC}"
fi

# Find and kill ML Backend
ML_PID=$(pgrep -f "python -m core.label_studio_ml_backend" || true)
if [ -n "$ML_PID" ]; then
    echo -e "${YELLOW}Stopping ML Backend (PID: $ML_PID)...${NC}"
    kill $ML_PID
    echo -e "${GREEN}ML Backend stopped${NC}"
else
    echo -e "${BLUE}ML Backend not running${NC}"
fi

echo ""
echo -e "${GREEN}All services stopped!${NC}"

