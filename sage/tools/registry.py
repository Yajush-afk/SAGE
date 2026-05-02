"""Typed tool registry and built-in developer workflow tools."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sage.contracts import RiskLevel, ToolCall, ToolResult, ToolSchema


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot run safely."""


class ExecutionContext(BaseModel):
    command_id: str
    cwd: Path
    timeout_seconds: int

    def resolve_path(self, path: Path | str | None = None) -> Path:
        target = self.cwd if path is None else Path(path)
        if not target.is_absolute():
            target = self.cwd / target
        resolved = target.expanduser().resolve(strict=False)
        if resolved != self.cwd and self.cwd not in resolved.parents:
            raise ToolExecutionError(f"path is outside command workspace: {resolved}")
        return resolved


class Tool(Protocol):
    name: str
    description: str
    risk: RiskLevel
    args_model: type[BaseModel]

    def run(self, args: BaseModel, context: ExecutionContext) -> ToolResult: ...

    def schema(self) -> ToolSchema: ...


class BaseTool:
    name: str
    description: str
    risk: RiskLevel
    args_model: type[BaseModel]

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            risk=self.risk,
            parameters_schema=self.args_model.model_json_schema(),
        )


class DetectProjectArgs(BaseModel):
    cwd: Path | None = None


class DetectProjectTool(BaseTool):
    name = "detect_project"
    description = "Detect project type markers in the current workspace."
    risk = RiskLevel.READ_ONLY
    args_model = DetectProjectArgs

    def run(self, args: DetectProjectArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        cwd = context.resolve_path(args.cwd)
        markers = {
            "package_json": cwd / "package.json",
            "pyproject": cwd / "pyproject.toml",
            "requirements": cwd / "requirements.txt",
            "cargo": cwd / "Cargo.toml",
            "docker_compose": cwd / "docker-compose.yml",
            "git": cwd / ".git",
        }
        found = [name for name, path in markers.items() if path.exists()]
        summary = "Detected project markers." if found else "No known project markers found."
        return ToolResult(
            tool_name=self.name,
            success=True,
            summary=summary,
            data={"cwd": str(cwd), "markers": found},
            duration_ms=_elapsed_ms(started_at),
        )


class GetProjectSummaryArgs(BaseModel):
    cwd: Path | None = None


class GetProjectSummaryTool(BaseTool):
    name = "get_project_summary"
    description = "Summarize basic project metadata and scripts."
    risk = RiskLevel.READ_ONLY
    args_model = GetProjectSummaryArgs

    def run(self, args: GetProjectSummaryArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        cwd = context.resolve_path(args.cwd)
        package_json = cwd / "package.json"
        scripts: dict[str, str] = {}
        package_name: str | None = None
        if package_json.exists():
            try:
                parsed = json.loads(package_json.read_text())
                package_name = parsed.get("name") if isinstance(parsed.get("name"), str) else None
                raw_scripts = parsed.get("scripts", {})
                if isinstance(raw_scripts, dict):
                    scripts = {
                        str(name): str(command)
                        for name, command in raw_scripts.items()
                        if isinstance(name, str)
                    }
            except json.JSONDecodeError:
                scripts = {}

        data = {
            "cwd": str(cwd),
            "name": package_name or cwd.name,
            "has_git": (cwd / ".git").exists(),
            "has_pyproject": (cwd / "pyproject.toml").exists(),
            "has_package_json": package_json.exists(),
            "scripts": scripts,
        }
        return ToolResult(
            tool_name=self.name,
            success=True,
            summary=f"Project summary for {data['name']}.",
            data=data,
            duration_ms=_elapsed_ms(started_at),
        )


class SearchProjectTextArgs(BaseModel):
    query: str = Field(min_length=1)
    cwd: Path | None = None
    max_results: int = Field(default=20, ge=1, le=100)


class SearchProjectTextTool(BaseTool):
    name = "search_project_text"
    description = "Search project files for literal text using ripgrep."
    risk = RiskLevel.READ_ONLY
    args_model = SearchProjectTextArgs

    def run(self, args: SearchProjectTextArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        cwd = context.resolve_path(args.cwd)
        command = [
            "rg",
            "--line-number",
            "--column",
            "--fixed-strings",
            "--max-count",
            str(args.max_results),
            args.query,
            str(cwd),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=context.timeout_seconds,
        )
        if completed.returncode not in {0, 1}:
            raise ToolExecutionError(completed.stderr.strip() or "ripgrep search failed")
        results = [line for line in completed.stdout.splitlines()[: args.max_results] if line]
        return ToolResult(
            tool_name=self.name,
            success=True,
            summary=f"Found {len(results)} matches.",
            data={"matches": results},
            duration_ms=_elapsed_ms(started_at),
        )


class ListProcessesArgs(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)


class ListProcessesTool(BaseTool):
    name = "list_processes"
    description = "List local user-visible processes from /proc."
    risk = RiskLevel.READ_ONLY
    args_model = ListProcessesArgs

    def run(self, args: ListProcessesArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        processes: list[dict[str, Any]] = []
        for proc_dir in sorted(Path("/proc").iterdir(), key=lambda path: path.name):
            if len(processes) >= args.limit:
                break
            if not proc_dir.name.isdigit():
                continue
            try:
                cmdline = (proc_dir / "cmdline").read_text(errors="ignore").replace("\x00", " ")
                comm = (proc_dir / "comm").read_text(errors="ignore").strip()
            except OSError:
                continue
            processes.append(
                {
                    "pid": int(proc_dir.name),
                    "name": comm,
                    "cmdline": cmdline.strip(),
                }
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            summary=f"Listed {len(processes)} processes.",
            data={"processes": processes},
            duration_ms=_elapsed_ms(started_at),
        )


class FindProcessOnPortArgs(BaseModel):
    port: int = Field(ge=1, le=65535)


class FindProcessOnPortTool(BaseTool):
    name = "find_process_on_port"
    description = "Find listening processes using a TCP or UDP port."
    risk = RiskLevel.READ_ONLY
    args_model = FindProcessOnPortArgs

    def run(self, args: FindProcessOnPortArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        completed = subprocess.run(
            ["ss", "-ltnup"],
            capture_output=True,
            text=True,
            check=False,
            timeout=context.timeout_seconds,
        )
        if completed.returncode != 0:
            raise ToolExecutionError(completed.stderr.strip() or "ss failed")
        matches = [
            line
            for line in completed.stdout.splitlines()
            if re.search(rf"[:.]{args.port}\b", line)
        ]
        return ToolResult(
            tool_name=self.name,
            success=True,
            summary=(
                f"Found {len(matches)} listener(s) on port {args.port}."
                if matches
                else f"No listener found on port {args.port}."
            ),
            data={"port": args.port, "matches": matches},
            duration_ms=_elapsed_ms(started_at),
        )


class RunTestsArgs(BaseModel):
    command: str = Field(pattern=r"^(pytest|npm test|npm run test)$")
    cwd: Path | None = None


class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "Run a constrained test command in the current workspace."
    risk = RiskLevel.SAFE_EXECUTION
    args_model = RunTestsArgs

    def run(self, args: RunTestsArgs, context: ExecutionContext) -> ToolResult:
        started_at = time.monotonic()
        cwd = context.resolve_path(args.cwd)
        completed = subprocess.run(
            args.command.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=context.timeout_seconds,
            env={**os.environ, "CI": "1"},
        )
        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
        return ToolResult(
            tool_name=self.name,
            success=completed.returncode == 0,
            summary="Tests passed." if completed.returncode == 0 else "Tests failed.",
            details=output[-4000:],
            data={"returncode": completed.returncode},
            duration_ms=_elapsed_ms(started_at),
        )


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or default_tools())}

    def list_schemas(self) -> list[ToolSchema]:
        return [tool.schema() for tool in self._tools.values()]

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown tool: {name}") from exc

    def validate_tool_call(self, call: ToolCall) -> ToolCall:
        tool = self.get(call.tool_name)
        tool.args_model.model_validate(call.arguments)
        return call

    def risk_for_tool(self, name: str) -> RiskLevel:
        return self.get(name).risk

    def run(self, call: ToolCall, context: ExecutionContext) -> ToolResult:
        tool = self.get(call.tool_name)
        args = tool.args_model.model_validate(call.arguments)
        return tool.run(args, context)


def default_tools() -> list[Tool]:
    return [
        DetectProjectTool(),
        GetProjectSummaryTool(),
        SearchProjectTextTool(),
        ListProcessesTool(),
        FindProcessOnPortTool(),
        RunTestsTool(),
    ]


def _elapsed_ms(started_at: float) -> int:
    return int((time.monotonic() - started_at) * 1000)
