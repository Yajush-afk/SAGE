"""SQLite persistence for SAGE settings, commands, and workflows."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sage.contracts import AssistantProfile, CommandRecord, RuntimeSettings, Workflow, WorkflowStep


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def save_command(self, record: CommandRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO commands (id, created_at, status, transcript, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.created_at.isoformat(),
                    record.status.value,
                    record.transcript,
                    record.model_dump_json(),
                ),
            )

    def list_recent_commands(self, limit: int = 20) -> list[CommandRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM commands ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [CommandRecord.model_validate_json(row["payload"]) for row in rows]

    def save_settings(self, settings: RuntimeSettings) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO settings (key, payload, updated_at)
                VALUES ('runtime', ?, ?)
                """,
                (settings.model_dump_json(), datetime.now(UTC).isoformat()),
            )

    def load_settings(self) -> RuntimeSettings | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM settings WHERE key = 'runtime'"
            ).fetchone()
        if row is None:
            return None
        return RuntimeSettings.model_validate_json(row["payload"])

    def save_profile(self, profile: AssistantProfile) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO settings (key, payload, updated_at)
                VALUES ('assistant_profile', ?, ?)
                """,
                (profile.model_dump_json(), datetime.now(UTC).isoformat()),
            )

    def load_profile(self) -> AssistantProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM settings WHERE key = 'assistant_profile'"
            ).fetchone()
        if row is None:
            return None
        return AssistantProfile.model_validate_json(row["payload"])

    def save_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        description: str = "",
        project_path: Path | None = None,
        is_global: bool = False,
    ) -> Workflow:
        now = datetime.now(UTC)
        workflow = Workflow(
            id=f"wf_{uuid4().hex}",
            name=name,
            description=description,
            project_path=project_path,
            is_global=is_global,
            steps=steps,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workflows (id, name, payload, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (workflow.id, workflow.name, workflow.model_dump_json(), now.isoformat()),
            )
        return workflow

    def list_workflows(self) -> list[Workflow]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM workflows ORDER BY name").fetchall()
        return [Workflow.model_validate_json(row["payload"]) for row in rows]

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        return cursor.rowcount > 0

    def stats(self) -> dict[str, int | str]:
        with self._connect() as connection:
            command_count = connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
            workflow_count = connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        size_bytes = self.path.stat().st_size if self.path.exists() else 0
        return {
            "path": str(self.path),
            "size_bytes": size_bytes,
            "command_count": command_count,
            "workflow_count": workflow_count,
        }


class InMemoryStore:
    """Test-friendly store with the same public methods as SQLiteStore."""

    def __init__(self) -> None:
        self.commands: dict[str, CommandRecord] = {}
        self.settings: RuntimeSettings | None = None
        self.profile: AssistantProfile | None = None
        self.workflows: dict[str, Workflow] = {}

    def save_command(self, record: CommandRecord) -> None:
        self.commands[record.id] = record

    def list_recent_commands(self, limit: int = 20) -> list[CommandRecord]:
        return sorted(
            self.commands.values(),
            key=lambda record: record.created_at,
            reverse=True,
        )[:limit]

    def save_settings(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def load_settings(self) -> RuntimeSettings | None:
        return self.settings

    def save_profile(self, profile: AssistantProfile) -> None:
        self.profile = profile

    def load_profile(self) -> AssistantProfile | None:
        return self.profile

    def save_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        description: str = "",
        project_path: Path | None = None,
        is_global: bool = False,
    ) -> Workflow:
        now = datetime.now(UTC)
        workflow = Workflow(
            id=f"wf_{uuid4().hex}",
            name=name,
            description=description,
            project_path=project_path,
            is_global=is_global,
            steps=steps,
            created_at=now,
            updated_at=now,
        )
        self.workflows[workflow.id] = workflow
        return workflow

    def list_workflows(self) -> list[Workflow]:
        return sorted(self.workflows.values(), key=lambda workflow: workflow.name)

    def delete_workflow(self, workflow_id: str) -> bool:
        return self.workflows.pop(workflow_id, None) is not None

    def stats(self) -> dict[str, int | str]:
        return {
            "path": "memory",
            "size_bytes": 0,
            "command_count": len(self.commands),
            "workflow_count": len(self.workflows),
        }
