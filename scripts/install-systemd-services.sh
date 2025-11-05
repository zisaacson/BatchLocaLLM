#!/bin/bash
#
# Install vLLM Batch Server systemd services for auto-start on boot
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Installing vLLM Batch Server systemd services...${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Project root: $PROJECT_ROOT"
echo "User: $ACTUAL_USER"
echo ""

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"
chown "$ACTUAL_USER:$ACTUAL_USER" "$PROJECT_ROOT/logs"

# Copy service files
echo -e "${YELLOW}📋 Copying service files...${NC}"
cp "$PROJECT_ROOT/deployment/systemd/vllm-api-server.service" /etc/systemd/system/
cp "$PROJECT_ROOT/deployment/systemd/vllm-watchdog.service" /etc/systemd/system/

echo -e "${GREEN}✅ Service files copied${NC}"
echo ""

# Reload systemd
echo -e "${YELLOW}🔄 Reloading systemd daemon...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✅ Systemd reloaded${NC}"
echo ""

# Enable services (auto-start on boot)
echo -e "${YELLOW}🔧 Enabling services for auto-start on boot...${NC}"
systemctl enable vllm-api-server.service
systemctl enable vllm-watchdog.service
echo -e "${GREEN}✅ Services enabled${NC}"
echo ""

# Start services
echo -e "${YELLOW}▶️  Starting services...${NC}"
systemctl start vllm-api-server.service
sleep 3
systemctl start vllm-watchdog.service
sleep 2
echo -e "${GREEN}✅ Services started${NC}"
echo ""

# Check status
echo -e "${GREEN}📊 Service Status:${NC}"
echo ""
echo "API Server:"
systemctl status vllm-api-server.service --no-pager -l | head -10
echo ""
echo "Watchdog:"
systemctl status vllm-watchdog.service --no-pager -l | head -10
echo ""

echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "Services will now start automatically on boot."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status vllm-api-server    # Check API server status"
echo "  sudo systemctl status vllm-watchdog      # Check watchdog status"
echo "  sudo systemctl restart vllm-api-server   # Restart API server"
echo "  sudo systemctl restart vllm-watchdog     # Restart watchdog"
echo "  sudo journalctl -u vllm-api-server -f    # View API server logs"
echo "  sudo journalctl -u vllm-watchdog -f      # View watchdog logs"
echo "  sudo systemctl disable vllm-api-server   # Disable auto-start"
echo "  sudo systemctl disable vllm-watchdog     # Disable auto-start"
echo ""

