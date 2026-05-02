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
    IntentPlan,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TextCommandRequest,
)
from sage.stt import STTProvider, TranscriptionError, build_stt_provider


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
    ) -> None:
        self._settings = RuntimeSettings()
        self._recent_commands: deque[CommandRecord] = deque(maxlen=max_recent_commands)
        self._recorder = recorder or FfmpegAudioRecorder()
        self._stt_provider = stt_provider

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

        record = CommandRecord(
            id=command_id,
            created_at=now,
            transcript=request.command_text,
            source=request.source,
            status=CommandStatus.NOT_IMPLEMENTED,
            intent_plan=self._planner_placeholder(),
            error="Planner and executor are not implemented in Phase 3.",
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
            record = CommandRecord(
                id=command_id,
                created_at=now,
                transcript=transcription.text,
                source="push_to_talk",
                status=CommandStatus.NOT_IMPLEMENTED,
                raw_audio_path=recording.path if self._settings.keep_raw_audio else None,
                transcription=transcription,
                intent_plan=self._planner_placeholder(),
                error="Planner and executor are not implemented in Phase 3.",
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

    @staticmethod
    def _planner_placeholder() -> IntentPlan:
        plan = IntentPlan(
            intent="planner_not_implemented",
            confidence=0.0,
            summary="The daemon accepted the command, but planning starts in Phase 4.",
            actions=[],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )
        return plan


daemon_state = DaemonState()
