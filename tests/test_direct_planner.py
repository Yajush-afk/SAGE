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


def test_direct_planner_returns_none_for_unknown_command():
    assert direct_plan("please reason about this vague task") is None
