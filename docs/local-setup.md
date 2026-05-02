# Local Setup

SAGE is designed to run without paid APIs.

Target development environment:

- Fedora KDE Wayland
- Conda-managed Python 3.12
- ffmpeg
- Whisper.cpp
- Ollama with Gemma 4
- Piper

Create the Python environment:

```bash
conda env create -f environment.yml
conda activate sage
```

Verify the scaffold:

```bash
sage --help
pytest
ruff check .
```

Start the Phase 2 local daemon:

```bash
sage daemon start
```

In another shell:

```bash
sage daemon health
sage text "start the frontend"
sage commands recent
sage tools list
```

The first MVP will use a KDE global shortcut that invokes:

```bash
sage listen-once
```
