"""Cross-Ticket review batches and their read-only status projection."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from .facts import read_rounds_summary

BATCH_STATUSES = {"open", "triaged", "closed", "superseded"}
_COVERING_STATUSES = {"open", "triaged", "closed"}


def _rows(profile: dict) -> list[dict]:
    rows = profile.get("batches", [])
    if not isinstance(rows, list):
        raise ValueError("profile batches 必须是 list")
    return rows


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _batch(profile: dict, batch_id: str) -> dict:
    for row in _rows(profile):
        if isinstance(row, dict) and row.get("batch_id") == batch_id:
            return row
    raise ValueError(f"batch 不存在：{batch_id}")


def _batch_id(value: object | None) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else f"batch-{uuid.uuid4().hex}"


def _optional_text(values: dict, name: str) -> str | None:
    value = values.get(name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{name} 必须是字符串")
    return value or None


def _list_field(values: dict, name: str) -> list[str]:
    value = values.get(name, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} 必须是字符串数组")
    return [item.strip() for item in value]


def register(profile: dict, values: dict) -> dict:
    batch_id = _batch_id(values.get("batch_id"))
    if any(isinstance(row, dict) and row.get("batch_id") == batch_id for row in _rows(profile)):
        raise ValueError(f"batch_id 已存在：{batch_id}")
    snapshot_kind = values.get("snapshot_kind", "integrated")
    status = values.get("status", "open")
    if snapshot_kind not in {"integrated", "isolated"}:
        raise ValueError(f"snapshot_kind 无效：{snapshot_kind}")
    if status not in BATCH_STATUSES:
        raise ValueError(f"batch status 无效：{status}")
    ticket_notes = values.get("ticket_notes", {})
    if not isinstance(ticket_notes, dict) or any(not isinstance(key, str) or not isinstance(note, str)
                                                  for key, note in ticket_notes.items()):
        raise ValueError("ticket_notes 必须是字符串到字符串的 object")
    record = {
        "batch_id": batch_id,
        "tickets": _list_field(values, "tickets"),
        "returns": _list_field(values, "returns"),
        "reviewed_head": _optional_text(values, "reviewed_head"),
        "snapshot_kind": snapshot_kind,
        "review_run_id": _optional_text(values, "review_run_id"),
        "rounds_file": _optional_text(values, "rounds_file"),
        "status": status,
        "ticket_notes": dict(ticket_notes),
        "note": values.get("note") or "",
    }
    if not isinstance(record["note"], str):
        raise ValueError("note 必须是字符串")
    _rows(profile).append(record)
    return dict(record)


def update(profile: dict, batch_id: str, changes: dict) -> dict:
    allowed = {"tickets", "returns", "reviewed_head", "snapshot_kind", "review_run_id",
               "rounds_file", "status", "ticket_notes", "note"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"不支持的 batch 字段：{', '.join(sorted(unknown))}")
    record = _batch(profile, batch_id)
    if "status" in changes and changes["status"] not in BATCH_STATUSES:
        raise ValueError(f"batch status 无效：{changes['status']}")
    if "snapshot_kind" in changes and changes["snapshot_kind"] not in {"integrated", "isolated"}:
        raise ValueError(f"snapshot_kind 无效：{changes['snapshot_kind']}")
    for name in ("tickets", "returns"):
        if name in changes:
            changes[name] = _list_field(changes, name)
    for name in ("reviewed_head", "review_run_id", "rounds_file"):
        if name in changes:
            changes[name] = _optional_text(changes, name)
    if "ticket_notes" in changes:
        notes = changes["ticket_notes"]
        if not isinstance(notes, dict) or any(not isinstance(key, str) or not isinstance(note, str)
                                               for key, note in notes.items()):
            raise ValueError("ticket_notes 必须是字符串到字符串的 object")
        changes = {**changes, "ticket_notes": {**record.get("ticket_notes", {}), **notes}}
    if "note" in changes and not isinstance(changes["note"], str):
        raise ValueError("note 必须是字符串")
    record.update(changes)
    return dict(record)


def close(profile: dict, batch_id: str) -> dict:
    return update(profile, batch_id, {"status": "closed"})


def list_batches(profile: dict) -> list[dict]:
    return [dict(row) for row in _rows(profile) if isinstance(row, dict)]


def _return_id(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("return_id") or item.get("candidate_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _current_head(package: str | Path) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(Path(package).expanduser().absolute()),
                                 "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True, timeout=3)
        head = result.stdout.strip()
        return head or None
    except (OSError, subprocess.SubprocessError):
        return None


def _rounds(package: Path, rounds_file: str) -> dict:
    path = Path(rounds_file).expanduser()
    if not path.is_absolute():
        path = package / path
    try:
        return read_rounds_summary(path)
    except Exception as error:
        return {"path": str(path), "status": "undetermined", "group": None, "round": None,
                "phase": None, "open_seq": 0, "closed": False, "tracks": [],
                "open_findings": [], "open_findings_count": 0, "converged": False,
                "reasons": [f"无法读取批次 rounds 摘要：{error}"]}


def status_view(profile: dict, pending_returns: list[dict], package: str | Path) -> dict:
    """Resolve return coverage and attach per-batch rounds and snapshot warnings."""
    root = Path(package).expanduser().absolute()
    raw_batches = list_batches(profile)
    pending = [item for item in pending_returns if isinstance(item, dict)]
    coverage: dict[str, str] = {}
    for row in raw_batches:
        batch_id = row.get("batch_id")
        if row.get("status") not in _COVERING_STATUSES or not isinstance(batch_id, str) or not batch_id.strip():
            continue
        for return_id in _strings(row.get("returns")):
            coverage.setdefault(return_id, batch_id)

    current_head = _current_head(root)
    views = []
    for row in raw_batches:
        batch_id = row.get("batch_id")
        if not isinstance(batch_id, str):
            continue
        view = dict(row)
        view["tickets"] = _strings(row.get("tickets"))
        view["returns"] = _strings(row.get("returns"))
        view["covered_returns"] = [return_id for return_id in view["returns"]
                                   if coverage.get(return_id) == batch_id
                                   and any(_return_id(item) == return_id for item in pending)]
        view["rounds_summary"] = _rounds(root, row["rounds_file"]) if isinstance(row.get("rounds_file"), str) and row["rounds_file"] else None
        view["current_head"] = current_head
        view["head_drift"] = bool(current_head and isinstance(row.get("reviewed_head"), str)
                                  and row["reviewed_head"] and row["reviewed_head"] != current_head)
        alerts = []
        if row.get("status") != "superseded":
            if view.get("snapshot_kind") == "isolated":
                alerts.append("隔离快照审阅：核对影响范围、确认集成后等价，并按票执行 evidence add。")
            if view["head_drift"]:
                alerts.append(f"审阅 HEAD {row['reviewed_head']} 与当前 HEAD {current_head} 不同：核对影响范围、确认等价，并按票执行 evidence add。")
        view["alerts"] = alerts
        views.append(view)

    assignments = [{"return_id": return_id, "batch_id": batch_id}
                   for return_id, batch_id in coverage.items()
                   if any(_return_id(item) == return_id for item in pending)]
    uncovered = [item for item in pending if _return_id(item) not in coverage]
    return {"items": views, "uncovered_returns": uncovered,
            "return_assignments": assignments, "current_head": current_head}
