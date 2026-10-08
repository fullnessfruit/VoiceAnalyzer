#!/bin/sh
# Create or reuse .venv and install requirements.txt.
# Does not download model weights. Python 3.10 or 3.11 is preferred.
# Python 3.12 and newer warns and continues. Below 3.10 stops.
cd "$(dirname "$0")" || exit 1
set -e

echo "=== VoiceAnalyzer Install ==="

# Print one interpreter name. Prefer 3.11, then 3.10, then python3, then python.
pick_python() {
  for c in python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        echo "$c"
        return 0
      fi
    fi
  done
  return 1
}

# Print the python inside an existing venv, POSIX layout first.
venv_python() {
  if [ -x ".venv/bin/python" ]; then
    echo ".venv/bin/python"
    return 0
  fi
  if [ -x ".venv/Scripts/python.exe" ]; then
    echo ".venv/Scripts/python.exe"
    return 0
  fi
  return 1
}

if VPY=$(venv_python); then
  echo "Using existing .venv"
else
  if ! PY=$(pick_python); then
    echo "Python 3.10 or newer was not found. Install Python 3.11 and run this script again." >&2
    exit 1
  fi
  echo "Creating .venv with $PY"
  if ! "$PY" -m venv .venv; then
    echo "Failed to create .venv" >&2
    exit 1
  fi
  if ! VPY=$(venv_python); then
    echo "Failed to create .venv" >&2
    exit 1
  fi
fi

if ! "$VPY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "The Python in .venv is older than 3.10. .venv was left in place." >&2
  echo "Install Python 3.11, remove .venv, and run this script again." >&2
  exit 1
fi

echo "Using Python:"
"$VPY" -c 'import sys; print(sys.version)'

if "$VPY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "WARNING: Python 3.12 or newer is not the intended runtime. Python 3.10 or 3.11 is preferred. Continuing." >&2
fi

echo "Upgrading pip"
if ! "$VPY" -m pip install --upgrade pip; then
  echo "pip install failed" >&2
  exit 1
fi
echo "Installing requirements.txt. This can take a while."
if ! "$VPY" -m pip install -r requirements.txt; then
  echo "pip install failed" >&2
  exit 1
fi

echo "Preparing the shared ImageAnalyzer and VoiceAnalyzer authentication key"
"$VPY" app/shared_secret.py ensure

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg is not on PATH. The server cannot read media until ffmpeg is installed." >&2
fi
if ! command -v ffprobe >/dev/null 2>&1; then
  echo "WARNING: ffprobe is not on PATH. Duration checks need ffprobe." >&2
fi

echo ""
echo "=== Install complete ==="
echo ""
echo "Next:"
echo "  1. Put reference wavs in refs/<speaker_id>/"
echo "  2. Put the media to search under data/"
echo "  3. Start the server with ./server.sh"
echo ""
echo "Model weights are downloaded on first use. This script does not fetch them."
