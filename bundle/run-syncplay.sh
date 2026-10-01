#!/usr/bin/env bash
# Starts Syncplay from source, creating a private virtualenv on first run (macOS and Linux).
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || true)
[ -n "$PY" ] || { echo "Python 3.9+ is required (install python3)."; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting things up, this takes a minute..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  EXTRA=""
  [ "$(uname)" = "Darwin" ] && EXTRA="appnope requests"
  .venv/bin/python -m pip install -r requirements.txt PySide6 $EXTRA || { rm -rf .venv; echo "Setup failed."; exit 1; }
fi
exec .venv/bin/python syncplayClient.py "$@"
