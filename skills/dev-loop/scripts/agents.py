"""Agent-pool records and reuse hints for a package profile."""

from __future__ import annotations

import uuid

AGENT_STATUSES = {"active", "replaced", "retired"}
_AGENT_FIELDS = {"role", "scope", "host", "agent_id", "model", "effort", "review_group",
                 "status", "replaced_by", "handoff_note", "note"}


def _rows(profile: dict) -> list[dict]:
    rows = profile.get("agents", [])
    if not isinstance(rows, list):
        raise ValueError("profile agents 必须是 list")
    return rows


def _agent_id(value: object | None = None) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else f"agent-{uuid.uuid4().hex}"


def _scope(value: object) -> str | list[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    raise ValueError("scope 必须是非空 Ticket 或 batch 字符串/列表")


def _scope_ids(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _record(profile: dict, agent_id: str) -> dict:
    for row in _rows(profile):
        if isinstance(row, dict) and row.get("id") == agent_id:
            return row
    raise ValueError(f"agent 不存在：{agent_id}")


def _unique(profile: dict, agent_id: str) -> None:
    if any(isinstance(row, dict) and row.get("id") == agent_id for row in _rows(profile)):
        raise ValueError(f"agent id 已存在：{agent_id}")


def _validate_optional_text(fields: dict, names: set[str]) -> None:
    for name in names.intersection(fields):
        value = fields[name]
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{name} 必须是字符串")


def register(profile: dict, values: dict) -> dict:
    """Append an agent, generating a stable profile-local id when omitted."""
    role, host = values.get("role"), values.get("host")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("role 必须是非空字符串")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host 必须是非空字符串")
    _validate_optional_text(values, {"agent_id", "model", "effort", "review_group", "note"})
    agent_id = _agent_id(values.get("id"))
    _unique(profile, agent_id)
    status = values.get("status", "active")
    if status not in AGENT_STATUSES:
        raise ValueError(f"agent status 无效：{status}")
    record = {
        "id": agent_id,
        "role": role.strip(),
        "scope": _scope(values.get("scope")),
        "host": host.strip(),
        "agent_id": values.get("agent_id") or None,
        "model": values.get("model"),
        "effort": values.get("effort"),
        "review_group": values.get("review_group") or None,
        "status": status,
        "replaced_by": None,
        "handoff_note": None,
        "note": values.get("note") or "",
    }
    _rows(profile).append(record)
    return dict(record)


def update(profile: dict, agent_id: str, changes: dict) -> dict:
    """Update supplied fields while keeping the agent id immutable."""
    unknown = set(changes) - _AGENT_FIELDS
    if unknown:
        raise ValueError(f"不支持的 agent 字段：{', '.join(sorted(unknown))}")
    _validate_optional_text(changes, _AGENT_FIELDS - {"scope", "status"})
    record = _record(profile, agent_id)
    if "role" in changes and (not isinstance(changes["role"], str) or not changes["role"].strip()):
        raise ValueError("role 必须是非空字符串")
    if "host" in changes and (not isinstance(changes["host"], str) or not changes["host"].strip()):
        raise ValueError("host 必须是非空字符串")
    if "scope" in changes:
        changes = {**changes, "scope": _scope(changes["scope"])}
    if "status" in changes and changes["status"] not in AGENT_STATUSES:
        raise ValueError(f"agent status 无效：{changes['status']}")
    record.update(changes)
    for name in ("role", "host"):
        if name in changes:
            record[name] = record[name].strip()
    if changes.get("agent_id") == "":
        record["agent_id"] = None
    return dict(record)


def replace(profile: dict, agent_id: str, values: dict, new_id: str | None = None,
            handoff_note: str | None = None) -> dict:
    """Mark an active agent replaced and create or associate its successor."""
    if not isinstance(handoff_note, str) or not handoff_note.strip():
        raise ValueError("replace 必须提供非空 handoff_note")
    old = _record(profile, agent_id)
    if old.get("status") != "active":
        raise ValueError(f"只能替代 active agent：{agent_id}")
    replacement_id = _agent_id(new_id or values.get("id"))
    if replacement_id == agent_id:
        raise ValueError("replacement agent 必须与旧 agent 不同")
    existing = next((row for row in _rows(profile)
                     if isinstance(row, dict) and row.get("id") == replacement_id), None)
    created = existing is None
    if existing is None:
        fields = {
            "id": replacement_id,
            "role": values.get("role", old.get("role")),
            "scope": values.get("scope", old.get("scope")),
            "host": values.get("host", old.get("host")),
            "agent_id": values.get("agent_id"),
            "model": values.get("model"),
            "effort": values.get("effort"),
            "review_group": values.get("review_group", old.get("review_group")),
            "note": values.get("note", ""),
        }
        successor = register(profile, fields)
    else:
        if existing.get("status") != "active":
            raise ValueError(f"replacement agent 必须处于 active：{replacement_id}")
        successor = update(profile, replacement_id, values) if values else dict(existing)
    old.update({"status": "replaced", "replaced_by": replacement_id,
                "handoff_note": handoff_note.strip()})
    return {"replaced": dict(old), "replacement": successor, "created": created}


def list_agents(profile: dict) -> list[dict]:
    return [dict(row) for row in _rows(profile) if isinstance(row, dict)]


def active_for_scope_role(profile: dict, scope: str, role: str) -> list[dict]:
    return [row for row in list_agents(profile)
            if row.get("status") == "active" and row.get("role") == role and scope in _scope_ids(row.get("scope"))]


def reuse_recommendations(profile: dict) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in list_agents(profile):
        role = row.get("role")
        if row.get("status") != "active" or not isinstance(role, str) or role.lower() not in {"implementer", "reviewer"}:
            continue
        for scope in _scope_ids(row.get("scope")):
            grouped.setdefault((scope, role), []).append(row)
    return [{"scope": scope, "role": role, "agents": agents_}
            for (scope, role), agents_ in grouped.items()]


def previous_reviewers(profile: dict) -> list[dict]:
    return [row for row in list_agents(profile)
            if isinstance(row.get("role"), str) and row["role"].lower() == "reviewer"]


def status_view(profile: dict) -> dict:
    items = list_agents(profile)
    display = [{**row, "agent_id": row.get("agent_id") or "unconfirmed"} for row in items]
    recommendations = reuse_recommendations(profile)
    recommendation_display = [
        {**item, "agents": [{**row, "agent_id": row.get("agent_id") or "unconfirmed"}
                             for row in item["agents"]]}
        for item in recommendations
    ]
    reviewers = [{**row, "agent_id": row.get("agent_id") or "unconfirmed"}
                 for row in previous_reviewers(profile)]
    return {"items": display,
            "active": [row for row in display if row.get("status") == "active"],
            "reuse_recommendations": recommendation_display,
            "previous_reviewers": reviewers}
