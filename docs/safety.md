# Safety

SAGE must never execute arbitrary model-generated shell commands in the
portfolio MVP.

The local model is allowed to propose a plan. It is not allowed to directly
execute that plan. All execution goes through registered typed tools, strict
schema validation, deterministic risk policy, and workspace path constraints.

## Risk Levels

- `read_only`
- `safe_execution`
- `state_changing`
- `destructive`
- `privileged`
- `blocked`

## Current Defaults

- read-only actions can run without confirmation,
- safe-execution actions can run without confirmation,
- state-changing actions require exact confirmation,
- destructive actions are blocked,
- privileged actions are blocked,
- arbitrary shell execution is blocked,
- unknown tools are blocked.

## Command Safety Flow

```text
IntentPlan
  -> strict Pydantic validation
  -> registered tool lookup
  -> tool argument validation
  -> effective risk calculation
  -> allow, require confirmation, or block
```

## Blocking Rules

SAGE blocks destructive, privileged, credential-related, and explicitly blocked
patterns. Current blocked intent/tool keywords include:

- `sudo`
- `privileged`
- `credential`
- `password`
- `secret`
- `remove_file`
- `rm_rf`
- `git_reset`
- `git_clean`
- `format_disk`

## Confirmation Rules

State-changing work requires exact confirmation. Plain `yes` is not accepted.
Wrong phrases do not consume the pending command. Confirmations expire according
to `confirmation_timeout_seconds`.

Example confirmation phrases:

- `confirm start`
- `confirm stop`
- `confirm restart`
- `confirm kill`
- `confirm install`
- `confirm save`
- `confirm change`

Confirmed commands execute in their original command workspace.

## Tool Boundaries

Every tool has:

- a registered name,
- a description,
- a risk level,
- a Pydantic arguments model,
- a typed result.

Tools that accept paths must resolve them through the command workspace. A path
outside the workspace is rejected.

## Current Gaps To Harden

Planned safety improvements:

- richer `ToolPolicy` metadata,
- output redaction before persistence and speech,
- maximum output sizes per tool,
- confirmation attempt tracking,
- expired confirmation cleanup/display,
- dry-run preview shape for future state-changing tools,
- UI explanation for blocked commands.

## Explicit Non-Goals For Portfolio MVP

- arbitrary shell execution,
- unrestricted file writes,
- `sudo`,
- package installation,
- destructive git operations,
- credential inspection,
- always-on microphone behavior.
