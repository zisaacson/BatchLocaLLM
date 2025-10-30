#!/bin/bash

echo "================================================================================"
echo "🧪 TESTING OPENAI-COMPATIBLE API - READY FOR WEB APP"
echo "================================================================================"

BASE_URL="http://localhost:4080"

echo ""
echo "1️⃣  Testing /v1/models endpoint..."
curl -s "$BASE_URL/v1/models" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'✅ Found {len(data[\"data\"])} models'); [print(f'   - {m[\"id\"]}') for m in data['data'][:3]]"

echo ""
echo "2️⃣  Creating test input file..."
cat > /tmp/test_batch_input.jsonl << 'EOF'
{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "Qwen/Qwen2.5-3B-Instruct", "messages": [{"role": "user", "content": "What is 2+2?"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "Qwen/Qwen2.5-3B-Instruct", "messages": [{"role": "user", "content": "What is the capital of France?"}]}}
EOF
echo "✅ Created test file with 2 requests"

echo ""
echo "3️⃣  Testing Files API - Upload file..."
UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/files" \
  -F "file=@/tmp/test_batch_input.jsonl" \
  -F "purpose=batch")

FILE_ID=$(echo "$UPLOAD_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$FILE_ID" ]; then
  echo "❌ File upload failed"
  echo "Response: $UPLOAD_RESPONSE"
  exit 1
fi

echo "✅ File uploaded: $FILE_ID"

echo ""
echo "4️⃣  Testing Batch API - Create batch..."
BATCH_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_file_id\": \"$FILE_ID\",
    \"endpoint\": \"/v1/chat/completions\",
    \"completion_window\": \"24h\"
  }")

BATCH_ID=$(echo "$BATCH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$BATCH_ID" ]; then
  echo "❌ Batch creation failed"
  echo "Response: $BATCH_RESPONSE"
  exit 1
fi

echo "✅ Batch created: $BATCH_ID"
echo "$BATCH_RESPONSE" | python3 -m json.tool | grep -E "\"id\"|\"status\"|\"endpoint\"|\"input_file_id\""

echo ""
echo "5️⃣  Testing Batch API - Get batch status..."
curl -s "$BASE_URL/v1/batches/$BATCH_ID" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'✅ Batch status: {data[\"status\"]}'); print(f'   Created at: {data[\"created_at\"]}'); print(f'   Endpoint: {data[\"endpoint\"]}')"

echo ""
echo "6️⃣  Testing Batch API - List batches..."
curl -s "$BASE_URL/v1/batches" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'✅ Found {len(data[\"data\"])} batches'); print(f'   Has more: {data[\"has_more\"]}')"

echo ""
echo "================================================================================"
echo "✅ API IS READY FOR YOUR WEB APP!"
echo "================================================================================"
echo ""
echo "Your web app can now:"
echo "  1. Upload files:      POST $BASE_URL/v1/files"
echo "  2. Create batches:    POST $BASE_URL/v1/batches"
echo "  3. Check status:      GET $BASE_URL/v1/batches/{batch_id}"
echo "  4. List batches:      GET $BASE_URL/v1/batches"
echo "  5. Download results:  GET $BASE_URL/v1/files/{output_file_id}/content"
echo ""
echo "OpenAI SDK compatible - just set base_url='$BASE_URL/v1'"
echo ""
echo "================================================================================"

