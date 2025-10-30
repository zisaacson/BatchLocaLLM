#!/bin/bash
# View benchmarking dashboard in browser

echo "=================================="
echo "Benchmarking Dashboard Viewer"
echo "=================================="
echo ""

# Check if pandoc is installed
if ! command -v pandoc &> /dev/null; then
    echo "⚠️  pandoc not found. Installing..."
    echo ""
    echo "Please install pandoc:"
    echo "  Ubuntu/Debian: sudo apt install pandoc"
    echo "  macOS: brew install pandoc"
    echo "  Or visit: https://pandoc.org/installing.html"
    echo ""
    exit 1
fi

# Convert markdown to HTML
echo "📄 Converting BENCHMARKING_JOURNEY.md to HTML..."
pandoc BENCHMARKING_JOURNEY.md \
    -o benchmarks/reports/index.html \
    --standalone \
    --css=https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css \
    --metadata title="Benchmarking Journey - RTX 4080 16GB"

echo "✅ Created benchmarks/reports/index.html"
echo ""

# Start simple HTTP server
echo "🌐 Starting web server on http://localhost:8081"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd benchmarks/reports
python3 -m http.server 8081

