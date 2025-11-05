#!/bin/bash

# End-to-End Plugin System Test
# Tests all plugin functionality including loading, enabling/disabling, UI components, and rendering

set -e

echo "========================================="
echo "Plugin System End-to-End Test"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to test API endpoint
test_endpoint() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="$4"
    local expected_status="${5:-200}"
    
    echo -n "Testing: $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $http_code)"
        echo "Response: $body"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Helper function to test JSON response
test_json_field() {
    local name="$1"
    local url="$2"
    local jq_query="$3"
    local expected="$4"
    
    echo -n "Testing: $name... "
    
    response=$(curl -s "$url")
    actual=$(echo "$response" | jq -r "$jq_query")
    
    if [ "$actual" = "$expected" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected '$expected', got '$actual')"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "========================================="
echo "1. Plugin Discovery & Loading"
echo "========================================="
echo ""

test_endpoint "Health check" "GET" "http://localhost:4080/health"
test_endpoint "List all plugins" "GET" "http://localhost:4080/api/plugins"
test_json_field "Plugin count" "http://localhost:4080/api/plugins" '.plugins | length' "3"

echo ""
echo "========================================="
echo "2. Individual Plugin Details"
echo "========================================="
echo ""

test_endpoint "Get candidate-evaluator plugin" "GET" "http://localhost:4080/api/plugins/candidate-evaluator"
test_endpoint "Get quality-rater plugin" "GET" "http://localhost:4080/api/plugins/quality-rater"
test_endpoint "Get batch-submitter plugin" "GET" "http://localhost:4080/api/plugins/batch-submitter"

test_json_field "Candidate evaluator name" "http://localhost:4080/api/plugins/candidate-evaluator" '.name' "Candidate Evaluator"
test_json_field "Quality rater name" "http://localhost:4080/api/plugins/quality-rater" '.name' "Quality Rater"
test_json_field "Batch submitter name" "http://localhost:4080/api/plugins/batch-submitter" '.name' "Batch Submitter"

echo ""
echo "========================================="
echo "3. Plugin Enable/Disable"
echo "========================================="
echo ""

test_endpoint "Disable candidate-evaluator" "POST" "http://localhost:4080/api/plugins/candidate-evaluator/disable"
test_json_field "Verify disabled" "http://localhost:4080/api/plugins/candidate-evaluator" '.enabled' "false"

test_endpoint "Enable candidate-evaluator" "POST" "http://localhost:4080/api/plugins/candidate-evaluator/enable"
test_json_field "Verify enabled" "http://localhost:4080/api/plugins/candidate-evaluator" '.enabled' "true"

echo ""
echo "========================================="
echo "4. UI Components"
echo "========================================="
echo ""

test_endpoint "Get candidate-evaluator UI components" "GET" "http://localhost:4080/api/plugins/candidate-evaluator/ui-components"
test_endpoint "Get quality-rater UI components" "GET" "http://localhost:4080/api/plugins/quality-rater/ui-components"
test_endpoint "Get batch-submitter UI components" "GET" "http://localhost:4080/api/plugins/batch-submitter/ui-components"

test_json_field "Candidate evaluator component count" "http://localhost:4080/api/plugins/candidate-evaluator/ui-components" '.components | length' "3"
test_json_field "Quality rater component count" "http://localhost:4080/api/plugins/quality-rater/ui-components" '.components | length' "3"
test_json_field "Batch submitter component count" "http://localhost:4080/api/plugins/batch-submitter/ui-components" '.components | length' "3"

echo ""
echo "========================================="
echo "5. Component Rendering"
echo "========================================="
echo ""

# Test candidate card rendering
test_endpoint "Render candidate card" "POST" "http://localhost:4080/api/plugins/candidate-evaluator/render-component" \
    '{"component_id": "candidate-card", "data": {"candidate": {"name": "Test User", "title": "Engineer", "company": "Test Corp"}}}'

# Test rating widget rendering
test_endpoint "Render rating widget" "POST" "http://localhost:4080/api/plugins/quality-rater/render-component" \
    '{"component_id": "rating-widget", "data": {"scale_type": "categorical"}}'

# Test job status rendering
test_endpoint "Render job status" "POST" "http://localhost:4080/api/plugins/batch-submitter/render-component" \
    '{"component_id": "job-status", "data": {"job": {"status": "completed", "progress": 100}}}'

# Verify rendered HTML contains expected content
echo -n "Testing: Candidate card contains name... "
response=$(curl -s -X POST "http://localhost:4080/api/plugins/candidate-evaluator/render-component" \
    -H "Content-Type: application/json" \
    -d '{"component_id": "candidate-card", "data": {"candidate": {"name": "Test User", "title": "Engineer", "company": "Test Corp"}}}')
html=$(echo "$response" | jq -r '.html')
if echo "$html" | grep -q "Test User"; then
    echo -e "${GREEN}✓ PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAIL${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "========================================="
echo "6. Plugin Types"
echo "========================================="
echo ""

test_endpoint "Get rating plugins" "GET" "http://localhost:4080/api/plugins/by-type/rating"
test_endpoint "Get UI plugins" "GET" "http://localhost:4080/api/plugins/by-type/ui"
test_endpoint "Get export plugins" "GET" "http://localhost:4080/api/plugins/by-type/export"

echo ""
echo "========================================="
echo "7. Plugin Management UI"
echo "========================================="
echo ""

test_endpoint "Plugin management page" "GET" "http://localhost:4080/plugins"
test_endpoint "Index page" "GET" "http://localhost:4080/"
test_endpoint "Queue monitor page" "GET" "http://localhost:4080/queue"

echo ""
echo "========================================="
echo "8. Static Assets"
echo "========================================="
echo ""

test_endpoint "Plugin manager JS" "GET" "http://localhost:4080/static/js/plugin-manager.js"

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}ALL TESTS PASSED! 🎉${NC}"
    echo -e "${GREEN}=========================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}SOME TESTS FAILED${NC}"
    echo -e "${RED}=========================================${NC}"
    exit 1
fi

