# Architecture

SAGE is split into a local Python daemon and a later Electron control panel.

The daemon is the source of truth. It owns speech input, transcription, planning,
safety validation, typed tool execution, speech output, memory, and logs.

The Electron app will connect to the daemon over a local API and will not execute
system commands directly.

Initial runtime flow:

```text
KDE shortcut
  -> sage listen-once
  -> local daemon
  -> audio capture
  -> Whisper.cpp transcription
  -> Ollama/Gemma planning
  -> safety policy
  -> typed tool execution
  -> Piper spoken response
  -> SQLite logs
```

## Shared Contracts

The command pipeline shares a single contract layer in `sage.contracts`.

Core contracts:

- `VoiceCommand`
- `ToolCall`
- `IntentPlan`
- `ToolResult`
- `ExecutionResult`
- `ToolSchema`

All contracts reject unknown fields by default. This keeps model output,
tool input, API payloads, and logs aligned around explicit schemas.

## Phase 2 Local API

The local daemon exposes a FastAPI app on `127.0.0.1:8765` by default.

Initial endpoints:

- `GET /health`
- `POST /commands/text`
- `POST /commands/listen-once`
- `GET /commands/recent`
- `GET /tools`
- `GET /settings`
- `PUT /settings`

Phase 2 intentionally keeps command history in memory. SQLite persistence is
introduced later with memory and observability.

## Phase 3 Voice Input

`POST /commands/listen-once` now runs the voice input boundary:

```text
record WAV with ffmpeg
  -> transcribe with Whisper.cpp provider
  -> store transcript in recent command history
  -> stop before planning/execution
```

The default STT path targets a Whisper.cpp/OpenAI-compatible HTTP endpoint at
`http://127.0.0.1:2022/v1/audio/transcriptions`.

Raw audio is deleted by default after transcription. Set `keep_raw_audio` to
`true` only for debugging.
