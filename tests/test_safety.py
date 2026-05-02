from datetime import UTC, datetime, timedelta

from sage.contracts import IntentPlan, RiskLevel, SafetyAction, ToolCall
from sage.safety import SafetyPolicy, confirmation_matches, confirmation_phrase_for_plan


def make_plan(
    intent: str,
    risk: RiskLevel,
    requires_confirmation: bool = False,
) -> IntentPlan:
    return IntentPlan(
        intent=intent,
        confidence=0.9,
        summary=f"Plan: {intent}",
        actions=[],
        risk=risk,
        requires_confirmation=requires_confirmation,
    )


def test_safety_policy_allows_read_only_plan():
    decision = SafetyPolicy().evaluate(
        make_plan("inspect_project", RiskLevel.READ_ONLY),
        confirmation_timeout_seconds=30,
        now=datetime.now(UTC),
    )

    assert decision.action == SafetyAction.ALLOW
    assert decision.risk == RiskLevel.READ_ONLY
    assert decision.confirmation_phrase is None


def test_safety_policy_requires_confirmation_for_state_changing_plan():
    now = datetime.now(UTC)
    decision = SafetyPolicy().evaluate(
        make_plan("start_dev_server", RiskLevel.STATE_CHANGING, requires_confirmation=True),
        confirmation_timeout_seconds=30,
        now=now,
    )

    assert decision.action == SafetyAction.REQUIRE_CONFIRMATION
    assert decision.confirmation_phrase == "confirm start"
    assert decision.expires_at == now + timedelta(seconds=30)


def test_safety_policy_blocks_privileged_plan():
    decision = SafetyPolicy().evaluate(
        make_plan("run_sudo_command", RiskLevel.PRIVILEGED),
        confirmation_timeout_seconds=30,
    )

    assert decision.action == SafetyAction.BLOCK
    assert decision.risk == RiskLevel.BLOCKED


def test_safety_policy_blocks_dangerous_tool_name():
    plan = IntentPlan(
        intent="cleanup_project",
        confidence=0.9,
        summary="Clean project.",
        actions=[ToolCall(tool_name="git_reset_hard", arguments={})],
        risk=RiskLevel.SAFE_EXECUTION,
        requires_confirmation=False,
    )

    decision = SafetyPolicy().evaluate(plan, confirmation_timeout_seconds=30)

    assert decision.action == SafetyAction.BLOCK
    assert decision.risk == RiskLevel.BLOCKED


def test_confirmation_phrase_mapping():
    plan = make_plan("kill_process_on_port", RiskLevel.STATE_CHANGING)

    assert confirmation_phrase_for_plan(plan) == "confirm kill"


def test_confirmation_matches_required_phrase_before_expiry():
    decision = SafetyPolicy().evaluate(
        make_plan("kill_process_on_port", RiskLevel.STATE_CHANGING, requires_confirmation=True),
        confirmation_timeout_seconds=30,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert confirmation_matches(decision, "confirm kill", now=datetime(2026, 1, 1, tzinfo=UTC))
    assert not confirmation_matches(decision, "yes", now=datetime(2026, 1, 1, tzinfo=UTC))


def test_confirmation_fails_after_expiry():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    decision = SafetyPolicy().evaluate(
        make_plan("kill_process_on_port", RiskLevel.STATE_CHANGING, requires_confirmation=True),
        confirmation_timeout_seconds=30,
        now=now,
    )

    assert not confirmation_matches(decision, "confirm kill", now=now + timedelta(seconds=31))
