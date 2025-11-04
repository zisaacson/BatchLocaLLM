#!/bin/bash
# =============================================================================
# Curation API Startup Script
# =============================================================================
#
# Starts the Conquest Curation API server on port 8001
# Integrates Label Studio with vLLM batch server for conquest annotation
#
# USAGE:
#   ./scripts/run-curation-api.sh
#
# REQUIREMENTS:
#   - Label Studio running on port 4115
#   - vLLM Batch Server database running on port 4332
#   - Python environment with dependencies installed
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo -e "Conquest Curation API - Startup"
echo -e "==========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo -e "${RED}❌ Error: Must run from vllm-batch-server root directory${NC}"
    echo -e "${YELLOW}   cd ~/Documents/augment-projects/Local/vllm-batch-server${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}   Copy .env.example to .env and configure:${NC}"
    echo -e "${YELLOW}   - LABEL_STUDIO_URL=http://10.0.0.223:4115${NC}"
    echo -e "${YELLOW}   - LABEL_STUDIO_API_KEY=<your-token>${NC}"
    exit 1
fi

# Source environment variables
source .env

# Check if Label Studio is accessible
echo -e "${BLUE}Checking Label Studio connection...${NC}"
if curl -s -f -o /dev/null -w "%{http_code}" "${LABEL_STUDIO_URL:-http://10.0.0.223:4115}/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Label Studio is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Label Studio may not be accessible${NC}"
    echo -e "${YELLOW}   URL: ${LABEL_STUDIO_URL:-http://10.0.0.223:4115}${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
fi

# Check if PostgreSQL is accessible
echo -e "${BLUE}Checking PostgreSQL connection...${NC}"
if pg_isready -h localhost -p 4332 -U vllm_batch_user > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: PostgreSQL may not be accessible${NC}"
    echo -e "${YELLOW}   Start with: docker compose -f docker/docker-compose.yml up -d postgres${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
fi

# Check if port 8001 is already in use
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: Port 8001 is already in use${NC}"
    echo -e "${YELLOW}   Kill the process with: kill \$(lsof -t -i:8001)${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Starting Curation API...${NC}"
echo -e "${BLUE}  Port: 8001${NC}"
echo -e "${BLUE}  Label Studio: ${LABEL_STUDIO_URL:-http://10.0.0.223:4115}${NC}"
echo -e "${BLUE}  Database: localhost:4332${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source venv/bin/activate
fi

# Start the Curation API
python -m integrations.aris.curation_app.api

# Note: The script will block here until the server is stopped with Ctrl+C

