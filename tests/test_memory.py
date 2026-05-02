from datetime import UTC, datetime

from sage.contracts import CommandRecord, CommandStatus, RuntimeSettings, WorkflowStep
from sage.memory import SQLiteStore


def test_sqlite_store_persists_commands_settings_and_workflows(tmp_path):
    store = SQLiteStore(tmp_path / "sage.db")
    record = CommandRecord(
        id="cmd_1",
        created_at=datetime.now(UTC),
        transcript="what project is this",
        source="api",
        status=CommandStatus.COMPLETED,
    )

    store.save_command(record)
    store.save_settings(RuntimeSettings(model_name="gemma4:e4b"))
    workflow = store.save_workflow(
        name="inspect",
        steps=[WorkflowStep(tool_name="detect_project", arguments={})],
    )

    assert store.list_recent_commands()[0].id == "cmd_1"
    assert store.load_settings().model_name == "gemma4:e4b"
    assert store.list_workflows()[0].name == "inspect"
    assert store.delete_workflow(workflow.id) is True
    assert store.stats()["command_count"] == 1
