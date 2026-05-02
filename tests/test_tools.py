from pathlib import Path

import pytest
from pydantic import ValidationError

from sage.contracts import ToolCall
from sage.tools import ExecutionContext, ToolExecutionError, ToolRegistry


def make_context(tmp_path: Path) -> ExecutionContext:
    return ExecutionContext(command_id="cmd_1", cwd=tmp_path.resolve(), timeout_seconds=5)


def test_registry_lists_builtin_tool_schemas():
    registry = ToolRegistry()

    tool_names = {schema.name for schema in registry.list_schemas()}

    assert "detect_project" in tool_names
    assert "get_project_summary" in tool_names
    assert "find_process_on_port" in tool_names
    assert "run_tests" in tool_names


def test_detect_project_tool_reports_markers(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="detect_project", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert "pyproject" in result.data["markers"]


def test_get_project_summary_reads_package_scripts(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name": "demo-app", "scripts": {"test": "vitest"}}'
    )
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_project_summary", arguments={}),
        make_context(tmp_path),
    )

    assert result.data["name"] == "demo-app"
    assert result.data["scripts"]["test"] == "vitest"


def test_tool_context_rejects_paths_outside_workspace(tmp_path):
    context = make_context(tmp_path)

    with pytest.raises(ToolExecutionError):
        context.resolve_path(tmp_path.parent)


def test_registry_rejects_unknown_tool():
    registry = ToolRegistry()

    with pytest.raises(ToolExecutionError, match="unknown tool"):
        registry.validate_tool_call(ToolCall(tool_name="missing_tool", arguments={}))


def test_registry_validates_tool_arguments():
    registry = ToolRegistry()

    with pytest.raises(ValidationError):
        registry.validate_tool_call(
            ToolCall(tool_name="find_process_on_port", arguments={"port": 999999})
        )
