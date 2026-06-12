"""Command line entrypoint for SAGE."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error, request

from sage import __version__
from sage.contracts import RuntimeSettings
from sage.daemon.server import run as run_daemon
from sage.memory.store import SQLiteStore
from sage.observability import run_diagnostics
from sage.runtime import start_stack

DEFAULT_DAEMON_URL = "http://127.0.0.1:8765"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sage",
        description="SAGE local-first voice command layer.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subcommands = parser.add_subparsers(dest="command")

    daemon = subcommands.add_parser("daemon", help="Manage the local SAGE daemon.")
    daemon_subcommands = daemon.add_subparsers(dest="daemon_command")
    daemon_start = daemon_subcommands.add_parser("start", help="Start the local daemon.")
    daemon_start.add_argument("--host", default="127.0.0.1", help="Daemon bind host.")
    daemon_start.add_argument("--port", default=8765, type=int, help="Daemon bind port.")
    daemon_health = daemon_subcommands.add_parser("health", help="Check daemon health.")
    daemon_health.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")

    listen_once = subcommands.add_parser("listen-once", help="Record one voice command.")
    listen_once.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    listen_once.add_argument(
        "--timeout",
        default=300,
        type=int,
        help="Seconds to wait for recording, transcription, planning, and speech.",
    )

    text = subcommands.add_parser("text", help="Send a text command through the assistant.")
    text.add_argument("command_text", help="Command text to process.")
    text.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    text.add_argument(
        "--timeout",
        default=300,
        type=int,
        help="Seconds to wait for planning, tool execution, and speech.",
    )

    start = subcommands.add_parser("start", help="Start the local SAGE stack.")
    start.add_argument("--host", default="127.0.0.1", help="Daemon bind host.")
    start.add_argument("--port", default=8765, type=int, help="Daemon bind port.")
    start.add_argument(
        "--with-ui",
        action="store_true",
        help="Also start the Electron control panel Vite server.",
    )
    start.add_argument("--ui-host", default="127.0.0.1", help="Control panel bind host.")
    start.add_argument("--ui-port", default=5174, type=int, help="Control panel bind port.")

    doctor = subcommands.add_parser("doctor", help="Check local SAGE dependencies.")
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print raw diagnostic JSON instead of the human-readable report.",
    )

    commands = subcommands.add_parser("commands", help="Inspect command history.")
    commands_subcommands = commands.add_subparsers(dest="commands_command")
    recent = commands_subcommands.add_parser("recent", help="List recent commands.")
    recent.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    recent.add_argument("--limit", default=20, type=int, help="Number of commands to show.")
    show = commands_subcommands.add_parser("show", help="Show one command record.")
    show.add_argument("command_id", help="Command id to inspect.")
    show.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    confirm = commands_subcommands.add_parser("confirm", help="Confirm a pending command.")
    confirm.add_argument("command_id", help="Command id to confirm.")
    confirm.add_argument("phrase", help="Required confirmation phrase.")
    confirm.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    cancel = commands_subcommands.add_parser("cancel", help="Cancel a command.")
    cancel.add_argument("command_id", help="Command id to cancel.")
    cancel.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")

    tools = subcommands.add_parser("tools", help="Inspect registered tools.")
    tools_subcommands = tools.add_subparsers(dest="tools_command")
    tools_list = tools_subcommands.add_parser("list", help="List registered tools.")
    tools_list.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")

    workflows = subcommands.add_parser("workflows", help="Inspect saved workflows.")
    workflows_subcommands = workflows.add_subparsers(dest="workflows_command")
    workflows_list = workflows_subcommands.add_parser("list", help="List saved workflows.")
    workflows_list.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    workflows_show = workflows_subcommands.add_parser("show", help="Show one saved workflow.")
    workflows_show.add_argument("workflow_id", help="Workflow id or unique name.")
    workflows_show.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    workflows_run = workflows_subcommands.add_parser("run", help="Run a saved workflow.")
    workflows_run.add_argument("workflow_id", help="Workflow id or unique name.")
    workflows_run.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    workflows_run.add_argument("--cwd", type=Path, help="Workspace directory for this run.")
    workflows_run.add_argument(
        "--timeout",
        default=300,
        type=int,
        help="Seconds to wait for workflow execution.",
    )
    workflows_delete = workflows_subcommands.add_parser("delete", help="Delete a saved workflow.")
    workflows_delete.add_argument("workflow_id", help="Workflow id or unique name.")
    workflows_delete.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")

    diagnostics = subcommands.add_parser("diagnostics", help="Show daemon diagnostics.")
    diagnostics.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")

    profile = subcommands.add_parser("profile", help="Inspect or update the local SAGE profile.")
    profile_subcommands = profile.add_subparsers(dest="profile_command")
    profile_show = profile_subcommands.add_parser("show", help="Show the assistant profile.")
    profile_show.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    profile_set = profile_subcommands.add_parser("set", help="Update editable profile fields.")
    profile_set.add_argument("--url", default=DEFAULT_DAEMON_URL, help="Daemon base URL.")
    profile_set.add_argument("--assistant-name", help="Assistant display name.")
    profile_set.add_argument("--assistant-role", help="Assistant role description.")
    profile_set.add_argument("--user-name", help="User display name.")

    return parser


def request_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    *,
    timeout_seconds: int = 5,
) -> tuple[int, object]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed_body = json.loads(body) if body else {"detail": exc.reason}
        return exc.code, parsed_body
    except error.URLError as exc:
        raise RuntimeError(f"could not reach SAGE daemon: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"SAGE daemon request timed out after {timeout_seconds} seconds"
        ) from exc


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def daemon_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def load_runtime_settings() -> RuntimeSettings:
    defaults = RuntimeSettings()
    return SQLiteStore(defaults.database_path).load_settings() or defaults


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "daemon" and args.daemon_command == "start":
            run_daemon(host=args.host, port=args.port)
            return 0

        if args.command == "daemon" and args.daemon_command == "health":
            status, body = request_json("GET", daemon_url(args.url, "/health"))
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "text":
            status, body = request_json(
                "POST",
                daemon_url(args.url, "/commands/text"),
                {
                    "command_text": args.command_text,
                    "source": "cli_debug",
                    "cwd": str(Path.cwd()),
                },
                timeout_seconds=args.timeout,
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "listen-once":
            status, body = request_json(
                "POST",
                daemon_url(args.url, "/commands/listen-once"),
                timeout_seconds=args.timeout,
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "start":
            return start_stack(
                load_runtime_settings(),
                host=args.host,
                port=args.port,
                with_ui=args.with_ui,
                ui_host=args.ui_host,
                ui_port=args.ui_port,
                repo_root=Path.cwd(),
            )

        if args.command == "commands" and args.commands_command == "recent":
            status, body = request_json(
                "GET",
                daemon_url(args.url, f"/commands/recent?limit={args.limit}"),
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "commands" and args.commands_command == "show":
            status, body = request_json(
                "GET",
                daemon_url(args.url, f"/commands/{args.command_id}"),
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "commands" and args.commands_command == "confirm":
            status, body = request_json(
                "POST",
                daemon_url(args.url, f"/commands/{args.command_id}/confirm"),
                {"phrase": args.phrase},
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "commands" and args.commands_command == "cancel":
            status, body = request_json(
                "POST",
                daemon_url(args.url, f"/commands/{args.command_id}/cancel"),
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "tools" and args.tools_command == "list":
            status, body = request_json("GET", daemon_url(args.url, "/tools"))
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "workflows" and args.workflows_command == "list":
            status, body = request_json("GET", daemon_url(args.url, "/workflows"))
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "workflows" and args.workflows_command == "show":
            status, body = request_json(
                "GET",
                daemon_url(args.url, f"/workflows/{args.workflow_id}"),
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "workflows" and args.workflows_command == "run":
            payload = {"cwd": str(args.cwd.resolve())} if args.cwd else {}
            status, body = request_json(
                "POST",
                daemon_url(args.url, f"/workflows/{args.workflow_id}/run"),
                payload,
                timeout_seconds=args.timeout,
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "workflows" and args.workflows_command == "delete":
            status, body = request_json(
                "DELETE",
                daemon_url(args.url, f"/workflows/{args.workflow_id}"),
            )
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "diagnostics":
            status, body = request_json("GET", daemon_url(args.url, "/diagnostics"))
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "profile" and args.profile_command == "show":
            status, body = request_json("GET", daemon_url(args.url, "/profile"))
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "profile" and args.profile_command == "set":
            payload = {
                key: value
                for key, value in {
                    "assistant_name": args.assistant_name,
                    "assistant_role": args.assistant_role,
                    "user_display_name": args.user_name,
                }.items()
                if value is not None
            }
            status, body = request_json("PUT", daemon_url(args.url, "/profile"), payload)
            print_json(body)
            return 0 if status < 400 else 1

        if args.command == "doctor":
            diagnostics = run_diagnostics(load_runtime_settings())
            if args.json:
                print_json([status.model_dump() for status in diagnostics])
            else:
                print_doctor_report(diagnostics)
            return 0 if all(status.ok or not status.required for status in diagnostics) else 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def print_doctor_report(diagnostics) -> None:
    print("SAGE doctor")
    print("")
    for status in diagnostics:
        marker = _doctor_marker(status)
        required = "required" if status.required else "optional"
        print(f"{marker} {status.name} ({required})")
        print(f"    {status.detail}")
        if not status.ok and status.fix_hint:
            print(f"    fix: {status.fix_hint}")
        if not status.ok and status.docs_anchor:
            print(f"    docs: {status.docs_anchor}")
    print("")
    failures = [status for status in diagnostics if not status.ok and status.required]
    warnings = [status for status in diagnostics if not status.ok and not status.required]
    if failures:
        print(f"{len(failures)} required check(s) failed.")
    elif warnings:
        print(f"All required checks passed; {len(warnings)} optional check(s) need attention.")
    else:
        print("All required checks passed.")


def _doctor_marker(status) -> str:
    if status.ok and status.severity == "warning":
        return "[WARN]"
    if status.ok:
        return "[OK]"
    if status.required:
        return "[FAIL]"
    return "[WARN]"


if __name__ == "__main__":
    raise SystemExit(main())
