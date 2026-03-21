#!/usr/bin/env bash
set -euo pipefail

DAEMON_DIR="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="$HOME"
PLIST_NAME="com.sogos.claude-daemon"
PLIST_SRC="$DAEMON_DIR/$PLIST_NAME.plist"
PLIST_DST="$HOME_DIR/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$HOME_DIR/Library/Logs/claude-daemon"

# Find Python — prefer venv if it exists
if [ -f "$DAEMON_DIR/venv/bin/python" ]; then
    PYTHON="$DAEMON_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "Error: python3 not found"
    exit 1
fi

echo "=== Claude Assistant Daemon Installer ==="
echo "Daemon dir:  $DAEMON_DIR"
echo "Python:      $PYTHON"
echo "Plist:       $PLIST_DST"
echo "Logs:        $LOG_DIR"

# Create log dir
mkdir -p "$LOG_DIR"

# Unload if already loaded
launchctl unload "$PLIST_DST" 2>/dev/null || true

# Generate plist with actual paths
sed \
    -e "s|__DAEMON_PYTHON__|$PYTHON|g" \
    -e "s|__DAEMON_DIR__|$DAEMON_DIR|g" \
    -e "s|__HOME__|$HOME_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# Load the service
launchctl load "$PLIST_DST"

echo "Daemon installed and started."
echo "Check logs: tail -f $LOG_DIR/stdout.log"
