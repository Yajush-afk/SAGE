# Roadmap

SAGE is currently a working local MVP / early alpha. The next build path focuses
on usability, auditability, setup reliability, and portfolio polish before
adding larger AI/platform features.

## Implemented Foundation

- Repository and environment foundation.
- Strict Pydantic contracts for commands, plans, tools, settings, profile,
  workflows, and diagnostics.
- Local FastAPI daemon and CLI.
- Whisper.cpp speech-to-text boundary.
- Ollama structured intent planner.
- Deterministic direct planner for common local commands.
- Deterministic safety policy with confirmation support.
- Typed tool registry.
- Piper text-to-speech adapter.
- SQLite settings, command history, assistant profile, and workflows.
- Diagnostics endpoint and `sage doctor`.
- Electron control panel dashboard.
- Local stack supervisor through `sage start` and `sage start --with-ui`.

## Phase 1: Documentation, Setup, And Demo Baseline

Status: implemented.

Goal:

- make the current implementation understandable, reproducible, and demoable.

Deliverables:

- accurate README,
- accurate setup, architecture, roadmap, and safety docs,
- local config examples,
- setup script,
- demo-readiness check script,
- reliable first demo command list.

## Phase 2: Doctor, Diagnostics, And Setup Reliability

Status: implemented.

Goal:

- make local dependency failures actionable.

Deliverables:

- diagnostic fix hints,
- severity levels,
- clearer human-readable `sage doctor`,
- better docs links from diagnostics.

Port preflight checks for daemon/UI/Whisper startup are kept for the later
runtime supervision phase because they belong next to stack startup behavior.

## Phase 3: Command Auditability

Status: implemented.

Goal:

- make every command inspectable end to end.

Deliverables:

- `GET /commands/{command_id}`,
- `sage commands show <command-id>`,
- richer command detail types in the frontend.

The visual command detail panel is kept for Phase 4 with the rest of the UI
command interaction work.

## Phase 4: UI Command Input And Push-To-Talk UX

Status: implemented.

Goal:

- make the control panel useful as an assistant surface, not only a dashboard.

Deliverables:

- text command input,
- listen-once button,
- visible command states,
- confirm/cancel controls,
- demo command panel.

## Phase 5: Spoken Response And Voice Confirmation UX

Status: implemented.

Goal:

- make voice responses short, natural, and safety-aware.

Deliverables:

- response formatter,
- clearer failed/unsupported command summaries,
- spoken confirmation for latest pending command,
- voice cancellation with "cancel that".

## Phase 6: Project Context Tools

Status: implemented.

Goal:

- improve repo awareness through deterministic read-only tools.

Deliverables:

- git status tool,
- project file listing,
- file excerpt tool,
- combined project context tool,
- direct-planner coverage for project questions.

## Phase 7: Multi-Tool Execution

Status: implemented.

Goal:

- support controlled typed tool composition.

Deliverables:

- deterministic project-overview commands that compose read-only project tools,
- sequential multi-action execution with ordered result persistence,
- read-only step failures continue to collect later read-only results,
- mixed-risk handling,
- combined project-aware summaries.

## Pre-Phase 8: Planner Reliability And Low-Resource Mode

Status: implemented.

Goal:

- make SAGE less dependent on one large Ollama model before adding workflows.

Deliverables:

- user-friendly Ollama runner crash messages,
- low-resource Ollama diagnostics and setup guidance,
- planner output normalization for common model aliases,
- injected planner chat-provider boundary,
- future custom-provider settings without changing tool execution,
- direct-planner coverage for common git status phrasing,
- tests for planner/provider/diagnostic failure paths.

## Phase 8: Runnable Workflows

Status: implemented.

Goal:

- turn saved workflows into executable typed routines.

Deliverables:

- workflow run API,
- workflow run CLI,
- workflow lookup by id or name,
- workflow runs recorded as auditable command records,
- safety/tool validation reused for saved workflow steps,
- workflow run/delete controls in the control panel.

## Phase 9: Internal Provider Abstraction

Status: implemented.

Goal:

- make the planner boundary cleaner without expanding scope.

Deliverables:

- small internal provider interface,
- planner factory from runtime settings,
- explicit unsupported-provider planner for reserved future providers,
- daemon planner rebuild on settings changes,
- keep Ollama as the only supported concrete provider for portfolio-ready.

Deferred:

- custom remote API providers,
- hybrid local/cloud routing,
- API key handling.

## Phase 10: Reliability And Runtime Supervision

Status: implemented.

Goal:

- make local demos fail clearly and recoverably.

Deliverables:

- startup port checks,
- readiness waits,
- clearer child-process failure output,
- optional external Whisper mode,
- storage cleanup commands.

Deferred:

- structured log files,
- process auto-restart policy.

## Phase 11: Safety Hardening

Status: Implemented.

Goal:

- strengthen the safety story as a portfolio centerpiece.

Implemented:

- `ToolPolicy` metadata,
- output redaction,
- confirmation attempt tracking,
- expired confirmation display,
- "why blocked" UI.

## Phase 12: Portfolio Packaging

Goal:

- make the GitHub repo easy to try and easy to evaluate.

Planned:

- screenshots/GIFs,
- architecture decisions doc,
- future production path doc,
- final portfolio narrative.

## Deferred Until After Portfolio Ready

- wake word,
- always-on assistant mode,
- custom remote providers,
- hybrid LLM routing,
- plugin system,
- production installers,
- cross-platform support.
