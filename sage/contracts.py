"""Shared data contracts for the SAGE command pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SageModel(BaseModel):
    """Base model with strict defaults for assistant contracts."""

    model_config = ConfigDict(extra="forbid")


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    SAFE_EXECUTION = "safe_execution"
    STATE_CHANGING = "state_changing"
    DESTRUCTIVE = "destructive"
    PRIVILEGED = "privileged"
    BLOCKED = "blocked"


class VoiceCommand(SageModel):
    id: str = Field(min_length=1)
    created_at: datetime
    raw_audio_path: Path | None = None
    transcript: str = Field(min_length=1)
    source: Literal["push_to_talk", "cli_debug", "api"]

    @field_validator("transcript")
    @classmethod
    def transcript_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("transcript must contain non-whitespace text")
        return normalized


class ToolCall(SageModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_name")
    @classmethod
    def tool_name_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool_name must contain non-whitespace text")
        return normalized


class IntentPlan(SageModel):
    intent: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    actions: list[ToolCall] = Field(default_factory=list)
    risk: RiskLevel
    requires_confirmation: bool

    @field_validator("intent", "summary")
    @classmethod
    def text_fields_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must contain non-whitespace text")
        return normalized


class ToolResult(SageModel):
    tool_name: str = Field(min_length=1)
    success: bool
    summary: str = Field(min_length=1)
    details: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = Field(ge=0)


class ExecutionResult(SageModel):
    command_id: str = Field(min_length=1)
    success: bool
    spoken_summary: str = Field(min_length=1)
    details: str = ""
    tool_results: list[ToolResult] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)


class ToolSchema(SageModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk: RiskLevel
    parameters_schema: dict[str, Any]


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class CommandRecord(SageModel):
    id: str = Field(min_length=1)
    created_at: datetime
    transcript: str = Field(min_length=1)
    source: Literal["push_to_talk", "cli_debug", "api"]
    status: CommandStatus
    intent_plan: IntentPlan | None = None
    execution_result: ExecutionResult | None = None
    error: str | None = None


class RuntimeSettings(SageModel):
    ollama_url: str = "http://127.0.0.1:11434"
    model_name: str = "gemma4"
    whisper_provider: str = "whisper_cpp"
    whisper_endpoint: str = "http://127.0.0.1:2022/v1"
    piper_enabled: bool = True
    piper_voice_path: Path | None = None
    default_editor: str = "code"
    max_recording_seconds: int = Field(default=12, ge=1, le=120)
    confirmation_timeout_seconds: int = Field(default=30, ge=5, le=300)


class RuntimeSettingsUpdate(SageModel):
    ollama_url: str | None = None
    model_name: str | None = None
    whisper_provider: str | None = None
    whisper_endpoint: str | None = None
    piper_enabled: bool | None = None
    piper_voice_path: Path | None = None
    default_editor: str | None = None
    max_recording_seconds: int | None = Field(default=None, ge=1, le=120)
    confirmation_timeout_seconds: int | None = Field(default=None, ge=5, le=300)


class HealthResponse(SageModel):
    status: Literal["ok"]
    version: str
    service: Literal["sage-daemon"] = "sage-daemon"


class TextCommandRequest(SageModel):
    command_text: str = Field(min_length=1)
    source: Literal["cli_debug", "api"] = "api"

    @field_validator("command_text")
    @classmethod
    def command_text_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("command_text must contain non-whitespace text")
        return normalized


def export_contract_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON schemas for contracts that are shared with the planner."""

    return {
        "VoiceCommand": VoiceCommand.model_json_schema(),
        "ToolCall": ToolCall.model_json_schema(),
        "IntentPlan": IntentPlan.model_json_schema(),
        "ToolResult": ToolResult.model_json_schema(),
        "ExecutionResult": ExecutionResult.model_json_schema(),
        "ToolSchema": ToolSchema.model_json_schema(),
        "CommandRecord": CommandRecord.model_json_schema(),
        "RuntimeSettings": RuntimeSettings.model_json_schema(),
        "HealthResponse": HealthResponse.model_json_schema(),
        "TextCommandRequest": TextCommandRequest.model_json_schema(),
    }
