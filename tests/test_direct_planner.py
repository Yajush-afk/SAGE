from sage.planner import direct_plan


def test_direct_planner_detects_project_request():
    plan = direct_plan("what project is this")

    assert plan.intent == "inspect_project"
    assert plan.actions[0].tool_name == "detect_project"


def test_direct_planner_detects_port_lookup():
    plan = direct_plan("what is running on port 3000")

    assert plan.intent == "find_process_on_port"
    assert plan.actions[0].arguments["port"] == 3000


def test_direct_planner_detects_system_info_request():
    plan = direct_plan("Hey, what system am I on?")

    assert plan.intent == "get_system_info"
    assert plan.actions[0].tool_name == "get_system_info"


def test_direct_planner_detects_laptop_specs_request():
    plan = direct_plan("what are the specs of this laptop?")

    assert plan.intent == "get_system_info"
    assert plan.actions[0].tool_name == "get_system_info"


def test_direct_planner_detects_assistant_identity_request():
    plan = direct_plan("Who are you?")

    assert plan.intent == "get_assistant_profile"
    assert plan.actions[0].tool_name == "get_assistant_profile"


def test_direct_planner_detects_assistant_capability_request():
    plan = direct_plan("Who are you and what are your functionalities?")

    assert plan.intent == "get_assistant_profile"
    assert plan.actions[0].tool_name == "get_assistant_profile"


def test_direct_planner_detects_capability_only_request():
    plan = direct_plan("Hey SAGE, what can you do?")

    assert plan.intent == "get_assistant_profile"
    assert plan.actions[0].tool_name == "get_assistant_profile"


def test_direct_planner_detects_memory_info_request():
    plan = direct_plan("How much RAM do I have?")

    assert plan.intent == "get_memory_info"
    assert plan.actions[0].tool_name == "get_memory_info"


def test_direct_planner_detects_project_context_request():
    plan = direct_plan("what is in this repo")

    assert plan.intent == "get_project_context"
    assert plan.actions[0].tool_name == "get_project_context"


def test_direct_planner_detects_project_overview_multi_tool_request():
    plan = direct_plan("inspect this repo")

    assert plan.intent == "project_overview"
    assert [action.tool_name for action in plan.actions] == [
        "detect_project",
        "get_project_summary",
        "get_git_status",
        "list_project_files",
    ]
    assert plan.requires_confirmation is False


def test_direct_planner_detects_git_status_request():
    plan = direct_plan("show git status")

    assert plan.intent == "get_git_status"
    assert plan.actions[0].tool_name == "get_git_status"


def test_direct_planner_detects_common_git_change_request():
    plan = direct_plan("what changed in this repo")

    assert plan.intent == "get_git_status"
    assert plan.actions[0].tool_name == "get_git_status"


def test_direct_planner_detects_project_file_listing_request():
    plan = direct_plan("list project files")

    assert plan.intent == "list_project_files"
    assert plan.actions[0].tool_name == "list_project_files"


def test_direct_planner_detects_file_excerpt_request():
    plan = direct_plan("show README.md")

    assert plan.intent == "show_file_excerpt"
    assert plan.actions[0].tool_name == "show_file_excerpt"
    assert plan.actions[0].arguments["path"] == "readme.md"


def test_direct_planner_returns_none_for_unknown_command():
    assert direct_plan("please reason about this vague task") is None
