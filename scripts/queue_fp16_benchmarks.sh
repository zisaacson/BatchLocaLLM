#!/bin/bash
# Queue OLMo 2 7B and GPT-OSS 20B benchmarks (FP16 with CPU offload)

set -e

API_URL="http://localhost:4080"

echo "============================================================"
echo "QUEUING OLMO 2 7B FP16 (8GB CPU OFFLOAD)"
echo "============================================================"

# Upload OLMo batch file
OLMO_FILE_ID=$(curl -s -X POST "$API_URL/v1/files" \
  -F "file=@batch_5k_olmo2_fp16.jsonl" \
  -F "purpose=batch" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ File uploaded: $OLMO_FILE_ID"

# Create OLMo batch
OLMO_BATCH_ID=$(curl -s -X POST "$API_URL/v1/batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$OLMO_FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\",
    \"metadata\": {
      \"description\": \"OLMo 2 7B FP16 - 5K benchmark\",
      \"model\": \"allenai/OLMo-2-1124-7B-Instruct\"
    }
  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ Batch created: $OLMO_BATCH_ID"

echo ""
echo "============================================================"
echo "QUEUING GPT-OSS 20B FP16 (25GB CPU OFFLOAD)"
echo "============================================================"

# Upload GPT-OSS batch file
GPTOSS_FILE_ID=$(curl -s -X POST "$API_URL/v1/files" \
  -F "file=@batch_5k_gptoss_fp16.jsonl" \
  -F "purpose=batch" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ File uploaded: $GPTOSS_FILE_ID"

# Create GPT-OSS batch
GPTOSS_BATCH_ID=$(curl -s -X POST "$API_URL/v1/batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$GPTOSS_FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\",
    \"metadata\": {
      \"description\": \"GPT-OSS 20B FP16 - 5K benchmark\",
      \"model\": \"openai/gpt-oss-20b\"
    }
  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "✅ Batch created: $GPTOSS_BATCH_ID"

echo ""
echo "============================================================"
echo "✅ BOTH JOBS QUEUED!"
echo "   OLMo 2 7B: $OLMO_BATCH_ID"
echo "   GPT-OSS 20B: $GPTOSS_BATCH_ID"
echo ""
echo "Worker will process sequentially with automatic hot-swap:"
echo "  1. Load OLMo 2 7B (8GB CPU offload) → Process 5K → Unload"
echo "  2. Load GPT-OSS 20B (25GB CPU offload) → Process 5K → Unload"
echo ""
echo "Monitor: tail -f logs/worker.log"
echo "============================================================"

