from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from sage.contracts import (
    ExecutionResult,
    IntentPlan,
    RiskLevel,
    RuntimeSettings,
    ToolCall,
    ToolResult,
    TranscriptionResult,
    VoiceCommand,
    export_contract_schemas,
)


def test_voice_command_accepts_valid_command():
    command = VoiceCommand(
        id="cmd_1",
        created_at=datetime.now(UTC),
        transcript="  start the frontend  ",
        source="push_to_talk",
    )

    assert command.transcript == "start the frontend"


def test_voice_command_rejects_empty_transcript():
    with pytest.raises(ValidationError):
        VoiceCommand(
            id="cmd_1",
            created_at=datetime.now(UTC),
            transcript="   ",
            source="push_to_talk",
        )


def test_voice_command_rejects_unknown_source():
    with pytest.raises(ValidationError):
        VoiceCommand(
            id="cmd_1",
            created_at=datetime.now(UTC),
            transcript="start the frontend",
            source="wake_word",
        )


def test_intent_plan_accepts_registered_shape():
    plan = IntentPlan(
        intent="start_dev_server",
        confidence=0.91,
        summary="Start the frontend dev server.",
        actions=[
            ToolCall(
                tool_name="start_frontend_server",
                arguments={"cwd": "/tmp/project"},
            )
        ],
        risk=RiskLevel.STATE_CHANGING,
        requires_confirmation=True,
    )

    assert plan.actions[0].tool_name == "start_frontend_server"
    assert plan.risk == RiskLevel.STATE_CHANGING


def test_intent_plan_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        IntentPlan(
            intent="start_dev_server",
            confidence=1.5,
            summary="Start the frontend dev server.",
            actions=[],
            risk=RiskLevel.STATE_CHANGING,
            requires_confirmation=True,
        )


def test_intent_plan_rejects_unknown_risk_level():
    with pytest.raises(ValidationError):
        IntentPlan(
            intent="start_dev_server",
            confidence=0.8,
            summary="Start the frontend dev server.",
            actions=[],
            risk="reckless",
            requires_confirmation=True,
        )


def test_contracts_forbid_extra_fields():
    with pytest.raises(ValidationError):
        ToolCall(tool_name="detect_project", arguments={}, shell_command="rm -rf .")


def test_execution_result_accepts_tool_results():
    result = ExecutionResult(
        command_id="cmd_1",
        success=True,
        spoken_summary="Frontend server started.",
        details="Server started on port 5173.",
        tool_results=[
            ToolResult(
                tool_name="start_frontend_server",
                success=True,
                summary="Started frontend.",
                duration_ms=120,
            )
        ],
        latency_ms=500,
    )

    assert result.tool_results[0].success is True
    assert result.latency_ms == 500


def test_schema_export_includes_planner_contracts():
    schemas = export_contract_schemas()

    assert "IntentPlan" in schemas
    assert "ToolCall" in schemas
    assert "TranscriptionResult" in schemas
    assert schemas["IntentPlan"]["additionalProperties"] is False


def test_transcription_result_rejects_empty_text():
    with pytest.raises(ValidationError):
        TranscriptionResult(text="   ", confidence=None, duration_ms=1, provider="test")


def test_runtime_settings_accepts_audio_and_stt_settings():
    settings = RuntimeSettings(
        whisper_provider="whisper_cpp_cli",
        whisper_cli_path="whisper-cli",
        max_recording_seconds=5,
        audio_sample_rate_hz=16000,
        audio_channels=1,
        keep_raw_audio=True,
    )

    assert settings.whisper_provider == "whisper_cpp_cli"
    assert settings.max_recording_seconds == 5
    assert settings.keep_raw_audio is True
