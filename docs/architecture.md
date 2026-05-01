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
