#!/bin/bash
# Stop vLLM Batch Server
# Usage: ./scripts/stop_server.sh

set -e

echo "🛑 Stopping vLLM Batch Server..."
echo ""

# Kill API server
echo "1️⃣ Stopping API server..."
if pkill -f "python -m uvicorn core.batch_app.api_server"; then
    echo "   ✅ API server stopped"
else
    echo "   ℹ️  No API server running"
fi

# Kill worker
echo "2️⃣ Stopping worker..."
if pkill -f "python -m core.batch_app.worker"; then
    echo "   ✅ Worker stopped"
else
    echo "   ℹ️  No worker running"
fi

sleep 2

# Force kill if still running
if pgrep -f "python -m uvicorn core.batch_app.api_server" > /dev/null; then
    echo "   ⚠️  Force killing API server..."
    pkill -9 -f "python -m uvicorn core.batch_app.api_server"
fi

if pgrep -f "python -m core.batch_app.worker" > /dev/null; then
    echo "   ⚠️  Force killing worker..."
    pkill -9 -f "python -m core.batch_app.worker"
fi

echo ""
echo "✅ Server stopped successfully!"

