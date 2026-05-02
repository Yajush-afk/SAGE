"""FastAPI application for the local SAGE daemon."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from sage import __version__
from sage.contracts import (
    CommandRecord,
    ConfirmationRequest,
    HealthResponse,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TextCommandRequest,
    ToolSchema,
)
from sage.daemon.state import CommandNotFoundError, DaemonState, daemon_state


def create_app(state: DaemonState | None = None) -> FastAPI:
    runtime_state = state or daemon_state
    app = FastAPI(
        title="SAGE Daemon API",
        version=__version__,
        description="Local API for the SAGE voice command daemon.",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.post("/commands/text", response_model=CommandRecord)
    def command_text(request: TextCommandRequest) -> CommandRecord:
        return runtime_state.accept_text_command(request)

    @app.post("/commands/listen-once", response_model=CommandRecord)
    def command_listen_once() -> CommandRecord:
        return runtime_state.listen_once()

    @app.get("/commands/recent", response_model=list[CommandRecord])
    def recent_commands(limit: int = Query(default=20, ge=1, le=100)) -> list[CommandRecord]:
        return runtime_state.list_recent_commands(limit=limit)

    @app.post("/commands/{command_id}/confirm", response_model=CommandRecord)
    def confirm_command(command_id: str, request: ConfirmationRequest) -> CommandRecord:
        try:
            return runtime_state.confirm_command(command_id, request)
        except CommandNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Command not found.") from exc

    @app.post("/commands/{command_id}/cancel", response_model=CommandRecord)
    def cancel_command(command_id: str) -> CommandRecord:
        try:
            return runtime_state.cancel_command(command_id)
        except CommandNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Command not found.") from exc

    @app.get("/tools", response_model=list[ToolSchema])
    def tools() -> list[ToolSchema]:
        return runtime_state.list_tools()

    @app.get("/settings", response_model=RuntimeSettings)
    def get_settings() -> RuntimeSettings:
        return runtime_state.settings

    @app.put("/settings", response_model=RuntimeSettings)
    def put_settings(update: RuntimeSettingsUpdate) -> RuntimeSettings:
        return runtime_state.update_settings(update)

    return app


app = create_app()
