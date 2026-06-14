"""FastAPI application for the local SAGE daemon."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from sage import __version__
from sage.contracts import (
    AssistantProfile,
    AssistantProfileUpdate,
    CommandRecord,
    ConfirmationRequest,
    DiagnosticStatus,
    HealthResponse,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    StorageCleanupRequest,
    StorageCleanupResult,
    TextCommandRequest,
    ToolSchema,
    Workflow,
    WorkflowCreateRequest,
    WorkflowRunRequest,
)
from sage.daemon.state import (
    CommandNotFoundError,
    DaemonState,
    WorkflowNotFoundError,
    daemon_state,
)


def create_app(state: DaemonState | None = None) -> FastAPI:
    runtime_state = state or daemon_state
    app = FastAPI(
        title="SAGE Daemon API",
        version=__version__,
        description="Local API for the SAGE voice command daemon.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
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

    @app.get("/commands/{command_id}", response_model=CommandRecord)
    def get_command(command_id: str) -> CommandRecord:
        try:
            return runtime_state.get_command(command_id)
        except CommandNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Command not found.") from exc

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

    @app.get("/workflows", response_model=list[Workflow])
    def workflows() -> list[Workflow]:
        return runtime_state.list_workflows()

    @app.get("/workflows/{workflow_id}", response_model=Workflow)
    def get_workflow(workflow_id: str) -> Workflow:
        try:
            return runtime_state.get_workflow(workflow_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workflow not found.") from exc

    @app.post("/workflows", response_model=Workflow)
    def create_workflow(request: WorkflowCreateRequest) -> Workflow:
        return runtime_state.save_workflow(
            name=request.name,
            steps=request.steps,
            description=request.description,
            project_path=request.project_path,
            is_global=request.is_global,
        )

    @app.post("/workflows/{workflow_id}/run", response_model=CommandRecord)
    def run_workflow(workflow_id: str, request: WorkflowRunRequest) -> CommandRecord:
        try:
            return runtime_state.run_workflow(workflow_id, cwd=request.cwd)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workflow not found.") from exc

    @app.delete("/workflows/{workflow_id}")
    def delete_workflow(workflow_id: str) -> dict[str, bool]:
        return {"deleted": runtime_state.delete_workflow(workflow_id)}

    @app.get("/diagnostics", response_model=list[DiagnosticStatus])
    def diagnostics() -> list[DiagnosticStatus]:
        return runtime_state.diagnostics()

    @app.get("/storage")
    def storage() -> dict[str, int | str]:
        return runtime_state.storage_stats()

    @app.post("/storage/cleanup", response_model=StorageCleanupResult)
    def cleanup_storage(request: StorageCleanupRequest) -> StorageCleanupResult:
        return runtime_state.cleanup_storage(audio_cache=request.audio_cache)

    @app.get("/settings", response_model=RuntimeSettings)
    def get_settings() -> RuntimeSettings:
        return runtime_state.settings

    @app.put("/settings", response_model=RuntimeSettings)
    def put_settings(update: RuntimeSettingsUpdate) -> RuntimeSettings:
        return runtime_state.update_settings(update)

    @app.get("/profile", response_model=AssistantProfile)
    def get_profile() -> AssistantProfile:
        return runtime_state.profile

    @app.put("/profile", response_model=AssistantProfile)
    def put_profile(update: AssistantProfileUpdate) -> AssistantProfile:
        return runtime_state.update_profile(update)

    return app


app = create_app()
