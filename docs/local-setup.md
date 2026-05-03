# Local Setup

SAGE is designed to run without paid APIs.

Target development environment:

- Fedora KDE Wayland
- Repo-local Python `.venv`
- ffmpeg
- Whisper.cpp
- Ollama with Gemma 4
- Piper

Create the Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]"
```

Verify the scaffold:

```bash
.venv/bin/sage --help
.venv/bin/pytest
.venv/bin/ruff check .
```

Start the Phase 2 local daemon:

```bash
.venv/bin/sage daemon start
```

In another shell:

```bash
.venv/bin/sage daemon health
.venv/bin/sage text "start the frontend"
.venv/bin/sage commands recent
.venv/bin/sage tools list
```

Phase 3 voice input requires a local Whisper.cpp-compatible transcription
endpoint before `.venv/bin/sage listen-once` can produce transcripts. SAGE
defaults to:

```text
http://127.0.0.1:2022/v1/audio/transcriptions
```

The recorder uses `ffmpeg` against the default PulseAudio/PipeWire input:

```text
ffmpeg -f pulse -i default
```

If Whisper.cpp is not running, `.venv/bin/sage listen-once` records the failure
in command history instead of executing anything.

Phase 4 planning requires Ollama to be running with the configured local model:

```bash
ollama serve
ollama pull gemma4
```

Then run:

```bash
.venv/bin/sage text "start the frontend"
.venv/bin/sage commands recent
```

At this phase SAGE should produce a validated intent plan, but it still will not
execute tools.

Phase 5 adds safety decisions and confirmations:

```bash
.venv/bin/sage text "start the frontend"
.venv/bin/sage commands recent
.venv/bin/sage commands confirm <command-id> "confirm start"
.venv/bin/sage commands cancel <command-id>
```

After Phase 6, confirmed commands with registered tool actions can execute.
Commands without executable tool actions are only marked confirmed.

Phase 6 adds the first typed tools:

```bash
.venv/bin/sage tools list
.venv/bin/sage text "what project is this"
.venv/bin/sage text "find process on port 3000"
.venv/bin/sage text "run tests"
```

The exact tool calls depend on the local model's structured plan. Unknown tools
are blocked, and tool arguments are validated before execution.

SAGE now also has a direct planner for obvious commands, so these can work even
before the local LLM is tuned:

```bash
.venv/bin/sage text "what project is this"
.venv/bin/sage text "what is running on port 3000"
.venv/bin/sage text "list processes"
.venv/bin/sage text "run tests"
```

Run local diagnostics:

```bash
.venv/bin/sage doctor
.venv/bin/sage diagnostics
```

`.venv/bin/sage doctor` exits non-zero when required local dependencies are
missing. Piper is required only when `piper_enabled` is true.

The Electron control panel lives in `apps/electron-control-panel`:

```bash
cd apps/electron-control-panel
npm install
npm run dev
```

The daemon allows the Vite control panel origins `http://127.0.0.1:5174` and
`http://localhost:5174`. To open the Electron shell against the Vite dev server:

```bash
npm run dev
npm run dev:electron
```

The first MVP will use a KDE global shortcut that invokes:

```bash
.venv/bin/sage listen-once
```
