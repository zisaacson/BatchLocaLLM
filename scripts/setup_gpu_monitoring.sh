#!/bin/bash

set -e

echo "🎮 Setting up GPU Monitoring for vLLM"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}❌ nvidia-smi not found. GPU monitoring requires NVIDIA drivers.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ NVIDIA drivers detected${NC}"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
echo ""

# Install nvidia_gpu_exporter
echo "📦 Installing nvidia_gpu_exporter..."

# Check if already installed
if command -v nvidia_gpu_exporter &> /dev/null; then
    echo -e "${YELLOW}⚠️  nvidia_gpu_exporter already installed${NC}"
else
    # Download and install
    EXPORTER_VERSION="1.2.0"
    ARCH="linux-amd64"
    
    echo "Downloading nvidia_gpu_exporter v${EXPORTER_VERSION}..."
    wget -q https://github.com/utkuozdemir/nvidia_gpu_exporter/releases/download/v${EXPORTER_VERSION}/nvidia_gpu_exporter_${EXPORTER_VERSION}_${ARCH}.tar.gz
    
    tar -xzf nvidia_gpu_exporter_${EXPORTER_VERSION}_${ARCH}.tar.gz
    sudo mv nvidia_gpu_exporter /usr/local/bin/
    rm nvidia_gpu_exporter_${EXPORTER_VERSION}_${ARCH}.tar.gz
    
    echo -e "${GREEN}✅ nvidia_gpu_exporter installed${NC}"
fi
echo ""

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/nvidia-gpu-exporter.service > /dev/null <<EOF
[Unit]
Description=NVIDIA GPU Metrics Exporter
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/nvidia_gpu_exporter
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✅ Systemd service created${NC}"

# Enable and start service
echo "🚀 Starting nvidia-gpu-exporter service..."
sudo systemctl daemon-reload
sudo systemctl enable nvidia-gpu-exporter
sudo systemctl restart nvidia-gpu-exporter
sleep 2

# Check status
if sudo systemctl is-active --quiet nvidia-gpu-exporter; then
    echo -e "${GREEN}✅ nvidia-gpu-exporter service running${NC}"
else
    echo -e "${RED}❌ Failed to start nvidia-gpu-exporter service${NC}"
    sudo systemctl status nvidia-gpu-exporter
    exit 1
fi
echo ""

# Test metrics endpoint
echo "🔍 Testing GPU metrics endpoint..."
if curl -s http://localhost:9835/metrics | grep -q "nvidia_gpu"; then
    echo -e "${GREEN}✅ GPU metrics endpoint working${NC}"
    echo ""
    echo "Sample metrics:"
    curl -s http://localhost:9835/metrics | grep "nvidia_gpu_temperature_celsius" | head -3
else
    echo -e "${RED}❌ GPU metrics endpoint not responding${NC}"
    exit 1
fi
echo ""

echo "======================================"
echo -e "${GREEN}✅ GPU Monitoring Setup Complete!${NC}"
echo "======================================"
echo ""
echo "📊 GPU Metrics available at: http://localhost:9835/metrics"
echo ""
echo "🎯 Next steps:"
echo "  1. Run: ./setup_monitoring.sh"
echo "  2. Open Grafana: http://localhost:4020"
echo "  3. View GPU metrics in vLLM dashboard"
echo ""

