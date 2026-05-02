"""In-memory daemon state for the local API."""

from __future__ import annotations

import subprocess
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sage.audio import AudioRecorder, AudioRecordingError, FfmpegAudioRecorder
from sage.contracts import (
    CommandRecord,
    CommandStatus,
    ConfirmationRequest,
    DiagnosticStatus,
    ExecutionResult,
    IntentPlan,
    PlannerContext,
    RecentCommand,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    SafetyAction,
    SafetyDecision,
    TextCommandRequest,
    ToolResult,
    Workflow,
    WorkflowStep,
)
from sage.memory import SQLiteStore
from sage.observability import run_diagnostics
from sage.planner import OllamaPlanner, Planner, PlannerError, direct_plan
from sage.safety import SafetyPolicy, confirmation_matches
from sage.stt import STTProvider, TranscriptionError, build_stt_provider
from sage.tools import ExecutionContext, ToolExecutionError, ToolRegistry
from sage.tts import PiperTTSProvider, TTSProvider


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
        tool_registry: ToolRegistry | None = None,
        tts_provider: TTSProvider | None = None,
        store=None,
    ) -> None:
        default_settings = RuntimeSettings()
        self._store = store or SQLiteStore(default_settings.database_path)
        self._settings = self._store.load_settings() or default_settings
        self._recent_commands: deque[CommandRecord] = deque(maxlen=max_recent_commands)
        for record in reversed(self._store.list_recent_commands(limit=max_recent_commands)):
            self._recent_commands.append(record)
        self._recorder = recorder or FfmpegAudioRecorder()
        self._stt_provider = stt_provider
        self._planner = planner or OllamaPlanner()
        self._safety_policy = safety_policy or SafetyPolicy()
        self._tool_registry = tool_registry or ToolRegistry()
        self._tts_provider = tts_provider or PiperTTSProvider()

    @property
    def settings(self) -> RuntimeSettings:
        return self._settings

    def update_settings(self, update: RuntimeSettingsUpdate) -> RuntimeSettings:
        updates = update.model_dump(exclude_unset=True)
        self._settings = self._settings.model_copy(update=updates)
        self._store.save_settings(self._settings)
        return self._settings

    def list_recent_commands(self, limit: int = 20) -> list[CommandRecord]:
        if limit < 1:
            return []
        return list(self._recent_commands)[-limit:][::-1]

    def list_tools(self):
        return self._tool_registry.list_schemas()

    def list_workflows(self) -> list[Workflow]:
        return self._store.list_workflows()

    def save_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        description: str = "",
        project_path: Path | None = None,
        is_global: bool = False,
    ) -> Workflow:
        return self._store.save_workflow(
            name=name,
            steps=steps,
            description=description,
            project_path=project_path,
            is_global=is_global,
        )

    def delete_workflow(self, workflow_id: str) -> bool:
        return self._store.delete_workflow(workflow_id)

    def diagnostics(self) -> list[DiagnosticStatus]:
        return run_diagnostics(self._settings)

    def storage_stats(self) -> dict[str, int | str]:
        return self._store.stats()

    def accept_text_command(self, request: TextCommandRequest) -> CommandRecord:
        now = datetime.now(UTC)
        command_id = f"cmd_{uuid4().hex}"
        if request.command_text.strip().lower() == "cancel that":
            latest_pending = self._latest_pending_command()
            if latest_pending is not None:
                return self.cancel_command(latest_pending.id)
        try:
            cwd = self._resolve_cwd(request.cwd)
        except ValueError as exc:
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript=request.command_text,
                source=request.source,
                status=CommandStatus.FAILED,
                cwd=request.cwd,
                error=str(exc),
            )
            self._recent_commands.append(record)
            self._store.save_command(record)
            return record

        try:
            plan = self._plan_transcript(request.command_text, cwd)
            record = self._record_from_plan(
                command_id=command_id,
                created_at=now,
                transcript=request.command_text,
                source=request.source,
                plan=plan,
                cwd=cwd,
            )
        except PlannerError as exc:
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript=request.command_text,
                source=request.source,
                status=CommandStatus.FAILED,
                cwd=cwd,
                error=str(exc),
            )

        self._recent_commands.append(record)
        self._store.save_command(record)
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
                plan = self._plan_transcript(transcription.text, self._resolve_cwd(Path.cwd()))
                record = self._record_from_plan(
                    command_id=command_id,
                    created_at=now,
                    transcript=transcription.text,
                    source="push_to_talk",
                    plan=plan,
                    cwd=self._resolve_cwd(Path.cwd()),
                    raw_audio_path=recording.path if self._settings.keep_raw_audio else None,
                    transcription=transcription,
                )
            except PlannerError as exc:
                record = CommandRecord(
                    id=command_id,
                created_at=now,
                transcript=transcription.text,
                source="push_to_talk",
                status=CommandStatus.FAILED,
                cwd=Path.cwd(),
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
                cwd=Path.cwd(),
                raw_audio_path=raw_audio_path if self._settings.keep_raw_audio else None,
                error=str(exc),
            )
        finally:
            if raw_audio_path is not None and not self._settings.keep_raw_audio:
                raw_audio_path.unlink(missing_ok=True)

        self._recent_commands.append(record)
        self._store.save_command(record)
        return record

    def confirm_command(self, command_id: str, request: ConfirmationRequest) -> CommandRecord:
        record = self._find_command(command_id)
        if record.status != CommandStatus.AWAITING_CONFIRMATION or record.safety_decision is None:
            return record.model_copy(update={"error": "Command is not awaiting confirmation."})

        now = datetime.now(UTC)
        if (
            record.safety_decision.expires_at is not None
            and now > record.safety_decision.expires_at
        ):
            updated = self._replace_command(
                record.model_copy(
                    update={
                        "status": CommandStatus.FAILED,
                        "error": "Confirmation window expired.",
                    }
                )
            )
            self._store.save_command(updated)
            return updated

        if not confirmation_matches(record.safety_decision, request.phrase):
            return record.model_copy(
                update={
                    "error": (
                        f"Confirmation phrase did not match. Say "
                        f"'{record.safety_decision.confirmation_phrase}' to continue."
                    )
                }
            )

        confirmed_decision = record.safety_decision.model_copy(update={"expires_at": None})
        confirmed_record = record.model_copy(
            update={
                "status": CommandStatus.CONFIRMED,
                "safety_decision": confirmed_decision,
                "error": None,
            }
        )
        if confirmed_record.intent_plan and confirmed_record.intent_plan.actions:
            confirmed_record = self._execute_record(
                confirmed_record,
                self._resolve_cwd(confirmed_record.cwd),
            )
        elif confirmed_record.intent_plan:
            confirmed_record = confirmed_record.model_copy(
                update={"error": "No executable tool actions."}
            )
        confirmed_record = self._speak_for_record(confirmed_record)
        updated = self._replace_command(confirmed_record)
        self._store.save_command(updated)
        return updated

    def cancel_command(self, command_id: str) -> CommandRecord:
        record = self._find_command(command_id)
        updated = self._replace_command(
            record.model_copy(
                update={
                    "status": CommandStatus.CANCELLED,
                    "error": "Command cancelled before execution.",
                }
            )
        )
        updated = self._speak_for_record(updated)
        self._store.save_command(updated)
        return updated

    def _plan_transcript(self, transcript: str, cwd: Path) -> IntentPlan:
        direct = direct_plan(transcript)
        if direct is not None:
            return direct
        context = PlannerContext(
            cwd=cwd,
            available_tools=self._tool_registry.list_schemas(),
            safety_rules_summary=self._safety_rules_summary(),
            recent_commands=self._recent_command_context(),
        )
        return self._planner.plan(transcript, context, self._settings)

    def _record_from_plan(
        self,
        command_id: str,
        created_at: datetime,
        transcript: str,
        source: str,
        plan: IntentPlan,
        cwd: Path,
        raw_audio_path: Path | None = None,
        transcription=None,
    ) -> CommandRecord:
        try:
            plan = self._validate_and_apply_tool_risk(plan)
        except ToolExecutionError as exc:
            decision = SafetyDecision(
                action=SafetyAction.BLOCK,
                risk=RiskLevel.BLOCKED,
                reason=str(exc),
            )
            return CommandRecord(
                id=command_id,
                created_at=created_at,
                transcript=transcript,
                source=source,
                status=CommandStatus.BLOCKED,
                cwd=cwd,
                raw_audio_path=raw_audio_path,
                transcription=transcription,
                intent_plan=plan,
                safety_decision=decision,
                error=str(exc),
            )

        safety_decision = self._evaluate_safety(plan)
        record = CommandRecord(
            id=command_id,
            created_at=created_at,
            transcript=transcript,
            source=source,
            status=self._status_for_safety_decision(safety_decision),
            cwd=cwd,
            raw_audio_path=raw_audio_path,
            transcription=transcription,
            intent_plan=plan,
            safety_decision=safety_decision,
            error=self._error_for_safety_decision(safety_decision, plan),
        )
        if safety_decision.action == SafetyAction.ALLOW and plan.actions:
            record = self._execute_record(record, cwd)
        return self._speak_for_record(record)

    def _validate_and_apply_tool_risk(self, plan: IntentPlan) -> IntentPlan:
        highest_risk = plan.risk
        for action in plan.actions:
            self._tool_registry.validate_tool_call(action)
            highest_risk = max_risk(
                highest_risk,
                self._tool_registry.risk_for_tool(action.tool_name),
            )
        return plan.model_copy(
            update={
                "risk": highest_risk,
                "requires_confirmation": (
                    plan.requires_confirmation or highest_risk == RiskLevel.STATE_CHANGING
                ),
            }
        )

    def _execute_record(self, record: CommandRecord, cwd: Path) -> CommandRecord:
        if record.intent_plan is None:
            return record.model_copy(
                update={"status": CommandStatus.FAILED, "error": "No intent plan."}
            )

        started_at = datetime.now(UTC)
        results: list[ToolResult] = []
        context = ExecutionContext(
            command_id=record.id,
            cwd=cwd,
            timeout_seconds=self._settings.tool_timeout_seconds,
        )
        try:
            for action in record.intent_plan.actions:
                results.append(self._tool_registry.run(action, context))
        except (ToolExecutionError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
            results.append(
                ToolResult(
                    tool_name=action.tool_name,
                    success=False,
                    summary="Tool execution failed.",
                    details=str(exc),
                    duration_ms=0,
                )
            )

        success = all(result.success for result in results)
        latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        execution_result = ExecutionResult(
            command_id=record.id,
            success=success,
            spoken_summary="Command completed." if success else "Command failed.",
            details="\n".join(result.summary for result in results),
            tool_results=results,
            latency_ms=latency_ms,
        )
        return record.model_copy(
            update={
                "status": CommandStatus.COMPLETED if success else CommandStatus.FAILED,
                "execution_result": execution_result,
                "error": None if success else execution_result.details,
            }
        )

    def _speak_for_record(self, record: CommandRecord) -> CommandRecord:
        text = self._spoken_text(record)
        speech = self._tts_provider.speak(text, self._settings)
        return record.model_copy(update={"speech_result": speech})

    @staticmethod
    def _spoken_text(record: CommandRecord) -> str:
        if record.status == CommandStatus.AWAITING_CONFIRMATION and record.safety_decision:
            phrase = record.safety_decision.confirmation_phrase or "confirm action"
            return f"{record.safety_decision.reason} Say {phrase} to continue."
        if record.execution_result:
            return record.execution_result.spoken_summary
        if record.status == CommandStatus.BLOCKED:
            return f"Blocked. {record.error or 'The command is not allowed.'}"
        if record.status == CommandStatus.FAILED:
            return f"Failed. {record.error or 'The command did not complete.'}"
        if record.status == CommandStatus.CANCELLED:
            return "Command cancelled."
        if record.status == CommandStatus.CONFIRMED:
            return "Command confirmed."
        return record.intent_plan.summary if record.intent_plan else "Command recorded."

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
    def _error_for_safety_decision(decision: SafetyDecision, plan: IntentPlan) -> str | None:
        if decision.action == SafetyAction.ALLOW:
            return None if plan.actions else "No executable tool actions."
        if decision.action == SafetyAction.REQUIRE_CONFIRMATION:
            return decision.reason
        return decision.reason

    def _find_command(self, command_id: str) -> CommandRecord:
        for record in self._recent_commands:
            if record.id == command_id:
                return record
        raise CommandNotFoundError(command_id)

    def _latest_pending_command(self) -> CommandRecord | None:
        for record in self.list_recent_commands(limit=20):
            if record.status == CommandStatus.AWAITING_CONFIRMATION:
                return record
        return None

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
            "Destructive and privileged work is blocked. State-changing work requires "
            "explicit confirmation. Only registered typed tools may execute."
        )

    @staticmethod
    def _resolve_cwd(cwd: Path | None) -> Path:
        resolved = (cwd or Path.cwd()).expanduser().resolve(strict=False)
        if not resolved.exists():
            raise ValueError(f"cwd does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"cwd is not a directory: {resolved}")
        return resolved


RISK_ORDER = {
    RiskLevel.READ_ONLY: 0,
    RiskLevel.SAFE_EXECUTION: 1,
    RiskLevel.STATE_CHANGING: 2,
    RiskLevel.DESTRUCTIVE: 3,
    RiskLevel.PRIVILEGED: 4,
    RiskLevel.BLOCKED: 5,
}


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if RISK_ORDER[left] >= RISK_ORDER[right] else right


daemon_state = DaemonState()
