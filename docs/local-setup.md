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

Phase 4 planning requires Ollama to be running with the configured local model:

```bash
ollama serve
ollama pull gemma4
```

Then run:

```bash
sage text "start the frontend"
sage commands recent
```

At this phase SAGE should produce a validated intent plan, but it still will not
execute tools.

Phase 5 adds safety decisions and confirmations:

```bash
sage text "start the frontend"
sage commands recent
sage commands confirm <command-id> "confirm start"
sage commands cancel <command-id>
```

After Phase 6, confirmed commands with registered tool actions can execute.
Commands without executable tool actions are only marked confirmed.

Phase 6 adds the first typed tools:

```bash
sage tools list
sage text "what project is this"
sage text "find process on port 3000"
sage text "run tests"
```

The exact tool calls depend on the local model's structured plan. Unknown tools
are blocked, and tool arguments are validated before execution.

The first MVP will use a KDE global shortcut that invokes:

```bash
sage listen-once
```
