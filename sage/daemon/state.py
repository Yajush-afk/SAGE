"""In-memory daemon state for the Phase 2 local API."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from uuid import uuid4

from sage.contracts import (
    CommandRecord,
    CommandStatus,
    IntentPlan,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TextCommandRequest,
)


class DaemonState:
    """State holder for the local daemon.

    Phase 2 keeps state in memory. SQLite-backed persistence is introduced later
    with memory and observability.
    """

    def __init__(self, max_recent_commands: int = 100) -> None:
        self._settings = RuntimeSettings()
        self._recent_commands: deque[CommandRecord] = deque(maxlen=max_recent_commands)

    @property
    def settings(self) -> RuntimeSettings:
        return self._settings

    def update_settings(self, update: RuntimeSettingsUpdate) -> RuntimeSettings:
        updates = update.model_dump(exclude_unset=True)
        self._settings = self._settings.model_copy(update=updates)
        return self._settings

    def list_recent_commands(self, limit: int = 20) -> list[CommandRecord]:
        if limit < 1:
            return []
        return list(self._recent_commands)[-limit:][::-1]

    def accept_text_command(self, request: TextCommandRequest) -> CommandRecord:
        now = datetime.now(UTC)
        command_id = f"cmd_{uuid4().hex}"

        plan = IntentPlan(
            intent="planner_not_implemented",
            confidence=0.0,
            summary="The daemon accepted the text command, but planning starts in Phase 4.",
            actions=[],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )
        record = CommandRecord(
            id=command_id,
            created_at=now,
            transcript=request.command_text,
            source=request.source,
            status=CommandStatus.NOT_IMPLEMENTED,
            intent_plan=plan,
            error="Planner and executor are not implemented in Phase 2.",
        )
        self._recent_commands.append(record)
        return record


daemon_state = DaemonState()
