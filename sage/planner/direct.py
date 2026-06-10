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

    if normalized_text in {
        "project overview",
        "repo overview",
        "repository overview",
        "inspect this repo",
        "inspect this repository",
        "inspect this project",
        "give me a project overview",
        "give me a repo overview",
        "summarize repo status",
        "summarize repository status",
    }:
        return IntentPlan(
            intent="project_overview",
            confidence=1.0,
            summary="Build a project overview from multiple read-only tools.",
            actions=[
                ToolCall(tool_name="detect_project", arguments={}),
                ToolCall(tool_name="get_project_summary", arguments={}),
                ToolCall(tool_name="get_git_status", arguments={}),
                ToolCall(
                    tool_name="list_project_files",
                    arguments={"max_files": 40, "max_depth": 3},
                ),
            ],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if normalized_text in {
        "project context",
        "get project context",
        "build project context",
        "summarize project context",
        "what is in this repo",
        "what is in this repository",
        "understand this project",
    }:
        return IntentPlan(
            intent="get_project_context",
            confidence=1.0,
            summary="Build project context.",
            actions=[ToolCall(tool_name="get_project_context", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if normalized_text in {
        "git status",
        "show git status",
        "what changed",
        "what changed in this repo",
        "what changed in this repository",
        "repo status",
        "repository status",
        "working tree status",
        "git changes",
        "show git changes",
    }:
        return IntentPlan(
            intent="get_git_status",
            confidence=1.0,
            summary="Report git status.",
            actions=[ToolCall(tool_name="get_git_status", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    if normalized_text in {
        "list project files",
        "show project files",
        "list files",
        "show files",
        "what files are in this project",
    }:
        return IntentPlan(
            intent="list_project_files",
            confidence=1.0,
            summary="List project files.",
            actions=[ToolCall(tool_name="list_project_files", arguments={})],
            risk=RiskLevel.READ_ONLY,
            requires_confirmation=False,
        )

    excerpt_match = re.search(r"^(?:show|read|open)\s+(.+)$", text)
    if excerpt_match:
        requested_path = excerpt_match.group(1).strip().strip("'\"")
        if _looks_like_project_file(requested_path):
            return IntentPlan(
                intent="show_file_excerpt",
                confidence=1.0,
                summary=f"Show file excerpt for {requested_path}.",
                actions=[
                    ToolCall(
                        tool_name="show_file_excerpt",
                        arguments={"path": requested_path},
                    )
                ],
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
        "what are the specs of this laptop",
        "what are my laptop specs",
        "show laptop specs",
        "laptop specs",
        "device specs",
        "computer specs",
        "tell me about this laptop",
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


def _looks_like_project_file(value: str) -> bool:
    normalized = _normalize_text(value)
    if not value or value in {".", ".."}:
        return False
    if "/" in value or "." in value:
        return True
    return normalized in {"readme", "readme md", "pyproject toml", "package json"}


def _normalize_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"^(hey sage|sage|hey)[,\s]+", "", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
