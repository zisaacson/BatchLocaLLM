#!/bin/bash

# Plugin System End-to-End Test Script
# Tests all plugin functionality

set -e

BASE_URL="http://localhost:4080"
PASSED=0
FAILED=0

echo "🧪 Plugin System End-to-End Tests"
echo "=================================="
echo ""

# Helper functions
pass() {
    echo "✅ PASS: $1"
    ((PASSED++))
}

fail() {
    echo "❌ FAIL: $1"
    ((FAILED++))
}

test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local expected_status="${4:-200}"
    
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$status" = "$expected_status" ]; then
        pass "$name (HTTP $status)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body" | head -c 100
    else
        fail "$name (Expected $expected_status, got $status)"
        echo "$body" | head -c 200
    fi
    echo ""
}

# Test 1: List all plugins
echo "Test 1: List all plugins"
echo "------------------------"
response=$(curl -s "$BASE_URL/api/plugins")
plugin_count=$(echo "$response" | jq '.plugins | length')

if [ "$plugin_count" -eq 3 ]; then
    pass "Found 3 plugins"
    echo "$response" | jq '.plugins | map({id, name, enabled})'
else
    fail "Expected 3 plugins, found $plugin_count"
fi
echo ""

# Test 2: Get specific plugin details
echo "Test 2: Get plugin details"
echo "--------------------------"
test_endpoint "Get candidate-evaluator details" "GET" "/api/plugins/candidate-evaluator"

# Test 3: Enable plugin
echo "Test 3: Enable plugin"
echo "---------------------"
test_endpoint "Enable candidate-evaluator" "POST" "/api/plugins/candidate-evaluator/enable"

# Verify it's enabled
response=$(curl -s "$BASE_URL/api/plugins")
enabled=$(echo "$response" | jq '.plugins[] | select(.id == "candidate-evaluator") | .enabled')
if [ "$enabled" = "true" ]; then
    pass "Plugin is enabled"
else
    fail "Plugin should be enabled"
fi
echo ""

# Test 4: Disable plugin
echo "Test 4: Disable plugin"
echo "----------------------"
test_endpoint "Disable candidate-evaluator" "POST" "/api/plugins/candidate-evaluator/disable"

# Verify it's disabled
response=$(curl -s "$BASE_URL/api/plugins")
enabled=$(echo "$response" | jq '.plugins[] | select(.id == "candidate-evaluator") | .enabled')
if [ "$enabled" = "false" ]; then
    pass "Plugin is disabled"
else
    fail "Plugin should be disabled"
fi
echo ""

# Test 5: Get plugins by type
echo "Test 5: Get plugins by type"
echo "---------------------------"
test_endpoint "Get rating plugins" "GET" "/api/plugins/by-type/rating"
test_endpoint "Get parser plugins" "GET" "/api/plugins/by-type/parser"
test_endpoint "Get export plugins" "GET" "/api/plugins/by-type/export"
test_endpoint "Get UI plugins" "GET" "/api/plugins/by-type/ui"
test_endpoint "Get schema plugins" "GET" "/api/plugins/by-type/schema"

# Test 6: Get UI components
echo "Test 6: Get UI components"
echo "-------------------------"
test_endpoint "Get candidate-evaluator UI components" "GET" "/api/plugins/candidate-evaluator/ui-components"

# Test 7: Plugin management page
echo "Test 7: Plugin management page"
echo "-------------------------------"
response=$(curl -s "$BASE_URL/plugins")
if echo "$response" | grep -q "Plugin Management"; then
    pass "Plugin management page loads"
else
    fail "Plugin management page doesn't load"
fi
echo ""

# Test 8: Test invalid plugin ID
echo "Test 8: Error handling"
echo "----------------------"
test_endpoint "Get non-existent plugin" "GET" "/api/plugins/non-existent" 404

# Test 9: Enable all plugins and verify
echo "Test 9: Enable all plugins"
echo "--------------------------"
for plugin in "candidate-evaluator" "quality-rater" "batch-submitter"; do
    curl -s -X POST "$BASE_URL/api/plugins/$plugin/enable" > /dev/null
done

response=$(curl -s "$BASE_URL/api/plugins")
enabled_count=$(echo "$response" | jq '[.plugins[] | select(.enabled == true)] | length')

if [ "$enabled_count" -eq 3 ]; then
    pass "All 3 plugins enabled"
else
    fail "Expected 3 enabled plugins, found $enabled_count"
fi
echo ""

# Test 10: Verify plugin capabilities
echo "Test 10: Verify plugin capabilities"
echo "------------------------------------"

# Candidate evaluator should provide all types
response=$(curl -s "$BASE_URL/api/plugins/candidate-evaluator")
provides=$(echo "$response" | jq -r '.manifest.provides | keys | join(", ")')
if echo "$provides" | grep -q "schema" && echo "$provides" | grep -q "parser"; then
    pass "Candidate evaluator provides schema and parser"
else
    fail "Candidate evaluator missing capabilities"
fi
echo ""

# Quality rater should provide ratings
response=$(curl -s "$BASE_URL/api/plugins/quality-rater")
provides=$(echo "$response" | jq -r '.manifest.provides | keys | join(", ")')
if echo "$provides" | grep -q "ratings"; then
    pass "Quality rater provides ratings"
else
    fail "Quality rater missing ratings capability"
fi
echo ""

# Batch submitter should provide UI and schema
response=$(curl -s "$BASE_URL/api/plugins/batch-submitter")
provides=$(echo "$response" | jq -r '.manifest.provides | keys | join(", ")')
if echo "$provides" | grep -q "ui_components" && echo "$provides" | grep -q "schema"; then
    pass "Batch submitter provides UI and schema"
else
    fail "Batch submitter missing capabilities"
fi
echo ""

# Summary
echo "=================================="
echo "Test Summary"
echo "=================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "⚠️  Some tests failed"
    exit 1
fi

