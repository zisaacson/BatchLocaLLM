#!/bin/bash
#
# Stop all vLLM Batch Server services
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping vLLM Batch Server...${NC}"
echo ""

# Stop API Server
if pgrep -f "core.batch_app.api_server" > /dev/null; then
    echo -e "${YELLOW}Stopping API Server...${NC}"
    pkill -f "core.batch_app.api_server"
    sleep 2
    echo -e "${GREEN}✅ API Server stopped${NC}"
else
    echo -e "${YELLOW}API Server not running${NC}"
fi

# Stop Watchdog (this will also stop the worker)
if pgrep -f "core.batch_app.watchdog" > /dev/null; then
    echo -e "${YELLOW}Stopping Watchdog...${NC}"
    pkill -f "core.batch_app.watchdog"
    sleep 2
    echo -e "${GREEN}✅ Watchdog stopped${NC}"
else
    echo -e "${YELLOW}Watchdog not running${NC}"
fi

# Stop Worker (in case it's running standalone)
if pgrep -f "core.batch_app.worker" > /dev/null; then
    echo -e "${YELLOW}Stopping Worker...${NC}"
    pkill -f "core.batch_app.worker"
    sleep 2
    echo -e "${GREEN}✅ Worker stopped${NC}"
else
    echo -e "${YELLOW}Worker not running${NC}"
fi

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"

