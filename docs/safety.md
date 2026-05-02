# Safety

SAGE must never execute arbitrary model-generated shell commands in the MVP.

All execution goes through registered typed tools. Model output is treated as a
proposal, then validated against schemas and a deterministic safety policy.

Initial risk levels:

- `read_only`
- `safe_execution`
- `state_changing`
- `destructive`
- `privileged`
- `blocked`

MVP defaults:

- read-only actions can run without confirmation
- state-changing actions may require confirmation
- destructive actions are blocked or require explicit confirmation
- privileged actions are blocked
- arbitrary shell execution is blocked

Implemented Phase 5 behavior:

- read-only and safe plans are allowed
- state-changing plans wait for exact confirmation
- destructive and privileged plans are blocked
- dangerous intent/tool names such as `sudo`, `git_reset`, `git_clean`, and
  `rm_rf` are blocked
- confirmations expire according to `confirmation_timeout_seconds`
- plain `yes` is not accepted as confirmation
- wrong confirmation phrases do not consume the pending command
- confirmed commands execute in their original command workspace

Example confirmation phrases:

- `confirm start`
- `confirm stop`
- `confirm restart`
- `confirm kill`
- `confirm install`
- `confirm save`
