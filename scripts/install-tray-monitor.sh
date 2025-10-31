#!/bin/bash
# Install Aristotle System Tray Monitor

set -e

echo "🚀 Installing Aristotle System Tray Monitor..."

# Install required packages
echo "📦 Installing dependencies..."
sudo apt-get update
sudo apt-get install -y \
    gir1.2-gtk-3.0 \
    gir1.2-appindicator3-0.1 \
    python3-gi \
    python3-requests

# Note: We use system python3-gi instead of venv because it requires system libraries
echo "✅ Using system Python GI bindings (python3-gi)"

# Make tray script executable
chmod +x monitoring/aristotle-tray.py

# Install desktop file for autostart
echo "⚙️  Setting up autostart..."
mkdir -p ~/.config/autostart
cp aristotle-tray.desktop ~/.config/autostart/

# Also install to applications
mkdir -p ~/.local/share/applications
cp aristotle-tray.desktop ~/.local/share/applications/

echo ""
echo "✅ Installation complete!"
echo ""
echo "📊 The system tray monitor will:"
echo "   - Show GPU temperature, memory, and utilization"
echo "   - Display active batch job count"
echo "   - Show API status (online/offline)"
echo "   - Provide quick links to Grafana, Label Studio, API docs"
echo "   - Allow restarting services and viewing logs"
echo ""
echo "🔧 To start now:"
echo "   ./monitoring/aristotle-tray.py"
echo ""
echo "🔄 To start on next login:"
echo "   It's already configured to auto-start!"
echo ""
echo "📍 You'll see an NVIDIA icon in your system tray with stats."
echo ""

