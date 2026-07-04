#!/bin/bash
# Uninstall S.T.O.A. (Session Timeline Organizer & Archiver)
set -e

echo ""
echo "  Removing S.T.O.A...."
echo ""

# Kill any running processes
pkill -f "server.py" 2>/dev/null && echo "  ✓ Stopped running server" || true
pkill -f "launcher" 2>/dev/null && echo "  ✓ Stopped launcher" || true

# Remove app (both old and new names)
for app in "S.T.O.A..app" "Claude Session Manager.app"; do
    if [ -d "/Applications/$app" ]; then
        rm -rf "/Applications/$app"
        echo "  ✓ Removed $app from /Applications"
    fi
done

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
