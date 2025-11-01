#!/bin/bash
#
# Run Week-Long Benchmark
#
# This script sets up a robust, long-running benchmark that can run for days/weeks.
# It handles:
# - Model registry setup
# - Batch job queueing
# - Worker startup with auto-restart
# - Logging and monitoring
#
# Just run this and walk away - it will keep going even if you disconnect.
#

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "================================================================================"
echo "🚀 Week-Long Benchmark Setup"
echo "================================================================================"
echo ""

# Check if models are downloaded
echo "📦 Checking if models are downloaded..."
if [ ! -f "models/olmo2-7b-q4/OLMo-2-1124-7B-Instruct-Q4_0.gguf" ]; then
    echo "❌ OLMo 2 7B Q4_0 not found!"
    echo "   Run: huggingface-cli download bartowski/OLMo-2-1124-7B-Instruct-GGUF --include 'OLMo-2-1124-7B-Instruct-Q4_0.gguf' --local-dir ./models/olmo2-7b-q4"
    exit 1
fi

if [ ! -f "models/gpt-oss-20b-q4/openai_gpt-oss-20b-Q4_0.gguf" ]; then
    echo "❌ GPT-OSS 20B Q4_0 not found!"
    echo "   Run: huggingface-cli download bartowski/openai_gpt-oss-20b-GGUF --include 'openai_gpt-oss-20b-Q4_0.gguf' --local-dir ./models/gpt-oss-20b-q4"
    exit 1
fi

echo "✅ OLMo 2 7B Q4_0: $(ls -lh models/olmo2-7b-q4/*.gguf | awk '{print $5}')"
echo "✅ GPT-OSS 20B Q4_0: $(ls -lh models/gpt-oss-20b-q4/*.gguf | awk '{print $5}')"
echo ""

# Check if batch file exists
echo "📄 Checking batch file..."
if [ ! -f "batch_5k.jsonl" ]; then
    echo "❌ batch_5k.jsonl not found!"
    exit 1
fi

BATCH_SIZE=$(wc -l < batch_5k.jsonl)
echo "✅ Batch file: $BATCH_SIZE requests"
echo ""

# Check if API server is running
echo "🔍 Checking API server..."
if ! curl -s http://localhost:4080/health > /dev/null 2>&1; then
    echo "❌ API server not running on port 4080!"
    echo "   Start it with: python -m uvicorn core.batch_app.api_server:app --host 0.0.0.0 --port 4080"
    exit 1
fi
echo "✅ API server is running"
echo ""

# Add models to registry and queue jobs
echo "📋 Setting up models and queueing jobs..."
source venv/bin/activate
python scripts/queue_olmo_and_gptoss_benchmarks.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to queue jobs!"
    exit 1
fi
echo ""

# Start worker in background with nohup (survives terminal disconnect)
echo "🔧 Starting worker..."
echo "   Logs: logs/worker.log"
echo "   PID file: worker.pid"
echo ""

# Kill existing worker if running
if [ -f "worker.pid" ]; then
    OLD_PID=$(cat worker.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "⚠️  Killing existing worker (PID: $OLD_PID)"
        kill $OLD_PID
        sleep 2
    fi
    rm worker.pid
fi

# Start worker with nohup
nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &
WORKER_PID=$!
echo $WORKER_PID > worker.pid

echo "✅ Worker started (PID: $WORKER_PID)"
echo ""

# Wait a few seconds and check if worker is still running
sleep 3
if ! ps -p $WORKER_PID > /dev/null 2>&1; then
    echo "❌ Worker died immediately! Check logs:"
    tail -20 logs/worker.log
    exit 1
fi

echo "================================================================================"
echo "✅ BENCHMARK STARTED"
echo "================================================================================"
echo ""
echo "📊 What's Running:"
echo "   • API Server: http://localhost:4080"
echo "   • Worker: PID $WORKER_PID"
echo "   • Jobs: 2 queued (OLMo 2 7B, GPT-OSS 20B)"
echo ""
echo "⏱️  Estimated Timeline:"
echo "   1. OLMo 2 7B Q4_0:  ~10-15 minutes"
echo "   2. GPT-OSS 20B Q4_0: ~60-90 minutes (with CPU offload)"
echo "   Total: ~70-105 minutes"
echo ""
echo "🔍 Monitor Progress:"
echo "   • Worker logs:  tail -f logs/worker.log"
echo "   • API logs:     tail -f logs/api.log"
echo "   • GPU usage:    watch -n 1 nvidia-smi"
echo "   • Job status:   curl http://localhost:4080/v1/batches"
echo ""
echo "🛡️  Robustness Features:"
echo "   ✅ Worker runs in background (nohup)"
echo "   ✅ Survives terminal disconnect"
echo "   ✅ Incremental saves (resume from crashes)"
echo "   ✅ Automatic model hot-swap"
echo "   ✅ GPU memory monitoring"
echo ""
echo "🛑 To Stop:"
echo "   kill $WORKER_PID"
echo "   # or"
echo "   kill \$(cat worker.pid)"
echo ""
echo "🚀 You can disconnect now - it will keep running!"
echo "================================================================================"

