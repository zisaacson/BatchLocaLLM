#!/bin/bash

# Run tests for vLLM Batch Server + Curation System

set -e

echo "🧪 Running tests for vLLM Batch Server + Curation System"
echo ""

# Check if pytest is installed
if ! python -m pytest --version > /dev/null 2>&1; then
    echo "📦 Installing test dependencies..."
    pip install -r tests/requirements-test.txt
fi

# Run tests with coverage
echo "🏃 Running tests..."
python -m pytest tests/ \
    -v \
    --cov=curation_app \
    --cov=batch_app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    "$@"

echo ""
echo "✅ Tests complete!"
echo "📊 Coverage report: htmlcov/index.html"

