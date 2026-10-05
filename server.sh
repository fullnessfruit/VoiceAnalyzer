#!/bin/sh
# Start VoiceAnalyzer on 127.0.0.1:8000.
# Uses .venv when it exists. Override with HOST and PORT.
cd "$(dirname "$0")" || exit 1

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  PY="python"
fi

exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
