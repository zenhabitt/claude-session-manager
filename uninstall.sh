#!/bin/bash
# Uninstall Claude Session Manager
set -e

echo ""
echo "  Removing Claude Session Manager..."
echo ""

# Kill any running processes
pkill -f "server.py" 2>/dev/null && echo "  ✓ Stopped running server" || true
pkill -f "launcher" 2>/dev/null && echo "  ✓ Stopped launcher" || true

# Remove app
if [ -d "/Applications/Claude Session Manager.app" ]; then
    rm -rf "/Applications/Claude Session Manager.app"
    echo "  ✓ Removed app from /Applications"
fi

# Remove data (trash, logs)
if [ -d "$HOME/.claude/session-manager" ]; then
    rm -rf "$HOME/.claude/session-manager"
    echo "  ✓ Removed session manager data"
fi

# Remove temporary files
rm -f /tmp/claude-session-manager.log /tmp/csm_icon_*.png /tmp/csm_icon.ppm

echo ""
echo "  ✨ Uninstall complete!"
echo ""
