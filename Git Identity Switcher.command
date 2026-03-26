#!/bin/bash
# Double-click in Finder to open the Git Identity Switcher UI.

PYTHON=/usr/local/bin/python3
DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$DIR/git_identity_ui.py"

# Verify python exists
if [ ! -f "$PYTHON" ]; then
  echo "ERROR: Python not found at $PYTHON"
  echo "Install from https://python.org or: brew install python"
  read -rp "Press Enter to close..."
  exit 1
fi

# Tell macOS to bring this Python process to the front once it starts
(sleep 1 && osascript -e 'tell application "Python" to activate' 2>/dev/null) &

# Run the UI — errors print here AND get written to ui_error.log
"$PYTHON" "$SCRIPT"
STATUS=$?

# If it failed, keep the window open so you can read the error
if [ $STATUS -ne 0 ]; then
  LOG="$DIR/ui_error.log"
  echo ""
  echo "--- FAILED (exit $STATUS) ---"
  [ -f "$LOG" ] && cat "$LOG"
  read -rp "Press Enter to close..."
fi
