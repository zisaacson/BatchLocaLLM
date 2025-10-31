#!/bin/bash
#
# Start Aristotle Static Server (Documentation + Integration)
#
# This server provides:
# - Documentation for engineers and AI agents (port 4081)
# - Aris integration files (vllm-batch-client.ts, etc.)
#

set -e

echo "=========================================="
echo "🚀 Starting Aristotle Static Server"
echo "=========================================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please create venv first: python3 -m venv venv"
    exit 1
fi

# Check if port 4081 is already in use
if lsof -Pi :4081 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 4081 is already in use!"
    echo ""
    echo "Existing process:"
    lsof -Pi :4081 -sTCP:LISTEN
    echo ""
    read -p "Kill existing process and restart? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔪 Killing existing process..."
        lsof -ti:4081 | xargs kill -9
        sleep 1
    else
        echo "❌ Aborted"
        exit 1
    fi
fi

echo "🌐 Starting server on http://localhost:4081"
echo ""
echo "📚 Available services:"
echo "  - Documentation:  http://localhost:4081"
echo "  - Integration:    http://localhost:4081/integration"
echo "  - Health Check:   http://localhost:4081/health"
echo ""
echo "📖 Documentation files:"
echo "  - START_HERE.md"
echo "  - ARISTOTLE_BUILD_INSTRUCTIONS.md"
echo "  - COMPLETE_DATA_FLOW_IMPLEMENTATION.md"
echo "  - AUTO_IMPORT_COMPLETE.md"
echo "  - README_CURATION_SYSTEM.md"
echo ""
echo "🤖 For AI agents:"
echo "   curl http://localhost:4081/START_HERE.md"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Activate venv and start server
source venv/bin/activate
python -m core.batch_app.static_server

