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

# Load settings saved by the Settings dialog.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to download the model and install llama.cpp." >&2
  exit 1
fi

"$VENV_PY" download_and_check_model.py
MODEL_PATH="$("$VENV_PY" -c 'from download_and_check_model import model_path; print(model_path())')"

LLAMA_HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_SERVER_PORT:-5001}"
LLAMA_URL="http://${LLAMA_HOST}:${LLAMA_PORT}"

N_CTX="${N_CTX:-6144}"
N_BATCH="${N_BATCH:-512}"
DEFAULT_THREADS="$(( $(nproc 2>/dev/null || echo 4) / 2 ))"
if [ "$DEFAULT_THREADS" -lt 1 ]; then
  DEFAULT_THREADS=1
fi
N_THREADS="${N_THREADS:-$DEFAULT_THREADS}"
N_GPU_LAYERS="${N_GPU_LAYERS:-0}"
LLM_MODEL="${LLM_MODEL:-MiniCPM5-2B}"

find_llama() {
  if [ -n "${LLAMA_SERVER_BIN:-}" ] && [ -x "${LLAMA_SERVER_BIN}" ]; then
    printf '%s\n' "$LLAMA_SERVER_BIN"
    return 0
  fi
  if command -v llama >/dev/null 2>&1; then
    command -v llama
    return 0
  fi
  if [ -x "$HOME/.local/bin/llama" ]; then
    printf '%s\n' "$HOME/.local/bin/llama"
    return 0
  fi
  if command -v llama-server >/dev/null 2>&1; then
    command -v llama-server
    return 0
  fi
  return 1
}

if ! LLAMA_BIN="$(find_llama)"; then
  echo "llama.cpp was not found; installing it with the official installer..."
  curl -LsSf https://llama.app/install.sh | sh
  if ! LLAMA_BIN="$(find_llama)"; then
    echo "Could not install llama.cpp automatically." >&2
    echo "Install it from https://llama.app and set LLAMA_SERVER_BIN in .env if needed." >&2
    exit 1
  fi
fi

SERVER_PID=""
SERVER_LOG=""

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    echo
    echo "Stopping llama.cpp server..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if curl -fsS "${LLAMA_URL}/health" >/dev/null 2>&1; then
  echo "Using the llama.cpp server already running at ${LLAMA_URL}"
else
  mkdir -p logs
  SERVER_LOG="logs/llama-server-$(date +%Y-%m-%d_%H-%M-%S).log"
  SERVER_ARGS=(
    --model "$MODEL_PATH"
    --alias "$LLM_MODEL"
    --host "$LLAMA_HOST"
    --port "$LLAMA_PORT"
    --ctx-size "$N_CTX"
    --batch-size "$N_BATCH"
    --threads "$N_THREADS"
    --gpu-layers "$N_GPU_LAYERS"
    --jinja
    --no-webui
  )

  if [ "$(basename "$LLAMA_BIN")" = "llama-server" ]; then
    echo "Starting llama.cpp server: ${LLAMA_BIN}"
    "$LLAMA_BIN" "${SERVER_ARGS[@]}" >"$SERVER_LOG" 2>&1 &
  else
    echo "Starting llama.cpp server: ${LLAMA_BIN} serve"
    "$LLAMA_BIN" serve "${SERVER_ARGS[@]}" >"$SERVER_LOG" 2>&1 &
  fi
  SERVER_PID=$!

  echo "Waiting for llama.cpp at ${LLAMA_URL} (log: ${SERVER_LOG})..."
  ready=0
  for _ in $(seq 1 180); do
    if curl -fsS "${LLAMA_URL}/health" >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  if [ "$ready" -ne 1 ]; then
    echo "llama.cpp server failed to start. Last log lines:" >&2
    tail -n 40 "$SERVER_LOG" >&2 || true
    exit 1
  fi
fi

echo "llama.cpp ready at ${LLAMA_URL}"
"$VENV_PY" app.py
