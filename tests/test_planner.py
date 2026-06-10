import json
from urllib import error

import pytest
from pydantic import ValidationError

from sage.context import generate_assistant_profile
from sage.contracts import PlannerContext, RiskLevel, RuntimeSettings
from sage.planner import OllamaPlanner, PlannerError, build_planner_messages, parse_intent_plan
from sage.planner.ollama import normalize_planner_payload


def test_parse_intent_plan_accepts_valid_json():
    plan = parse_intent_plan(
        json.dumps(
            {
                "intent": "start_dev_server",
                "confidence": 0.87,
                "summary": "Start the frontend server.",
                "actions": [],
                "risk": "state_changing",
                "requires_confirmation": True,
            }
        )
    )

    assert plan.intent == "start_dev_server"
    assert plan.risk == RiskLevel.STATE_CHANGING


def test_parse_intent_plan_accepts_json_fence():
    plan = parse_intent_plan(
        json.dumps(
            {
                "intent": "inspect_project",
                "confidence": 0.8,
                "summary": "Inspect the project.",
                "actions": [],
                "risk": "read_only",
                "requires_confirmation": False,
            }
        ).join(["```json\n", "\n```"])
    )

    assert plan.intent == "inspect_project"


def test_parse_intent_plan_normalizes_tool_input_to_arguments():
    plan = parse_intent_plan(
        json.dumps(
            {
                "intent": "get_laptop_specs",
                "confidence": 0.9,
                "summary": "Report laptop specs.",
                "actions": [
                    {
                        "tool_name": "get_system_info",
                        "tool_input": {},
                    }
                ],
                "risk": "read_only",
                "requires_confirmation": False,
            }
        )
    )

    assert plan.intent == "get_laptop_specs"
    assert plan.actions[0].tool_name == "get_system_info"
    assert plan.actions[0].arguments == {}


def test_normalize_planner_payload_does_not_mutate_input():
    payload = {
        "intent": "get_laptop_specs",
        "actions": [{"tool_name": "get_system_info", "tool_input": {"cwd": "."}}],
    }

    normalized = normalize_planner_payload(payload)

    assert payload["actions"][0] == {"tool_name": "get_system_info", "tool_input": {"cwd": "."}}
    assert normalized["actions"][0] == {
        "tool_name": "get_system_info",
        "arguments": {"cwd": "."},
    }


def test_parse_intent_plan_rejects_tool_input_when_arguments_already_present():
    with pytest.raises(ValidationError):
        parse_intent_plan(
            json.dumps(
                {
                    "intent": "inspect_project",
                    "confidence": 0.8,
                    "summary": "Inspect the project.",
                    "actions": [
                        {
                            "tool_name": "detect_project",
                            "arguments": {},
                            "tool_input": {},
                        }
                    ],
                    "risk": "read_only",
                    "requires_confirmation": False,
                }
            )
        )


def test_parse_intent_plan_rejects_invalid_shape():
    with pytest.raises(ValidationError):
        parse_intent_plan('{"intent": "missing required fields"}')


def test_build_planner_messages_includes_context(tmp_path):
    context = PlannerContext(
        cwd=tmp_path,
        assistant_profile=generate_assistant_profile(),
        available_tools=[],
        safety_rules_summary="No execution.",
        recent_commands=[],
    )

    messages = build_planner_messages("start frontend", context)

    assert messages[0]["role"] == "system"
    assert "multiple ordered read-only actions" in messages[0]["content"]
    assert "start frontend" in messages[1]["content"]
    assert str(tmp_path) in messages[1]["content"]


def test_ollama_planner_sends_schema_and_parses_response(monkeypatch, tmp_path):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return json.dumps(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "start_dev_server",
                                "confidence": 0.9,
                                "summary": "Start the frontend server.",
                                "actions": [],
                                "risk": "state_changing",
                                "requires_confirmation": True,
                            }
                        )
                    }
                }
            ).encode()

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("sage.planner.ollama.request.urlopen", fake_urlopen)

    context = PlannerContext(
        cwd=tmp_path,
        assistant_profile=generate_assistant_profile(),
        available_tools=[],
        safety_rules_summary="No execution.",
        recent_commands=[],
    )
    plan = OllamaPlanner().plan("start frontend", context, RuntimeSettings(model_name="gemma4"))

    assert plan.intent == "start_dev_server"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "gemma4"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"]["title"] == "IntentPlan"
    assert captured["timeout"] == 120


def test_ollama_planner_repairs_invalid_output(monkeypatch, tmp_path):
    responses = [
        {"message": {"content": '{"intent": "broken"}'}},
        {
            "message": {
                "content": json.dumps(
                    {
                        "intent": "inspect_project",
                        "confidence": 0.8,
                        "summary": "Inspect the project.",
                        "actions": [],
                        "risk": "read_only",
                        "requires_confirmation": False,
                    }
                )
            }
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(req, timeout):
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr("sage.planner.ollama.request.urlopen", fake_urlopen)

    context = PlannerContext(
        cwd=tmp_path,
        assistant_profile=generate_assistant_profile(),
        available_tools=[],
        safety_rules_summary="No execution.",
        recent_commands=[],
    )
    plan = OllamaPlanner().plan(
        "what project is this",
        context,
        RuntimeSettings(planner_repair_attempts=1),
    )

    assert plan.intent == "inspect_project"


def test_ollama_planner_reports_connection_failure(monkeypatch, tmp_path):
    def fake_urlopen(req, timeout):
        raise error.URLError("connection refused")

    monkeypatch.setattr("sage.planner.ollama.request.urlopen", fake_urlopen)

    context = PlannerContext(
        cwd=tmp_path,
        assistant_profile=generate_assistant_profile(),
        available_tools=[],
        safety_rules_summary="No execution.",
        recent_commands=[],
    )

    with pytest.raises(PlannerError, match="could not reach Ollama"):
        OllamaPlanner().plan("start frontend", context, RuntimeSettings())
