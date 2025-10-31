#!/bin/bash

set -e

echo "🔧 Setting up vLLM Batch Server Monitoring"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if containers are running
echo "📋 Checking monitoring stack..."
if ! docker ps | grep -q aristotle-prometheus; then
    echo -e "${RED}❌ Prometheus container not running${NC}"
    exit 1
fi

if ! docker ps | grep -q aristotle-grafana; then
    echo -e "${RED}❌ Grafana container not running${NC}"
    exit 1
fi

if ! docker ps | grep -q aristotle-loki; then
    echo -e "${RED}❌ Loki container not running${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All monitoring containers running${NC}"
echo ""

# Update Prometheus configuration
echo "📝 Updating Prometheus configuration..."
docker cp monitoring/prometheus.yml aristotle-prometheus:/etc/prometheus/prometheus.yml
echo -e "${GREEN}✅ Prometheus config updated${NC}"

# Reload Prometheus
echo "🔄 Reloading Prometheus..."
docker exec aristotle-prometheus kill -HUP 1 || docker restart aristotle-prometheus
sleep 2
echo -e "${GREEN}✅ Prometheus reloaded${NC}"
echo ""

# Copy Grafana dashboards
echo "📊 Setting up Grafana dashboards..."
docker exec aristotle-grafana mkdir -p /etc/grafana/provisioning/dashboards
docker exec aristotle-grafana mkdir -p /etc/grafana/provisioning/datasources

docker cp monitoring/grafana/dashboards/dashboard-provider.yml aristotle-grafana:/etc/grafana/provisioning/dashboards/
docker cp monitoring/grafana/dashboards/vllm-dashboard.json aristotle-grafana:/etc/grafana/provisioning/dashboards/
docker cp monitoring/grafana/datasources/datasources.yml aristotle-grafana:/etc/grafana/provisioning/datasources/

echo -e "${GREEN}✅ Grafana dashboards copied${NC}"

# Restart Grafana to load new dashboards
echo "🔄 Restarting Grafana..."
docker restart aristotle-grafana
sleep 5
echo -e "${GREEN}✅ Grafana restarted${NC}"
echo ""

# Check if vLLM server is exposing metrics
echo "🔍 Checking vLLM metrics endpoint..."
if curl -s http://localhost:4080/metrics > /dev/null 2>&1; then
    echo -e "${GREEN}✅ vLLM metrics endpoint accessible${NC}"
else
    echo -e "${YELLOW}⚠️  vLLM metrics endpoint not accessible (server may not be running)${NC}"
fi
echo ""

# Print access information
echo "=========================================="
echo -e "${GREEN}✅ Monitoring Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📊 Access your monitoring dashboards:"
echo ""
echo "  Grafana:    http://localhost:4020"
echo "  Prometheus: http://localhost:4022"
echo "  Loki:       http://localhost:4021"
echo ""
echo "🔑 Default Grafana credentials:"
echo "  Username: admin"
echo "  Password: admin (change on first login)"
echo ""
echo "📈 Available metrics:"
echo "  - vLLM Server:     http://localhost:4080/metrics"
echo "  - GPU Metrics:     (install nvidia_gpu_exporter for detailed GPU metrics)"
echo ""
echo "🎯 Next steps:"
echo "  1. Open Grafana: http://localhost:4020"
echo "  2. Navigate to Dashboards → vLLM"
echo "  3. View 'vLLM Batch Server - GPU & Performance'"
echo ""
echo "💡 To view logs in Grafana:"
echo "  1. Go to Explore"
echo "  2. Select 'Loki' datasource"
echo "  3. Query: {job=\"vllm-server\"}"
echo ""

