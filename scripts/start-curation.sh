#!/bin/bash

# Unified Conquest Curation System - Quick Start
# This script starts the curation system (Label Studio + Curation API)

set -e

echo "🚀 Starting Unified Conquest Curation System..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

# Start Label Studio and Curation API
echo "📦 Starting services..."
docker-compose up -d label-studio curation-api

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check Label Studio
echo "🔍 Checking Label Studio..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Label Studio is ready at http://localhost:8080"
else
    echo "⚠️  Label Studio is starting... (may take a few more seconds)"
fi

# Check Curation API
echo "🔍 Checking Curation API..."
if curl -f http://localhost:8001/api/schemas > /dev/null 2>&1; then
    echo "✅ Curation API is ready at http://localhost:8001"
else
    echo "⚠️  Curation API is starting... (may take a few more seconds)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Unified Conquest Curation System is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Services:"
echo "   • Curation UI:    http://localhost:8001"
echo "   • Label Studio:   http://localhost:8080"
echo ""
echo "📚 Documentation:"
echo "   • Architecture:   UNIFIED_CONQUEST_CURATION_ARCHITECTURE.md"
echo "   • Template Guide: CONQUEST_TEMPLATE_GUIDE.md"
echo "   • Complete Guide: UNIFIED_CONQUEST_CURATION_COMPLETE.md"
echo ""
echo "⌨️  Keyboard Shortcuts:"
echo "   • ← →           Navigate tasks"
echo "   • Ctrl+S        Save annotation"
echo "   • Ctrl+E        Export dataset"
echo ""
echo "🛑 To stop: docker-compose down"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

