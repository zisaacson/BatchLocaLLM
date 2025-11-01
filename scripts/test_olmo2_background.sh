#!/bin/bash
# Run OLMo 2 7B test in background with live logging

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/olmo2_7b_test.log"

cd "$PROJECT_ROOT"

echo "═══════════════════════════════════════════════════════════"
echo "  BACKGROUND MODEL TEST - OLMo 2 7B"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📝 Log file: $LOG_FILE"
echo ""
echo "To watch progress in real-time, run:"
echo "  tail -f $LOG_FILE"
echo ""
echo "═══════════════════════════════════════════════════════════"

# Stop worker to free GPU
echo "🛑 Stopping worker..."
pkill -f "python.*batch_app.worker" || true
sleep 2

# Run test in background, redirect all output to log file
echo "🚀 Starting test in background..."
nohup python core/tests/manual/test_olmo2_7b_single.py > "$LOG_FILE" 2>&1 &
TEST_PID=$!

echo "✅ Test running in background (PID: $TEST_PID)"
echo ""
echo "Commands:"
echo "  Watch logs:  tail -f $LOG_FILE"
echo "  Check GPU:   nvidia-smi"
echo "  Kill test:   kill $TEST_PID"
echo ""
echo "When test completes, restart worker with:"
echo "  nohup python -m core.batch_app.worker > logs/worker.log 2>&1 &"
echo ""

