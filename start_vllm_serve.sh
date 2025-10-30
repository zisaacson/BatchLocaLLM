#!/bin/bash
# Start vLLM in serve mode (OpenAI-compatible API)
# This provides real-time inference instead of batch processing

set -e

echo "🚀 Starting vLLM Server in Serve Mode"
echo "======================================"
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values if not set in .env
MODEL_NAME=${MODEL_NAME:-"google/gemma-3-4b-it"}
PORT=${PORT:-8000}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.90}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-256}

echo "📋 Configuration:"
echo "   Model: $MODEL_NAME"
echo "   Port: $PORT"
echo "   GPU Memory: ${GPU_MEMORY_UTILIZATION}"
echo "   Max Context: ${MAX_MODEL_LEN} tokens"
echo "   Max Sequences: ${MAX_NUM_SEQS}"
echo ""

# Check if vLLM is installed
if ! command -v vllm &> /dev/null; then
    echo "❌ vLLM not found. Installing..."
    source venv/bin/activate
    pip install vllm
fi

# Activate virtual environment
source venv/bin/activate

echo "🔥 Starting vLLM server..."
echo "   API will be available at: http://localhost:${PORT}"
echo "   OpenAI-compatible endpoints:"
echo "     - POST /v1/chat/completions"
echo "     - POST /v1/completions"
echo "     - GET /v1/models"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start vLLM server
vllm serve "$MODEL_NAME" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --enable-prefix-caching \
    --disable-log-requests

