#!/bin/bash

set -e

echo "🧹 Docker Cleanup for vLLM Batch Server Workstation"
echo "===================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "📋 Current Docker containers:"
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | head -20
echo ""

echo -e "${YELLOW}⚠️  This will remove containers you don't need for vLLM batch processing.${NC}"
echo ""
echo "KEEPING (for vLLM monitoring):"
echo "  ✅ aristotle-prometheus       (metrics database)"
echo "  ✅ aristotle-grafana          (dashboards)"
echo "  ✅ aristotle-loki             (logs)"
echo "  ✅ aristotle-nvidia-gpu-exporter (GPU metrics)"
echo "  ✅ aristotle-label-studio     (data curation)"
echo ""
echo "REMOVING (Aristotle app stuff, not needed here):"
echo "  ❌ aristotle-resume-ner"
echo "  ❌ aristotle-docmost + docmost-db + docmost-redis"
echo "  ❌ aristotle-mlflow"
echo "  ❌ aristotle-dev-db + test-db"
echo "  ❌ aristotle-qdrant"
echo "  ❌ aristotle-prefect"
echo "  ❌ aristotle-chromadb"
echo "  ❌ aristotle-neo4j"
echo "  ❌ aristotle-inngest"
echo "  ❌ aristotle-alloy"
echo "  ❌ aristotle-duckdb"
echo ""

read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "🛑 Stopping containers..."

# Array of containers to remove
CONTAINERS_TO_REMOVE=(
    "aristotle-resume-ner"
    "aristotle-docmost"
    "aristotle-docmost-db"
    "aristotle-docmost-redis"
    "aristotle-mlflow"
    "aristotle-dev-db"
    "aristotle-test-db"
    "aristotle-qdrant"
    "aristotle-prefect"
    "aristotle-chromadb"
    "aristotle-neo4j"
    "aristotle-inngest"
    "aristotle-alloy"
    "aristotle-duckdb"
)

for container in "${CONTAINERS_TO_REMOVE[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "  Stopping ${container}..."
        docker stop "${container}" 2>/dev/null || true
    fi
done

echo ""
echo "🗑️  Removing containers..."

for container in "${CONTAINERS_TO_REMOVE[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "  Removing ${container}..."
        docker rm "${container}" 2>/dev/null || true
    fi
done

echo ""
echo "🧹 Cleaning up unused volumes..."
docker volume prune -f

echo ""
echo "🧹 Cleaning up unused networks..."
docker network prune -f

echo ""
echo "🧹 Cleaning up unused images..."
docker image prune -f

echo ""
echo "======================================"
echo -e "${GREEN}✅ Cleanup Complete!${NC}"
echo "======================================"
echo ""
echo "📊 Remaining containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "💾 Disk space saved:"
docker system df
echo ""
echo "🎯 Your vLLM monitoring stack is now clean and minimal!"
echo ""

