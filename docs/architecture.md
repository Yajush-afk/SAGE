# Architecture

SAGE is split into a local Python daemon and a later Electron control panel.

The daemon is the source of truth. It owns speech input, transcription, planning,
safety validation, typed tool execution, speech output, memory, and logs.

The Electron app will connect to the daemon over a local API and will not execute
system commands directly.

Initial runtime flow:

```text
KDE shortcut
  -> .venv/bin/sage listen-once
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

## Phase 4 Intent Planning

Text commands and transcribed voice commands now pass through an Ollama-backed
planner.

```text
transcript
  -> planner context
  -> Ollama /api/chat
  -> IntentPlan JSON
  -> strict Pydantic validation
  -> command history
```

The planner uses the `IntentPlan` JSON schema and retries once with a repair
prompt if the model returns invalid JSON.

Phase 4 still does not execute actions. If a plan is valid, the command status is
`planned`; if Ollama is unavailable or the model output cannot be validated, the
command status is `failed`.

## Phase 5 Safety

Every valid `IntentPlan` now passes through a deterministic safety policy before
anything can be executed in later phases.

```text
IntentPlan
  -> SafetyPolicy
  -> SafetyDecision
  -> command status
```

Safety outcomes:

- `allow`: command stays `planned`
- `require_confirmation`: command becomes `awaiting_confirmation`
- `block`: command becomes `blocked`

Destructive, privileged, credential-related, and explicitly blocked patterns are
blocked in this phase. State-changing commands require exact confirmation phrases
such as `confirm start`, `confirm stop`, or `confirm kill`.

Confirmation and cancellation endpoints:

- `POST /commands/{command_id}/confirm`
- `POST /commands/{command_id}/cancel`

After Phase 6, confirmed commands with registered tool actions can execute.
Confirmed commands without executable actions remain recorded but do not run.

## Phase 6 Typed Tools

SAGE now has a typed tool registry. The planner sees registered tool schemas, and
the daemon validates every planned tool name and argument before execution.

Initial tools:

- `detect_project`
- `get_project_summary`
- `search_project_text`
- `list_processes`
- `find_process_on_port`
- `run_tests`

Execution rules:

- read-only and safe-execution tools can run after planning
- state-changing tools require confirmation before execution
- unknown tools are blocked
- tool paths are constrained to the command workspace
- confirmed commands execute in the original command directory

## Phase 7-10 Voice MVP

The daemon can now speak concise responses through a `TTSProvider`. Piper is the
default provider, and missing Piper configuration is recorded as a speech failure
without failing the command itself.

SQLite stores:

- command records
- runtime settings
- workflows

Diagnostics expose local dependency status for `ffmpeg`, `rg`, Ollama, Piper,
audio playback, database path, and Piper voice configuration.

The MVP loop is:

```text
text or voice
  -> direct planner for obvious commands or Ollama planner
  -> safety policy
  -> typed tools
  -> command persistence
  -> optional spoken response
```

## Phase 11 Control Panel

The Electron control panel under `apps/electron-control-panel` reads from the
daemon API and shows health, diagnostics, command history, tools, and workflows.
It does not execute system commands directly.

The daemon enables CORS only for the local control panel dev origins. The
Electron main process uses context isolation, sandboxing, disabled Node
integration, and blocks arbitrary navigation/window creation.
