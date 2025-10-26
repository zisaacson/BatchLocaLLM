#!/bin/bash
# Quick start script for vLLM Batch Server

set -e

echo "=========================================="
echo "vLLM Batch Server - Quick Start"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  Please edit .env and set:"
    echo "   - MODEL_NAME (default: meta-llama/Llama-3.1-8B-Instruct)"
    echo "   - HF_TOKEN (required for gated models like Llama)"
    echo ""
    read -p "Press Enter to continue after editing .env..."
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check for NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  nvidia-smi not found. Make sure NVIDIA drivers are installed."
    echo "   Continuing anyway..."
else
    echo "GPU Information:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo ""
fi

# Build and start containers
echo "Building Docker image..."
docker-compose build

echo ""
echo "Starting vLLM Batch Server..."
docker-compose up -d

echo ""
echo "Waiting for server to be ready..."
sleep 5

# Wait for health check
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Server is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Server failed to start. Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ vLLM Batch Server is running!"
echo "=========================================="
echo ""
echo "API Endpoint: http://localhost:8000"
echo "Health Check: http://localhost:8000/health"
echo "Metrics:      http://localhost:9090/metrics"
echo ""
echo "Next steps:"
echo "  1. Check health: curl http://localhost:8000/health"
echo "  2. Run example:  python examples/simple_batch.py"
echo "  3. View logs:    docker-compose logs -f"
echo "  4. Stop server:  docker-compose down"
echo ""

