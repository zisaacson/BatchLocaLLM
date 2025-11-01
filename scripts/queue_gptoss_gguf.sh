#!/bin/bash
# Queue GPT-OSS 20B GGUF (Q4_0 = 11.5 GB, NO CPU OFFLOAD!)

set -e

API_URL="http://localhost:4080"

echo "============================================================"
echo "QUEUING GPT-OSS 20B Q4_0 GGUF (NO CPU OFFLOAD!)"
echo "============================================================"

# Upload batch file
GPTOSS_FILE_ID=$(curl -s -X POST "$API_URL/v1/files" \
  -F "file=@batch_5k_gptoss_gguf.jsonl" \
  -F "purpose=batch" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ File uploaded: $GPTOSS_FILE_ID"

# Create batch
GPTOSS_BATCH_ID=$(curl -s -X POST "$API_URL/v1/batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$GPTOSS_FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\",
    \"metadata\": {
      \"description\": \"GPT-OSS 20B Q4_0 GGUF - NO CPU OFFLOAD\",
      \"model\": \"unsloth/gpt-oss-20b-GGUF\"
    }
  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ Batch created: $GPTOSS_BATCH_ID"
echo ""
echo "============================================================"
echo "✅ GPT-OSS 20B GGUF QUEUED!"
echo "   Batch ID: $GPTOSS_BATCH_ID"
echo ""
echo "Q4_0 quantization = 11.5 GB"
echo "NO CPU OFFLOAD NEEDED - runs at full speed!"
echo ""
echo "Will process after OLMo 2 7B completes."
echo "============================================================"

