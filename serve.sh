#!/bin/sh
# Serve greentea in a browser on the local network.
# Usage: ./serve.sh [host-ip]
#
# textual serve spawns child processes using whatever `python` is in PATH,
# not the venv python — so we must pass the venv python explicitly via -c.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
VENV_TEXTUAL="$SCRIPT_DIR/.venv/bin/textual"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "No venv found. Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

HOST="${1:-$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')}"
PORT=8765

echo "Serving at http://$HOST:$PORT"
exec "$VENV_TEXTUAL" serve \
    -h 0.0.0.0 \
    -p "$PORT" \
    --url "http://$HOST:$PORT" \
    -c "$VENV_PYTHON $SCRIPT_DIR/greentea.py"
