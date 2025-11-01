#!/bin/bash
# Check vLLM Batch Server status
# Usage: ./scripts/status_server.sh

echo "📊 vLLM Batch Server Status"
echo "=============================="
echo ""

# Check processes
echo "🔍 Processes:"
API_PID=$(pgrep -f "python -m uvicorn core.batch_app.api_server" || echo "")
WORKER_PID=$(pgrep -f "python -m core.batch_app.worker" || echo "")

if [ -n "$API_PID" ]; then
    echo "   ✅ API Server running (PID: $API_PID)"
else
    echo "   ❌ API Server NOT running"
fi

if [ -n "$WORKER_PID" ]; then
    echo "   ✅ Worker running (PID: $WORKER_PID)"
else
    echo "   ❌ Worker NOT running"
fi
echo ""

# Check API health
echo "🏥 API Health:"
if curl -s http://localhost:4080/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:4080/health)
    echo "   ✅ API is responding"
    echo "   Status: $(echo $HEALTH | jq -r '.status')"
    echo "   Version: $(echo $HEALTH | jq -r '.version')"
else
    echo "   ❌ API is NOT responding"
fi
echo ""

# Check GPU
echo "🎮 GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
    GPU_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)
    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
    GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits)
    
    echo "   Memory: ${GPU_MEM}MB / ${GPU_TOTAL}MB ($(( GPU_MEM * 100 / GPU_TOTAL ))%)"
    echo "   Utilization: ${GPU_UTIL}%"
    echo "   Temperature: ${GPU_TEMP}°C"
else
    echo "   ⚠️  nvidia-smi not found"
fi
echo ""

# Check queue
echo "📋 Job Queue:"
if curl -s http://localhost:4080/v1/queue > /dev/null 2>&1; then
    QUEUE=$(curl -s http://localhost:4080/v1/queue)
    QUEUE_LEN=$(echo $QUEUE | jq -r '.queue_length')
    echo "   Jobs in queue: $QUEUE_LEN"
    
    # Show active job if any
    ACTIVE=$(echo $QUEUE | jq -r '.queue[] | select(.status == "processing") | .batch_id' | head -1)
    if [ -n "$ACTIVE" ] && [ "$ACTIVE" != "null" ]; then
        echo "   Active job: $ACTIVE"
    fi
else
    echo "   ⚠️  Cannot fetch queue status"
fi
echo ""

# Check models
echo "🤖 Available Models:"
if curl -s http://localhost:4080/v1/models > /dev/null 2>&1; then
    MODELS=$(curl -s http://localhost:4080/v1/models | jq -r '.data[].id')
    echo "$MODELS" | while read model; do
        echo "   - $model"
    done
else
    echo "   ⚠️  Cannot fetch models"
fi
echo ""

echo "=============================="
echo "📝 Logs:"
echo "   API: tail -f logs/api_server.log"
echo "   Worker: tail -f logs/worker.log"
echo ""
echo "🔗 URLs:"
echo "   API: http://localhost:4080"
echo "   Queue Monitor: http://localhost:4080/queue-monitor.html"
echo "   Health: http://localhost:4080/health"

