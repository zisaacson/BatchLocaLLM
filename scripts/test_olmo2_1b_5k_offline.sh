#!/bin/bash

# Test OLMo 2-1B with 5K requests using vLLM offline batch mode

# Activate venv
source venv/bin/activate

MODEL="allenai/OLMo-2-0425-1B"
INPUT_FILE="batch_5k_olmo2_1b.jsonl"
OUTPUT_FILE="olmo2_1b_5k_offline_results.jsonl"
LOG_FILE="olmo2_1b_5k_offline.log"

echo "🚀 Starting vLLM Offline Batch Processing"
echo "Model: $MODEL"
echo "Input: $INPUT_FILE ($(wc -l < $INPUT_FILE) requests)"
echo "Output: $OUTPUT_FILE"
echo "Log: $LOG_FILE"
echo ""

python -m vllm.entrypoints.openai.run_batch \
    -i "$INPUT_FILE" \
    -o "$OUTPUT_FILE" \
    --model "$MODEL" \
    --gpu-memory-utilization 0.8 \
    --enforce-eager \
    --max-model-len 4096 \
    --max-num-seqs 256 \
    --enable-prefix-caching \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "✅ Batch processing complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "Log saved to: $LOG_FILE"

