#!/bin/bash

# Run all model benchmarks sequentially
# This will take several hours to complete all models

echo "🚀 Starting Full Benchmark Suite"
echo "=================================="
echo ""
echo "Models to test:"
echo "  1. Qwen 3-4B"
echo "  2. Gemma 3-4B"
echo "  3. Llama 3.2-3B"
echo "  4. Llama 3.2-1B"
echo ""
echo "Total requests: 20,000 (5K per model)"
echo "Estimated time: ~2-3 hours"
echo ""
read -p "Press Enter to start..."

# Track start time
START_TIME=$(date +%s)

# 1. Qwen 3-4B
echo ""
echo "=========================================="
echo "1/4: Testing Qwen 3-4B"
echo "=========================================="
./test_qwen3_4b_5k_offline.sh
echo "✅ Qwen 3-4B complete"

# 2. Gemma 3-4B
echo ""
echo "=========================================="
echo "2/4: Testing Gemma 3-4B"
echo "=========================================="
./test_gemma3_4b_5k_offline.sh
echo "✅ Gemma 3-4B complete"

# 3. Llama 3.2-3B
echo ""
echo "=========================================="
echo "3/4: Testing Llama 3.2-3B"
echo "=========================================="
./test_llama32_3b_5k_offline.sh
echo "✅ Llama 3.2-3B complete"

# 4. Llama 3.2-1B
echo ""
echo "=========================================="
echo "4/4: Testing Llama 3.2-1B"
echo "=========================================="
./test_llama32_1b_5k_offline.sh
echo "✅ Llama 3.2-1B complete"

# Calculate total time
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
HOURS=$((TOTAL_TIME / 3600))
MINUTES=$(((TOTAL_TIME % 3600) / 60))
SECONDS=$((TOTAL_TIME % 60))

echo ""
echo "=========================================="
echo "🎉 All Benchmarks Complete!"
echo "=========================================="
echo "Total time: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "Results:"
echo "  - qwen3_4b_5k_offline_results.jsonl"
echo "  - gemma3_4b_5k_offline_results.jsonl"
echo "  - llama32_3b_5k_offline_results.jsonl"
echo "  - llama32_1b_5k_offline_results.jsonl"
echo ""
echo "View results at: http://localhost:8001/"

