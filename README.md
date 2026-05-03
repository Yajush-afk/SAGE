# SAGE

System Assistant for General Execution.

SAGE is a local-first, voice-controlled command layer for developer laptops. The
project is intentionally starting with a small Linux-first foundation: a Python
daemon, a push-to-talk command path, local speech-to-text, local LLM planning,
typed tools, local text-to-speech, SQLite memory, and an Electron control panel
after the core daemon is useful.

## Development

The Python backend uses a repo-local virtual environment. Do not install Python
dependencies globally for this project.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]"
```

Basic checks:

```bash
.venv/bin/sage --help
.venv/bin/pytest
.venv/bin/ruff check .
```

The Electron control panel keeps its Node dependencies inside
`apps/electron-control-panel/node_modules`.
