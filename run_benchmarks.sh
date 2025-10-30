#!/bin/bash
# Benchmark runner script - makes it easy to run all tests

set -e

echo "=================================="
echo "🚀 vLLM Benchmark Runner"
echo "=================================="
echo ""

# Check for zombie processes
echo "🔍 Checking for zombie processes..."
ZOMBIES=$(ps aux | grep -E "python.*vllm|python.*batch" | grep -v grep | wc -l)
if [ $ZOMBIES -gt 0 ]; then
    echo "⚠️  Found $ZOMBIES running processes:"
    ps aux | grep -E "python.*vllm|python.*batch" | grep -v grep
    echo ""
    read -p "Kill these processes? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "python.*vllm" || true
        pkill -f "python.*batch" || true
        sleep 2
        echo "✅ Processes killed"
    fi
fi

# Check GPU
echo ""
echo "🎮 GPU Status:"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
echo ""

# Menu
echo "Select benchmark to run:"
echo ""
echo "  1) Llama 3.2 1B - 5K batch (DONE ✅)"
echo "  2) Llama 3.2 3B - 5K batch"
echo "  3) Qwen 3 4B - 5K batch"
echo "  4) Gemma 3 4B - 50K batch (6 hours)"
echo "  5) Llama 3.2 1B - 50K batch (18 min)"
echo "  6) OLMo 1B - 5K batch"
echo "  7) Run cost analysis"
echo "  8) View benchmark summary"
echo "  9) Custom test"
echo "  0) Exit"
echo ""
read -p "Choice: " choice

case $choice in
    1)
        echo "✅ Already completed! View results:"
        echo "   - benchmarks/metadata/llama32-1b-5k-2025-10-28.json"
        echo "   - llama32_1b_5k_results.jsonl"
        ;;
    2)
        echo "🚀 Running Llama 3.2 3B - 5K batch..."
        echo "⚠️  Not implemented yet. Create test_llama32_3b.py first."
        ;;
    3)
        echo "🚀 Running Qwen 3 4B - 5K batch..."
        if [ ! -f "test_qwen3_4b_5k.py" ]; then
            echo "❌ test_qwen3_4b_5k.py not found"
            exit 1
        fi
        source venv/bin/activate
        python test_qwen3_4b_5k.py 2>&1 | tee qwen3_4b_5k_test.log
        ;;
    4)
        echo "🚀 Running Gemma 3 4B - 50K batch..."
        echo "⚠️  This will take ~6 hours. Continue? (y/n)"
        read -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "⚠️  Not implemented yet. Create test_gemma3_4b_50k.py first."
        fi
        ;;
    5)
        echo "🚀 Running Llama 3.2 1B - 50K batch..."
        echo "⚠️  This will take ~18 minutes. Continue? (y/n)"
        read -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "⚠️  Not implemented yet. Create test_llama32_1b_50k.py first."
        fi
        ;;
    6)
        echo "🚀 Running OLMo 1B - 5K batch..."
        echo "⚠️  Not implemented yet. Create test_olmo_1b.py first."
        ;;
    7)
        echo "💰 Running cost analysis..."
        source venv/bin/activate
        python cost_analysis.py
        ;;
    8)
        echo "📊 Benchmark Summary:"
        echo ""
        if [ -f "BENCHMARK_SUMMARY.md" ]; then
            cat BENCHMARK_SUMMARY.md | head -100
            echo ""
            echo "📄 Full report: BENCHMARK_SUMMARY.md"
        else
            echo "❌ BENCHMARK_SUMMARY.md not found"
        fi
        ;;
    9)
        echo "🔧 Custom test"
        read -p "Enter model ID (e.g., meta-llama/Llama-3.2-1B-Instruct): " model_id
        read -p "Enter batch size (e.g., 5000): " batch_size
        echo "⚠️  Custom test not implemented yet."
        ;;
    0)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Done!"

