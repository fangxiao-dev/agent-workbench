#!/usr/bin/env python3
"""Append-only coordination ledger for thread-harness."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


STATE_VALUES = {"working", "awaiting_seam", "awaiting_owner", "done"}
DEFAULT_STALL_LIMIT = 5
HEARTBEAT_LEAD_ROUNDS = 2
KNOWN_WORKING_STATUSES = {
    "idle",
    "notloaded",
    "not_loaded",
    "inactive",
    "running",
    "inprogress",
    "in_progress",
    "queued",
    "pending",
    "actionable",
    "actionablestatus",
    "turncompleted",
}
SEAM_STATUS_VALUES = {"assigned", "delivered"}
SESSIONS_ROOT_ENV = "THREAD_HARNESS_SESSIONS_ROOT"
BROKER_ROOT_ENV = "THREAD_HARNESS_BROKER_ROOT"
PREFLIGHT_CHILD_LIMIT = 8
PREFLIGHT_RUNTIME_FILES = ("progress.jsonl", "seams.jsonl", "decisions.jsonl", "acts.jsonl")
IDLE_STATUS_VALUES = {"idle", "inactive", "notloaded", "not_loaded"}
LEDGER_FILES = PREFLIGHT_RUNTIME_FILES
LEDGER_INTEGRITY_FAILED = 6
NON_RUNNABLE_STATES = {"awaiting_seam", "awaiting_owner", "done"}
INTEGRITY_GUARDED_COMMANDS = {
    "sync", "stall-check", "report", "seam", "decide", "act", "heartbeat", "status", "preflight"
}


PROGRESS_ROOT = Path(__file__).resolve().parents[3] / ".progress-record"
ACTIVE_REGISTRY_PATH: Path | None = None


def broker_dir() -> Path:
    """运行时根目录（只在没有 --registry 时兜底）。

    默认是本仓库的 `.progress-record/`，从脚本自身位置推导，所以不需要任何配置，
    也不含盘符或用户名。它被 .gitignore 掉——账本是运行时记录，不是源码。

    **不要放 %TEMP%**：账本是接手与复盘唯一的事实来源，放在操作系统随时可以
    清空的目录里，等于把可靠层建在最不可靠的存储上。

    真实 coordination 用 `--registry <绝对路径>` 显式指定，运行时目录跟着 registry
    所在目录走，可以放在被调度仓库的主工作区下（如
    `D:\\CodeSpace\\prj-supplyer-webapp\\.progress-record\\`）。
    coordination_id 用 `<YYMMDDHH>-<slug>`。

    THREAD_HARNESS_BROKER_ROOT 仍可覆盖默认根；测试必须用它指到临时目录——
    默认目录是生产运行时，往里写会和在跑的 harness 抢同一棵目录树。
    """
    override = os.environ.get(BROKER_ROOT_ENV)
    return Path(override) if override else PROGRESS_ROOT


class LedgerError(Exception):
    pass


class UsageError(Exception):
    pass


class LedgerIntegrityError(LedgerError):
    def __init__(self, issues: list[tuple[str, int, str]]):
        self.issues = issues
        super().__init__("ledger integrity failed")


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def to_local_iso(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat(timespec="seconds")
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return value


def parse_iso_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def ts_not_earlier(candidate, baseline) -> bool:
    candidate_dt = parse_iso_ts(candidate)
    baseline_dt = parse_iso_ts(baseline)
    if candidate_dt and baseline_dt:
        if candidate_dt.tzinfo and baseline_dt.tzinfo:
            return candidate_dt.astimezone(timezone.utc) >= baseline_dt.astimezone(timezone.utc)
        if not candidate_dt.tzinfo and not baseline_dt.tzinfo:
            return candidate_dt >= baseline_dt
        return False
    if isinstance(candidate, str) and isinstance(baseline, str):
        return candidate >= baseline
    return False


def runtime_dir(coordination_id: str) -> Path:
    return registry_path(coordination_id).parent / coordination_id


def registry_path(coordination_id: str) -> Path:
    if ACTIVE_REGISTRY_PATH is not None:
        return ACTIVE_REGISTRY_PATH
    return broker_dir() / f"{coordination_id}.json"


def jsonl_path(coordination_id: str, name: str) -> Path:
    return runtime_dir(coordination_id) / name


def ensure_runtime(coordination_id: str) -> Path:
    root = runtime_dir(coordination_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in LEDGER_FILES:
        jsonl_path(coordination_id, name).touch(exist_ok=True)
    return root


def append_jsonl(path: Path, row: dict) -> None:
    """Append one complete JSONL row and make it durable.

    Coordination serialization is provided by ``coordination_write_lock``.  This
    lower-level helper deliberately only owns the bytes/write/fsync contract so
    multi-file commands can keep all appends inside one lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o666)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise LedgerError(f"partial ledger write: {path.name}")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def coordination_write_lock(coordination_id: str):
    """Serialize all ledger mutations for one coordination across processes."""
    root = runtime_dir(coordination_id)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".ledger.write.lock"
    with lock_path.open("a+b") as lock_file:
        if lock_file.seek(0, os.SEEK_END) == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
                    lock_file.seek(0)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def scan_jsonl(path: Path) -> tuple[list[dict], list[tuple[str, int, str]]]:
    rows = []
    issues = []
    if not path.exists():
        return rows, issues
    try:
        with path.open("rb") as fh:
            for line_no, raw in enumerate(fh, 1):
                if not raw.endswith(b"\n"):
                    issues.append((path.name, line_no, "truncated_line"))
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    issues.append((path.name, line_no, "invalid_utf8"))
                    continue
                if not line:
                    issues.append((path.name, line_no, "empty_line"))
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append((path.name, line_no, "invalid_json"))
                    continue
                if not isinstance(value, dict):
                    issues.append((path.name, line_no, "row_not_object"))
                    continue
                if raw.endswith(b"\n"):
                    rows.append(value)
    except OSError as exc:
        issues.append((path.name, 0, f"unreadable:{exc.__class__.__name__}"))
    return rows, issues


def ledger_integrity_issues(coordination_id: str) -> list[tuple[str, int, str]]:
    issues = []
    for name in LEDGER_FILES:
        _, file_issues = scan_jsonl(jsonl_path(coordination_id, name))
        issues.extend(file_issues)
    return issues


def print_integrity_failure(issues: list[tuple[str, int, str]]) -> None:
    for index, (name, line_no, reason) in enumerate(issues):
        prefix = "LEDGER INTEGRITY FAILED" if index == 0 else "  also"
        location = f"{name}:{line_no}" if line_no else name
        print(f"{prefix}: {location} {reason}")


def assert_ledger_integrity(coordination_id: str) -> None:
    issues = ledger_integrity_issues(coordination_id)
    if issues:
        raise LedgerIntegrityError(issues)


def read_jsonl_with_corrupt(path: Path) -> tuple[list[dict], int]:
    rows, issues = scan_jsonl(path)
    return rows, len(issues)


def read_jsonl(path: Path) -> list[dict]:
    return read_jsonl_with_corrupt(path)[0]


def corrupt_ledger_lines(coordination_id: str) -> int:
    return len(ledger_integrity_issues(coordination_id))


def load_state(coordination_id: str) -> dict:
    path = runtime_dir(coordination_id) / "sync-state.json"
    if not path.exists():
        return {"invalid_rounds": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"invalid_rounds": 0}


def save_state(coordination_id: str, state: dict) -> None:
    path = runtime_dir(coordination_id) / "sync-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_seq(state: dict, key: str) -> int:
    seq = int(state.get(key) or 0) + 1
    state[key] = seq
    return seq


def load_registry(coordination_id: str) -> dict:
    path = registry_path(coordination_id)
    if not path.exists():
        raise LedgerError(f"registry not found: {path}")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"registry is not valid JSON: {path} ({exc})") from exc
    if not isinstance(registry, dict):
        raise LedgerError(f"registry root must be an object: {path}")
    return registry


def configure_routing(args) -> None:
    """Resolve the explicit registry path, with legacy coordination-id fallback."""
    global ACTIVE_REGISTRY_PATH

    registry_arg = getattr(args, "registry", None)
    coordination_id = getattr(args, "coordination_id", None)
    if registry_arg:
        path = Path(registry_arg).expanduser()
        if not path.is_absolute():
            raise UsageError("--registry must be an absolute JSON path")
        path = path.resolve(strict=False)
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise LedgerError(f"registry not found: {path}") from exc
        except (OSError, UnicodeError) as exc:
            raise LedgerError(f"registry unreadable: {path} ({exc})") from exc
        except json.JSONDecodeError as exc:
            raise LedgerError(f"registry is not valid JSON: {path} ({exc})") from exc
        if not isinstance(registry, dict):
            raise LedgerError(f"registry root must be an object: {path}")
        registry_coordination_id = registry.get("coordination_id")
        if not isinstance(registry_coordination_id, str) or not registry_coordination_id.strip():
            raise LedgerError(f"registry missing coordination_id: {path}")
        registry_coordination_id = registry_coordination_id.strip()
        if coordination_id and coordination_id != registry_coordination_id:
            raise UsageError(
                f"--coordination-id {coordination_id} does not match registry coordination_id "
                f"{registry_coordination_id}"
            )
        ACTIVE_REGISTRY_PATH = path
        args.coordination_id = registry_coordination_id
        return

    ACTIVE_REGISTRY_PATH = None
    if not isinstance(coordination_id, str) or not coordination_id.strip():
        raise UsageError("one of --registry or --coordination-id is required")
    args.coordination_id = coordination_id.strip()


def node_session_id(node: dict) -> str | None:
    for key in ("current_session_id", "session_id", "thread_id", "threadId"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def registry_nodes(registry: dict) -> list[dict]:
    nodes: list[dict] = []

    def add(name: str, value: dict, role: str) -> None:
        session_id = node_session_id(value)
        if session_id:
            nodes.append(
                {
                    "name": name,
                    "session_id": session_id,
                    "role": role,
                    "worktree": value.get("worktree") if isinstance(value.get("worktree"), str) else None,
                    "active": value.get("active", True) is not False,
                }
            )

    controller = registry.get("controller")
    if isinstance(controller, dict):
        add(controller.get("name") or "controller", controller, "controller")

    children = registry.get("children") or registry.get("nodes") or []
    if isinstance(children, dict):
        for name, value in children.items():
            if isinstance(value, dict):
                add(value.get("name") or str(name), value, "child")
    elif isinstance(children, list):
        for index, value in enumerate(children):
            if isinstance(value, dict):
                add(value.get("name") or value.get("node") or f"child_{index}", value, "child")

    if not nodes:
        raise LedgerError("registry has no controller/children with current_session_id")
    return nodes


def route_registry_entries(registry: dict) -> list[dict]:
    """Return raw registry node objects with stable labels for route verification."""
    entries = []
    controller = registry.get("controller")
    if isinstance(controller, dict):
        aliases = {"controller"}
        for key in ("name", "node_id", "node"):
            value = controller.get(key)
            if isinstance(value, str) and value:
                aliases.add(value)
        entries.append(
            {
                "label": "controller",
                "role": "controller",
                "name": str(controller.get("name") or "controller"),
                "aliases": aliases,
                "active": True,
                "node": controller,
                "container_key": None,
                "item_key": None,
            }
        )

    children = registry.get("children")
    children_key = "children"
    if not children:
        children = registry.get("nodes")
        children_key = "nodes"
    if isinstance(children, dict):
        child_items = children.items()
    elif isinstance(children, list):
        child_items = enumerate(children)
    else:
        child_items = []
    for key, value in child_items:
        if not isinstance(value, dict):
            continue
        aliases = {str(key)}
        for name_key in ("name", "node", "node_id"):
            name = value.get(name_key)
            if isinstance(name, str) and name:
                aliases.add(name)
        if isinstance(children, dict):
            name = value.get("name") or str(key)
        else:
            name = value.get("name") or value.get("node") or f"child_{key}"
        entries.append(
            {
                "label": f"{children_key}[{key!r}]",
                "role": "child",
                "name": str(name),
                "aliases": aliases,
                "active": value.get("active", True) is not False,
                "node": value,
                "container_key": children_key,
                "item_key": key,
            }
        )
    return entries


def session_age_text(registry: dict) -> str:
    """Format active-child session ages; malformed timestamps are measurements, not errors."""
    now = datetime.now().astimezone()
    ages = []
    for entry in route_registry_entries(registry):
        if entry["role"] != "child" or not entry["active"]:
            continue
        age = None
        try:
            timestamp = parse_iso_ts(entry["node"].get("updated_at"))
            if timestamp is not None and timestamp.tzinfo is not None:
                age = (
                    now.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)
                ).total_seconds() / 3600
        except (OverflowError, TypeError, ValueError):
            age = None
        ages.append((entry["name"], age))

    ages.sort(
        key=lambda item: (
            item[1] is None,
            -(item[1] if item[1] is not None else 0),
            item[0],
        )
    )
    return ", ".join(
        f"{name}={age:.1f}" if age is not None else f"{name}=?"
        for name, age in ages
    ) or "-"


def find_rollout(session_id: str) -> Path:
    root = Path(os.environ.get(SESSIONS_ROOT_ENV) or (Path.home() / ".codex" / "sessions"))
    if not root.exists():
        raise LedgerError(f"sessions root not found: {root}")
    matches = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".git", "__pycache__"}]
        for filename in files:
            if filename.startswith("rollout-") and filename.endswith(".jsonl") and session_id in filename:
                matches.append(Path(current_root) / filename)
    if not matches:
        raise LedgerError(
            f"rollout not found for session id {session_id} under {root}; "
            "controller may be running in ephemeral mode, which does not persist rollout"
        )
    matches.sort(key=lambda path: str(path))
    return matches[-1]


def normalized_worktree(worktree: str) -> str:
    """用于 preflight 的 Windows 路径比较：规范化、绝对化并忽略大小写。"""
    try:
        path = Path(worktree).expanduser().resolve(strict=False)
        return os.path.normcase(os.path.normpath(str(path)))
    except (OSError, RuntimeError, ValueError):
        return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(worktree))))


def preflight_git_command(worktree: str, arguments: list[str], *, text: bool = True):
    try:
        return subprocess.run(
            ["git", "-C", worktree, *arguments],
            capture_output=True,
            text=text,
            encoding="utf-8" if text else None,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def preflight_dirty_file_count(worktree: str) -> int | None:
    """只用 diff/ls-files 读取 WIP，避免 status 刷新 index。"""
    paths = set()
    for arguments in (
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ):
        result = preflight_git_command(worktree, arguments, text=False)
        if result is None or result.returncode != 0:
            return None
        for raw_path in (result.stdout or b"").split(b"\0"):
            if raw_path:
                paths.add(raw_path)
    return len(paths)


def preflight_git_info(worktree: str) -> dict:
    path = Path(worktree)
    try:
        if not path.exists():
            return {"kind": "missing"}
        if not path.is_dir():
            return {"kind": "not_git"}
    except OSError:
        return {"kind": "missing"}

    inside = preflight_git_command(worktree, ["rev-parse", "--is-inside-work-tree"])
    if inside is None or inside.returncode != 0 or (inside.stdout or "").strip().lower() != "true":
        return {"kind": "not_git"}

    head_result = preflight_git_command(worktree, ["rev-parse", "HEAD"])
    head = (head_result.stdout or "").strip() if head_result else ""
    head_ok = bool(head_result and head_result.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", head))

    branch_result = preflight_git_command(worktree, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch_result and branch_result.returncode == 0 and (branch_result.stdout or "").strip():
        actual_branch = branch_result.stdout.strip()
    elif branch_result and branch_result.returncode == 1:
        actual_branch = "<detached>"
    else:
        actual_branch = "<unknown>"

    return {
        "kind": "ok" if head_ok else "head_unavailable",
        "head": head.lower() if head_ok else None,
        "branch": actual_branch,
        "dirty_count": preflight_dirty_file_count(worktree),
    }


def preflight_registry_nodes(registry: dict, issues: list[tuple[str, str]]) -> tuple[list[dict], int]:
    nodes = []

    controller = registry.get("controller")
    if not isinstance(controller, dict):
        issues.append(
            (
                "registry_missing_controller" if "controller" not in registry else "registry_invalid_controller",
                "controller",
            )
        )
    else:
        nodes.append(
            {
                "name": str(controller.get("name") or controller.get("node_id") or "controller"),
                "role": "controller",
                "session_id": controller.get("current_session_id"),
                "worktree": controller.get("worktree"),
                "branch": controller.get("branch"),
                "active": True,
            }
        )

    children = registry.get("children")
    if "children" not in registry:
        issues.append(("registry_missing_children", "children"))
        return nodes, 0
    if isinstance(children, dict):
        child_items = list(children.items())
    elif isinstance(children, list):
        child_items = [(index, value) for index, value in enumerate(children)]
    else:
        issues.append(("registry_invalid_children", "children"))
        return nodes, 0

    active_children_count = 0
    for index, value in child_items:
        if not isinstance(value, dict):
            issues.append(("registry_invalid_child", str(index)))
            continue
        if value.get("active", True) is False:
            continue
        active_children_count += 1
        nodes.append(
            {
                "name": str(value.get("name") or value.get("node") or index),
                "role": "child",
                "session_id": value.get("current_session_id"),
                "worktree": value.get("worktree"),
                "branch": value.get("branch"),
                "active": True,
            }
        )
    return nodes, active_children_count


def preflight_field_issues(nodes: list[dict], issues: list[tuple[str, str]]) -> None:
    for node in nodes:
        name = node["name"]
        session_id = node.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            issues.append(("missing_session_id", name))
        elif session_id != session_id.strip():
            node["session_id"] = session_id.strip()

        worktree = node.get("worktree")
        if not isinstance(worktree, str) or not worktree.strip():
            issues.append(("worktree_missing", f"{name} -> <missing>"))
        elif worktree != worktree.strip():
            node["worktree"] = worktree.strip()

        branch = node.get("branch")
        if not isinstance(branch, str) or not branch.strip():
            issues.append(("branch_missing", name))
        elif branch != branch.strip():
            node["branch"] = branch.strip()


def preflight_duplicate_issues(nodes: list[dict], field_name: str, tag: str, normalizer=None) -> list[tuple[str, str]]:
    groups = {}
    displays = {}
    for node in nodes:
        value = node.get(field_name)
        if not isinstance(value, str) or not value.strip():
            continue
        key = normalizer(value) if normalizer else value
        groups.setdefault(key, []).append(node["name"])
        displays.setdefault(key, value)

    findings = []
    for key in sorted(groups, key=str):
        names = sorted(groups[key])
        if len(names) > 1:
            findings.append((tag, f"{', '.join(names)} -> {displays[key]}"))
    return findings


def cmd_preflight(args) -> int:
    issues: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    path = registry_path(args.coordination_id)
    registry = None

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(("registry_missing", str(path)))
    except (OSError, UnicodeError) as exc:
        issues.append(("registry_unreadable", f"{path} ({exc})"))
    else:
        try:
            registry = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError) as exc:
            issues.append(("registry_unparseable", f"{path} ({exc})"))
        if registry is not None and not isinstance(registry, dict):
            issues.append(("registry_unparseable", "registry root must be an object"))
            registry = None

    nodes: list[dict] = []
    children_count = 0
    if registry is not None:
        nodes, children_count = preflight_registry_nodes(registry, issues)
        if children_count > PREFLIGHT_CHILD_LIMIT:
            issues.append(("children_limit", f"children={children_count} max={PREFLIGHT_CHILD_LIMIT}"))
        preflight_field_issues(nodes, issues)
        issues.extend(preflight_duplicate_issues(nodes, "session_id", "duplicate_session_id"))
        issues.extend(preflight_duplicate_issues(nodes, "branch", "duplicate_branch"))
        issues.extend(
            preflight_duplicate_issues(nodes, "worktree", "shared_worktree", normalized_worktree)
        )

        for node in nodes:
            worktree = node.get("worktree")
            if not isinstance(worktree, str) or not worktree.strip():
                continue
            info = preflight_git_info(worktree)
            if info["kind"] == "missing":
                issues.append(("worktree_missing", f"{node['name']} -> {worktree}"))
                continue
            if info["kind"] == "not_git":
                issues.append(("not_git_repository", f"{node['name']} -> {worktree}"))
                continue
            if info["kind"] == "head_unavailable":
                issues.append(("head_unavailable", f"{node['name']} -> {worktree}"))

            registry_branch = node.get("branch")
            if isinstance(registry_branch, str) and registry_branch.strip():
                if info.get("branch") != registry_branch:
                    issues.append(
                        (
                            "branch_mismatch",
                            f"{node['name']} registry={registry_branch} actual={info.get('branch') or '<unknown>'}",
                        )
                    )

            dirty_count = info.get("dirty_count")
            if isinstance(dirty_count, int) and dirty_count:
                warnings.append(("dirty_worktree", f"{node['name']} ({dirty_count} files)"))

        for node in nodes:
            session_id = node.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                continue
            try:
                find_rollout(session_id)
            except (LedgerError, OSError):
                if node["role"] == "controller":
                    issues.append(("controller_rollout_missing", session_id))
                else:
                    warnings.append(("child_rollout_missing", node["name"]))

    runtime_missing = []
    for name in PREFLIGHT_RUNTIME_FILES:
        runtime_path = jsonl_path(args.coordination_id, name)
        try:
            present = runtime_path.is_file()
        except OSError:
            present = False
        if not present:
            runtime_missing.append(name)
    if runtime_missing:
        issues.append(("runtime_uninitialized", f"missing={', '.join(runtime_missing)}; run init first"))

    if issues:
        print("PREFLIGHT FAILED")
        for tag, detail in issues:
            print(f"  {tag:<24} {detail}")
    else:
        print(f"PREFLIGHT OK  nodes={len(nodes)} children={children_count}")
    if warnings:
        print("warnings:")
        for tag, detail in sorted(warnings, key=lambda item: (item[0], item[1])):
            print(f"  {tag:<24} {detail}")
    return 5 if issues else 0


def response_item(obj: dict) -> dict | None:
    if obj.get("type") == "response_item":
        item = obj.get("payload") or obj.get("item") or obj.get("response_item")
        return item if isinstance(item, dict) else None
    if obj.get("type") in {"custom_tool_call", "custom_tool_call_output"}:
        return obj
    payload = obj.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"custom_tool_call", "custom_tool_call_output"}:
        return payload
    return None


def payload_of(item: dict) -> dict:
    payload = item.get("payload")
    return payload if isinstance(payload, dict) else item


def stringify(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def tool_call_source_text(payload: dict, item: dict) -> str:
    """Read only the real shell command from legacy or modern tool payloads."""
    def command_text(value) -> str:
        if isinstance(value, dict):
            command = value.get("command")
            return command if isinstance(command, str) else ""
        if not isinstance(value, str):
            return stringify(value)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, dict):
            command = parsed.get("command")
            return command if isinstance(command, str) else ""
        return parsed if isinstance(parsed, str) else value

    for container in (payload, item):
        if not isinstance(container, dict):
            continue
        for key in ("arguments", "input"):
            if key not in container:
                continue
            return command_text(container.get(key))
    return ""


def is_shell_exec_call(payload: dict, item: dict) -> bool:
    return (payload.get("name") or item.get("name")) == "exec"


def read_rollout_events(path: Path, offset: int) -> tuple[list[dict], int, int]:
    events = []
    scanned = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        while True:
            raw = fh.readline()
            if not raw:
                break
            scanned += 1
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events, fh.tell(), scanned


def latest_wait_round(events: list[dict]) -> tuple[dict | None, dict | None]:
    calls: dict[str, dict] = {}
    outputs: dict[str, dict] = {}
    order: list[str] = []
    for obj in events:
        item = response_item(obj)
        if not item:
            continue
        payload = payload_of(item)
        item_type = item.get("type") or payload.get("type")
        call_id = item.get("call_id") or payload.get("call_id") or item.get("id") or payload.get("id")
        if not call_id:
            continue
        if item_type == "custom_tool_call":
            if not is_shell_exec_call(payload, item):
                continue
            text = tool_call_source_text(payload, item)
            if "codex_app__wait_threads" in text:
                calls[call_id] = {"call_id": call_id, "arguments": text}
                order.append(call_id)
        elif item_type == "custom_tool_call_output":
            outputs[call_id] = {"call_id": call_id, "output": payload.get("output", item.get("output"))}
    for call_id in reversed(order):
        if call_id in outputs:
            return calls[call_id], outputs[call_id]
    return (calls[order[-1]], None) if order else (None, None)


def count_dispatch_calls(events: list[dict]) -> int:
    count = 0
    needles = ("tools.codex_app__send_message_to_thread", "tools.codex_app__create_thread")
    outputs = set()
    calls = []
    for obj in events:
        item = response_item(obj)
        if not item:
            continue
        payload = payload_of(item)
        item_type = item.get("type") or payload.get("type")
        call_id = item.get("call_id") or payload.get("call_id") or item.get("id") or payload.get("id")
        if not call_id:
            continue
        if item_type == "custom_tool_call":
            if not is_shell_exec_call(payload, item):
                continue
            text = tool_call_source_text(payload, item)
            if any(needle in text for needle in needles):
                calls.append(call_id)
        elif item_type == "custom_tool_call_output":
            outputs.add(call_id)
    for call_id in calls:
        if call_id in outputs:
            count += 1
    return count


def text_candidates(output_value) -> list[str]:
    candidates = []
    if isinstance(output_value, list):
        for item in output_value:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                candidates.append(item["text"])
            elif isinstance(item, str):
                candidates.append(item)
    elif isinstance(output_value, str):
        candidates.append(output_value)
    return candidates


def extract_projection(output_value):
    for text in text_candidates(output_value):
        try:
            value = json.loads(text.strip())
            if isinstance(value, dict) and value.get("v") == 1:
                return value
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
                if isinstance(value, dict) and value.get("v") == 1:
                    return value
            except json.JSONDecodeError:
                continue
    return None


def parse_ids_array(arguments: str) -> list[str] | None:
    match = re.search(r"\bconst\s+ids\s*=\s*(\[[\s\S]*?\])\s*;", arguments)
    if not match:
        return None
    try:
        value = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value


def validate_call(arguments: str, expected_session_ids: list[str]) -> tuple[str | None, list[str]]:
    timeout_match = re.search(r'"?timeoutMs"?\s*[:=]\s*(\d+)', arguments)
    if not timeout_match:
        return "timeoutMs missing (expected 120000)", []
    timeout_ms = int(timeout_match.group(1))
    if timeout_ms != 120000:
        return f"timeoutMs {timeout_ms} != 120000", []

    actual_ids = parse_ids_array(arguments)
    if actual_ids is None:
        return "cannot parse ids array from call", []
    actual = set(actual_ids)
    expected = set(expected_session_ids)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        return f"targets mismatch (missing={missing}, unexpected={unexpected})", actual_ids
    if len(actual_ids) != len(actual):
        duplicates = sorted({item for item in actual_ids if actual_ids.count(item) > 1})
        return f"targets mismatch (missing=[], unexpected=duplicate:{duplicates})", actual_ids
    return None, actual_ids


def validate_projection(payload: dict | None, actual_targets: int, expected_poll_ids: set[str]) -> str | None:
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return "projection missing or wrong version"
    for key in ("n", "polls", "timedOut"):
        if key not in payload:
            return f"projection shape altered (missing {key})"
    n = payload.get("n")
    if n != actual_targets:
        return f"projection n={n} != actual targets {actual_targets}"
    polls = payload.get("polls")
    if not isinstance(polls, list):
        return "poll entry shape altered"
    seen_ids = set()
    for poll in polls:
        if not isinstance(poll, dict) or any(key not in poll for key in ("id", "status", "turn", "turnStatus", "txt")):
            return "poll entry shape altered"
        poll_id = poll.get("id")
        if poll_id not in expected_poll_ids:
            return f"poll id not in registry ({poll_id})"
        if poll_id in seen_ids:
            return f"duplicate poll id ({poll_id})"
        seen_ids.add(poll_id)
    return None


def field(obj: dict, *names):
    for name in names:
        if name in obj:
            return obj[name]
    return None


def extract_head(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("head", "id", "turn_id", "turnId", "message_id", "messageId"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return None


def normalize_state(raw, waiting_on=None) -> str:
    text = str(raw or "").lower()
    if text in STATE_VALUES:
        return text
    if text in {"completed", "complete", "closed"}:
        return "done"
    if "owner" in text:
        return "awaiting_owner"
    if "seam" in text or waiting_on:
        return "awaiting_seam"
    if text in KNOWN_WORKING_STATUSES:
        return "working"
    return "unknown"


def git_head(worktree: str | None) -> str | None:
    if not worktree:
        return None
    path = Path(worktree)
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = (result.stdout or "").strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", head):
        return None
    return head.lower()


def git_is_ancestor(worktree: str | None, ancestor: str, descendant: str) -> bool:
    if not worktree or not ancestor or not descendant:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(worktree)), "merge-base", "--is-ancestor", ancestor, descendant],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def git_commit_paths(worktree: str | None, head: str | None, old_head: str | None = None) -> list[str] | None:
    if not worktree or not head:
        return None
    if old_head:
        try:
            result = subprocess.run(
                ["git", "-C", str(Path(worktree)), "merge-base", "--is-ancestor", old_head, head],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        command = ["git", "-C", str(Path(worktree)), "log", "--name-only", "--pretty=format:", f"{old_head}..{head}"]
    else:
        command = ["git", "-C", str(Path(worktree)), "show", "--name-only", "--pretty=format:", head]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [line.strip().replace("\\", "/") for line in (result.stdout or "").splitlines() if line.strip()]


def advance_kind(worktree: str | None, head: str | None, old_head: str | None = None) -> str:
    paths = git_commit_paths(worktree, head, old_head)
    if paths is None or not paths:
        return "unknown"
    for path in paths:
        if not (path.endswith(".md") or path.startswith("docs/")):
            return "code"
    return "docs"


def wake_thread_ids(wake: dict) -> set[str]:
    ids = set()
    for key in ("threadId", "thread_id", "target", "session_id", "sessionId"):
        value = wake.get(key)
        if isinstance(value, str):
            ids.add(value)
    for key in ("targets", "threadIds", "thread_ids"):
        value = wake.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    ids.add(item)
                elif isinstance(item, dict):
                    tid = field(item, "threadId", "thread_id", "session_id", "sessionId")
                    if isinstance(tid, str):
                        ids.add(tid)
    return ids


def classify_and_rows(payload: dict, nodes: list[dict], round_no: int, seq: int, previous: dict) -> tuple[list[dict], dict]:
    ts = now_local()
    by_session = {node["session_id"]: node for node in nodes}
    by_name = {node["name"]: node for node in nodes}
    rows_by_name = {}
    polls = payload.get("polls") if isinstance(payload.get("polls"), list) else []
    heads = {node["name"]: git_head(node.get("worktree")) for node in nodes}

    for poll in polls:
        if not isinstance(poll, dict):
            continue
        session_id = field(poll, "id")
        name = field(poll, "node", "name")
        node = by_session.get(session_id) or by_name.get(name)
        if not node:
            continue
        status = field(poll, "status")
        note = field(poll, "txt")
        rows_by_name[node["name"]] = {
            "ts": ts,
            "src": "poll",
            "seq": seq,
            "round": round_no,
            "node": node["name"],
            "head": heads.get(node["name"]),
            "turn": field(poll, "turn"),
            "status": status,
            "turn_status": field(poll, "turnStatus"),
            "state": normalize_state(status),
            "note": str(note or status or "")[:500],
        }

    for node in nodes:
        if node["name"] not in rows_by_name:
            prev = previous.get(node["name"], {})
            rows_by_name[node["name"]] = {
                "ts": ts,
                "src": "poll",
                "seq": seq,
                "round": round_no,
                "node": node["name"],
                "head": heads.get(node["name"]),
                "turn": prev.get("turn"),
                "status": prev.get("status"),
                "turn_status": prev.get("turn_status"),
                "state": prev.get("state") if prev.get("state") in STATE_VALUES else "working",
                "note": "no poll payload for node",
            }

    wake = payload.get("wake") if isinstance(payload.get("wake"), dict) else {}
    wake_reason = wake.get("reason")

    def latest_state(name: str) -> str:
        previous_state = previous.get(name, {}).get("state")
        if previous_state in STATE_VALUES:
            return previous_state
        return rows_by_name[name].get("state") or "unknown"

    def may_be_idle(name: str) -> bool:
        return latest_state(name) == "working"

    idle_sessions = wake_thread_ids(wake) if wake_reason == "inactiveStatus" else set()
    idle_nodes = {
        by_session[sid]["name"]
        for sid in idle_sessions
        if sid in by_session and by_session[sid].get("active", True) and may_be_idle(by_session[sid]["name"])
    }
    # Desktop may expose an idle thread through polls[].status even when wake.reason
    # is turnCompleted or absent.  Treat status as the primary per-node signal and
    # inactiveStatus only as an additional wake hint.
    for poll in polls:
        if not isinstance(poll, dict):
            continue
        status_text = str(field(poll, "status") or "").lower().replace("-", "_")
        session_id = field(poll, "id")
        node = by_session.get(session_id)
        if node and status_text in IDLE_STATUS_VALUES and node.get("active", True) and may_be_idle(node["name"]):
            idle_nodes.add(node["name"])

    changed_nodes = []
    advance_kinds = {}
    unchanged = []
    head_changed = False
    for node in nodes:
        name = node["name"]
        row = rows_by_name[name]
        old_head = previous.get(name, {}).get("head")
        new_head = row.get("head")
        if new_head and old_head and new_head != old_head:
            head_changed = True
            advance_kinds[name] = advance_kind(node.get("worktree"), new_head, old_head)
            changed_nodes.append((name, new_head, old_head))
        elif new_head and not old_head:
            head_changed = True
            advance_kinds[name] = advance_kind(node.get("worktree"), new_head)
            changed_nodes.append((name, new_head, None))
        else:
            if name in idle_nodes:
                continue
            unchanged.append(name)

    return list(rows_by_name.values()), {
        "wake_reason": wake_reason,
        "idle_nodes": sorted(idle_nodes),
        "changed_nodes": changed_nodes,
        "advance_kinds": advance_kinds,
        "unchanged": unchanged,
        "head_changed": head_changed,
        "head_unavailable": sorted(name for name, head in heads.items() if head is None),
        "unknown_status": sorted(
            row["node"] for row in rows_by_name.values()
            if row.get("state") == "unknown" and row.get("note") != "no poll payload for node"
        ),
        "timed_out": bool(payload.get("timedOut")),
        "timed_out_no_change": bool(payload.get("timedOut")) and not polls,
    }


def latest_progress_parts(coordination_id: str) -> tuple[dict, dict]:
    latest_poll = {}
    latest_report = {}
    for row in read_jsonl(jsonl_path(coordination_id, "progress.jsonl")):
        node = row.get("node")
        if not node:
            continue
        if row.get("src") == "report":
            latest_report[node] = row
        elif row.get("src") == "poll":
            latest_poll[node] = row
        else:
            latest_report[node] = row
    return latest_poll, latest_report


def stale_report_nodes(coordination_id: str) -> set[str]:
    latest_report_index = {}
    rows = read_jsonl(jsonl_path(coordination_id, "progress.jsonl"))
    for index, row in enumerate(rows):
        if row.get("src") == "report" and row.get("node"):
            latest_report_index[row["node"]] = (index, row)

    stale = set()
    for node, (report_index, report) in latest_report_index.items():
        report_head = report.get("head")
        for row in rows[report_index + 1:]:
            if row.get("src") != "poll" or row.get("node") != node:
                continue
            poll_head = row.get("head")
            if poll_head and (not report_head or poll_head != report_head):
                stale.add(node)
                break
    return stale


def latest_progress(coordination_id: str) -> dict:
    latest_poll, latest_report = latest_progress_parts(coordination_id)
    stale_nodes = stale_report_nodes(coordination_id)
    names = set(latest_poll) | set(latest_report)
    latest = {}
    for name in names:
        poll = latest_poll.get(name, {})
        report = latest_report.get(name, {})
        row = dict(poll or report)
        if report:
            row["state"] = report.get("state")
            if name in stale_nodes:
                row["state"] = f"{row['state']}(stale)"
            row["waiting_on"] = report.get("waiting_on") if isinstance(report.get("waiting_on"), list) else []
            row["last_report_ts"] = report.get("last_report_ts") or report.get("ts")
        else:
            row["state"] = poll.get("state") if poll.get("state") in STATE_VALUES else "working"
            row["waiting_on"] = []
            row["last_report_ts"] = None
        if poll:
            row["head"] = poll.get("head")
            row["turn"] = poll.get("turn")
            row["status"] = poll.get("status")
            row["turn_status"] = poll.get("turn_status")
        latest[name] = row
    return latest


def runnable_watch_nodes(coordination_id: str, active_children: list[dict]) -> list[dict]:
    """Return the active children that still need a blocking wait.

    A report-backed seam/owner wait or completed node is already waiting on an
    explicit controller/Owner action.  It must remain in HEAD collection and
    progress projection, but it must not keep waking a fixed blocking wait.
    A dispatch recorded after the report makes that producer runnable again.
    """
    latest = latest_progress(coordination_id)
    _, latest_report = latest_progress_parts(coordination_id)
    stale_nodes = stale_report_nodes(coordination_id)
    dispatched_nodes = set()
    for act in read_jsonl(jsonl_path(coordination_id, "acts.jsonl")):
        producer = act.get("producer")
        if act.get("kind") != "dispatch" or not producer:
            continue
        report = latest_report.get(producer)
        if not report or ts_not_earlier(act.get("ts"), report.get("ts")):
            dispatched_nodes.add(producer)
    runnable = []
    for node in active_children:
        name = node["name"]
        state = latest.get(name, {}).get("state")
        if (
            name not in latest_report
            or name in stale_nodes
            or name in dispatched_nodes
            or state not in NON_RUNNABLE_STATES
        ):
            runnable.append(node)
    return runnable


def pending_decisions(coordination_id: str) -> list[dict]:
    status_by_id = {}
    for row in read_jsonl(jsonl_path(coordination_id, "decisions.jsonl")):
        decision_id = row.get("decision_id")
        if decision_id:
            status_by_id[decision_id] = row
    return [row for row in status_by_id.values() if row.get("status") == "pending"]


def decision_ids(rows: list[dict]) -> list[str]:
    return [row.get("decision_id") for row in rows if row.get("decision_id")]


def format_id_list(ids: list) -> str:
    return ", ".join(str(item) for item in ids if item) or "-"


def pending_escalation_groups(coordination_id: str) -> tuple[list[dict], list[dict]]:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    unreported = []
    already_escalated = []
    for decision in pending_decisions(coordination_id):
        decision_id = decision.get("decision_id")
        decision_instance_id = decision.get("decision_instance_id")
        if isinstance(decision_instance_id, str) and decision_instance_id:
            escalated = any(
                row.get("kind") == "escalate"
                and row.get("decision_id") == decision_id
                and row.get("decision_instance_id") == decision_instance_id
                for row in acts
            )
        else:
            # Legacy rows have no instance id.  Keep the old timestamp fallback
            # only for legacy raise/escalate rows; a newer instance must not
            # accidentally mask a legacy pending record.
            raise_ts = decision.get("ts")
            escalated = any(
                row.get("kind") == "escalate"
                and row.get("decision_id") == decision_id
                and not row.get("decision_instance_id")
                and ts_not_earlier(row.get("ts"), raise_ts)
                for row in acts
            )
        if escalated:
            already_escalated.append(decision)
        else:
            unreported.append(decision)
    return unreported, already_escalated


def latest_act(coordination_id: str) -> dict | None:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    return acts[-1] if acts else None


def halted_act(coordination_id: str) -> dict | None:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    halt = next((row for row in reversed(acts) if row.get("kind") == "halt"), None)
    if not halt:
        return None
    halt_poll_seq = halt.get("halt_poll_seq")
    if not isinstance(halt_poll_seq, int):
        # 旧 halt 行没有 poll 序号。**不要拿 act seq 去比 poll seq**——它们是两个
        # 独立计数器（实测一次真实运行里 poll 已到 135 而 act 才 38），比较的结果
        # 是任何旧 halt 行都立刻失效。退回旧语义：只有当它仍是最后一条 act 时才
        # 算 halted，由后续 act 显式解除。
        return halt if acts and acts[-1] is halt else None
    current_poll_seq = int(load_state(coordination_id).get("next_poll_seq") or 0)
    if current_poll_seq > halt_poll_seq:
        return None
    return halt


def last_must_act_answered(coordination_id: str) -> bool:
    state = load_state(coordination_id)
    last_seq = state.get("last_must_act_seq")
    if not isinstance(last_seq, int):
        return False
    for row in read_jsonl(jsonl_path(coordination_id, "acts.jsonl")):
        seq = row.get("seq")
        if isinstance(seq, int) and seq > last_seq:
            return True
    return False


def seam_producers(coordination_id: str) -> dict:
    producers = {}
    for row in read_jsonl(jsonl_path(coordination_id, "seams.jsonl")):
        seam_id = row.get("seam_id")
        producer = row.get("producer")
        if seam_id and producer:
            producers[seam_id] = producer
    return producers


def latest_by_round(coordination_id: str) -> list[tuple[int, dict]]:
    rounds = {}
    for row in read_jsonl(jsonl_path(coordination_id, "progress.jsonl")):
        if row.get("src") != "poll":
            continue
        round_no = row.get("seq")
        node = row.get("node")
        if isinstance(round_no, int) and node:
            rounds.setdefault(round_no, {})[node] = row.get("head")
    return sorted(rounds.items(), key=lambda item: item[0])


def stall_streak(coordination_id: str) -> int:
    """连续多少轮没有任何 node 的 git HEAD 推进。

    head 取不到（worktree 缺失/不是 git 仓库）时**沿用该 node 上次已知值**，
    即"无证据表明有推进"，而不是重置计数。

    这里必须 fail-closed：曾经的实现是"任一 head 为 None 就把 streak 清零"，
    后果是一条线的 worktree 路径写错就永久关掉整组的停滞检测，而且完全无声——
    正是本 harness 要消灭的那种失效。误报一次 MUST_ACT 的代价远低于永不报警。
    取不到这件事本身由摘要的 head_unavailable 单独暴露。
    """
    rounds = latest_by_round(coordination_id)
    reset_seq = load_state(coordination_id).get("stall_reset_seq")
    if isinstance(reset_seq, int):
        rounds = [(seq, heads) for seq, heads in rounds if seq >= reset_seq]
    streak = 0
    previous = None
    carried: dict = {}
    for _, heads in rounds:
        effective = {}
        for node, head in heads.items():
            if head is None:
                effective[node] = carried.get(node)
            else:
                effective[node] = head
                carried[node] = head
        if previous is not None and effective == previous:
            streak += 1
        else:
            streak = 0
        previous = effective
    return streak


def seams_waiting_counts(coordination_id: str) -> tuple[int, int, int]:
    producers = seam_producers(coordination_id)
    latest = latest_progress(coordination_id)
    missing = set()
    malformed = 0
    stale_waiting_on = 0
    for row in latest.values():
        waiting_on = row.get("waiting_on")
        state = row.get("state")
        if state != "awaiting_seam":
            if state == "awaiting_seam(stale)" and isinstance(waiting_on, list):
                stale_waiting_on += len(waiting_on)
            elif state == "awaiting_seam(stale)" and waiting_on:
                stale_waiting_on += 1
            continue
        if not isinstance(waiting_on, list):
            if waiting_on:
                malformed += 1
            continue
        for item in waiting_on:
            if isinstance(item, str) and item.startswith("seam:"):
                seam_id = item.split(":", 1)[1]
                if seam_id and seam_id not in producers:
                    missing.add(seam_id)
                elif not seam_id:
                    malformed += 1
            elif item:
                malformed += 1
            else:
                malformed += 1
    return len(missing), malformed, stale_waiting_on


def seams_unowned_count(coordination_id: str) -> int:
    return seams_waiting_counts(coordination_id)[0]


def rollout_stats(path: Path) -> tuple[str, int | None, str | None]:
    absolute = str(path.resolve())
    try:
        stat = path.stat()
    except OSError:
        return absolute, None, None
    return absolute, stat.st_size, to_local_iso(stat.st_mtime)


def format_sync_stale(path: Path, scanned_lines: int) -> str:
    absolute, size, mtime = rollout_stats(path)
    return (
        "SYNC STALE: rollout not flushed "
        f"(path={absolute}, bytes={size}, mtime={mtime}, scanned_lines={scanned_lines})"
    )


def format_summary(
    round_no: int,
    valid: bool,
    offset: int,
    classification: dict,
    coordination_id: str,
    streak_limit: int,
    registry: dict | None = None,
) -> str:
    changed = classification["changed_nodes"]
    pending = pending_decisions(coordination_id)
    unowned, malformed, stale_waiting_on = seams_waiting_counts(coordination_id)
    state = load_state(coordination_id)
    changed_text = ", ".join(
        f"{name}({new} <- {old})" if old else f"{name}({new} <- none)"
        for name, new, old in changed
    ) or "-"
    pending_text = f"{len(pending)}"
    if pending:
        first = pending[0]
        pending_text += f"  ({first.get('decision_id')}, raised_by={first.get('raised_by')}, blocks={len(first.get('blocks') or [])})"
    return "\n".join(
        [
            f"ROUND {round_no}  valid={'yes' if valid else 'no'}  offset={offset}",
            f"poll_targets:    {', '.join(classification.get('watch_nodes') or []) or '-'}",
            f"idle_nodes:      {', '.join(classification['idle_nodes']) or '-'}",
            f"changed_nodes:   {changed_text}",
            f"advance_kinds:   {', '.join(f'{name}={kind}' for name, kind in sorted((classification.get('advance_kinds') or {}).items())) or '-'}",
            f"unchanged:       {', '.join(classification['unchanged']) or '-'}",
            f"session_age_h:   {session_age_text(registry or {})}",
            f"timedOut:        {str(bool(classification.get('timed_out'))).lower()}"
            + (" (timeout, no change)" if classification.get("timed_out_no_change") else ""),
            f"head_unavailable: {', '.join(classification.get('head_unavailable') or []) or '-'}",
            f"never_reported:  {', '.join(classification.get('never_reported') or []) or '-'}",
            f"stale_reports:   {', '.join(sorted(stale_report_nodes(coordination_id))) or '-'}",
            f"unknown_status:  {', '.join(classification.get('unknown_status') or []) or '-'}",
            f"pending_decisions: {pending_text}",
            f"stall_streak:    {stall_streak(coordination_id)}/{streak_limit}",
            f"seams_unowned:   {unowned}",
            f"stale_waiting_on: {stale_waiting_on}",
            f"malformed_waiting_on: {malformed}",
            f"dispatches_since_progress: {state.get('dispatches_since_progress', 0)}",
            f"docs_only_advances: {state.get('docs_only_advances', 0)}",
            f"corrupt_ledger_lines: {corrupt_ledger_lines(coordination_id)}",
        ]
    )


def cmd_init(args) -> int:
    ensure_runtime(args.coordination_id)
    print(f"initialized {runtime_dir(args.coordination_id)}")
    return 0


def cmd_sync(args) -> int:
    ensure_runtime(args.coordination_id)
    registry = load_registry(args.coordination_id)
    nodes = registry_nodes(registry)
    controller = next((node for node in nodes if node["role"] == "controller"), nodes[0])
    rollout = find_rollout(controller["session_id"])
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        state = load_state(args.coordination_id)
        if state.get("rollout_path") != str(rollout):
            state["rollout_path"] = str(rollout)
            state["offset"] = 0
        offset = int(state.get("offset") or 0)

        call = output = None
        events = []
        new_offset = offset
        scanned_lines = 0
        for attempt in range(20):
            rollout.stat()
            events, new_offset, scanned_lines = read_rollout_events(rollout, offset)
            call, output = latest_wait_round(events)
            if call and output:
                break
            if attempt < 19:
                time.sleep(0.1)

        if not call or not output:
            print(format_sync_stale(rollout, scanned_lines))
            return 1

        dispatches = count_dispatch_calls(events)
        state["dispatches_since_progress"] = int(state.get("dispatches_since_progress") or 0) + dispatches

        # HEAD 采集覆盖全部 active children；阻塞 wait 只覆盖 runnable watch-set。
        active_children = [
            node for node in nodes
            if node["role"] != "controller" and node.get("active", True)
        ]
        poll_targets = runnable_watch_nodes(args.coordination_id, active_children)
        reason, actual_ids = validate_call(call["arguments"], [node["session_id"] for node in poll_targets])
        if reason:
            state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
            state["offset"] = new_offset
            save_state(args.coordination_id, state)
            print(f"ROUND INVALID: poll snippet altered ({reason})")
            return 1

        payload = extract_projection(output["output"])
        expected_poll_ids = {node["session_id"] for node in poll_targets}
        reason = validate_projection(payload, len(actual_ids), expected_poll_ids)
        if reason:
            state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
            state["offset"] = new_offset
            save_state(args.coordination_id, state)
            if reason.startswith("poll id not in registry"):
                print(f"ROUND INVALID: {reason}")
            elif reason.startswith("duplicate poll id"):
                print(f"ROUND INVALID: {reason}")
            else:
                print(f"ROUND INVALID: poll snippet altered ({reason})")
            return 1

        latest_poll, latest_report = latest_progress_parts(args.coordination_id)
        poll_seq = next_seq(state, "next_poll_seq")
        rows, classification = classify_and_rows(
            payload, active_children, args.round, poll_seq, latest_progress(args.coordination_id)
        )
        classification["watch_nodes"] = [node["name"] for node in poll_targets]
        classification["never_reported"] = sorted(
            node["name"] for node in active_children if node["name"] not in latest_report
        )
        for row in rows:
            append_jsonl(jsonl_path(args.coordination_id, "progress.jsonl"), row)
        if classification["head_changed"]:
            kinds = classification.get("advance_kinds") or {}
            has_code = any(kind != "docs" for kind in kinds.values())
            docs_count = sum(1 for kind in kinds.values() if kind == "docs")
            if has_code:
                state["dispatches_since_progress"] = 0
                state["docs_only_advances"] = 0
            elif docs_count:
                state["docs_only_advances"] = int(state.get("docs_only_advances") or 0) + docs_count
        state["offset"] = new_offset
        save_state(args.coordination_id, state)
        print(
            format_summary(
                args.round,
                True,
                new_offset,
                classification,
                args.coordination_id,
                args.streak,
                registry,
            )
        )
        return 0


def registry_node_by_name(registry: dict, node_name: str) -> dict | None:
    return next((node for node in registry_nodes(registry) if node["name"] == node_name), None)


def route_entry_by_name(registry: dict, node_name: str) -> dict:
    matches = [entry for entry in route_registry_entries(registry) if node_name in entry["aliases"]]
    if not matches:
        raise UsageError(f"unknown node: {node_name}")
    if len(matches) > 1:
        labels = ", ".join(entry["label"] for entry in matches)
        raise UsageError(f"ambiguous node {node_name}: {labels}")
    return matches[0]


def route_masked_serialization(registry: dict, target: dict) -> str:
    masked = deepcopy(registry)
    container_key = target["container_key"]
    if container_key is None:
        masked["controller"] = None
    else:
        masked[container_key][target["item_key"]] = None
    return json.dumps(masked, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def route_entry_by_label(registry: dict, label: str) -> dict | None:
    return next((entry for entry in route_registry_entries(registry) if entry["label"] == label), None)


def route_registry_bytes(registry: dict, original_bytes: bytes) -> bytes:
    original_text = original_bytes.decode("utf-8")
    stripped = original_text.strip()
    if "\n" not in stripped and "\r" not in stripped:
        rendered = json.dumps(registry, ensure_ascii=False, separators=(",", ":"))
    else:
        indent = "  "
        for line in original_text.splitlines()[1:]:
            if line.strip():
                leading = line[: len(line) - len(line.lstrip())]
                if leading:
                    indent = leading
                break
        rendered = json.dumps(registry, ensure_ascii=False, indent=indent)
    if original_text.endswith("\r\n"):
        rendered += "\r\n"
    elif original_text.endswith("\n"):
        rendered += "\n"
    return rendered.encode("utf-8")


def replace_file_bytes(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            temporary = Path(fh.name)
            fh.write(data)
        os.replace(str(temporary), str(path))
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def cmd_route(args) -> int:
    path = registry_path(args.coordination_id)
    try:
        original_bytes = path.read_bytes()
        registry = json.loads(original_bytes.decode("utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"registry not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise LedgerError(f"registry unreadable: {path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"registry is not valid JSON: {path} ({exc})") from exc
    if not isinstance(registry, dict):
        raise LedgerError(f"registry root must be an object: {path}")

    target = route_entry_by_name(registry, args.node)
    node = target["node"]
    old_session = node.get("current_session_id")
    if not isinstance(old_session, str) or not old_session:
        raise UsageError(f"node {args.node} has no current_session_id")
    if args.expect_current is not None and args.expect_current != old_session:
        raise UsageError(
            f"current session mismatch for {args.node}: "
            f"registry={old_session} expected={args.expect_current}"
        )
    new_session = args.new_session
    if not new_session.strip():
        raise UsageError("--new-session must be non-empty")
    if any(entry["node"].get("current_session_id") == new_session for entry in route_registry_entries(registry)):
        raise UsageError(f"new session is already current: {new_session}")

    previous = node.get("previous_session_ids")
    if previous is None:
        previous = []
    if not isinstance(previous, list):
        raise UsageError(f"node {args.node} previous_session_ids must be a list")

    masked_before = route_masked_serialization(registry, target)
    if old_session not in previous:
        previous.append(old_session)
    node["previous_session_ids"] = previous
    node["current_session_id"] = new_session
    node["updated_at"] = now_local()

    try:
        replace_file_bytes(path, route_registry_bytes(registry, original_bytes))
        reread_bytes = path.read_bytes()
        reread = json.loads(reread_bytes.decode("utf-8"))
        if not isinstance(reread, dict):
            raise ValueError("registry root is no longer an object")
        reread_target = route_entry_by_label(reread, target["label"])
        if not reread_target or reread_target["node"].get("current_session_id") != new_session:
            raise ValueError("target current_session_id verification failed")
        if route_masked_serialization(reread, reread_target) != masked_before:
            raise ValueError("non-target registry content changed")
    except Exception as exc:
        try:
            replace_file_bytes(path, original_bytes)
        except OSError as restore_exc:
            raise LedgerError(
                f"route verification failed: {exc}; registry restore failed: {restore_exc}"
            ) from exc
        raise LedgerError(f"route verification failed: {exc}") from exc

    print(f"ROUTED {args.node} {old_session} -> {new_session}")
    return 0


def validate_report_source(coordination_id: str, node_name: str, source_session: str, head: str, registry: dict) -> dict:
    node = registry_node_by_name(registry, node_name)
    if not node:
        raise UsageError(f"unknown node: {node_name}")
    if node["role"] == "controller":
        raise UsageError("H1 source must be a child node")
    if not node.get("active", True):
        raise UsageError(f"inactive node cannot submit H1: {node_name}")
    if source_session != node["session_id"]:
        raise UsageError(
            f"H1 source session mismatch for {node_name}: "
            f"registry={node['session_id']} source={source_session}"
        )
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head or ""):
        raise UsageError("H1 head must be a full 40-character git SHA")

    baseline = latest_progress(coordination_id).get(node_name, {}).get("head")
    if baseline and baseline != head and not git_is_ancestor(node.get("worktree"), baseline, head):
        raise UsageError(
            f"H1 head is not a descendant of latest ledger HEAD for {node_name}: "
            f"baseline={baseline} source={head}"
        )
    current_head = git_head(node.get("worktree"))
    if not current_head:
        raise UsageError(f"H1 worktree HEAD unavailable for {node_name}")
    if current_head != head and not git_is_ancestor(node.get("worktree"), head, current_head):
        raise UsageError(
            f"H1 head is not on current worktree history for {node_name}: "
            f"source={head} worktree={current_head}"
        )
    return node


def cmd_report(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        if args.state not in STATE_VALUES:
            raise UsageError(f"invalid state {args.state}; expected one of {', '.join(sorted(STATE_VALUES))}")
        waiting_on = args.waiting_on or []
        if args.state == "awaiting_seam":
            valid_seams = [
                item for item in waiting_on
                if isinstance(item, str) and item.startswith("seam:") and item.split(":", 1)[1]
            ]
            if not valid_seams:
                raise UsageError("state awaiting_seam requires --waiting-on seam:<id>")

        registry = load_registry(args.coordination_id)
        node = registry_node_by_name(registry, args.node)
        if not node:
            raise UsageError(f"unknown node: {args.node}")
        if args.registry and node["role"] != "controller" and not args.source_session:
            raise UsageError("explicit --registry report requires --source-session")

        # head 缺省时自己从 registry 的 worktree 读，不要依赖子线记得传 --head。
        # 依据 design-notes §2.1：报告没带 head 会被判成 stale，其 waiting_on 就不计入
        # seams_unowned——那样读数 5 会不管实际情况一律接近 0。head 是有客观来源的事实，
        # 不该退回账本纪律。
        head = args.head
        head_source = "arg"
        if not head:
            head = git_head(node.get("worktree"))
            head_source = "worktree" if head else "unavailable"

        if args.source_session:
            node = validate_report_source(args.coordination_id, args.node, args.source_session, head, registry)

        row = {
            "ts": now_local(),
            "src": "report",
            "round": args.round,
            "node": args.node,
            "head": head,
            "head_source": head_source,
            "state": args.state,
            "waiting_on": waiting_on,
            "last_report_ts": now_local(),
            "note": args.note or "",
        }
        if args.source_session:
            row["source_session_id"] = args.source_session
            row["source_registry"] = str(registry_path(args.coordination_id).resolve())
        append_jsonl(jsonl_path(args.coordination_id, "progress.jsonl"), row)
        suffix = ""
        if args.state in {"working", "done"} and waiting_on:
            suffix = " (note: waiting_on is ignored for working/done state summaries)"
        if head_source == "unavailable":
            suffix += " (warning: head unavailable, report will be treated as stale once HEAD advances)"
        print(f"reported {args.node} state={args.state} head={head or 'none'}({head_source}){suffix}")
        return 0


def cmd_seam(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        known_nodes = {node["name"] for node in registry_nodes(registry)}
        if args.producer not in known_nodes:
            raise UsageError(f"unknown producer node: {args.producer}")
        for consumer in args.consumers or []:
            if consumer not in known_nodes:
                raise UsageError(f"unknown consumer node: {consumer}")
        status = "delivered" if args.deliver else "assigned"
        append_jsonl(
            jsonl_path(args.coordination_id, "seams.jsonl"),
            {
                "ts": now_local(),
                "seam_id": args.seam_id,
                "producer": args.producer,
                "consumers": args.consumers or [],
                "status": status,
                "artifact": args.deliver,
            },
        )
        print(f"seam {args.seam_id} status={status}")
        return 0


def cmd_decide(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        if args.raise_id:
            decision_instance_id = str(uuid.uuid4())
            append_jsonl(
                jsonl_path(args.coordination_id, "decisions.jsonl"),
                {
                    "ts": now_local(),
                    "decision_id": args.raise_id,
                    "decision_instance_id": decision_instance_id,
                    "raised_by": args.by,
                    "blocks": args.blocks or [],
                    "question": args.question,
                    "status": "pending",
                    "answer": None,
                },
            )
            print(f"decision {args.raise_id} status=pending instance={decision_instance_id}")
            return 0
        if args.answer:
            pending = {
                row.get("decision_id"): row
                for row in pending_decisions(args.coordination_id)
                if row.get("decision_id")
            }
            decision = pending.get(args.answer)
            if decision is None:
                raise UsageError(f"decision is not pending: {args.answer}")
            row = {
                "ts": now_local(),
                "decision_id": args.answer,
                "raised_by": None,
                "blocks": [],
                "question": None,
                "status": "answered",
                "answer": args.text,
            }
            instance = decision.get("decision_instance_id")
            if isinstance(instance, str) and instance:
                row["decision_instance_id"] = instance
            append_jsonl(jsonl_path(args.coordination_id, "decisions.jsonl"), row)
            print(f"decision {args.answer} status=answered")
            return 0
        raise UsageError("decide requires --raise or --answer")


def cmd_act(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        state = load_state(args.coordination_id)
        seq = next_seq(state, "next_act_seq")
        row = {"ts": now_local(), "seq": seq}
        if args.dispatch:
            missing = [
                name for name, value in (
                    ("--seam-id", args.seam_id),
                    ("--producer", args.producer),
                    ("--deliverable", args.deliverable),
                )
                if not value
            ]
            if missing:
                raise UsageError(f"act --dispatch requires {', '.join(missing)}")
            registry = load_registry(args.coordination_id)
            known_nodes = {node["name"] for node in registry_nodes(registry)}
            if args.producer not in known_nodes:
                raise UsageError(f"unknown producer node: {args.producer}")
            current_producer = seam_producers(args.coordination_id).get(args.seam_id)
            if current_producer and current_producer != args.producer:
                print(
                    f"producer changed for seam {args.seam_id}: "
                    f"{current_producer} -> {args.producer}; appending new assignment"
                )
            row.update(
                {
                    "kind": "dispatch",
                    "seam_id": args.seam_id,
                    "producer": args.producer,
                    "deliverable": args.deliverable,
                    "decision_id": None,
                }
            )
        elif args.escalate:
            if not args.decision_id:
                raise UsageError("act --escalate requires --decision-id")
            pending = next(
                (
                    decision for decision in pending_decisions(args.coordination_id)
                    if decision.get("decision_id") == args.decision_id
                ),
                None,
            )
            if pending is None:
                raise UsageError(f"decision is not pending: {args.decision_id}")
            row.update(
                {
                    "kind": "escalate",
                    "seam_id": None,
                    "producer": None,
                    "deliverable": None,
                    "decision_id": args.decision_id,
                }
            )
            instance = pending.get("decision_instance_id")
            if isinstance(instance, str) and instance:
                row["decision_instance_id"] = instance
        elif args.halt:
            reason = (args.reason or "").strip()
            if not reason:
                raise UsageError("act --halt requires --reason")
            row.update(
                {
                    "kind": "halt",
                    "seam_id": None,
                    "producer": None,
                    "deliverable": None,
                    "decision_id": None,
                    "reason": reason,
                    "pending_decision_ids": decision_ids(pending_decisions(args.coordination_id)),
                    "halt_poll_seq": int(state.get("next_poll_seq") or 0),
                }
            )
        else:
            raise UsageError("act requires --dispatch, --escalate, or --halt")
        append_jsonl(jsonl_path(args.coordination_id, "acts.jsonl"), row)
        if args.dispatch:
            append_jsonl(
                jsonl_path(args.coordination_id, "seams.jsonl"),
                {
                    "ts": now_local(),
                    "seam_id": args.seam_id,
                    "producer": args.producer,
                    "consumers": [],
                    "status": "assigned",
                    "artifact": None,
                },
            )
        save_state(args.coordination_id, state)
        print(f"act {row['kind']} seq={seq}")
        return 0


def format_status(
    coordination_id: str,
    registry: dict,
    streak_limit: int = DEFAULT_STALL_LIMIT,
    *,
    integrity_failed: bool = False,
) -> str:
    latest = latest_progress(coordination_id)
    registry_by_name = {node["name"]: node for node in registry_nodes(registry)}
    registry_names = sorted(node["name"] for node in registry_by_name.values() if node["role"] != "controller")
    pending = pending_decisions(coordination_id)
    unowned, malformed, stale_waiting_on = seams_waiting_counts(coordination_id)
    act = latest_act(coordination_id)
    halt = halted_act(coordination_id)
    node_lines = []
    for name in sorted(set(registry_names) | set(latest)):
        row = latest.get(name, {})
        registry_node = registry_by_name.get(name)
        lifecycle = "active" if registry_node and registry_node.get("active", True) else "retired"
        if not registry_node:
            lifecycle = "unregistered"
        node_lines.append(
            f"  {name}: lifecycle={lifecycle} state={row.get('state') or '-'} head={row.get('head') or '-'} "
            f"turn={row.get('turn') or '-'} last_report_ts={row.get('last_report_ts') or '-'}"
        )
    pending_text = ", ".join(row.get("decision_id") for row in pending if row.get("decision_id")) or "-"
    act_text = "-"
    if act:
        act_text = f"seq={act.get('seq')} kind={act.get('kind')}"
        if act.get("kind") == "dispatch":
            act_text += f" seam={act.get('seam_id')} producer={act.get('producer')}"
        elif act.get("kind") == "halt":
            act_text += f" reason={act.get('reason') or '-'}"
        elif act.get("decision_id"):
            act_text += f" decision={act.get('decision_id')}"
    header_lines = ["STATUS"]
    if integrity_failed:
        header_lines.append("ledger_integrity: FAILED (partial rows are diagnostic only; current state is not authoritative)")
    if halt:
        header_lines.extend(
            [
                "halted: yes",
                f"halt_ts: {halt.get('ts') or '-'}",
                f"halt_reason: {halt.get('reason') or '-'}",
                f"halt_pending_decisions: {format_id_list(halt.get('pending_decision_ids') or [])}",
            ]
        )
    runtime_root = runtime_dir(coordination_id)
    missing_runtime = []
    for name in PREFLIGHT_RUNTIME_FILES:
        if not (runtime_root / name).is_file():
            missing_runtime.append(name)
    if missing_runtime:
        runtime_line = (
            f"runtime_uninitialized: yes; runtime: missing ({', '.join(missing_runtime)}); "
            f"run init --registry {registry_path(coordination_id)}"
        )
    else:
        runtime_line = f"runtime_uninitialized: no; runtime: ready ({runtime_root})"
    return "\n".join(
        header_lines
        + [
            f"registry: {registry_path(coordination_id)}",
            runtime_line,
            "nodes:",
            *(node_lines or ["  -"]),
            f"pending_decisions: {pending_text}",
            f"seams_unowned:   {unowned}",
            f"stale_waiting_on: {stale_waiting_on}",
            f"malformed_waiting_on: {malformed}",
            f"stale_reports:   {', '.join(sorted(stale_report_nodes(coordination_id))) or '-'}",
            f"stall_streak:    {stall_streak(coordination_id)}/{streak_limit}",
            f"dispatches_since_progress: {load_state(coordination_id).get('dispatches_since_progress', 0)}",
            f"docs_only_advances: {load_state(coordination_id).get('docs_only_advances', 0)}",
            f"last_act:        {act_text}",
            f"corrupt_ledger_lines: {corrupt_ledger_lines(coordination_id)}",
        ]
    )


def cmd_status(args, integrity_issues: list[tuple[str, int, str]] | None = None) -> int:
    registry = load_registry(args.coordination_id)
    if integrity_issues is None:
        integrity_issues = ledger_integrity_issues(args.coordination_id)
    if integrity_issues:
        print_integrity_failure(integrity_issues)
    print(format_status(args.coordination_id, registry, integrity_failed=bool(integrity_issues)))
    return LEDGER_INTEGRITY_FAILED if integrity_issues else 0


def cmd_heartbeat(args) -> int:
    """Controller 读取 thread 后，用 concrete progress 重置 HEAD 停滞计数。"""
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        children = {
            node["name"]
            for node in registry_nodes(registry)
            if node["role"] != "controller" and node.get("active", True)
        }
        if args.node not in children:
            raise UsageError(f"unknown child node: {args.node}")
        streak = stall_streak(args.coordination_id)
        minimum = max(1, args.streak - HEARTBEAT_LEAD_ROUNDS)
        if not minimum <= streak < args.streak:
            raise UsageError(
                f"heartbeat requires {minimum}/{args.streak} <= stall_streak < "
                f"{args.streak}/{args.streak}; current={streak}/{args.streak}"
            )
        evidence = args.evidence.strip()
        if not evidence:
            raise UsageError("heartbeat requires non-empty --evidence")
        state = load_state(args.coordination_id)
        reset_seq = int(state.get("next_poll_seq") or 0)
        if reset_seq < 1:
            raise UsageError("heartbeat requires at least one valid sync")
        state["stall_reset_seq"] = reset_seq
        save_state(args.coordination_id, state)
        print(
            f"heartbeat reset node={args.node} stall_streak={streak}/{args.streak} "
            f"reset_seq={reset_seq}"
        )
        return 0


def cmd_stall_check(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        halt = halted_act(args.coordination_id)
        if halt:
            pending = format_id_list(halt.get("pending_decision_ids") or [])
            print(f"HALTED (ts={halt.get('ts') or '-'}, reason={halt.get('reason') or '-'}, pending={pending})")
            return 4
        state = load_state(args.coordination_id)
        dispatches = int(state.get("dispatches_since_progress") or 0)
        answered_line = f"last_must_act_answered: {'yes' if last_must_act_answered(args.coordination_id) else 'no'}"
        unreported, already_escalated = pending_escalation_groups(args.coordination_id)
        if unreported:
            items = format_id_list(decision_ids(unreported))
            lines = [f"MUST_ESCALATE pending_decisions: {items} dispatches_since_progress={dispatches}"]
            if already_escalated:
                lines.append(f"already_escalated: {format_id_list(decision_ids(already_escalated))}")
            lines.append(answered_line)
            print("\n".join(lines))
            return 3
        pending_suffix = ""
        if already_escalated:
            pending_suffix = f" pending_escalated: {format_id_list(decision_ids(already_escalated))}"
        streak = stall_streak(args.coordination_id)
        if streak >= args.streak:
            state["last_must_act_seq"] = int(state.get("next_act_seq") or 0)
            save_state(args.coordination_id, state)
            print(
                f"MUST_ACT stall_streak={streak}/{args.streak} "
                f"dispatches_since_progress={dispatches}{pending_suffix}\n{answered_line}"
            )
            return 2
        if streak >= max(1, args.streak - HEARTBEAT_LEAD_ROUNDS):
            print(
                f"CHECK_HEARTBEAT stall_streak={streak}/{args.streak} "
                f"dispatches_since_progress={dispatches} read_thread_required=yes{pending_suffix}\n{answered_line}"
            )
            return 0
        print(f"OK stall_streak={streak}/{args.streak} dispatches_since_progress={dispatches}{pending_suffix}\n{answered_line}")
        return 0


class UsageErrorParser(argparse.ArgumentParser):
    """用法错误退出 64（EX_USAGE），不用 argparse 默认的 2。

    2 是 stall-check 的 MUST_ACT。若用法错误也退 2，broker 会把一次拼错的命令
    读成"必须行动"，或者反过来把真正的 MUST_ACT 当成拼写问题忽略掉。退出码
    必须在语义上唯一。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"ERROR: {message}", file=sys.stderr)
        raise SystemExit(64)


def build_parser() -> argparse.ArgumentParser:
    parser = UsageErrorParser(description="thread-harness append-only ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_routing_args(command):
        routing = command.add_mutually_exclusive_group(required=True)
        routing.add_argument("--registry")
        routing.add_argument("--coordination-id")

    init = sub.add_parser("init")
    add_routing_args(init)
    init.set_defaults(func=cmd_init)

    sync = sub.add_parser("sync")
    add_routing_args(sync)
    sync.add_argument("--round", required=True, type=int)
    sync.add_argument("--streak", type=int, default=DEFAULT_STALL_LIMIT)
    sync.set_defaults(func=cmd_sync)

    route = sub.add_parser("route")
    route.add_argument("--registry", required=True)
    route.add_argument("--node", required=True)
    route.add_argument("--new-session", required=True)
    route.add_argument("--expect-current")
    route.set_defaults(func=cmd_route)

    report = sub.add_parser("report")
    add_routing_args(report)
    report.add_argument("--node", required=True)
    report.add_argument("--state", required=True)
    report.add_argument("--round", type=int, default=0)
    report.add_argument("--head")
    report.add_argument("--source-session")
    report.add_argument("--waiting-on", action="extend", nargs="+", default=[])
    report.add_argument("--note")
    report.set_defaults(func=cmd_report)

    seam = sub.add_parser("seam")
    add_routing_args(seam)
    seam.add_argument("--seam-id", required=True)
    seam.add_argument("--producer", required=True)
    seam.add_argument("--consumers", action="extend", nargs="+", default=[])
    seam.add_argument("--deliver")
    seam.set_defaults(func=cmd_seam)

    decide = sub.add_parser("decide")
    add_routing_args(decide)
    decide.add_argument("--raise", dest="raise_id")
    decide.add_argument("--by")
    decide.add_argument("--blocks", action="extend", nargs="+", default=[])
    decide.add_argument("--question")
    decide.add_argument("--answer")
    decide.add_argument("--text")
    decide.set_defaults(func=cmd_decide)

    act = sub.add_parser("act")
    add_routing_args(act)
    mode = act.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dispatch", action="store_true")
    mode.add_argument("--escalate", action="store_true")
    mode.add_argument("--halt", action="store_true")
    act.add_argument("--seam-id")
    act.add_argument("--producer")
    act.add_argument("--deliverable")
    act.add_argument("--decision-id")
    act.add_argument("--reason")
    act.set_defaults(func=cmd_act)

    status = sub.add_parser("status")
    add_routing_args(status)
    status.set_defaults(func=cmd_status)

    heartbeat = sub.add_parser("heartbeat")
    add_routing_args(heartbeat)
    heartbeat.add_argument("--node", required=True)
    heartbeat.add_argument("--evidence", required=True)
    heartbeat.add_argument("--streak", type=int, default=DEFAULT_STALL_LIMIT)
    heartbeat.set_defaults(func=cmd_heartbeat)

    stall = sub.add_parser("stall-check")
    add_routing_args(stall)
    stall.add_argument("--streak", type=int, default=DEFAULT_STALL_LIMIT)
    stall.set_defaults(func=cmd_stall_check)

    preflight = sub.add_parser("preflight")
    add_routing_args(preflight)
    preflight.set_defaults(func=cmd_preflight)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        configure_routing(args)
        if args.command in INTEGRITY_GUARDED_COMMANDS:
            issues = ledger_integrity_issues(args.coordination_id)
            if issues:
                if args.command == "status":
                    return cmd_status(args, integrity_issues=issues)
                print_integrity_failure(issues)
                return LEDGER_INTEGRITY_FAILED
        return args.func(args)
    except LedgerIntegrityError as exc:
        print_integrity_failure(exc.issues)
        return LEDGER_INTEGRITY_FAILED
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 64
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
