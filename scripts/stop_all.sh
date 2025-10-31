#!/bin/bash

# Stop all vLLM batch server components
# Usage: ./stop_all.sh

echo "🛑 Stopping vLLM Batch Server Components"
echo "========================================"
echo ""

# Kill processes
pkill -f "batch_app.api_server" && echo "✅ Stopped API Server" || echo "⚠️  API Server not running"
pkill -f "batch_app.worker" && echo "✅ Stopped Worker" || echo "⚠️  Worker not running"
pkill -f "batch_app.static_server" && echo "✅ Stopped Integration Server" || echo "⚠️  Integration Server not running"
pkill -f "serve_results.py" && echo "✅ Stopped Results Viewer" || echo "⚠️  Results Viewer not running"

echo ""
echo "✅ All components stopped"

