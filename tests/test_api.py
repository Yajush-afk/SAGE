from fastapi.testclient import TestClient

from sage.api import create_app
from sage.contracts import (
    AssistantProfileUpdate,
    AudioRecording,
    IntentPlan,
    PlannerContext,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    ToolCall,
    TranscriptionResult,
    WorkflowStep,
)
from sage.daemon.state import DaemonState
from sage.memory import InMemoryStore
from sage.tts import NullTTSProvider


class FakeRecorder:
    def __init__(self, audio_path):
        self.audio_path = audio_path

    def record_once(self, settings: RuntimeSettings) -> AudioRecording:
        self.audio_path.write_bytes(b"audio")
        return AudioRecording(
            path=self.audio_path,
            duration_ms=25,
            sample_rate_hz=settings.audio_sample_rate_hz,
            channels=settings.audio_channels,
        )


class FakeSTTProvider:
    def __init__(self, text: str = "start the frontend") -> None:
        self.text = text

    def transcribe(self, audio_path, settings: RuntimeSettings) -> TranscriptionResult:
        assert audio_path.exists()
        return TranscriptionResult(
            text=self.text,
            confidence=None,
            duration_ms=10,
            provider="fake_stt",
        )


class FailingSTTProvider:
    def transcribe(self, audio_path, settings: RuntimeSettings) -> TranscriptionResult:
        raise OSError("transcription failed")


class FakePlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        assert context.assistant_profile.assistant_name
        return IntentPlan(
            intent="start_dev_server" if "start" in transcript else "inspect_project",
            confidence=0.9,
            summary=f"Plan for: {transcript}",
            actions=[],
            risk=RiskLevel.STATE_CHANGING if "start" in transcript else RiskLevel.READ_ONLY,
            requires_confirmation="start" in transcript,
        )


class DetectProjectPlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        return IntentPlan(
            intent="inspect_project",
            confidence=0.9,
            summary="Detect project markers.",
            actions=[ToolCall(tool_name="detect_project", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )


class UnknownToolPlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        return IntentPlan(
            intent="mystery",
            confidence=0.9,
            summary="Use an unknown tool.",
            actions=[ToolCall(tool_name="missing_tool", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )


class KnownIntentMissingActionPlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        return IntentPlan(
            intent="get_assistant_profile",
            confidence=0.9,
            summary="Report assistant identity and capabilities.",
            actions=[],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )


class UnknownIntentMissingActionPlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        return IntentPlan(
            intent="unmapped_question",
            confidence=0.7,
            summary="No executable tool selected.",
            actions=[],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )


class ReadOnlyFailureThenSuccessPlanner:
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        return IntentPlan(
            intent="partial_read_only_plan",
            confidence=0.9,
            summary="Run a read-only plan with one failing step.",
            actions=[
                ToolCall(tool_name="show_file_excerpt", arguments={"path": "missing.md"}),
                ToolCall(tool_name="detect_project", arguments={}),
            ],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )


def make_client(state: DaemonState | None = None) -> TestClient:
    return TestClient(
        create_app(
            state
            or DaemonState(
                planner=FakePlanner(),
                store=InMemoryStore(),
                tts_provider=NullTTSProvider(),
            )
        )
    )


def make_state(**kwargs) -> DaemonState:
    return DaemonState(
        store=InMemoryStore(),
        tts_provider=NullTTSProvider(),
        **kwargs,
    )


def test_health_endpoint():
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "sage-daemon"


def test_cors_allows_control_panel_origin():
    client = make_client()

    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_text_command_is_recorded_and_recent_commands_are_newest_first():
    client = make_client()

    first = client.post(
        "/commands/text",
        json={"command_text": "what project is this", "source": "api"},
    )
    second = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )
    recent = client.get("/commands/recent?limit=2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "awaiting_confirmation"
    assert second.json()["intent_plan"]["intent"] == "start_dev_server"
    assert second.json()["safety_decision"]["confirmation_phrase"] == "confirm start"
    assert recent.status_code == 200
    assert [record["transcript"] for record in recent.json()] == [
        "start the frontend",
        "what project is this",
    ]


def test_get_command_returns_existing_command():
    client = make_client()
    created = client.post(
        "/commands/text",
        json={"command_text": "what project is this", "source": "api"},
    )

    response = client.get(f"/commands/{created.json()['id']}")

    assert created.status_code == 200
    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]
    assert response.json()["transcript"] == "what project is this"
    assert response.json()["intent_plan"] is not None


def test_get_unknown_command_returns_404():
    client = make_client()

    response = client.get("/commands/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Command not found."


def test_text_command_rejects_empty_command():
    client = make_client()

    response = client.post("/commands/text", json={"command_text": "   ", "source": "api"})

    assert response.status_code == 422


def test_listen_once_records_transcribes_and_stores_command(tmp_path):
    audio_path = tmp_path / "command.wav"
    state = make_state(
        recorder=FakeRecorder(audio_path),
        stt_provider=FakeSTTProvider(),
        planner=FakePlanner(),
    )
    state.update_settings(RuntimeSettingsUpdate(keep_raw_audio=True))
    client = make_client(state)

    response = client.post("/commands/listen-once")

    assert response.status_code == 200
    assert response.json()["transcript"] == "start the frontend"
    assert response.json()["source"] == "push_to_talk"
    assert response.json()["status"] == "awaiting_confirmation"
    assert response.json()["raw_audio_path"] == str(audio_path)
    assert response.json()["transcription"]["provider"] == "fake_stt"


def test_listen_once_deletes_raw_audio_by_default(tmp_path):
    audio_path = tmp_path / "command.wav"
    client = make_client(
        make_state(
            recorder=FakeRecorder(audio_path),
            stt_provider=FakeSTTProvider(),
            planner=FakePlanner(),
        )
    )

    response = client.post("/commands/listen-once")

    assert response.status_code == 200
    assert response.json()["raw_audio_path"] is None
    assert not audio_path.exists()


def test_listen_once_records_failed_transcription(tmp_path):
    audio_path = tmp_path / "command.wav"
    client = make_client(
        make_state(
            recorder=FakeRecorder(audio_path),
            stt_provider=FailingSTTProvider(),
            planner=FakePlanner(),
        )
    )

    response = client.post("/commands/listen-once")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["transcript"] == "[voice command unavailable]"
    assert response.json()["error"] == "transcription failed"


def test_tools_endpoint_returns_registered_tools():
    client = make_client()

    response = client.get("/tools")

    assert response.status_code == 200
    assert {tool["name"] for tool in response.json()} >= {
        "detect_project",
        "get_project_summary",
        "find_process_on_port",
    }


def test_settings_can_be_read_and_updated():
    client = make_client()

    initial = client.get("/settings")
    updated = client.put(
        "/settings",
        json={
            "model_name": "gemma4:latest",
            "piper_enabled": False,
            "max_recording_seconds": 10,
            "whisper_provider": "whisper_cpp_cli",
            "audio_input": "default",
            "keep_raw_audio": True,
            "ollama_num_ctx": 8192,
            "whisper_timeout_seconds": 60,
        },
    )

    assert initial.status_code == 200
    assert initial.json()["model_name"] == "gemma4"
    assert updated.status_code == 200
    assert updated.json()["model_name"] == "gemma4:latest"
    assert updated.json()["piper_enabled"] is False
    assert updated.json()["max_recording_seconds"] == 10
    assert updated.json()["whisper_provider"] == "whisper_cpp_cli"
    assert updated.json()["keep_raw_audio"] is True
    assert updated.json()["ollama_num_ctx"] == 8192
    assert updated.json()["whisper_timeout_seconds"] == 60


def test_settings_update_validates_bounds():
    client = make_client()

    response = client.put("/settings", json={"max_recording_seconds": 0})

    assert response.status_code == 422


def test_profile_can_be_read_and_updated():
    client = make_client()

    initial = client.get("/profile")
    updated = client.put(
        "/profile",
        json={
            "assistant_name": "Local Sage",
            "assistant_role": "Local workflow assistant.",
            "user_display_name": "Yajush",
            "notes": ["Prefer concise spoken responses."],
        },
    )

    assert initial.status_code == 200
    assert initial.json()["assistant_name"]
    assert initial.json()["device"]["hostname"]
    assert updated.status_code == 200
    assert updated.json()["assistant_name"] == "Local Sage"
    assert updated.json()["assistant_role"] == "Local workflow assistant."
    assert updated.json()["user_display_name"] == "Yajush"
    assert updated.json()["notes"] == ["Prefer concise spoken responses."]


def test_confirm_command_accepts_required_phrase():
    client = make_client()
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    confirmed = client.post(
        f"/commands/{planned.json()['id']}/confirm",
        json={"phrase": "confirm start"},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "failed"
    assert "no registered tool can handle" in confirmed.json()["error"]


def test_confirm_command_rejects_wrong_phrase():
    client = make_client()
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    confirmed = client.post(
        f"/commands/{planned.json()['id']}/confirm",
        json={"phrase": "yes"},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "awaiting_confirmation"
    assert "Confirmation phrase did not match" in confirmed.json()["error"]

    recent = client.get("/commands/recent?limit=1")

    assert recent.json()[0]["status"] == "awaiting_confirmation"


def test_cancel_command_updates_status():
    client = make_client()
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    cancelled = client.post(f"/commands/{planned.json()['id']}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_text_confirmation_phrase_confirms_latest_pending_command():
    client = make_client()
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    confirmed = client.post(
        "/commands/text",
        json={"command_text": "confirm start", "source": "api"},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["id"] == planned.json()["id"]
    assert confirmed.json()["status"] == "failed"
    assert "no registered tool can handle" in confirmed.json()["speech_result"]["text"]


def test_listen_once_confirmation_phrase_confirms_latest_pending_command(tmp_path):
    audio_path = tmp_path / "command.wav"
    state = make_state(
        recorder=FakeRecorder(audio_path),
        stt_provider=FakeSTTProvider("confirm start"),
        planner=FakePlanner(),
    )
    client = make_client(state)
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    confirmed = client.post("/commands/listen-once")
    recent = client.get("/commands/recent?limit=5")

    assert confirmed.status_code == 200
    assert confirmed.json()["id"] == planned.json()["id"]
    assert confirmed.json()["status"] == "failed"
    assert [record["id"] for record in recent.json()].count(planned.json()["id"]) == 1


def test_confirm_unknown_command_returns_404():
    client = make_client()

    response = client.post("/commands/missing/confirm", json={"phrase": "confirm start"})

    assert response.status_code == 404


def test_read_only_tool_executes_immediately(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    client = make_client(make_state(planner=DetectProjectPlanner()))

    response = client.post(
        "/commands/text",
        json={"command_text": "what project is this", "source": "api", "cwd": str(tmp_path)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["execution_result"]["success"] is True
    assert response.json()["execution_result"]["tool_results"][0]["tool_name"] == "detect_project"


def test_executed_tool_summary_is_spoken(tmp_path):
    client = make_client(make_state())

    response = client.post(
        "/commands/text",
        json={
            "command_text": "Hey, what system am I on?",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["execution_result"]["tool_results"][0]["tool_name"] == "get_system_info"
    assert body["execution_result"]["spoken_summary"].startswith("This laptop is running ")
    assert body["speech_result"]["text"].startswith("This laptop is running ")


def test_memory_question_uses_direct_tool_without_planner(tmp_path):
    client = make_client(make_state())

    response = client.post(
        "/commands/text",
        json={
            "command_text": "How much RAM do I have?",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent_plan"]["intent"] == "get_memory_info"
    assert body["execution_result"]["tool_results"][0]["tool_name"] == "get_memory_info"
    assert "GiB of RAM" in body["speech_result"]["text"]


def test_identity_question_uses_stored_profile(tmp_path):
    state = make_state()
    state.update_profile(AssistantProfileUpdate(assistant_name="Laptop Sage"))
    client = make_client(state)

    response = client.post(
        "/commands/text",
        json={
            "command_text": "Who are you?",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent_plan"]["intent"] == "get_assistant_profile"
    assert body["speech_result"]["text"].startswith("I'm Laptop Sage")
    assert "currently registered capabilities" not in body["speech_result"]["text"]
    assert body["execution_result"]["tool_results"][0]["data"]["capabilities"]


def test_identity_and_capability_question_uses_direct_profile_tool(tmp_path):
    client = make_client(make_state())

    response = client.post(
        "/commands/text",
        json={
            "command_text": "Who are you and what are your functionalities?",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent_plan"]["intent"] == "get_assistant_profile"
    assert body["intent_plan"]["actions"][0]["tool_name"] == "get_assistant_profile"
    assert "inspect projects" in body["speech_result"]["text"]


def test_project_overview_uses_multi_tool_direct_plan(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo-project'\n")
    client = make_client(make_state())

    response = client.post(
        "/commands/text",
        json={
            "command_text": "inspect this repo",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent_plan"]["intent"] == "project_overview"
    assert [result["tool_name"] for result in body["execution_result"]["tool_results"]] == [
        "detect_project",
        "get_project_summary",
        "get_git_status",
        "list_project_files",
    ]
    assert body["execution_result"]["spoken_summary"].startswith("Project overview for")
    assert "listed file" in body["speech_result"]["text"]


def test_read_only_multi_tool_plan_continues_after_step_failure(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    client = make_client(make_state(planner=ReadOnlyFailureThenSuccessPlanner()))

    response = client.post(
        "/commands/text",
        json={
            "command_text": "run partial read-only plan",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    results = body["execution_result"]["tool_results"]
    assert body["status"] == "failed"
    assert [result["tool_name"] for result in results] == [
        "show_file_excerpt",
        "detect_project",
    ]
    assert results[0]["success"] is False
    assert results[1]["success"] is True


def test_known_zero_arg_intent_without_action_is_repaired(tmp_path):
    client = make_client(make_state(planner=KnownIntentMissingActionPlanner()))

    response = client.post(
        "/commands/text",
        json={
            "command_text": "describe your local role",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent_plan"]["actions"][0]["tool_name"] == "get_assistant_profile"


def test_unknown_zero_action_plan_fails_instead_of_remaining_planned(tmp_path):
    client = make_client(make_state(planner=UnknownIntentMissingActionPlanner()))

    response = client.post(
        "/commands/text",
        json={
            "command_text": "please handle something unsupported",
            "source": "api",
            "cwd": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "no registered tool can handle" in body["error"]
    assert body["speech_result"]["text"] == (
        "Failed. I can't do that yet because no registered tool can handle this request."
    )


def test_unknown_tool_is_blocked(tmp_path):
    client = make_client(make_state(planner=UnknownToolPlanner()))

    response = client.post(
        "/commands/text",
        json={"command_text": "do mystery thing", "source": "api", "cwd": str(tmp_path)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert "unknown tool" in response.json()["error"]


def test_text_command_rejects_missing_cwd():
    client = make_client(make_state(planner=DetectProjectPlanner()))

    response = client.post(
        "/commands/text",
        json={
            "command_text": "what project is this",
            "source": "api",
            "cwd": "/definitely/missing/sage/path",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "cwd does not exist" in response.json()["error"]


def test_workflow_endpoints_save_and_list_workflows():
    client = make_client()

    created = client.post(
        "/workflows",
        json={
            "name": "inspect",
            "description": "Inspect current project",
            "steps": [WorkflowStep(tool_name="detect_project", arguments={}).model_dump()],
        },
    )
    listed = client.get("/workflows")

    assert created.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "inspect"


def test_diagnostics_endpoint_returns_statuses():
    client = make_client()

    response = client.get("/diagnostics")

    assert response.status_code == 200
    assert any(item["name"] == "ffmpeg" for item in response.json())


def test_storage_endpoint_returns_stats():
    client = make_client()

    response = client.get("/storage")

    assert response.status_code == 200
    assert response.json()["path"] == "memory"
