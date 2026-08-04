#!/usr/bin/env python3
"""Inventory and safely prune Codex sessions through the App Server API.

The command never parses or mutates rollout JSONL files and never mutates the
Codex state database.  With ``--disk-size`` it only enumerates matching rollout
files and reads their filesystem metadata to report byte totals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import ntpath
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Sequence

try:
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from codex_harness_cli import JsonRpcSession, app_server_command, initialize_params


UNKNOWN_PROJECT = "(unknown)"
PAGE_LIMIT = 100
RPC_TIMEOUT_SECONDS = 60.0
ALL_SOURCE_KINDS = (
    "cli",
    "vscode",
    "exec",
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
    "unknown",
)

_UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
_THREAD_ID_RE = re.compile(r"\bthr_[A-Za-z0-9_.:-]+\b")
_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class SessionProtocol(Protocol):
    def request(
        self, request_id: int, method: str, params: dict[str, Any], timeout: float
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]: ...

    def close(self) -> None: ...


SessionFactory = Callable[[], SessionProtocol]


class PruneError(RuntimeError):
    """A user-facing validation or App Server error."""


@dataclass(frozen=True)
class RolloutUsage:
    sizes: Mapping[str, int]
    files: int
    total_bytes: int
    roots: tuple[str, ...]
    errors: tuple[str, ...] = ()


def _looks_like_windows_path(value: str) -> bool:
    return bool(_WINDOWS_ABS_RE.match(value)) or "\\" in value


def is_absolute_path(value: str) -> bool:
    """Recognize native paths and Windows paths in cross-platform tests."""

    if _looks_like_windows_path(value):
        return ntpath.isabs(value)
    return os.path.isabs(value)


def normalize_project(value: str | None) -> str | None:
    """Return a stable exact-match key for a session cwd/project path."""

    if value is None or not isinstance(value, str) or not value.strip():
        return None
    raw = os.path.expanduser(value.strip())
    if _looks_like_windows_path(raw) or os.name == "nt":
        return ntpath.normcase(ntpath.normpath(raw.replace("/", "\\")))
    return os.path.normcase(os.path.normpath(os.path.abspath(raw)))


def _project_display(value: str | None) -> str:
    return normalize_project(value) or UNKNOWN_PROJECT


def _json_id_values(value: Any) -> Iterator[str]:
    """Extract IDs from structured registry JSON without trusting arbitrary text."""

    interesting_keys = {
        "id",
        "threadid",
        "thread_id",
        "sessionid",
        "session_id",
        "agentthreadid",
        "agent_thread_id",
        "rootthreadid",
        "root_thread_id",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in interesting_keys and isinstance(nested, str):
                yield nested
            yield from _json_id_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _json_id_values(nested)


def _extract_registry_ids(text: str) -> set[str]:
    found: set[str] = set()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        found.update(value for value in _json_id_values(parsed) if value)
    else:
        # Registry files are often JSONL or contain a JSON object followed by
        # comments/annotations.  Recover structured ID fields line by line
        # before falling back to the conservative token scans below.
        for line in text.splitlines():
            try:
                line_value = json.loads(line)
            except json.JSONDecodeError:
                continue
            found.update(value for value in _json_id_values(line_value) if value)
    found.update(_UUID_RE.findall(text))
    found.update(_THREAD_ID_RE.findall(text))
    return found


def load_registry_ids(paths: Sequence[str | Path]) -> set[str]:
    """Read registry references from files/directories, failing on bad paths."""

    ids: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise PruneError(f"registry path does not exist: {path}")
        files = [path] if path.is_file() else [
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in {".json", ".jsonl", ".yaml", ".yml", ".toml", ".md", ".txt"}
        ]
        if not path.is_file() and not path.is_dir():
            raise PruneError(f"registry path is not a file or directory: {path}")
        for item in files:
            try:
                text = item.read_text(encoding="utf-8")
            except OSError as exc:
                raise PruneError(f"cannot read registry path: {item}: {exc}") from exc
            ids.update(_extract_registry_ids(text))
    return ids


def resolve_codex_home(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex").resolve()


def collect_rollout_usage(codex_home: str | Path | None = None) -> RolloutUsage:
    """Index rollout file sizes by thread ID without reading file contents."""

    root = resolve_codex_home(codex_home)
    rollout_roots = (root / "sessions", root / "archived_sessions")
    sizes: dict[str, int] = {}
    files = 0
    total_bytes = 0
    errors: list[str] = []
    for rollout_root in rollout_roots:
        if not rollout_root.exists():
            continue
        try:
            paths = rollout_root.rglob("*.jsonl")
            for path in paths:
                ids = set(_UUID_RE.findall(path.stem)) | set(_THREAD_ID_RE.findall(path.stem))
                if not ids:
                    continue
                try:
                    size = path.stat().st_size
                except OSError as exc:
                    errors.append(f"cannot stat rollout file {path}: {exc}")
                    continue
                files += 1
                total_bytes += size
                for thread_id in ids:
                    sizes[thread_id] = sizes.get(thread_id, 0) + size
        except OSError as exc:
            errors.append(f"cannot enumerate rollout directory {rollout_root}: {exc}")
    return RolloutUsage(
        sizes=sizes,
        files=files,
        total_bytes=total_bytes,
        roots=tuple(str(path) for path in rollout_roots),
        errors=tuple(errors),
    )


def format_bytes(value: int) -> str:
    number = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(number) < 1024 or unit == "TiB":
            return f"{int(value)} B" if unit == "B" else f"{number:.2f} {unit}"
        number /= 1024
    return f"{int(value)} B"


def resolve_global_state_path(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return (root / ".codex-global-state.json").resolve()


def load_pinned_ids(path: str | Path | None = None) -> tuple[set[str], str | None]:
    """Load pinned IDs; return a reason when the guard cannot be trusted."""

    state_path = resolve_global_state_path(path)
    if not state_path.exists():
        return set(), None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), f"cannot read pinned-thread-ids from {state_path}: {exc}"
    if not isinstance(state, Mapping):
        return set(), f"global state is not a JSON object: {state_path}"
    values: Any = state.get("pinned-thread-ids")
    if values is None:
        values = state.get("pinnedThreadIds")
    if values is None:
        return set(), None
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return set(), f"pinned-thread-ids is malformed in {state_path}"
    return set(values), None


def _finite_timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return None
    return result


@dataclass(frozen=True)
class ThreadInfo:
    id: str
    cwd: str | None
    project: str
    archived: bool
    source_kind: str
    parent_id: str | None
    created_at: Any
    updated_at: Any
    raw: dict[str, Any] = field(repr=False, compare=False)

    @property
    def updated_timestamp(self) -> float | None:
        return _finite_timestamp(self.updated_at)

    @property
    def project_known(self) -> bool:
        return self.cwd is not None and self.project != UNKNOWN_PROJECT

    def as_dict(
        self,
        *,
        reason: str | None = None,
        selected: bool | None = None,
        descendants: int = 0,
        pinned: bool | None = None,
        loaded: bool | None = None,
        registry_protected: bool | None = None,
        disk_size_bytes: int | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "project": self.project,
            "cwd": self.cwd,
            "archived": self.archived,
            "source_kind": self.source_kind,
            "pinned": self.raw.get("pinned") if pinned is None else pinned,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "descendants": descendants,
        }
        if loaded is not None:
            result["loaded"] = loaded
        if registry_protected is not None:
            result["registry_protected"] = registry_protected
        if disk_size_bytes is not None:
            result["disk_size_bytes"] = disk_size_bytes
            result["disk_size"] = format_bytes(disk_size_bytes)
        if reason is not None:
            result["reason"] = reason
        if selected is not None:
            result["selected"] = selected
        return result


def thread_info(raw: Mapping[str, Any], archived: bool) -> ThreadInfo:
    thread_id = raw.get("id")
    if not isinstance(thread_id, str) or not thread_id:
        raise PruneError(f"thread/list returned a thread without a valid id: {raw!r}")
    cwd = raw.get("cwd") if isinstance(raw.get("cwd"), str) else None
    source = raw.get("threadSource") or raw.get("source") or "unknown"
    if not isinstance(source, str):
        source = str(source)
    parent = raw.get("parentThreadId")
    if not isinstance(parent, str):
        parent = None
    return ThreadInfo(
        id=thread_id,
        cwd=cwd,
        project=_project_display(cwd),
        archived=archived,
        source_kind=source,
        parent_id=parent,
        created_at=raw.get("createdAt"),
        updated_at=raw.get("updatedAt"),
        raw=dict(raw),
    )


class RequestIds:
    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def rpc_request(session: SessionProtocol, request_ids: RequestIds, method: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        result, _ = session.request(request_ids.next(), method, params, RPC_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - normalize transport errors for CLI
        raise PruneError(f"{method} failed: {exc}") from exc
    if not isinstance(result, dict):
        raise PruneError(f"{method} returned a non-object result")
    return result


def paginate_threads(
    session: SessionProtocol,
    request_ids: RequestIds,
    *,
    archived: bool,
    ancestor_thread_id: str | None = None,
) -> list[ThreadInfo]:
    result: list[ThreadInfo] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {
            "cursor": cursor,
            "limit": PAGE_LIMIT,
            "sortKey": "updated_at",
            "sortDirection": "asc",
            "sourceKinds": list(ALL_SOURCE_KINDS),
            "archived": archived,
            "useStateDbOnly": True,
        }
        if ancestor_thread_id is not None:
            params["ancestorThreadId"] = ancestor_thread_id
        payload = rpc_request(session, request_ids, "thread/list", params)
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise PruneError("thread/list returned a non-array data field")
        result.extend(thread_info(item, archived) for item in data if isinstance(item, Mapping))
        next_cursor = payload.get("nextCursor")
        if not next_cursor:
            return result
        if not isinstance(next_cursor, str):
            raise PruneError("thread/list returned an invalid nextCursor")
        cursor = next_cursor


def collect_inventory(session: SessionProtocol, request_ids: RequestIds) -> tuple[list[ThreadInfo], list[str]]:
    active = paginate_threads(session, request_ids, archived=False)
    archived = paginate_threads(session, request_ids, archived=True)
    merged: dict[str, ThreadInfo] = {}
    for item in active + archived:
        merged.setdefault(item.id, item)
    loaded_payload = rpc_request(session, request_ids, "thread/loaded/list", {})
    loaded = loaded_payload.get("data", [])
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        raise PruneError("thread/loaded/list returned an invalid data field")
    return list(merged.values()), list(loaded)


def inventory_rows(
    threads: Sequence[ThreadInfo],
    rollout_sizes: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in threads:
        row = grouped.setdefault(item.project, {"project": item.project, "active": 0, "archived": 0, "total": 0})
        row["archived" if item.archived else "active"] += 1
        row["total"] += 1
        if rollout_sizes is not None:
            row["disk_size_bytes"] = row.get("disk_size_bytes", 0) + rollout_sizes.get(item.id, 0)
    return sorted(grouped.values(), key=lambda row: (row["project"] == UNKNOWN_PROJECT, str(row["project"]).casefold()))


def _state_matches(item: ThreadInfo, archive_state: str) -> bool:
    return archive_state == "all" or item.archived == (archive_state == "archived")


@dataclass
class Candidate:
    root: ThreadInfo
    descendants: list[ThreadInfo]
    affected_ids: set[str]
    reasons: list[str] = field(default_factory=list)
    selected: bool = False
    pinned_ids: frozenset[str] = field(default_factory=frozenset, repr=False)
    loaded_ids: frozenset[str] = field(default_factory=frozenset, repr=False)
    registry_ids: frozenset[str] = field(default_factory=frozenset, repr=False)
    rollout_sizes: Mapping[str, int] = field(default_factory=dict, repr=False, compare=False)
    include_disk_size: bool = False

    @property
    def eligible(self) -> bool:
        return not self.reasons

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.as_dict(
                selected=self.selected,
                descendants=len(self.descendants),
                pinned=self.root.id in self.pinned_ids,
                loaded=self.root.id in self.loaded_ids,
                registry_protected=self.root.id in self.registry_ids,
                disk_size_bytes=self.rollout_sizes.get(self.root.id, 0) if self.include_disk_size else None,
            ),
            "descendants": [
                item.as_dict(
                    pinned=item.id in self.pinned_ids,
                    loaded=item.id in self.loaded_ids,
                    registry_protected=item.id in self.registry_ids,
                    disk_size_bytes=self.rollout_sizes.get(item.id, 0) if self.include_disk_size else None,
                )
                for item in self.descendants
            ],
            "affected_ids": sorted(self.affected_ids),
            "reasons": list(self.reasons),
        }


@dataclass
class PrunePlan:
    project_filters: list[str]
    all_projects: bool
    archive_state: str
    take: int
    max_affected: int
    roots: list[Candidate]
    selected: list[Candidate]
    affected_ids: list[str]
    guard_unavailable: list[str]
    counters: dict[str, int]
    blocked_reasons: list[str]
    plan_id: str
    rollout_sizes: Mapping[str, int] = field(default_factory=dict, repr=False)
    include_disk_size: bool = False

    @property
    def total_affected(self) -> int:
        return len(self.affected_ids)

    @property
    def disk_size_bytes(self) -> int:
        return sum(self.rollout_sizes.get(thread_id, 0) for thread_id in self.affected_ids)

    @property
    def apply_allowed(self) -> bool:
        return not self.guard_unavailable and not self.blocked_reasons

    def as_dict(self) -> dict[str, Any]:
        result = {
            "project_filters": list(self.project_filters),
            "all_projects": self.all_projects,
            "archive_state": self.archive_state,
            "take": self.take,
            "max_affected": self.max_affected,
            "selection": f"oldest {self.take} eligible roots",
            "root_threads": len(self.selected),
            "descendants": max(0, self.total_affected - len(self.selected)),
            "total_affected": self.total_affected,
            "counters": dict(self.counters),
            "blocked_reasons": list(self.blocked_reasons),
            "guard_unavailable": list(self.guard_unavailable),
            "plan_id": self.plan_id,
            "apply_allowed": self.apply_allowed,
            "details": [candidate.as_dict() for candidate in self.roots],
        }
        if self.include_disk_size:
            result["disk_size_bytes"] = self.disk_size_bytes
            result["disk_size"] = format_bytes(self.disk_size_bytes)
        return result


def compute_plan_id(
    root_ids: Iterable[str],
    affected_ids: Iterable[str],
    project_filters: Sequence[str],
    archive_state: str,
    take: int,
    max_affected: int,
    *,
    all_projects: bool = False,
    include_disk_size: bool = False,
) -> str:
    payload = {
        "root_thread_ids": sorted(set(root_ids)),
        "affected_thread_ids": sorted(set(affected_ids)),
        "project_filters": sorted(project_filters),
        "all_projects": all_projects,
        "archive_state": archive_state,
        "take": take,
        "max_affected": max_affected,
        "include_disk_size": include_disk_size,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _allowed_projects(project_filters: Sequence[str], all_projects: bool) -> set[str] | None:
    return None if all_projects else set(project_filters)


def _root_reason(
    root: ThreadInfo,
    archive_state: str,
    pinned_ids: set[str],
    loaded_ids: set[str],
    registry_ids: set[str],
    allowed_projects: set[str] | None,
) -> list[str]:
    reasons: list[str] = []
    if not root.project_known:
        reasons.append("unknown_project")
    elif allowed_projects is not None and root.project not in allowed_projects:
        reasons.append("project_filter")
    if not _state_matches(root, archive_state):
        reasons.append("archive_state_filter")
    if root.id in pinned_ids:
        reasons.append("pinned")
    if root.id in loaded_ids:
        reasons.append("loaded")
    if root.id in registry_ids:
        reasons.append("registry")
    if root.updated_timestamp is None:
        reasons.append("invalid_updated_at")
    return reasons


def _merge_thread_records(items: Iterable[ThreadInfo]) -> list[ThreadInfo]:
    merged: dict[str, ThreadInfo] = {}
    for item in items:
        merged.setdefault(item.id, item)
    return list(merged.values())


def _descendant_threads(
    session: SessionProtocol,
    request_ids: RequestIds,
    root_id: str,
) -> list[ThreadInfo]:
    # Query both archive states so a selected state can reject cross-state cascades.
    active = paginate_threads(session, request_ids, archived=False, ancestor_thread_id=root_id)
    archived = paginate_threads(session, request_ids, archived=True, ancestor_thread_id=root_id)
    return _merge_thread_records(active + archived)


def build_prune_plan(
    session: SessionProtocol,
    request_ids: RequestIds,
    threads: Sequence[ThreadInfo],
    loaded_ids: Iterable[str],
    *,
    project_filters: Sequence[str],
    all_projects: bool,
    archive_state: str,
    take: int,
    max_affected: int,
    pinned_ids: Iterable[str] = (),
    registry_ids: Iterable[str] = (),
    guard_unavailable: Sequence[str] = (),
    rollout_sizes: Mapping[str, int] | None = None,
    include_disk_size: bool = False,
) -> PrunePlan:
    if archive_state not in {"active", "archived", "all"}:
        raise PruneError(f"invalid archive state: {archive_state}")
    if take < 0 or max_affected < 0:
        raise PruneError("take and max-affected must be non-negative")
    if not all_projects and not project_filters:
        raise PruneError("a project filter or --all-projects is required for a prune plan")

    pinned = set(pinned_ids)
    loaded = set(loaded_ids)
    registry = set(registry_ids)
    sizes = rollout_sizes or {}
    allowed = _allowed_projects(project_filters, all_projects)
    roots = [item for item in threads if item.parent_id is None and _state_matches(item, archive_state)]
    roots.sort(key=lambda item: (item.updated_timestamp is None, item.updated_timestamp or 0, item.id))

    counters: dict[str, int] = {
        "protected_pinned": 0,
        "protected_loaded": 0,
        "protected_registry": 0,
        "rejected_cross_project": 0,
        "rejected_cross_state": 0,
        "rejected_unknown_project": 0,
        "rejected_invalid_updated_at": 0,
    }
    protected_seen = {"pinned": set(), "loaded": set(), "registry": set()}
    candidates: list[Candidate] = []
    for root in roots:
        reasons = _root_reason(root, archive_state, pinned, loaded, registry, allowed)
        descendants: list[ThreadInfo] = []
        affected = {root.id}
        if not reasons:
            descendants = _descendant_threads(session, request_ids, root.id)
            affected.update(item.id for item in descendants)
            for item in [root, *descendants]:
                if item.id in pinned:
                    protected_seen["pinned"].add(item.id)
                if item.id in loaded:
                    protected_seen["loaded"].add(item.id)
                if item.id in registry:
                    protected_seen["registry"].add(item.id)
                if item is root:
                    continue
                if not item.project_known or (allowed is not None and item.project not in allowed):
                    if "cross_project" not in reasons:
                        reasons.append("cross_project")
                if archive_state != "all" and item.archived != root.archived:
                    if "cross_archive_state" not in reasons:
                        reasons.append("cross_archive_state")
                if item.id in pinned and "descendant_pinned" not in reasons:
                    reasons.append("descendant_pinned")
                if item.id in loaded and "descendant_loaded" not in reasons:
                    reasons.append("descendant_loaded")
                if item.id in registry and "descendant_registry" not in reasons:
                    reasons.append("descendant_registry")
        for reason in reasons:
            if reason in {"pinned", "descendant_pinned"}:
                counters["protected_pinned"] += 1
            elif reason in {"loaded", "descendant_loaded"}:
                counters["protected_loaded"] += 1
            elif reason in {"registry", "descendant_registry"}:
                counters["protected_registry"] += 1
            elif reason == "cross_project":
                counters["rejected_cross_project"] += 1
            elif reason == "cross_archive_state":
                counters["rejected_cross_state"] += 1
            elif reason == "unknown_project":
                counters["rejected_unknown_project"] += 1
            elif reason == "invalid_updated_at":
                counters["rejected_invalid_updated_at"] += 1
        candidates.append(
            Candidate(
                root,
                descendants,
                affected,
                reasons,
                False,
                frozenset(pinned),
                frozenset(loaded),
                frozenset(registry),
                sizes,
                include_disk_size,
            )
        )

    eligible = [candidate for candidate in candidates if candidate.eligible]
    selected = eligible[:take]
    for candidate in selected:
        candidate.selected = True
    affected_ids = sorted({thread_id for candidate in selected for thread_id in candidate.affected_ids})
    blocked: list[str] = []
    if len(affected_ids) > max_affected:
        blocked.append(f"total_affected {len(affected_ids)} exceeds max-affected {max_affected}")
    blocked.extend(guard_unavailable)
    plan_id = compute_plan_id(
        (candidate.root.id for candidate in selected),
        affected_ids,
        project_filters,
        archive_state,
        take,
        max_affected,
        all_projects=all_projects,
        include_disk_size=include_disk_size,
    )
    return PrunePlan(
        project_filters=list(project_filters),
        all_projects=all_projects,
        archive_state=archive_state,
        take=take,
        max_affected=max_affected,
        roots=candidates,
        selected=selected,
        affected_ids=affected_ids,
        guard_unavailable=list(guard_unavailable),
        counters=counters,
        blocked_reasons=blocked,
        plan_id=plan_id,
        rollout_sizes=sizes,
        include_disk_size=include_disk_size,
    )


def _format_inventory(rows: Sequence[Mapping[str, Any]]) -> str:
    include_disk_size = any("disk_size_bytes" in row for row in rows)
    header = f"{'PROJECT':<38} {'ACTIVE':>7} {'ARCHIVED':>9} {'TOTAL':>7}"
    if include_disk_size:
        header += f" {'DISK_SIZE':>12}"
    lines = [header]
    for row in rows:
        line = f"{str(row['project']):<38} {int(row['active']):>7} {int(row['archived']):>9} {int(row['total']):>7}"
        if include_disk_size:
            line += f" {format_bytes(int(row.get('disk_size_bytes', 0))):>12}"
        lines.append(line)
    return "\n".join(lines)


def _format_plan(plan: PrunePlan) -> str:
    counters = plan.counters
    lines = [
        f"project_filter:    {', '.join(plan.project_filters) if plan.project_filters else '(all projects)'}",
        f"archive_state:     {plan.archive_state}",
        f"selection:         oldest {plan.take} eligible roots",
        f"root_threads:      {len(plan.selected)}",
        f"descendants:       {max(0, plan.total_affected - len(plan.selected))}",
        f"total_affected:    {plan.total_affected}",
        f"protected_pinned:  {counters.get('protected_pinned', 0)}",
        f"protected_loaded:  {counters.get('protected_loaded', 0)}",
        f"protected_registry: {counters.get('protected_registry', 0)}",
        f"rejected_cross_project: {counters.get('rejected_cross_project', 0)}",
        f"rejected_cross_state:   {counters.get('rejected_cross_state', 0)}",
        f"plan_id:            {plan.plan_id}",
    ]
    if plan.include_disk_size:
        lines.insert(6, f"disk_size:         {format_bytes(plan.disk_size_bytes)} ({plan.disk_size_bytes} bytes)")
    if plan.blocked_reasons:
        lines.append("blocked:            " + "; ".join(plan.blocked_reasons))
    lines.append("details:")
    for candidate in plan.roots:
        status = "selected" if candidate.selected else ("rejected: " + ",".join(candidate.reasons) if candidate.reasons else "eligible-not-taken")
        lines.append(
            f"  {candidate.root.id} project={candidate.root.project} archived={candidate.root.archived} "
            f"createdAt={candidate.root.created_at!r} updatedAt={candidate.root.updated_at!r} "
            f"descendants={len(candidate.descendants)} pinned={candidate.root.id in candidate.pinned_ids}"
            f"{(' disk_size=' + format_bytes(sum(candidate.rollout_sizes.get(item_id, 0) for item_id in candidate.affected_ids))) if candidate.include_disk_size else ''} {status}"
        )
    return "\n".join(lines)


@contextmanager
def default_session() -> Iterator[SessionProtocol]:
    stderr_path = Path(tempfile.gettempdir()) / f"codex-session-prune-{os.getpid()}-{time.monotonic_ns()}.stderr.log"
    session: SessionProtocol = JsonRpcSession(
        app_server_command(enable_multi_agent=True, approval_policy="never"), stderr_path
    )
    try:
        request_ids = RequestIds()
        session.request(request_ids.next(), "initialize", initialize_params("codex-session-prune"), RPC_TIMEOUT_SECONDS)
        yield session
    finally:
        session.close()
        try:
            stderr_path.unlink()
        except OSError:
            pass


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.project and args.all_projects:
        parser.error("--project and --all-projects are mutually exclusive")
    if args.project and any(not is_absolute_path(value) for value in args.project):
        parser.error("--project values must be absolute paths")
    if args.apply != (args.expect_plan is not None):
        parser.error("--apply and --expect-plan must be supplied together")
    candidate_args = any(value is not None for value in (args.archive_state, args.take, args.max_affected))
    if candidate_args and (args.archive_state is None or args.take is None or args.max_affected is None):
        parser.error("candidate mode requires --archive-state, --take, and --max-affected")
    if args.apply and not candidate_args:
        parser.error("--apply requires candidate selection arguments")
    if args.archive_state is not None and args.archive_state not in {"active", "archived", "all"}:
        parser.error("--archive-state must be active, archived, or all")
    if args.take is not None and args.take < 0:
        parser.error("--take must be non-negative")
    if args.max_affected is not None and args.max_affected < 0:
        parser.error("--max-affected must be non-negative")
    if args.all_projects is False and args.archive_state is not None and not args.project:
        parser.error("candidate mode requires --project or --all-projects")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory and safely prune Codex sessions through the Codex App Server API."
    )
    parser.add_argument("--project", action="append", help="exact absolute project cwd; repeatable")
    parser.add_argument("--all-projects", action="store_true", help="allow all known projects (unknown cwd remains protected)")
    parser.add_argument("--archive-state", choices=("active", "archived", "all"), help="session archive state")
    parser.add_argument("--take", type=int, help="select at most N oldest eligible deletion roots")
    parser.add_argument("--max-affected", type=int, help="hard cap including cascaded descendants")
    parser.add_argument(
        "--disk-size",
        action="store_true",
        help="report rollout JSONL sizes using filesystem metadata only",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--protect-registry", action="append", default=[], help="read-only registry file/directory; repeatable")
    parser.add_argument("--apply", action="store_true", help="apply a previously reviewed plan")
    parser.add_argument("--expect-plan", help="required sha256 plan id for --apply")
    return parser


def run(args: argparse.Namespace, session_context: Callable[[], Any] = default_session) -> int:
    project_filters = sorted({normalize_project(value) for value in (args.project or []) if normalize_project(value)})
    registry_ids = load_registry_ids(args.protect_registry)
    pinned_ids, pinned_error = load_pinned_ids()
    guard_unavailable = [pinned_error] if pinned_error else []
    rollout_usage = collect_rollout_usage() if args.disk_size else RolloutUsage({}, 0, 0, ())
    if args.disk_size:
        guard_unavailable.extend(f"disk-size unavailable: {error}" for error in rollout_usage.errors)
    with session_context() as session:
        request_ids = RequestIds()
        threads, loaded_ids = collect_inventory(session, request_ids)
        rows = inventory_rows(threads, rollout_usage.sizes if args.disk_size else None)
        disk_payload = {
            "files": rollout_usage.files,
            "bytes": rollout_usage.total_bytes,
            "size": format_bytes(rollout_usage.total_bytes),
            "roots": list(rollout_usage.roots),
            "errors": list(rollout_usage.errors),
        }
        if args.archive_state is None:
            payload: dict[str, Any] = {"inventory": rows}
            if args.disk_size:
                payload["disk_size"] = disk_payload
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(_format_inventory(rows))
            return 0

        plan = build_prune_plan(
            session,
            request_ids,
            threads,
            loaded_ids,
            project_filters=project_filters,
            all_projects=args.all_projects,
            archive_state=args.archive_state,
            take=args.take,
            max_affected=args.max_affected,
            pinned_ids=pinned_ids,
            registry_ids=registry_ids,
            guard_unavailable=guard_unavailable,
            rollout_sizes=rollout_usage.sizes if args.disk_size else None,
            include_disk_size=args.disk_size,
        )
        payload = {"inventory": rows, "plan": plan.as_dict()}
        if args.disk_size:
            payload["disk_size"] = disk_payload
        if not args.apply:
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(_format_inventory(rows))
                print()
                print(_format_plan(plan))
            return 0

        if args.expect_plan != plan.plan_id:
            message = f"plan hash mismatch: expected {args.expect_plan}, current {plan.plan_id}; deleted 0"
            if args.json:
                payload["apply"] = {"status": "rejected", "reason": message, "deleted": [], "failed": [], "not_attempted": [item.root.id for item in plan.selected]}
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(_format_plan(plan))
                print(message)
            return 2
        if not plan.apply_allowed:
            message = "plan is blocked; deleted 0: " + "; ".join(plan.blocked_reasons or plan.guard_unavailable)
            if args.json:
                payload["apply"] = {"status": "rejected", "reason": message, "deleted": [], "failed": [], "not_attempted": [item.root.id for item in plan.selected]}
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(_format_plan(plan))
                print(message)
            return 2

        deleted: list[str] = []
        failed: list[dict[str, str]] = []
        not_attempted: list[str] = []
        for index, candidate in enumerate(plan.selected):
            try:
                rpc_request(session, request_ids, "thread/delete", {"threadId": candidate.root.id})
            except PruneError as exc:
                failed.append({"id": candidate.root.id, "error": str(exc)})
                not_attempted = [item.root.id for item in plan.selected[index + 1 :]]
                break
            deleted.append(candidate.root.id)

        remaining_threads, _ = collect_inventory(session, request_ids)
        remaining_ids = {item.id for item in remaining_threads}
        residual = sorted(set(plan.affected_ids) & remaining_ids)
        status = "succeeded" if not failed and not residual else "failed"
        apply_result = {
            "status": status,
            "deleted": deleted,
            "failed": failed,
            "not_attempted": not_attempted,
            "residual_ids": residual,
        }
        if args.json:
            payload["apply"] = apply_result
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(_format_plan(plan))
            print(json.dumps({"deleted": deleted, "failed": failed, "not_attempted": not_attempted, "residual_ids": residual}, ensure_ascii=False))
        return 0 if status == "succeeded" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)
    try:
        return run(args)
    except PruneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
