"""In-memory daemon state for the local API."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sage.audio import AudioRecorder, AudioRecordingError, FfmpegAudioRecorder
from sage.contracts import (
    CommandRecord,
    CommandStatus,
    ConfirmationRequest,
    IntentPlan,
    PlannerContext,
    RecentCommand,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    SafetyAction,
    SafetyDecision,
    TextCommandRequest,
)
from sage.planner import OllamaPlanner, Planner, PlannerError
from sage.safety import SafetyPolicy, confirmation_matches
from sage.stt import STTProvider, TranscriptionError, build_stt_provider


class CommandNotFoundError(KeyError):
    """Raised when a command id is not in the in-memory command history."""


class DaemonState:
    """State holder for the local daemon.

    Phase 2 keeps state in memory. SQLite-backed persistence is introduced later
    with memory and observability.
    """

    def __init__(
        self,
        max_recent_commands: int = 100,
        recorder: AudioRecorder | None = None,
        stt_provider: STTProvider | None = None,
        planner: Planner | None = None,
        safety_policy: SafetyPolicy | None = None,
    ) -> None:
        self._settings = RuntimeSettings()
        self._recent_commands: deque[CommandRecord] = deque(maxlen=max_recent_commands)
        self._recorder = recorder or FfmpegAudioRecorder()
        self._stt_provider = stt_provider
        self._planner = planner or OllamaPlanner()
        self._safety_policy = safety_policy or SafetyPolicy()

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
        cwd = request.cwd or Path.cwd()

        try:
            plan = self._plan_transcript(request.command_text, cwd)
            safety_decision = self._evaluate_safety(plan)
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript=request.command_text,
                source=request.source,
                status=self._status_for_safety_decision(safety_decision),
                intent_plan=plan,
                safety_decision=safety_decision,
                error=self._error_for_safety_decision(safety_decision),
            )
        except PlannerError as exc:
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript=request.command_text,
                source=request.source,
                status=CommandStatus.FAILED,
                error=str(exc),
            )

        self._recent_commands.append(record)
        return record

    def listen_once(self) -> CommandRecord:
        now = datetime.now(UTC)
        command_id = f"cmd_{uuid4().hex}"
        raw_audio_path: Path | None = None

        try:
            recording = self._recorder.record_once(self._settings)
            raw_audio_path = recording.path
            stt_provider = self._stt_provider or build_stt_provider(self._settings)
            transcription = stt_provider.transcribe(recording.path, self._settings)
            try:
                plan = self._plan_transcript(transcription.text, Path.cwd())
                safety_decision = self._evaluate_safety(plan)
                record = CommandRecord(
                    id=command_id,
                    created_at=now,
                    transcript=transcription.text,
                    source="push_to_talk",
                    status=self._status_for_safety_decision(safety_decision),
                    raw_audio_path=recording.path if self._settings.keep_raw_audio else None,
                    transcription=transcription,
                    intent_plan=plan,
                    safety_decision=safety_decision,
                    error=self._error_for_safety_decision(safety_decision),
                )
            except PlannerError as exc:
                record = CommandRecord(
                    id=command_id,
                    created_at=now,
                    transcript=transcription.text,
                    source="push_to_talk",
                    status=CommandStatus.FAILED,
                    raw_audio_path=recording.path if self._settings.keep_raw_audio else None,
                    transcription=transcription,
                    error=str(exc),
                )
        except (AudioRecordingError, TranscriptionError, OSError) as exc:
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript="[voice command unavailable]",
                source="push_to_talk",
                status=CommandStatus.FAILED,
                raw_audio_path=raw_audio_path if self._settings.keep_raw_audio else None,
                error=str(exc),
            )
        finally:
            if raw_audio_path is not None and not self._settings.keep_raw_audio:
                raw_audio_path.unlink(missing_ok=True)

        self._recent_commands.append(record)
        return record

    def confirm_command(self, command_id: str, request: ConfirmationRequest) -> CommandRecord:
        record = self._find_command(command_id)
        if record.status != CommandStatus.AWAITING_CONFIRMATION or record.safety_decision is None:
            return self._replace_command(
                record.model_copy(
                    update={
                        "status": CommandStatus.FAILED,
                        "error": "Command is not awaiting confirmation.",
                    }
                )
            )

        if not confirmation_matches(record.safety_decision, request.phrase):
            return self._replace_command(
                record.model_copy(
                    update={
                        "status": CommandStatus.FAILED,
                        "error": (
                            "Confirmation phrase did not match or confirmation window expired."
                        ),
                    }
                )
            )

        return self._replace_command(
            record.model_copy(
                update={
                    "status": CommandStatus.CONFIRMED,
                    "error": "Executor is not implemented in Phase 5.",
                }
            )
        )

    def cancel_command(self, command_id: str) -> CommandRecord:
        record = self._find_command(command_id)
        return self._replace_command(
            record.model_copy(
                update={
                    "status": CommandStatus.CANCELLED,
                    "error": "Command cancelled before execution.",
                }
            )
        )

    def _plan_transcript(self, transcript: str, cwd: Path) -> IntentPlan:
        context = PlannerContext(
            cwd=cwd,
            available_tools=[],
            safety_rules_summary=self._safety_rules_summary(),
            recent_commands=self._recent_command_context(),
        )
        return self._planner.plan(transcript, context, self._settings)

    def _evaluate_safety(self, plan: IntentPlan) -> SafetyDecision:
        return self._safety_policy.evaluate(
            plan,
            confirmation_timeout_seconds=self._settings.confirmation_timeout_seconds,
        )

    @staticmethod
    def _status_for_safety_decision(decision: SafetyDecision) -> CommandStatus:
        if decision.action == SafetyAction.ALLOW:
            return CommandStatus.PLANNED
        if decision.action == SafetyAction.REQUIRE_CONFIRMATION:
            return CommandStatus.AWAITING_CONFIRMATION
        return CommandStatus.BLOCKED

    @staticmethod
    def _error_for_safety_decision(decision: SafetyDecision) -> str:
        if decision.action == SafetyAction.ALLOW:
            return "Executor is not implemented in Phase 5."
        if decision.action == SafetyAction.REQUIRE_CONFIRMATION:
            return decision.reason
        return decision.reason

    def _find_command(self, command_id: str) -> CommandRecord:
        for record in self._recent_commands:
            if record.id == command_id:
                return record
        raise CommandNotFoundError(command_id)

    def _replace_command(self, replacement: CommandRecord) -> CommandRecord:
        for index, record in enumerate(self._recent_commands):
            if record.id == replacement.id:
                self._recent_commands[index] = replacement
                return replacement
        raise CommandNotFoundError(replacement.id)

    def _recent_command_context(self) -> list[RecentCommand]:
        context: list[RecentCommand] = []
        for record in self.list_recent_commands(limit=5):
            context.append(
                RecentCommand(
                    transcript=record.transcript,
                    status=record.status,
                    intent=record.intent_plan.intent if record.intent_plan else None,
                )
            )
        return context

    @staticmethod
    def _safety_rules_summary() -> str:
        return (
            f"Allowed risk levels: {', '.join(level.value for level in RiskLevel)}. "
            "No commands execute in Phase 5. Destructive and privileged work is blocked. "
            "State-changing work requires explicit confirmation."
        )


daemon_state = DaemonState()
