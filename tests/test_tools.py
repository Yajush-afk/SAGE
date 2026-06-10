from pathlib import Path

import pytest
from pydantic import ValidationError

from sage.context import generate_assistant_profile
from sage.contracts import ToolCall
from sage.tools import ExecutionContext, ToolExecutionError, ToolRegistry


def make_context(tmp_path: Path) -> ExecutionContext:
    registry = ToolRegistry()
    return ExecutionContext(
        command_id="cmd_1",
        cwd=tmp_path.resolve(),
        timeout_seconds=5,
        assistant_profile=generate_assistant_profile(),
        available_tools=registry.list_schemas(),
    )


def test_registry_lists_builtin_tool_schemas():
    registry = ToolRegistry()

    tool_names = {schema.name for schema in registry.list_schemas()}

    assert "detect_project" in tool_names
    assert "get_project_summary" in tool_names
    assert "find_process_on_port" in tool_names
    assert "get_system_info" in tool_names
    assert "get_memory_info" in tool_names
    assert "get_assistant_profile" in tool_names
    assert "get_git_status" in tool_names
    assert "list_project_files" in tool_names
    assert "show_file_excerpt" in tool_names
    assert "get_project_context" in tool_names
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


def test_get_git_status_reports_non_git_workspace(tmp_path):
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_git_status", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["is_git_repo"] is False
    assert "not a git repository" in result.summary


def test_list_project_files_respects_limits_and_ignores_runtime_dirs(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / "sage").mkdir()
    (tmp_path / "sage" / "app.py").write_text("print('ok')\n")
    (tmp_path / ".sage").mkdir()
    (tmp_path / ".sage" / "secret.db").write_text("local")
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="list_project_files", arguments={"max_files": 10}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert "README.md" in result.data["files"]
    assert "sage/app.py" in result.data["files"]
    assert ".sage/secret.db" not in result.data["files"]


def test_show_file_excerpt_reads_bounded_text_file(tmp_path):
    (tmp_path / "README.md").write_text("\n".join(f"line {index}" for index in range(20)))
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(
            tool_name="show_file_excerpt",
            arguments={"path": "README.md", "max_lines": 3},
        ),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["path"] == "README.md"
    assert result.data["excerpt"] == "line 0\nline 1\nline 2"
    assert result.data["truncated"] is True


def test_show_file_excerpt_rejects_outside_workspace(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside")
    registry = ToolRegistry()

    with pytest.raises(ToolExecutionError, match="outside command workspace"):
        registry.run(
            ToolCall(tool_name="show_file_excerpt", arguments={"path": str(outside)}),
            make_context(tmp_path),
        )


def test_get_project_context_combines_repo_metadata(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\nA local project.\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo-project'\n")
    (tmp_path / "package.json").write_text(
        '{"name": "demo-app", "scripts": {"test": "vitest"}}'
    )
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_project_context", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["name"] == "demo-app"
    assert "pyproject" in result.data["markers"]
    assert "package_json" in result.data["markers"]
    assert "pytest" in result.data["test_commands"]
    assert "npm test" in result.data["test_commands"]
    assert result.data["readme_excerpt"].startswith("# Demo")


def test_get_system_info_reports_local_platform(tmp_path):
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_system_info", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["system"]
    assert "os_name" in result.data
    assert result.data["machine"]
    assert str(tmp_path.resolve()) == result.data["cwd"]


def test_get_memory_info_reports_ram_totals(tmp_path):
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_memory_info", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["total_bytes"] > 0
    assert result.data["total_gib"] > 0
    assert "GiB of RAM" in result.summary


def test_get_assistant_profile_reports_local_identity(tmp_path):
    registry = ToolRegistry()

    result = registry.run(
        ToolCall(tool_name="get_assistant_profile", arguments={}),
        make_context(tmp_path),
    )

    assert result.success is True
    assert result.data["assistant_name"]
    assert result.data["capabilities"]
    assert result.summary.startswith("I am ")
    assert "running locally" in result.summary
    assert "currently registered capabilities" in result.summary


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
