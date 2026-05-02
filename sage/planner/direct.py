"""Small deterministic planner for obvious local commands."""

from __future__ import annotations

import re

from sage.contracts import IntentPlan, RiskLevel, ToolCall


def direct_plan(transcript: str) -> IntentPlan | None:
    text = transcript.strip().lower()

    if text in {"what project is this", "detect project", "inspect project"}:
        return IntentPlan(
            intent="inspect_project",
            confidence=1.0,
            summary="Detect project markers.",
            actions=[ToolCall(tool_name="detect_project", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if text in {"summarize project", "project summary", "summarize this project"}:
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

    if text in {"list processes", "show processes", "what processes are running"}:
        return IntentPlan(
            intent="list_processes",
            confidence=1.0,
            summary="List running processes.",
            actions=[ToolCall(tool_name="list_processes", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if text in {"run tests", "run the tests"}:
        return IntentPlan(
            intent="run_tests",
            confidence=1.0,
            summary="Run tests.",
            actions=[ToolCall(tool_name="run_tests", arguments={"command": "pytest"})],
            risk=RiskLevel.SAFE_EXECUTION,
            requires_confirmation=False,
        )

    return None
