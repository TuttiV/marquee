#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run bash run-syncplay.sh once first so the setup can finish."; exit 1; }
echo "Starting a Syncplay server on port 8999. Share your IP address and this port with friends."
exec .venv/bin/python syncplayServer.py --port 8999 "$@"
