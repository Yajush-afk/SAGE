from sage.planner import direct_plan


def test_direct_planner_detects_project_request():
    plan = direct_plan("what project is this")

    assert plan.intent == "inspect_project"
    assert plan.actions[0].tool_name == "detect_project"


def test_direct_planner_detects_port_lookup():
    plan = direct_plan("what is running on port 3000")

    assert plan.intent == "find_process_on_port"
    assert plan.actions[0].arguments["port"] == 3000


def test_direct_planner_returns_none_for_unknown_command():
    assert direct_plan("please reason about this vague task") is None
