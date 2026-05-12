#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

.venv/bin/pytest
.venv/bin/ruff check .
npm --prefix apps/electron-control-panel run build

if [ "${SKIP_DOCTOR:-0}" = "1" ]; then
  echo "Skipping sage doctor because SKIP_DOCTOR=1."
else
  .venv/bin/sage doctor
fi
