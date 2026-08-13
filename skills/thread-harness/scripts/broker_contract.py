#!/usr/bin/env python3
"""Pure validation and budget helpers for the thread-harness broker."""

from __future__ import annotations


PROFILES = {"solo", "swarm"}
BUDGET_FIELDS = (
    "smart_zone_tokens",
    "tail_requests",
    "tail_p75_increment_tokens",
)
BUDGET_STAGES = {"tracking", "handoff_due"}
COMPACTION_HANDOFF_LIMIT = 3


def node_kind(value: dict) -> str:
    """Classify a child without making the agent infer a coordination profile.

    Explicit ``node_type``/``kind`` wins.  A package entry is the smallest
    positive signal for a task node; a child without one is a Platform node in
    swarm mode.
    """
    declared = value.get("node_type") or value.get("kind")
    if isinstance(declared, str):
        normalized = declared.strip().lower()
        if normalized in {"task", "package", "worker"}:
            return "task"
        if normalized in {"platform", "shared"}:
            return "platform"
    package_entry = value.get("package_entry")
    if isinstance(package_entry, str) and package_entry.strip():
        return "task"
    return "platform"


def _positive_int(value) -> bool:
    return type(value) is int and value > 0


def validate_broker_config(registry: dict) -> tuple[dict | None, list[tuple[str, str]]]:
    """Return normalized broker config and fail-closed validation issues."""
    issues: list[tuple[str, str]] = []
    broker = registry.get("broker") if isinstance(registry, dict) else None
    if not isinstance(broker, dict):
        return None, [("broker_missing", "broker")]

    profile = broker.get("profile")
    if not isinstance(profile, str) or profile not in PROFILES:
        issues.append(("broker_invalid_profile", str(profile)))

    budget = broker.get("budget")
    if not isinstance(budget, dict):
        issues.append(("broker_budget_missing", "broker.budget"))
        return None, issues

    values = {}
    for field in BUDGET_FIELDS:
        value = budget.get(field)
        if not _positive_int(value):
            issues.append(("broker_invalid_budget", f"broker.budget.{field}={value!r}"))
        else:
            values[field] = value

    if len(values) == len(BUDGET_FIELDS):
        tail_reserve = values["tail_requests"] * values["tail_p75_increment_tokens"]
        handoff_at = values["smart_zone_tokens"] - tail_reserve
        if handoff_at <= 0:
            issues.append(("broker_invalid_handoff_threshold", f"handoff_at={handoff_at}"))
        values["tail_reserve_tokens"] = tail_reserve
        values["handoff_at"] = handoff_at

    if issues:
        return None, issues
    return {"profile": profile, "budget": values}, []


def budget_stage(
    observer: dict | None,
    config: dict,
    *,
    previous_stage: str | None = None,
    compaction_count: int | None = None,
) -> tuple[str, str]:
    """Return ``(stage, source)`` without treating missing token data as zero."""
    if previous_stage == "handoff_due":
        return "handoff_due", "sticky"

    observer = observer if isinstance(observer, dict) else {}
    handoff_at = config["budget"]["handoff_at"]
    token_usage = observer.get("last_token_usage")
    context_window = observer.get("model_context_window")
    token_available = observer.get("token_usage_available") is True
    if token_available and isinstance(token_usage, dict):
        input_tokens = token_usage.get("input_tokens")
        if (
            type(input_tokens) is int
            and input_tokens >= 0
            and type(context_window) is int
            and context_window >= handoff_at
        ):
            if input_tokens >= handoff_at:
                return "handoff_due", "token"
            return "tracking", "token"

    # Compatibility path: only an observed compaction count can activate it.
    # Missing observer data remains unknown and never becomes a guessed zero.
    if type(compaction_count) is int and compaction_count > COMPACTION_HANDOFF_LIMIT:
        return "handoff_due", "compaction_fallback"
    return "tracking", "compaction_fallback"
