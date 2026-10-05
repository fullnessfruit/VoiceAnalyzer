#!/bin/sh
# Remove the .venv created by install.sh.
# Leaves source, config.yaml, refs, data, and cache in place.
cd "$(dirname "$0")" || exit 1

echo "=== VoiceAnalyzer Uninstall ==="

if [ -L ".venv" ]; then
  echo ".venv is a link. Refusing to remove it." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo ".venv is not present. Nothing to remove."
  exit 0
fi

echo "Removing .venv. This can take a while."
if ! rm -rf ".venv"; then
  echo "Failed to remove .venv. Stop the server if it is using this environment, then run this script again." >&2
  exit 1
fi

if [ -d ".venv" ] || [ -L ".venv" ]; then
  echo "Failed to remove .venv. Stop the server if it is using this environment, then run this script again." >&2
  exit 1
fi

echo ""
echo "=== Uninstall complete ==="
echo "Removed .venv."
echo "Source, config.yaml, refs, data, and cache were left in place."
