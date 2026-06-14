"""Planner construction from runtime settings."""

from __future__ import annotations

from sage.contracts import IntentPlan, PlannerContext, RuntimeSettings
from sage.planner.ollama import OllamaPlanner, Planner, PlannerError


class UnsupportedPlanner:
    """Planner placeholder for configured providers that are not implemented yet."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def plan(
        self,
        transcript: str,
        context: PlannerContext,
        settings: RuntimeSettings,
    ) -> IntentPlan:
        raise PlannerError(
            f"planner_provider={self.provider} is configured, "
            "but only ollama is implemented right now."
        )


def build_planner(settings: RuntimeSettings) -> Planner:
    if settings.planner_provider == "ollama":
        return OllamaPlanner()
    return UnsupportedPlanner(settings.planner_provider)
