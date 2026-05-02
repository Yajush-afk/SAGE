from fastapi.testclient import TestClient

from sage.api import create_app
from sage.contracts import (
    AudioRecording,
    IntentPlan,
    PlannerContext,
    RiskLevel,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TranscriptionResult,
)
from sage.daemon.state import DaemonState


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
    def transcribe(self, audio_path, settings: RuntimeSettings) -> TranscriptionResult:
        assert audio_path.exists()
        return TranscriptionResult(
            text="start the frontend",
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
        return IntentPlan(
            intent="start_dev_server" if "start" in transcript else "inspect_project",
            confidence=0.9,
            summary=f"Plan for: {transcript}",
            actions=[],
            risk=RiskLevel.STATE_CHANGING if "start" in transcript else RiskLevel.READ_ONLY,
            requires_confirmation="start" in transcript,
        )


def make_client(state: DaemonState | None = None) -> TestClient:
    return TestClient(create_app(state or DaemonState(planner=FakePlanner())))


def test_health_endpoint():
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "sage-daemon"


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


def test_text_command_rejects_empty_command():
    client = make_client()

    response = client.post("/commands/text", json={"command_text": "   ", "source": "api"})

    assert response.status_code == 422


def test_listen_once_records_transcribes_and_stores_command(tmp_path):
    audio_path = tmp_path / "command.wav"
    state = DaemonState(
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
        DaemonState(
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
        DaemonState(
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


def test_tools_endpoint_returns_empty_registry_for_phase_2():
    client = make_client()

    response = client.get("/tools")

    assert response.status_code == 200
    assert response.json() == []


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


def test_settings_update_validates_bounds():
    client = make_client()

    response = client.put("/settings", json={"max_recording_seconds": 0})

    assert response.status_code == 422


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
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["error"] == "Executor is not implemented in Phase 5."


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
    assert confirmed.json()["status"] == "failed"
    assert "Confirmation phrase did not match" in confirmed.json()["error"]


def test_cancel_command_updates_status():
    client = make_client()
    planned = client.post(
        "/commands/text",
        json={"command_text": "start the frontend", "source": "api"},
    )

    cancelled = client.post(f"/commands/{planned.json()['id']}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_confirm_unknown_command_returns_404():
    client = make_client()

    response = client.post("/commands/missing/confirm", json={"phrase": "confirm start"})

    assert response.status_code == 404
