#!/bin/bash
# Check GPU memory and clear if needed before starting worker
# Prevents "not enough memory" errors on startup

set -e

# Configuration
MIN_FREE_GB="${MIN_FREE_GB:-12}"  # Minimum free GB needed for worker
FORCE_CLEAR="${FORCE_CLEAR:-false}"

echo "🎮 Checking GPU memory..."

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found! Is NVIDIA driver installed?"
    exit 1
fi

# Get GPU memory info
gpu_info=$(nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits | head -1)
free_mb=$(echo "$gpu_info" | awk '{print $1}')
total_mb=$(echo "$gpu_info" | awk '{print $3}')

free_gb=$(echo "scale=2; $free_mb / 1024" | bc)
total_gb=$(echo "scale=2; $total_mb / 1024" | bc)
used_gb=$(echo "scale=2; $total_gb - $free_gb" | bc)

echo "   Total: ${total_gb} GB"
echo "   Used:  ${used_gb} GB"
echo "   Free:  ${free_gb} GB"
echo ""

# Check if we have enough free memory
if (( $(echo "$free_gb < $MIN_FREE_GB" | bc -l) )) || [ "$FORCE_CLEAR" = "true" ]; then
    echo "⚠️  Not enough free GPU memory (need ${MIN_FREE_GB} GB, have ${free_gb} GB)"
    echo "🧹 Clearing GPU memory..."
    
    # Kill any vLLM/Python processes using GPU
    echo "   Killing vLLM/worker processes..."
    pkill -9 -f "python.*vllm" 2>/dev/null || true
    pkill -9 -f "python.*worker" 2>/dev/null || true
    pkill -9 -f "python.*api_server" 2>/dev/null || true
    
    # Wait for processes to die
    sleep 3
    
    # Check memory again
    gpu_info=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    free_mb=$gpu_info
    free_gb=$(echo "scale=2; $free_mb / 1024" | bc)
    
    echo "   After cleanup: ${free_gb} GB free"
    
    if (( $(echo "$free_gb < $MIN_FREE_GB" | bc -l) )); then
        echo "❌ Still not enough memory after cleanup!"
        echo "   Please check what's using GPU memory:"
        echo "   nvidia-smi"
        exit 1
    else
        echo "✅ GPU memory cleared successfully!"
    fi
else
    echo "✅ Sufficient GPU memory available (${free_gb} GB >= ${MIN_FREE_GB} GB)"
fi

exit 0

