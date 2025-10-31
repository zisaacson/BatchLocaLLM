#!/bin/bash

# Start all vLLM batch server components
# Usage: ./start_all.sh

set -e

echo "🚀 Starting vLLM Batch Server Components"
echo "========================================"
echo ""

# Check if running
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "⚠️  Port $port is already in use"
        return 1
    fi
    return 0
}

# Kill existing processes
cleanup() {
    echo "🧹 Cleaning up existing processes..."
    pkill -f "batch_app.api_server" 2>/dev/null || true
    pkill -f "batch_app.worker" 2>/dev/null || true
    pkill -f "batch_app.static_server" 2>/dev/null || true
    sleep 2
}

# Start component in background
start_component() {
    local name=$1
    local command=$2
    local log_file=$3
    
    echo "▶️  Starting $name..."
    nohup $command > "$log_file" 2>&1 &
    local pid=$!
    echo "   PID: $pid"
    echo "   Log: $log_file"
    sleep 2
}

# Main
main() {
    # Cleanup first
    cleanup
    
    # Create logs directory
    mkdir -p logs
    
    echo ""
    echo "Starting components..."
    echo ""
    
    # 1. Start Integration Server (port 4081)
    start_component \
        "Integration Server" \
        "python -m core.batch_app.static_server" \
        "logs/integration_server.log"

    # 2. Start API Server (port 4080)
    start_component \
        "API Server" \
        "python -m core.batch_app.api_server" \
        "logs/api_server.log"

    # 3. Start Worker
    start_component \
        "Worker" \
        "python -m core.batch_app.worker" \
        "logs/worker.log"

    # 4. Start Results Viewer (port 8001)
    start_component \
        "Results Viewer" \
        "python serve_results.py" \
        "logs/results_viewer.log"

    echo ""
    echo "✅ All components started!"
    echo ""
    echo "📊 Service URLs:"
    echo "   Integration:     http://10.0.0.223:4081"
    echo "   API Server:      http://10.0.0.223:4080"
    echo "   Results Viewer:  http://10.0.0.223:8001/view_results.html"
    echo "   Monitor:         file://$(pwd)/monitor.html"
    echo ""
    echo "📥 Aris Integration:"
    echo "   curl http://10.0.0.223:4081/vllm-batch-client.ts > ../aris/src/lib/inference/vllm-batch-client.ts"
    echo ""
    echo "📝 Logs:"
    echo "   Integration: tail -f logs/integration_server.log"
    echo "   API Server:  tail -f logs/api_server.log"
    echo "   Worker:      tail -f logs/worker.log"
    echo ""
    echo "🛑 Stop all:"
    echo "   ./stop_all.sh"
    echo ""
}

main

