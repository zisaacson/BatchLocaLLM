#!/bin/bash
# =============================================================================
# Aristotle Inference Endpoint Setup Script
# =============================================================================
#
# This script sets up the complete inference endpoint with:
# 1. vLLM Batch API (systemd service with direct GPU access)
# 2. Label Studio (Docker)
# 3. Monitoring stack (Docker: Grafana, Prometheus, Loki)
#
# =============================================================================

set -e  # Exit on error

echo "========================================================================="
echo "Aristotle Inference Endpoint Setup"
echo "========================================================================="
echo ""

# Check if running from correct directory
if [ ! -f "batch_app/api_server.py" ]; then
    echo "ERROR: Must run from vllm-batch-server directory"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "ERROR: Python venv not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
    exit 1
fi

echo "Step 1: Installing systemd services..."
echo "---------------------------------------------------------------------"
sudo cp aristotle-batch-api.service /etc/systemd/system/
sudo cp aristotle-batch-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aristotle-batch-api
sudo systemctl enable aristotle-batch-worker
echo "✓ Systemd services installed"
echo ""

echo "Step 2: Starting Docker services (Label Studio + Monitoring)..."
echo "---------------------------------------------------------------------"
docker compose up -d
echo "✓ Docker services started"
echo ""

echo "Step 3: Starting vLLM Batch API + Worker..."
echo "---------------------------------------------------------------------"
sudo systemctl start aristotle-batch-api
sudo systemctl start aristotle-batch-worker
sleep 3
sudo systemctl status aristotle-batch-api --no-pager
echo ""
sudo systemctl status aristotle-batch-worker --no-pager
echo ""

echo "========================================================================="
echo "Setup Complete!"
echo "========================================================================="
echo ""
echo "Services:"
echo "  - vLLM Batch API:    http://localhost:4080"
echo "  - Label Studio:      http://localhost:4015"
echo "  - Grafana:           http://localhost:4020 (admin/admin)"
echo "  - Prometheus:        http://localhost:4022"
echo "  - Loki:              http://localhost:4021"
echo ""
echo "Management Commands:"
echo "  - View API logs:     journalctl -u aristotle-batch-api -f"
echo "  - Restart API:       sudo systemctl restart aristotle-batch-api"
echo "  - Stop API:          sudo systemctl stop aristotle-batch-api"
echo ""
echo "  - View Worker logs:  journalctl -u aristotle-batch-worker -f"
echo "  - Restart Worker:    sudo systemctl restart aristotle-batch-worker"
echo "  - Stop Worker:       sudo systemctl stop aristotle-batch-worker"
echo ""
echo "  - Docker services:   docker compose ps"
echo ""
echo "Testing:"
echo "  curl http://localhost:4080/v1/models"
echo ""

