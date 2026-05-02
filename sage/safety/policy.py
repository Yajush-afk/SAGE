"""Deterministic safety policy for planned commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from sage.contracts import IntentPlan, RiskLevel, SafetyAction, SafetyDecision

BLOCKED_INTENT_KEYWORDS: Final[tuple[str, ...]] = (
    "sudo",
    "privileged",
    "credential",
    "password",
    "secret",
    "delete",
    "remove_file",
    "rm_rf",
    "git_reset",
    "git_clean",
    "format_disk",
)

CONFIRMATION_INTENT_KEYWORDS: Final[tuple[str, ...]] = (
    "kill",
    "stop",
    "restart",
    "install",
    "write",
    "save",
    "modify",
    "create",
    "start",
)


class SafetyPolicy:
    """Apply deterministic safety rules after model planning."""

    def evaluate(
        self,
        plan: IntentPlan,
        confirmation_timeout_seconds: int,
        now: datetime | None = None,
    ) -> SafetyDecision:
        evaluated_at = now or datetime.now(UTC)
        risk = self._effective_risk(plan)

        if risk in {RiskLevel.BLOCKED, RiskLevel.PRIVILEGED, RiskLevel.DESTRUCTIVE}:
            return SafetyDecision(
                action=SafetyAction.BLOCK,
                risk=risk,
                reason=f"{risk.value} commands are blocked in the current safety policy.",
            )

        if risk == RiskLevel.STATE_CHANGING or plan.requires_confirmation:
            phrase = confirmation_phrase_for_plan(plan)
            return SafetyDecision(
                action=SafetyAction.REQUIRE_CONFIRMATION,
                risk=risk,
                reason="This command changes local state and requires explicit confirmation.",
                confirmation_phrase=phrase,
                expires_at=evaluated_at + timedelta(seconds=confirmation_timeout_seconds),
            )

        return SafetyDecision(
            action=SafetyAction.ALLOW,
            risk=risk,
            reason="This command is read-only or safe to plan without confirmation.",
        )

    def _effective_risk(self, plan: IntentPlan) -> RiskLevel:
        intent = plan.intent.lower()
        tool_names = " ".join(action.tool_name.lower() for action in plan.actions)
        searchable = f"{intent} {tool_names}"

        if any(keyword in searchable for keyword in BLOCKED_INTENT_KEYWORDS):
            return RiskLevel.BLOCKED

        if plan.risk in {RiskLevel.BLOCKED, RiskLevel.PRIVILEGED, RiskLevel.DESTRUCTIVE}:
            return plan.risk

        if plan.risk == RiskLevel.STATE_CHANGING:
            return plan.risk

        if any(keyword in searchable for keyword in CONFIRMATION_INTENT_KEYWORDS):
            return RiskLevel.STATE_CHANGING

        return plan.risk


def confirmation_phrase_for_plan(plan: IntentPlan) -> str:
    intent = plan.intent.lower()

    if "kill" in intent:
        return "confirm kill"
    if "stop" in intent:
        return "confirm stop"
    if "restart" in intent:
        return "confirm restart"
    if "install" in intent:
        return "confirm install"
    if "save" in intent or "remember" in intent:
        return "confirm save"
    if "start" in intent:
        return "confirm start"
    if "write" in intent or "modify" in intent or "create" in intent:
        return "confirm change"

    return "confirm action"


def confirmation_matches(
    decision: SafetyDecision,
    phrase: str,
    now: datetime | None = None,
) -> bool:
    if decision.action != SafetyAction.REQUIRE_CONFIRMATION:
        return False
    if decision.confirmation_phrase is None:
        return False
    if decision.expires_at is not None and (now or datetime.now(UTC)) > decision.expires_at:
        return False
    return phrase.strip().lower() == decision.confirmation_phrase
