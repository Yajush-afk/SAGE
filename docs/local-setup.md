# Local Setup

SAGE is designed to run locally without paid APIs. The setup has two parts:
repo-local development dependencies that scripts can install, and machine-local
audio/model/service wiring that you must configure on your laptop.

## Target Environment

- Linux desktop, currently developed against Fedora KDE Wayland
- Python 3.12 or newer
- Repo-local `.venv`
- `ffmpeg`
- `rg`
- Whisper.cpp server or CLI
- Ollama with the configured local model
- Piper and a local Piper voice model, unless TTS is disabled
- Node/npm for the Electron control panel

## Repo Setup

From the repository root:

```bash
./scripts/setup-local.sh
```

Equivalent manual commands:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]"

cd apps/electron-control-panel
npm install
```

Verify the development scaffold:

```bash
.venv/bin/sage --help
.venv/bin/pytest
.venv/bin/ruff check .
cd apps/electron-control-panel && npm run build
```

## Manual Local Wiring

These items are machine-specific and cannot be committed for you.

### Ollama

Install Ollama, start it, and pull the configured model:

```bash
systemctl start ollama
ollama pull gemma4
```

If you use a different model, update runtime settings through the daemon
settings API once the daemon is running.

### Whisper.cpp

SAGE defaults to a Whisper.cpp/OpenAI-compatible HTTP endpoint:

```text
http://127.0.0.1:2022/v1/audio/transcriptions
```

`.venv/bin/sage start` can start `whisper-server`, but only after
`whisper_model_path` points to a real local model file. The model itself is not
tracked in this repo.

### Piper

Piper is optional at runtime, but enabled by default. Configure:

- `piper_binary_path`
- `piper_voice_path`
- `audio_player`

If `piper_voice_path` is not configured, commands can still complete, but the
speech result records a TTS failure.

### Audio Input

Voice input records from ffmpeg against the default PulseAudio/PipeWire input:

```text
ffmpeg -f pulse -i default
```

If your microphone is not the default input, update `audio_input` in runtime
settings.

### Control Panel API URL

The control panel defaults to:

```text
http://127.0.0.1:8765
```

Only create `apps/electron-control-panel/.env.local` if you run the daemon at a
different URL:

```text
VITE_SAGE_API_URL=http://127.0.0.1:8765
```

## Start The Stack

Start Ollama separately:

```bash
systemctl start ollama
```

Then start SAGE:

```bash
.venv/bin/sage start
```

Start the daemon plus the Vite control panel:

```bash
.venv/bin/sage start --with-ui
```

Open:

```text
http://127.0.0.1:5174
```

The Electron shell can also be opened against the Vite dev server:

```bash
cd apps/electron-control-panel
npm run dev:electron
```

## Smoke Test

In another shell:

```bash
.venv/bin/sage daemon health
.venv/bin/sage tools list
.venv/bin/sage text "who are you"
.venv/bin/sage text "what project is this"
.venv/bin/sage text "summarize this project"
.venv/bin/sage text "what is running on port 3000"
.venv/bin/sage text "run tests"
.venv/bin/sage commands recent
```

Voice input:

```bash
.venv/bin/sage listen-once
```

## Diagnostics

```bash
.venv/bin/sage doctor
.venv/bin/sage diagnostics
```

Current diagnostics report dependency status. The next implementation phase will
make `sage doctor` more actionable by adding fix hints and clearer severity.

## Profile

SAGE creates a local editable profile on first run. The profile stores the
assistant name, role, user display name, and generated laptop context such as OS,
desktop session, shell, CPU, and RAM.

```bash
.venv/bin/sage profile show
.venv/bin/sage profile set --assistant-name "Laptop Sage" --user-name "Yajush"
```

## Demo Readiness

Run the local verification script:

```bash
./scripts/check-demo-ready.sh
```

By default it runs Python tests, Ruff, the control panel build, and `sage
doctor`. If the local audio/model stack is not fully wired yet, use:

```bash
SKIP_DOCTOR=1 ./scripts/check-demo-ready.sh
```

Skipping doctor is useful for CI-like checks, but a real demo should pass doctor
on the target laptop.

## KDE Shortcut

The intended first push-to-talk shortcut invokes:

```bash
/absolute/path/to/SAGE/.venv/bin/sage listen-once
```

Global shortcut wiring is manual for now. Later UI/packaging phases may make
this smoother.
