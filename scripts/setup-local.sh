#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]"

if command -v npm >/dev/null 2>&1; then
  npm --prefix apps/electron-control-panel install
else
  echo "npm was not found; install Node/npm before using the control panel." >&2
fi

cat <<'MSG'

Local repo setup complete.

Manual wiring still required:
- install ffmpeg, rg, Ollama, Whisper.cpp, Piper, and Node/npm if missing
- start Ollama and pull the configured model
- configure Whisper model path and Piper voice path in SAGE runtime settings
- run .venv/bin/sage doctor after the daemon/settings are configured

MSG
