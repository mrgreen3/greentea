#!/bin/bash
set -e

cd "$(dirname "$0")"

LOCAL_IP=$(ip route get 1.1.1.1 | awk '{print $7; exit}')

.venv/bin/pip install -q -r requirements.txt

echo "Serving at http://${LOCAL_IP}:8766"
exec .venv/bin/python web_server.py
