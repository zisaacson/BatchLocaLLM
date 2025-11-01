#!/bin/bash
# Safe model testing script - stops worker, runs test, restarts worker
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <test_script> [test_args...]${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 core/tests/manual/test_olmo2_7b_single.py"
    echo "  $0 core/tests/manual/test_granite_3b_single.py"
    exit 1
fi

TEST_SCRIPT=$1
shift  # Remove first arg, rest are test args

# Check if test script exists
if [ ! -f "$TEST_SCRIPT" ]; then
    echo -e "${RED}❌ Test script not found: $TEST_SCRIPT${NC}"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  SAFE MODEL TESTING${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Test script:${NC} $TEST_SCRIPT"
echo ""

# Function to check if worker is running
check_worker_running() {
    if pgrep -f "python.*batch_app.worker" > /dev/null; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

# Function to check if API is running
check_api_running() {
    if pgrep -f "uvicorn.*api_server" > /dev/null; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

# Check initial state
WORKER_WAS_RUNNING=false
API_WAS_RUNNING=false

if check_worker_running; then
    WORKER_WAS_RUNNING=true
    echo -e "${YELLOW}📊 Worker is running${NC}"
fi

if check_api_running; then
    API_WAS_RUNNING=true
    echo -e "${YELLOW}📊 API server is running${NC}"
fi

# Check GPU status
echo ""
echo -e "${BLUE}📊 GPU Status Before Test:${NC}"
nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader,nounits | \
    awk '{printf "   Used: %d MB, Free: %d MB, Total: %d MB\n", $1, $2, $3}'

GPU_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
if [ "$GPU_FREE" -lt 14000 ]; then
    echo -e "${YELLOW}⚠️  GPU has only ${GPU_FREE}MB free (need ~14GB for 7B models)${NC}"
    echo -e "${YELLOW}   Stopping worker to free GPU memory...${NC}"
    
    if [ "$WORKER_WAS_RUNNING" = true ]; then
        echo -e "${YELLOW}🛑 Stopping worker...${NC}"
        pkill -f "python.*batch_app.worker" || true
        sleep 3
        
        # Check if stopped
        if check_worker_running; then
            echo -e "${RED}❌ Failed to stop worker${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ Worker stopped${NC}"
        
        # Check GPU again
        GPU_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
        echo -e "${GREEN}   GPU now has ${GPU_FREE}MB free${NC}"
    fi
fi

# Check RAM
echo ""
echo -e "${BLUE}📊 RAM Status:${NC}"
free -h | grep "^Mem:" | awk '{printf "   Total: %s, Used: %s, Free: %s, Available: %s\n", $2, $3, $4, $7}'

AVAILABLE_RAM=$(free -g | awk '/^Mem:/{print $7}')
if [ "$AVAILABLE_RAM" -lt 8 ]; then
    echo -e "${YELLOW}⚠️  Only ${AVAILABLE_RAM}GB RAM available (recommended: 8GB+)${NC}"
    echo -e "${YELLOW}   Test may be slow or fail due to memory pressure${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Test cancelled${NC}"
        exit 1
    fi
fi

# Run the test
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🧪 Running test...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Run test and capture exit code
set +e
python "$TEST_SCRIPT" "$@"
TEST_EXIT_CODE=$?
set -e

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Check test result
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ TEST PASSED${NC}"
else
    echo -e "${RED}❌ TEST FAILED (exit code: $TEST_EXIT_CODE)${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Restart services if they were running
if [ "$WORKER_WAS_RUNNING" = true ]; then
    if ! check_worker_running; then
        echo -e "${YELLOW}🔄 Restarting worker...${NC}"
        nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
        sleep 2
        
        if check_worker_running; then
            echo -e "${GREEN}✅ Worker restarted${NC}"
        else
            echo -e "${RED}❌ Failed to restart worker${NC}"
            echo -e "${YELLOW}   Run manually: python -m core.batch_app.worker${NC}"
        fi
    fi
fi

# Final GPU status
echo ""
echo -e "${BLUE}📊 GPU Status After Test:${NC}"
nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader,nounits | \
    awk '{printf "   Used: %d MB, Free: %d MB, Total: %d MB\n", $1, $2, $3}'

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Done!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

exit $TEST_EXIT_CODE

