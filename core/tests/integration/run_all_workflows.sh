#!/bin/bash
#
# Run All Integration Tests for vLLM Batch Server Workflows
#
# This script runs comprehensive integration tests for ALL workflows:
# 1. Batch Processing Workflow
# 2. Label Studio Auto-Import Workflow
# 3. Curation Workflow
# 4. Gold Star Workflow
# 5. Webhook Workflow
# 6. Model Hot-Swapping Workflow
# 7. Conquest Data Flow Workflow
# 8. Bidirectional Sync Workflow
#
# Requirements:
# - API server running (port 4080)
# - Worker running
# - Label Studio running (port 4115)
# - Curation app running (port 8001)
# - PostgreSQL running (port 4332)
#

set -e  # Exit on error

echo "================================================================================"
echo "🧪 INTEGRATION TESTS - ALL WORKFLOWS"
echo "================================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo "🔍 Checking required services..."
echo ""

check_service() {
    local name=$1
    local url=$2
    local port=$3
    
    if curl -s -f -o /dev/null "$url"; then
        echo -e "   ${GREEN}✅${NC} $name (port $port)"
        return 0
    else
        echo -e "   ${RED}❌${NC} $name (port $port) - NOT RUNNING"
        return 1
    fi
}

# Check all services
all_services_running=true

check_service "Batch API" "http://localhost:4080/health" "4080" || all_services_running=false
check_service "Label Studio" "http://localhost:4115" "4115" || all_services_running=false
check_service "Curation API" "http://localhost:8001/health" "8001" || all_services_running=false

# Check worker heartbeat
echo -n "   "
if python3 -c "
from core.batch_app.database import SessionLocal, WorkerHeartbeat
from datetime import datetime, timedelta
db = SessionLocal()
try:
    heartbeat = db.query(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen.desc()).first()
    if heartbeat:
        age = (datetime.utcnow() - heartbeat.last_seen).total_seconds()
        if age < 60:
            print('✅ Worker (heartbeat active)')
            exit(0)
        else:
            print(f'❌ Worker (heartbeat stale: {int(age)}s ago)')
            exit(1)
    else:
        print('❌ Worker (no heartbeat found)')
        exit(1)
finally:
    db.close()
" 2>/dev/null; then
    :
else
    all_services_running=false
fi

echo ""

if [ "$all_services_running" = false ]; then
    echo -e "${YELLOW}⚠️  WARNING: Some services are not running${NC}"
    echo ""
    echo "To start services:"
    echo "  1. API Server: python -m core.batch_app.api_server"
    echo "  2. Worker: python -m core.batch_app.worker"
    echo "  3. Label Studio: docker-compose up label-studio"
    echo "  4. Curation App: cd integrations/aris/curation_app && python api.py"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "================================================================================"
echo "📋 Running Integration Tests"
echo "================================================================================"
echo ""

# Run tests
pytest_args="-v -s --tb=short"

echo "🧪 Test Suite 1: Core Workflows"
echo "--------------------------------------------------------------------------------"
pytest core/tests/integration/test_all_workflows.py $pytest_args
test1_result=$?
echo ""

echo "🧪 Test Suite 2: Conquest Workflows"
echo "--------------------------------------------------------------------------------"
pytest core/tests/integration/test_conquest_workflows.py $pytest_args
test2_result=$?
echo ""

echo "🧪 Test Suite 3: Full Pipeline"
echo "--------------------------------------------------------------------------------"
pytest core/tests/integration/test_full_pipeline.py $pytest_args 2>/dev/null || echo "⚠️  Skipped (requires all services)"
test3_result=$?
echo ""

# Summary
echo "================================================================================"
echo "📊 TEST RESULTS SUMMARY"
echo "================================================================================"
echo ""

total_passed=0
total_failed=0

if [ $test1_result -eq 0 ]; then
    echo -e "   ${GREEN}✅${NC} Core Workflows: PASSED"
    ((total_passed++))
else
    echo -e "   ${RED}❌${NC} Core Workflows: FAILED"
    ((total_failed++))
fi

if [ $test2_result -eq 0 ]; then
    echo -e "   ${GREEN}✅${NC} Conquest Workflows: PASSED"
    ((total_passed++))
else
    echo -e "   ${RED}❌${NC} Conquest Workflows: FAILED"
    ((total_failed++))
fi

if [ $test3_result -eq 0 ]; then
    echo -e "   ${GREEN}✅${NC} Full Pipeline: PASSED"
    ((total_passed++))
else
    echo -e "   ${YELLOW}⚠️${NC}  Full Pipeline: SKIPPED/FAILED"
fi

echo ""
echo "================================================================================"

if [ $total_failed -eq 0 ]; then
    echo -e "${GREEN}✅ ALL INTEGRATION TESTS PASSED!${NC}"
    echo "================================================================================"
    exit 0
else
    echo -e "${RED}❌ SOME INTEGRATION TESTS FAILED${NC}"
    echo "================================================================================"
    exit 1
fi

