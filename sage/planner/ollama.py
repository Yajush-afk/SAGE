"""Ollama-backed structured intent planner."""

from __future__ import annotations

import json
from typing import Protocol
from urllib import error, request

from pydantic import ValidationError

from sage.contracts import IntentPlan, PlannerContext, RuntimeSettings


class PlannerError(RuntimeError):
    """Raised when a transcript cannot be converted into a valid intent plan."""


class Planner(Protocol):
    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        ...


class OllamaPlanner:
    """Ask Ollama for an IntentPlan and validate the result strictly."""

    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        messages = build_planner_messages(transcript, context)
        last_error: Exception | None = None

        for attempt in range(settings.planner_repair_attempts + 1):
            if attempt > 0:
                messages = build_repair_messages(transcript, context, str(last_error))

            raw_content = self._chat(messages, settings)
            try:
                return parse_intent_plan(raw_content)
            except (json.JSONDecodeError, ValidationError, PlannerError) as exc:
                last_error = exc

        raise PlannerError(f"Ollama returned invalid planner output: {last_error}")

    def _chat(self, messages: list[dict[str, str]], settings: RuntimeSettings) -> str:
        endpoint = f"{settings.ollama_url.rstrip('/')}/api/chat"
        payload = {
            "model": settings.model_name,
            "messages": messages,
            "stream": False,
            "format": IntentPlan.model_json_schema(),
            "keep_alive": settings.ollama_keep_alive,
            "options": {
                "temperature": 0,
                "num_ctx": settings.ollama_num_ctx,
            },
        }
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.ollama_timeout_seconds) as response:
                body = response.read().decode()
        except error.HTTPError as exc:
            error_body = exc.read().decode()
            detail = error_body or exc.reason
            raise PlannerError(f"Ollama request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise PlannerError(f"could not reach Ollama at {settings.ollama_url}: {exc}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PlannerError("Ollama returned a non-JSON API response") from exc

        content = parsed.get("message", {}).get("content")
        if isinstance(content, str) and content.strip():
            return content

        response_content = parsed.get("response")
        if isinstance(response_content, str) and response_content.strip():
            return response_content

        raise PlannerError("Ollama response did not include planner content")


def build_planner_messages(transcript: str, context: PlannerContext) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are SAGE's local command planner. Convert the user's transcript into "
                "one valid JSON object matching the IntentPlan schema. Do not include "
                "Markdown. Do not invent tools. Only use tools listed in available_tools. "
                "If no tool is available for the command, return actions as an empty list. "
                "Use multiple ordered read-only actions when the user asks for a broader "
                "project overview that benefits from combining available project tools. "
                "Classify risk conservatively."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "transcript": transcript,
                    "context": context.model_dump(mode="json"),
                    "required_shape": {
                        "intent": "short_snake_case_intent",
                        "confidence": "number from 0.0 to 1.0",
                        "summary": "brief human-readable summary",
                        "actions": [],
                        "risk": (
                            "read_only | safe_execution | state_changing | destructive | "
                            "privileged | blocked"
                        ),
                        "requires_confirmation": "boolean",
                    },
                },
                sort_keys=True,
            ),
        },
    ]


def build_repair_messages(
    transcript: str,
    context: PlannerContext,
    validation_error: str,
) -> list[dict[str, str]]:
    messages = build_planner_messages(transcript, context)
    messages.append(
        {
            "role": "user",
            "content": (
                "The previous output failed validation. Return only corrected JSON. "
                f"Validation error: {validation_error}"
            ),
        }
    )
    return messages


def normalize_planner_payload(parsed: dict) -> dict:
    actions = parsed.get("actions")
    if isinstance(actions, list):
        normalized_actions = []
        for action in actions:
            if isinstance(action, dict):
                action = dict(action)
                if "arguments" not in action and "tool_input" in action:
                    action["arguments"] = action.pop("tool_input")
            normalized_actions.append(action)
        parsed = dict(parsed)
        parsed["actions"] = normalized_actions
    return parsed


def parse_intent_plan(raw_content: str) -> IntentPlan:
    content = strip_json_fence(raw_content)
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise PlannerError("planner output must be a JSON object")
    return IntentPlan.model_validate(normalize_planner_payload(parsed))


def strip_json_fence(raw_content: str) -> str:
    content = raw_content.strip()
    if not content.startswith("```"):
        return content

    lines = content.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return content
