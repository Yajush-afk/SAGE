# SAGE

System Assistant for General Execution.

SAGE is a local-first, voice-controlled command layer for developer laptops. The
project is intentionally starting with a small Linux-first foundation: a Python
daemon, a push-to-talk command path, local speech-to-text, local LLM planning,
typed tools, local text-to-speech, SQLite memory, and an Electron control panel
after the core daemon is useful.

## Current Phase

Phase 0: repository and environment foundation.

This phase only establishes the project structure, packaging metadata, CLI
entrypoint, documentation skeleton, and baseline tests.

## Development

The intended project environment is Conda-managed Python 3.12:

```bash
conda env create -f environment.yml
conda activate sage
pip install -e ".[dev]"
```

Basic checks:

```bash
sage --help
pytest
ruff check .
```
