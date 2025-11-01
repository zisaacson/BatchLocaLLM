#!/bin/bash
# Quick start script for Gemma 3 conquest system
# Assumes PostgreSQL is already running

set -e

cd "$(dirname "$0")/.."

echo "============================================================"
echo "🚀 STARTING GEMMA 3 CONQUEST SYSTEM"
echo "============================================================"
echo ""

# Activate venv
source venv/bin/activate

# Kill any existing processes
echo "🔪 Killing existing processes..."
pkill -9 -f "worker.py" 2>/dev/null || true
pkill -9 -f "uvicorn.*api_server" 2>/dev/null || true
pkill -9 -f "ray::EngineCore" 2>/dev/null || true
sleep 3
echo "✅ Processes killed"
echo ""

# Start PostgreSQL if not running
echo "🐘 Checking PostgreSQL..."
if ! docker ps | grep -q vllm-batch-postgres; then
    echo "Starting PostgreSQL..."
    docker compose -f docker-compose.postgres.yml up -d
    sleep 5
fi
echo "✅ PostgreSQL running"
echo ""

# Start API server
echo "🌐 Starting API server..."
nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080 > logs/api_server.log 2>&1 &
sleep 5
echo "✅ API server started"
echo ""

# Start worker (will load Gemma 3 4B on first request)
echo "⚙️  Starting worker..."
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
sleep 5
echo "✅ Worker started"
echo ""

echo "============================================================"
echo "✅ SYSTEM READY FOR CONQUEST REQUESTS"
echo "============================================================"
echo ""
echo "API Endpoint: http://localhost:4080"
echo ""
echo "Test with:"
echo "  curl -s http://localhost:4080/health"
echo "  curl -s http://localhost:4080/v1/queue"
echo ""
echo "Monitor logs:"
echo "  tail -f logs/worker.log"
echo "  tail -f logs/api_server.log"
echo ""

