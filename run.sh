#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_PY=".venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
  python3 -m venv .venv
fi

if [ ! -f .venv/.installed ]; then
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
  touch .venv/.installed
fi

"$VENV_PY" scripts/download_and_check_model.py

exec "$VENV_PY" app.py
