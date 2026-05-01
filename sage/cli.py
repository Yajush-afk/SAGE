"""Command line entrypoint for SAGE."""

from __future__ import annotations

import argparse

from sage import __version__


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
    daemon_subcommands.add_parser("start", help="Start the local daemon.")
    daemon_subcommands.add_parser("health", help="Check daemon health.")

    subcommands.add_parser("listen-once", help="Record one voice command.")

    text = subcommands.add_parser("text", help="Send a text command through the assistant.")
    text.add_argument("command_text", help="Command text to process.")

    subcommands.add_parser("doctor", help="Check local SAGE dependencies.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    print("SAGE Phase 0 scaffold is installed. Runtime implementation starts in Phase 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
