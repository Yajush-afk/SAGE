"""Small deterministic planner for obvious local commands."""

from __future__ import annotations

import re

from sage.contracts import IntentPlan, RiskLevel, ToolCall


def direct_plan(transcript: str) -> IntentPlan | None:
    text = transcript.strip().lower()
    normalized_text = _normalize_text(text)

    if normalized_text in {"what project is this", "detect project", "inspect project"}:
        return IntentPlan(
            intent="inspect_project",
            confidence=1.0,
            summary="Detect project markers.",
            actions=[ToolCall(tool_name="detect_project", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if _is_assistant_identity_request(text):
        return IntentPlan(
            intent="get_assistant_profile",
            confidence=1.0,
            summary="Report assistant identity and local profile.",
            actions=[ToolCall(tool_name="get_assistant_profile", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if _is_system_info_request(text):
        return IntentPlan(
            intent="get_system_info",
            confidence=1.0,
            summary="Report local system information.",
            actions=[ToolCall(tool_name="get_system_info", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if _is_memory_info_request(text):
        return IntentPlan(
            intent="get_memory_info",
            confidence=1.0,
            summary="Report local memory information.",
            actions=[ToolCall(tool_name="get_memory_info", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if normalized_text in {"summarize project", "project summary", "summarize this project"}:
        return IntentPlan(
            intent="summarize_project",
            confidence=1.0,
            summary="Summarize project metadata.",
            actions=[ToolCall(tool_name="get_project_summary", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    port_match = re.search(r"(?:port|on)\s+(\d{1,5})", text)
    if port_match and ("running" in text or "process" in text or "listening" in text):
        port = int(port_match.group(1))
        if 1 <= port <= 65535:
            return IntentPlan(
                intent="find_process_on_port",
                confidence=1.0,
                summary=f"Find process on port {port}.",
                actions=[ToolCall(tool_name="find_process_on_port", arguments={"port": port})],
                risk=RiskLevel.READ_ONLY,
                requires_confirmation=False,
            )

    if normalized_text in {"list processes", "show processes", "what processes are running"}:
        return IntentPlan(
            intent="list_processes",
            confidence=1.0,
            summary="List running processes.",
            actions=[ToolCall(tool_name="list_processes", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if normalized_text in {"run tests", "run the tests"}:
        return IntentPlan(
            intent="run_tests",
            confidence=1.0,
            summary="Run tests.",
            actions=[ToolCall(tool_name="run_tests", arguments={"command": "pytest"})],
            risk=RiskLevel.SAFE_EXECUTION,
            requires_confirmation=False,
        )

    return None


def _is_system_info_request(text: str) -> bool:
    normalized = _normalize_text(text)
    return normalized in {
        "what system am i on",
        "what os am i on",
        "what operating system am i on",
        "what machine am i on",
        "tell me about this system",
        "show system info",
        "system info",
    }


def _is_assistant_identity_request(text: str) -> bool:
    normalized = _normalize_text(text)
    identity_patterns = (
        r"\bwho are you\b",
        r"\bwhat are you\b",
        r"\bwhat is your name\b",
        r"\bwho am i talking to\b",
        r"\btell me about yourself\b",
        r"\bintroduce yourself\b",
    )
    capability_patterns = (
        r"\bwhat can you do\b",
        r"\bwhat are your capabilities\b",
        r"\bwhat capabilities do you have\b",
        r"\bwhat are your functionalities\b",
        r"\bwhat functionalities do you have\b",
        r"\bwhat are your functions\b",
        r"\bwhat are your features\b",
    )
    return any(re.search(pattern, normalized) for pattern in identity_patterns) or any(
        re.search(pattern, normalized) for pattern in capability_patterns
    )


def _is_memory_info_request(text: str) -> bool:
    normalized = _normalize_text(text)
    return normalized in {
        "how much ram do i have",
        "how much memory do i have",
        "what is my ram",
        "what is my memory",
        "show memory info",
        "memory info",
        "ram info",
    }


def _normalize_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"^(hey sage|sage|hey)[,\s]+", "", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
