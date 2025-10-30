#!/bin/bash

# vLLM Offline Batch Processing for Qwen 3-4B with 5K candidates
# This uses vLLM's built-in offline batch mode which is MUCH more efficient

# Activate venv
source venv/bin/activate

MODEL="Qwen/Qwen3-4B-Instruct-2507"
INPUT_FILE="batch_5k_qwen.jsonl"
OUTPUT_FILE="qwen3_4b_5k_offline_results.jsonl"
LOG_FILE="qwen3_4b_5k_offline.log"

echo "🚀 Starting vLLM Offline Batch Processing"
echo "Model: $MODEL"
echo "Input: $INPUT_FILE (5000 requests)"
echo "Output: $OUTPUT_FILE"
echo "Log: $LOG_FILE"
echo ""

# Run vLLM offline batch mode
python3 -m vllm.entrypoints.openai.run_batch \
    -i "$INPUT_FILE" \
    -o "$OUTPUT_FILE" \
    --model "$MODEL" \
    --gpu-memory-utilization 0.8 \
    --enforce-eager \
    --max-model-len 8192 \
    --max-num-seqs 256 \
    --enable-prefix-caching \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "✅ Batch processing complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "Log saved to: $LOG_FILE"

# Count results
RESULT_COUNT=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo "0")
echo "Total results: $RESULT_COUNT / 5000"

