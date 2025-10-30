#!/bin/bash
# GPT-OSS 20B Test with llama.cpp
# Using Unsloth's fixed GGUF version

set -e

echo "================================================================================"
echo "GPT-OSS 20B LOAD TEST - llama.cpp"
echo "================================================================================"
echo "Model: unsloth/gpt-oss-20b-GGUF (Q4_K_M - 11.6 GB)"
echo "GPU: RTX 4080 16GB"
echo "================================================================================"

# Check if llama.cpp exists
if [ ! -d "llama.cpp" ]; then
    echo ""
    echo "📥 Installing llama.cpp..."
    apt-get update
    apt-get install -y pciutils build-essential cmake curl libcurl4-openssl-dev
    
    git clone https://github.com/ggml-org/llama.cpp
    
    cmake llama.cpp -B llama.cpp/build \
        -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON -DLLAMA_CURL=ON
    
    cmake --build llama.cpp/build --config Release -j --clean-first \
        --target llama-cli llama-server
    
    cp llama.cpp/build/bin/llama-* llama.cpp/
    
    echo "✅ llama.cpp installed"
else
    echo "✅ llama.cpp already installed"
fi

echo ""
echo "📊 Initial GPU Memory:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

echo ""
echo "🚀 Testing GPT-OSS 20B with llama.cpp..."
echo "This will download the model (~11.6 GB) and test generation"
echo ""

# Test with a simple prompt
./llama.cpp/llama-cli \
    -hf unsloth/gpt-oss-20b-GGUF:Q4_K_M \
    --jinja -ngl 99 --threads -1 --ctx-size 4096 \
    --temp 1.0 --top-p 1.0 --top-k 0 \
    -n 100 \
    -p "What is the capital of France? Think step by step."

echo ""
echo "📊 Final GPU Memory:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

echo ""
echo "================================================================================"
echo "✅ TEST COMPLETE"
echo "================================================================================"
echo "If you see output above, GPT-OSS 20B works on RTX 4080!"
echo "================================================================================"

