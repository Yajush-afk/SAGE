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


class SpeechResult(SageModel):
    success: bool
    provider: str = Field(min_length=1)
    text: str = Field(min_length=1)
    audio_path: Path | None = None
    error: str | None = None


class ToolSchema(SageModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk: RiskLevel
    parameters_schema: dict[str, Any]


class AudioRecording(SageModel):
    path: Path
    duration_ms: int = Field(ge=0)
    sample_rate_hz: int = Field(ge=8000)
    channels: int = Field(ge=1, le=2)


class TranscriptionResult(SageModel):
    text: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    duration_ms: int = Field(ge=0)
    provider: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def text_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must contain non-whitespace text")
        return normalized


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    PLANNED = "planned"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class SafetyAction(StrEnum):
    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCK = "block"


class SafetyDecision(SageModel):
    action: SafetyAction
    risk: RiskLevel
    reason: str = Field(min_length=1)
    confirmation_phrase: str | None = None
    expires_at: datetime | None = None


class CommandRecord(SageModel):
    id: str = Field(min_length=1)
    created_at: datetime
    transcript: str = Field(min_length=1)
    source: Literal["push_to_talk", "cli_debug", "api"]
    status: CommandStatus
    cwd: Path | None = None
    raw_audio_path: Path | None = None
    transcription: TranscriptionResult | None = None
    intent_plan: IntentPlan | None = None
    safety_decision: SafetyDecision | None = None
    execution_result: ExecutionResult | None = None
    speech_result: SpeechResult | None = None
    error: str | None = None


class RuntimeSettings(SageModel):
    planner_provider: Literal["ollama", "custom_http"] = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    model_name: str = "gemma4"
    planner_api_url: str | None = None
    planner_api_key_env: str | None = None
    whisper_provider: str = "whisper_cpp"
    whisper_endpoint: str = "http://127.0.0.1:2022/v1"
    whisper_cli_path: str = "whisper-cli"
    whisper_model_path: Path | None = None
    whisper_timeout_seconds: int = Field(default=120, ge=1, le=600)
    piper_enabled: bool = True
    piper_binary_path: str = "piper"
    piper_voice_path: Path | None = None
    audio_player: str = "ffplay"
    default_editor: str = "code"
    max_recording_seconds: int = Field(default=12, ge=1, le=120)
    audio_input: str = "default"
    audio_sample_rate_hz: int = Field(default=16000, ge=8000, le=48000)
    audio_channels: int = Field(default=1, ge=1, le=2)
    audio_cache_dir: Path = Path(".sage/audio")
    data_dir: Path = Path(".sage")
    database_path: Path = Path(".sage/sage.db")
    keep_raw_audio: bool = False
    ollama_timeout_seconds: int = Field(default=120, ge=1, le=600)
    ollama_keep_alive: str = "5m"
    ollama_num_ctx: int = Field(default=4096, ge=512, le=262144)
    planner_repair_attempts: int = Field(default=1, ge=0, le=3)
    confirmation_timeout_seconds: int = Field(default=30, ge=5, le=300)
    tool_timeout_seconds: int = Field(default=120, ge=1, le=600)


class RuntimeSettingsUpdate(SageModel):
    planner_provider: Literal["ollama", "custom_http"] | None = None
    ollama_url: str | None = None
    model_name: str | None = None
    planner_api_url: str | None = None
    planner_api_key_env: str | None = None
    whisper_provider: str | None = None
    whisper_endpoint: str | None = None
    whisper_cli_path: str | None = None
    whisper_model_path: Path | None = None
    whisper_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    piper_enabled: bool | None = None
    piper_binary_path: str | None = None
    piper_voice_path: Path | None = None
    audio_player: str | None = None
    default_editor: str | None = None
    max_recording_seconds: int | None = Field(default=None, ge=1, le=120)
    audio_input: str | None = None
    audio_sample_rate_hz: int | None = Field(default=None, ge=8000, le=48000)
    audio_channels: int | None = Field(default=None, ge=1, le=2)
    audio_cache_dir: Path | None = None
    data_dir: Path | None = None
    database_path: Path | None = None
    keep_raw_audio: bool | None = None
    ollama_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    ollama_keep_alive: str | None = None
    ollama_num_ctx: int | None = Field(default=None, ge=512, le=262144)
    planner_repair_attempts: int | None = Field(default=None, ge=0, le=3)
    confirmation_timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    tool_timeout_seconds: int | None = Field(default=None, ge=1, le=600)


class HealthResponse(SageModel):
    status: Literal["ok"]
    version: str
    service: Literal["sage-daemon"] = "sage-daemon"


class TextCommandRequest(SageModel):
    command_text: str = Field(min_length=1)
    source: Literal["cli_debug", "api"] = "api"
    cwd: Path | None = None

    @field_validator("command_text")
    @classmethod
    def command_text_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("command_text must contain non-whitespace text")
        return normalized


class ConfirmationRequest(SageModel):
    phrase: str = Field(min_length=1)

    @field_validator("phrase")
    @classmethod
    def phrase_must_have_text(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("phrase must contain non-whitespace text")
        return normalized


class RecentCommand(SageModel):
    transcript: str = Field(min_length=1)
    status: CommandStatus
    intent: str | None = None


class DeviceProfile(SageModel):
    hostname: str = Field(min_length=1)
    username: str = Field(min_length=1)
    home_dir: Path
    os_name: str | None = None
    kernel: str | None = None
    machine: str | None = None
    desktop: str | None = None
    session_type: str | None = None
    shell: str | None = None
    cpu_model: str | None = None
    cpu_count: int | None = Field(default=None, ge=1)
    ram_total_gib: float | None = Field(default=None, ge=0)
    generated_at: datetime


class AssistantProfile(SageModel):
    assistant_name: str = Field(default="SAGE", min_length=1)
    assistant_role: str = Field(
        default="Local-first voice command layer for this laptop.",
        min_length=1,
    )
    user_display_name: str | None = None
    device: DeviceProfile
    notes: list[str] = Field(default_factory=list)
    updated_at: datetime


class AssistantProfileUpdate(SageModel):
    assistant_name: str | None = Field(default=None, min_length=1)
    assistant_role: str | None = Field(default=None, min_length=1)
    user_display_name: str | None = None
    device: DeviceProfile | None = None
    notes: list[str] | None = None


class PlannerContext(SageModel):
    cwd: Path
    assistant_profile: AssistantProfile
    available_tools: list[ToolSchema] = Field(default_factory=list)
    safety_rules_summary: str
    recent_commands: list[RecentCommand] = Field(default_factory=list)


class WorkflowStep(SageModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class Workflow(SageModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    project_path: Path | None = None
    is_global: bool = False
    steps: list[WorkflowStep] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowCreateRequest(SageModel):
    name: str = Field(min_length=1)
    description: str = ""
    project_path: Path | None = None
    is_global: bool = False
    steps: list[WorkflowStep] = Field(default_factory=list)


class DiagnosticStatus(SageModel):
    name: str = Field(min_length=1)
    ok: bool
    detail: str
    required: bool = True
    severity: Literal["ok", "warning", "error"] = "ok"
    fix_hint: str = ""
    docs_anchor: str = ""


def export_contract_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON schemas for contracts that are shared with the planner."""

    return {
        "VoiceCommand": VoiceCommand.model_json_schema(),
        "ToolCall": ToolCall.model_json_schema(),
        "IntentPlan": IntentPlan.model_json_schema(),
        "ToolResult": ToolResult.model_json_schema(),
        "ExecutionResult": ExecutionResult.model_json_schema(),
        "ToolSchema": ToolSchema.model_json_schema(),
        "AudioRecording": AudioRecording.model_json_schema(),
        "TranscriptionResult": TranscriptionResult.model_json_schema(),
        "SpeechResult": SpeechResult.model_json_schema(),
        "SafetyDecision": SafetyDecision.model_json_schema(),
        "CommandRecord": CommandRecord.model_json_schema(),
        "RuntimeSettings": RuntimeSettings.model_json_schema(),
        "HealthResponse": HealthResponse.model_json_schema(),
        "TextCommandRequest": TextCommandRequest.model_json_schema(),
        "ConfirmationRequest": ConfirmationRequest.model_json_schema(),
        "RecentCommand": RecentCommand.model_json_schema(),
        "DeviceProfile": DeviceProfile.model_json_schema(),
        "AssistantProfile": AssistantProfile.model_json_schema(),
        "AssistantProfileUpdate": AssistantProfileUpdate.model_json_schema(),
        "PlannerContext": PlannerContext.model_json_schema(),
        "WorkflowStep": WorkflowStep.model_json_schema(),
        "Workflow": Workflow.model_json_schema(),
        "WorkflowCreateRequest": WorkflowCreateRequest.model_json_schema(),
        "DiagnosticStatus": DiagnosticStatus.model_json_schema(),
    }
