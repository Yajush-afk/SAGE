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

Phase 3 voice input requires a local Whisper.cpp-compatible transcription
endpoint before `sage listen-once` can produce transcripts. SAGE defaults to:

```text
http://127.0.0.1:2022/v1/audio/transcriptions
```

The recorder uses `ffmpeg` against the default PulseAudio/PipeWire input:

```text
ffmpeg -f pulse -i default
```

If Whisper.cpp is not running, `sage listen-once` records the failure in command
history instead of executing anything.

The first MVP will use a KDE global shortcut that invokes:

```bash
sage listen-once
```
