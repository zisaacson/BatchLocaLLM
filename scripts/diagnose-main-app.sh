#!/bin/bash
# Diagnose why main app (Aristotle on 10.0.0.185:4002) is down

echo "============================================================"
echo "MAIN APP DIAGNOSIS (Aristotle @ 10.0.0.185:4002)"
echo "============================================================"
echo ""

echo "1. CHECKING PORT 4002..."
echo "-----------------------------------------------------------"
netstat -tlnp 2>/dev/null | grep 4002 || ss -tlnp 2>/dev/null | grep 4002 || echo "Port 4002 not found"
echo ""

echo "2. CHECKING DOCKER CONTAINERS..."
echo "-----------------------------------------------------------"
docker ps --filter "publish=4002" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not available or no containers on port 4002"
echo ""

echo "3. CHECKING ALL DOCKER CONTAINERS..."
echo "-----------------------------------------------------------"
docker ps -a --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | head -20 || echo "Docker not available"
echo ""

echo "4. TESTING CONNECTION TO 10.0.0.185:4002..."
echo "-----------------------------------------------------------"
curl -v http://10.0.0.185:4002/api/health 2>&1 | head -30
echo ""

echo "5. TESTING CONNECTION TO localhost:4002..."
echo "-----------------------------------------------------------"
curl -v http://localhost:4002/api/health 2>&1 | head -30
echo ""

echo "6. CHECKING VLLM BATCH SERVER STATUS..."
echo "-----------------------------------------------------------"
curl -s http://localhost:4080/health | jq . 2>/dev/null || echo "vLLM batch server not responding"
echo ""

echo "============================================================"
echo "SUMMARY"
echo "============================================================"
echo ""
echo "The vLLM batch server watchdog ONLY monitors the vLLM worker."
echo "It does NOT monitor the main Aristotle app (Next.js on port 4002)."
echo ""
echo "If the main app is down, you need to:"
echo "  1. Check if it's a Docker container: docker ps -a"
echo "  2. Start the container: docker start <container_name>"
echo "  3. Or start the Next.js app manually in the Aris project"
echo ""

