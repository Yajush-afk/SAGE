"""Concise user-facing response formatting for command records."""

from __future__ import annotations

from sage.contracts import CommandRecord, CommandStatus, ToolResult

NO_TOOL_MESSAGE = "I can't do that yet because no registered tool can handle this request."


def format_execution_summary(results: list[ToolResult], success: bool) -> str:
    if not results:
        return "Command completed." if success else "Command failed."
    if len(results) == 1:
        return _format_tool_result(results[0], success)
    return _format_multi_tool_results(results, success)


def _format_multi_tool_results(results: list[ToolResult], success: bool) -> str:
    tool_names = {result.tool_name for result in results}
    project_overview_tools = {
        "detect_project",
        "get_project_summary",
        "get_git_status",
        "list_project_files",
    }
    if project_overview_tools.issubset(tool_names):
        return _format_project_overview_results(results, success)

    if success:
        summaries = [_shorten(result.summary, limit=80) for result in results[:3]]
        suffix = f" plus {len(results) - 3} more step(s)" if len(results) > 3 else ""
        return f"Completed {len(results)} tool steps: {'; '.join(summaries)}{suffix}."

    failed = [result for result in results if not result.success]
    if failed:
        return f"Command failed while running {failed[0].tool_name}."
    return "Command failed."


def _format_project_overview_results(results: list[ToolResult], success: bool) -> str:
    by_name = {result.tool_name: result for result in results}
    summary = by_name["get_project_summary"].data
    project_name = summary.get("name") or "this project"

    markers = by_name["detect_project"].data.get("markers", [])
    marker_count = len(markers) if isinstance(markers, list) else 0

    git = by_name["get_git_status"].data
    if git.get("is_git_repo"):
        branch = git.get("branch") or "detached"
        changed_count = git.get("changed_count", 0)
        git_part = f"branch {branch} with {changed_count} changed file(s)"
    else:
        git_part = "not a git repository"

    files = by_name["list_project_files"].data.get("files", [])
    file_count = len(files) if isinstance(files, list) else 0

    if success:
        return (
            f"Project overview for {project_name}: {marker_count} marker(s), "
            f"{git_part}, and {file_count} listed file(s)."
        )

    failed = [result for result in results if not result.success]
    if failed:
        return (
            f"Project overview partially failed at {failed[0].tool_name}. "
            f"Collected {len(results) - len(failed)} successful step(s)."
        )
    return "Project overview failed."


def format_spoken_text(record: CommandRecord) -> str:
    if record.status == CommandStatus.AWAITING_CONFIRMATION and record.safety_decision:
        phrase = record.safety_decision.confirmation_phrase or "confirm action"
        return f"This changes local state. Say {phrase} to continue, or say cancel that."
    if record.execution_result:
        return _shorten(record.execution_result.spoken_summary)
    if record.status == CommandStatus.BLOCKED:
        return f"Blocked. {_clean_error(record.error) or 'That command is not allowed.'}"
    if record.status == CommandStatus.FAILED:
        return f"Failed. {_clean_error(record.error) or 'The command did not complete.'}"
    if record.status == CommandStatus.CANCELLED:
        return "Command cancelled."
    if record.status == CommandStatus.CONFIRMED:
        return "Command confirmed."
    if record.intent_plan:
        return _shorten(record.intent_plan.summary)
    return "Command recorded."


def _format_tool_result(result: ToolResult, success: bool) -> str:
    if not success:
        return f"{result.tool_name} failed."
    if result.tool_name == "get_assistant_profile":
        return _assistant_profile_summary(result)
    if result.tool_name == "get_system_info":
        os_name = result.data.get("os_name") or result.data.get("system")
        machine = result.data.get("machine")
        if os_name and machine:
            return f"This laptop is running {os_name} on {machine}."
    return _shorten(result.summary)


def _assistant_profile_summary(result: ToolResult) -> str:
    assistant_name = str(result.data.get("assistant_name") or "SAGE")
    capabilities = result.data.get("capabilities")
    capability_names: list[str] = []
    if isinstance(capabilities, list):
        for item in capabilities:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                capability_names.append(item["name"])

    parts = [f"I'm {assistant_name}, your local laptop assistant."]
    if capability_names:
        parts.append(_capability_summary(capability_names))
    return " ".join(parts)


def _capability_summary(capability_names: list[str]) -> str:
    readable = {
        "detect_project": "inspect projects",
        "get_project_summary": "summarize projects",
        "search_project_text": "search project text",
        "list_processes": "list processes",
        "find_process_on_port": "check ports",
        "get_system_info": "check system info",
        "get_memory_info": "check memory",
        "run_tests": "run constrained tests",
    }
    selected = [readable[name] for name in capability_names if name in readable]
    if not selected:
        return "I can use registered local tools safely."
    if len(selected) > 4:
        selected = selected[:4] + ["more"]
    return f"I can {', '.join(selected)}."


def _clean_error(error: str | None) -> str:
    if not error:
        return ""
    if "No executable tool actions." in error or "no registered executable tool" in error:
        return NO_TOOL_MESSAGE
    if "Ollama returned invalid planner output" in error:
        return "I couldn't turn that into a valid tool plan yet."
    return _shorten(error)


def _shorten(text: str, limit: int = 220) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "."
