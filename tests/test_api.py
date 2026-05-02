from fastapi.testclient import TestClient

from sage.api import create_app
from sage.daemon.state import DaemonState


def make_client() -> TestClient:
    return TestClient(create_app(DaemonState()))


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
    assert second.json()["status"] == "not_implemented"
    assert second.json()["intent_plan"]["intent"] == "planner_not_implemented"
    assert recent.status_code == 200
    assert [record["transcript"] for record in recent.json()] == [
        "start the frontend",
        "what project is this",
    ]


def test_text_command_rejects_empty_command():
    client = make_client()

    response = client.post("/commands/text", json={"command_text": "   ", "source": "api"})

    assert response.status_code == 422


def test_listen_once_endpoint_exists_but_is_not_implemented():
    client = make_client()

    response = client.post("/commands/listen-once")

    assert response.status_code == 501
    assert response.json()["detail"] == "Voice capture and STT are implemented in Phase 3."


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
        },
    )

    assert initial.status_code == 200
    assert initial.json()["model_name"] == "gemma4"
    assert updated.status_code == 200
    assert updated.json()["model_name"] == "gemma4:latest"
    assert updated.json()["piper_enabled"] is False
    assert updated.json()["max_recording_seconds"] == 10


def test_settings_update_validates_bounds():
    client = make_client()

    response = client.put("/settings", json={"max_recording_seconds": 0})

    assert response.status_code == 422
