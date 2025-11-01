#!/bin/bash

# Download Gemma 3 12B Q4_0 GGUF model
# GGUF models must be downloaded locally before use with vLLM

echo "========================================================================"
echo "Downloading Gemma 3 12B Q4_0 GGUF"
echo "========================================================================"
echo ""

# Create models directory
mkdir -p models/gemma-3-12b-it-qat-q4_0-gguf
cd models/gemma-3-12b-it-qat-q4_0-gguf

echo "Downloading model file..."
echo "This may take a while (6 GB download)..."
echo ""

# Download using huggingface-cli
huggingface-cli download google/gemma-3-12b-it-qat-q4_0-gguf \
    --local-dir . \
    --local-dir-use-symlinks False

echo ""
echo "========================================================================"
echo "✅ Download complete!"
echo "========================================================================"
echo "Model location: $(pwd)"
echo ""
echo "To use with vLLM:"
echo "  vllm serve $(pwd)/gemma-3-12b-it-qat-q4_0.gguf"
echo ""

