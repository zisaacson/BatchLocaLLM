#!/bin/bash
set -e

echo "🚀 Deploying vLLM Batch Server to RTX 4080 (10.0.0.223)"
echo "========================================================="

RTX_HOST="10.0.0.223"
RTX_USER="user"  # Change this to your actual username
REMOTE_DIR="~/vllm-batch-server"

echo ""
echo "Step 1: Clone repo on RTX 4080..."
ssh ${RTX_USER}@${RTX_HOST} "
  cd ~ && \
  rm -rf vllm-batch-server && \
  git clone https://github.com/zisaacson/vllm-batch-server.git && \
  cd vllm-batch-server && \
  echo '✅ Repo cloned'
"

echo ""
echo "Step 2: Build Docker image on RTX 4080..."
ssh ${RTX_USER}@${RTX_HOST} "
  cd ~/vllm-batch-server && \
  docker compose build && \
  echo '✅ Image built'
"

echo ""
echo "Step 3: Start vLLM server..."
ssh ${RTX_USER}@${RTX_HOST} "
  cd ~/vllm-batch-server && \
  docker compose up -d && \
  echo '✅ Server starting'
"

echo ""
echo "Step 4: Wait for model download and server startup..."
echo "This will take 5-10 minutes (downloading Gemma 3 12B ~8GB)"
ssh ${RTX_USER}@${RTX_HOST} "
  cd ~/vllm-batch-server && \
  echo 'Waiting for server to be ready...' && \
  for i in {1..60}; do
    if docker compose logs | grep -q 'Uvicorn running'; then
      echo '✅ Server is ready!'
      break
    fi
    echo \"Attempt \$i/60: Still starting...\"
    sleep 10
  done
"

echo ""
echo "Step 5: Test the server..."
ssh ${RTX_USER}@${RTX_HOST} "
  curl -s http://localhost:8000/health && \
  echo '' && \
  echo '✅ Health check passed!'
"

echo ""
echo "Step 6: Install systemd service for auto-start..."
ssh ${RTX_USER}@${RTX_HOST} "
  cd ~/vllm-batch-server && \
  sudo cp /tmp/vllm-batch-server.service /etc/systemd/system/ 2>/dev/null || \
  sudo tee /etc/systemd/system/vllm-batch-server.service > /dev/null << 'SYSTEMD'
[Unit]
Description=vLLM Batch Server
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/${RTX_USER}/vllm-batch-server
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0
User=${RTX_USER}
Group=${RTX_USER}

[Install]
WantedBy=multi-user.target
SYSTEMD
  sudo systemctl daemon-reload && \
  sudo systemctl enable vllm-batch-server && \
  echo '✅ Systemd service installed and enabled'
"

echo ""
echo "Step 7: Stop Ollama (optional - uncomment if ready)..."
# ssh ${RTX_USER}@${RTX_HOST} "
#   sudo systemctl stop ollama && \
#   sudo systemctl disable ollama && \
#   echo '✅ Ollama stopped and disabled'
# "

echo ""
echo "========================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "========================================================="
echo ""
echo "vLLM Server: http://10.0.0.223:8000"
echo "Health Check: curl http://10.0.0.223:8000/health"
echo "Metrics: http://10.0.0.223:9090/metrics"
echo ""
echo "Test single request:"
echo "curl -X POST http://10.0.0.223:8000/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"model\": \"google/gemma-3-12b-it\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
echo ""
echo "To stop Ollama, uncomment Step 7 in this script and re-run."
echo ""
