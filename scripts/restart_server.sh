#!/bin/bash
# Restart vLLM Batch Server
# Usage: ./scripts/restart_server.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔄 Restarting vLLM Batch Server..."
echo ""

# Kill existing processes
echo "1️⃣ Stopping existing processes..."
pkill -f "python -m uvicorn core.batch_app.api_server" || echo "   No API server running"
pkill -f "python -m core.batch_app.worker" || echo "   No worker running"
sleep 2

# Verify processes are dead
if pgrep -f "python -m uvicorn core.batch_app.api_server" > /dev/null; then
    echo "   ⚠️  API server still running, force killing..."
    pkill -9 -f "python -m uvicorn core.batch_app.api_server"
    sleep 1
fi

if pgrep -f "python -m core.batch_app.worker" > /dev/null; then
    echo "   ⚠️  Worker still running, force killing..."
    pkill -9 -f "python -m core.batch_app.worker"
    sleep 1
fi

echo "   ✅ All processes stopped"
echo ""

# Wait for PostgreSQL to be ready
echo "2️⃣ Waiting for PostgreSQL..."
if [ -f "$SCRIPT_DIR/wait_for_postgres.sh" ]; then
    if ! "$SCRIPT_DIR/wait_for_postgres.sh"; then
        echo "❌ PostgreSQL is not ready! Aborting."
        exit 1
    fi
else
    echo "   ⚠️  wait_for_postgres.sh not found, skipping health check"
    sleep 2
fi
echo ""

# Check and clear GPU memory if needed
echo "3️⃣ Checking GPU memory..."
if [ -f "$SCRIPT_DIR/check_gpu_memory.sh" ]; then
    if ! "$SCRIPT_DIR/check_gpu_memory.sh"; then
        echo "❌ GPU memory check failed! Aborting."
        exit 1
    fi
else
    echo "   ⚠️  check_gpu_memory.sh not found, using basic check"
    if command -v nvidia-smi &> /dev/null; then
        GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
        GPU_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)
        echo "   GPU Memory: ${GPU_MEM}MB / ${GPU_TOTAL}MB"
    else
        echo "   ⚠️  nvidia-smi not found, skipping GPU check"
    fi
fi
echo ""

# Create logs directory
mkdir -p logs

# Start API server on port 4080
echo "4️⃣ Starting API server (port 4080)..."
source venv/bin/activate
nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080 > logs/api_server.log 2>&1 &
API_PID=$!
echo "   Started API server (PID: $API_PID)"
sleep 3

# Check if API server is responding
if curl -s http://localhost:4080/health > /dev/null 2>&1; then
    echo "   ✅ API server is healthy"
else
    echo "   ❌ API server failed to start"
    echo "   Check logs/api_server.log for details"
    exit 1
fi

# Start docs server on port 4081
echo "   Starting docs server (port 4081)..."
nohup python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4081 > logs/docs_server.log 2>&1 &
DOCS_PID=$!
echo "   Started docs server (PID: $DOCS_PID)"
sleep 2
echo ""

# Start worker
echo "5️⃣ Starting worker..."
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
WORKER_PID=$!
echo "   Started worker (PID: $WORKER_PID)"
sleep 5

# Check worker logs
if tail -5 logs/worker.log | grep -q "Worker initialized"; then
    echo "   ✅ Worker is healthy"
else
    echo "   ⚠️  Worker may have issues, check logs/worker.log"
fi
echo ""

# Summary
echo "✅ Server restarted successfully!"
echo ""
echo "📊 Access Points:"
echo "   📖 Documentation Hub: http://localhost:4081"
echo "   🎛️  Admin Panel: http://localhost:4081/admin"
echo "   📊 Queue Monitor: http://localhost:4081/queue"
echo "   🔌 API Server: http://localhost:4080"
echo "   ❤️  Health Check: http://localhost:4080/health"
echo ""
echo "📝 Logs:"
echo "   API: tail -f logs/api_server.log"
echo "   Worker: tail -f logs/worker.log"
echo "   Docs: tail -f logs/docs_server.log"
echo ""
echo "🛑 To stop:"
echo "   ./scripts/stop_server.sh"

