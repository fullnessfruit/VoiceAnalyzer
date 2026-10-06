#!/bin/sh
# Delete only the shared key, including after uninstall has removed .venv.
set -e
cd "$(dirname "$0")"
echo "This key is shared by ImageAnalyzer, VoiceAnalyzer, and the OCR broker."
if [ -x .venv/bin/python ]; then
  .venv/bin/python app/shared_secret.py delete
elif [ -x .venv/Scripts/python.exe ]; then
  .venv/Scripts/python.exe app/shared_secret.py delete
elif command -v python3 >/dev/null 2>&1; then
  python3 app/shared_secret.py delete
else
  python app/shared_secret.py delete
fi
