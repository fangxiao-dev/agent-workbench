"""Constants, StateError/Lifecycle, git query helpers and file IO shared by every runtime block."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from contextvars import ContextVar
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


STATE_PATH = Path(".impl-package/state.json")
ATTEMPT_ARCHIVE_PATH = Path(".impl-package/attempts")
PROGRESS_PATH = Path("progress.md")
EXECUTION_PATH = Path("execution")
ACTIVE_TRAIL_NAME = "trail.jsonl"
TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")
GATE_PATH = Path("gate.md")
FORMAT_VERSION = "3.6"

TICKET_STATES = {"PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED"}
TERMINAL_VERDICTS = {"pass", "fail", "defer"}
VERDICTS = TERMINAL_VERDICTS | {"blocked"}
TIMINGS = {"early-falsification", "remaining-completion"}
CONCLUSIONS = {"supporting", "contradictory", "inconclusive"}
DISPOSITIONS = {"waived", "superseded"}
TRAIL_APPEND_KINDS = frozenset({"dispatch", "escape", "fact", "worker-return"})
RETIRED_DISPATCH_FIELDS = frozenset({"candidates_of", "declaration_status", "declaration_reason", "runnable_candidate_ids", "state_sha256", "situation_digest"})
TRAIL_COMMON_FIELDS = frozenset({"v", "seq", "ts", "head"})
FIXED_COMMIT_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
LEASE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
LEASE_FILE_RE = re.compile(r"^[0-9a-f]{64}\.json$")

ATTEMPT_RE = re.compile(r"(?im)^[^\r\n]*(?:Attempt ID|执行尝试 ID)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*([^\s*]+)")
COMPOSITION_RE = re.compile(r"Composition[^\n]*tickets=(true|false),\s*dag=(true|false)", re.I)
DECISION_RE = re.compile(r"(?im)^[^\r\n]*(?:Decision Revision|决策修订)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*(D\d+)\b")
SPEC_RE = re.compile(r"(?im)^[^\r\n]*(?:Spec Revision|规格修订)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*(S\d+)\b")
PLAN_RE = re.compile(r"(?im)^[^\r\n]*(?:Plan Revision|计划修订)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*(P\d+)\b")
PREDECESSORS_RE = re.compile(r"(?im)^[^\r\n]*(?:Predecessors|前置包)[^：:\r\n]*[：:][ \t]*(.*?)[ \t]*$")
ACCEPTANCE_JOURNEY_RE = re.compile(r"(?m)^Acceptance: journey[ \t]*$")
RELEASE_ORDER_RE = re.compile(r"(?m)^Release order: (required|none)[ \t]*$")
TICKET_ID_RE = re.compile(r"(?im)^[^\r\n]*Ticket ID[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*([^\s*]+)")
PUBLICATION_RE = re.compile(r"(?im)^([^\r\n]*(?:Publication Status|发布状态)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*)(Draft|Approved)[ \t]*$")
BATCH_ESTIMATE_RE = re.compile(r"(?m)^[^\r\n]*预计批次[：:]")
ARRIVAL_PATH_RE = re.compile(r"(?im)^[^\r\n]*(?:Arrival path|到达路径)[^：:\r\n]*[：:][ \t]*(.*?)[ \t]*$")
DEPENDENCY_HEADING_RE = re.compile(r"(?ims)^##\s+(?:阻塞依赖|Blocking Dependencies)\s*$\r?\n(.*?)(?=^##\s+|\Z)")

ARRIVAL_SEGMENT_RE = re.compile(r"^(EXISTS|NEW)\s*:\s*(.+?)\s*$")
ER_ENTRY_RE = re.compile(r"(?m)^## ([^\s]+-ER-(\d{3})) · (checkpoint|judgment)\s*$")
COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
PACKAGE_ID_RE = re.compile(r"^(?:\d{6}|\d{8}|\d{4}-\d{2}-\d{2})[-_][A-Za-z0-9].+")
ATTEMPT_ID_RE = re.compile(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})")

class StateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Lifecycle:
    attempt: str
    value: str
    gate: dict[str, Any] | None

    @property
    def frozen(self) -> bool:
        return self.value == "frozen"

    @property
    def gate_verdict(self) -> str:
        return self.gate["verdict"] if self.gate else "open"


_GitResult = tuple[int, str, str]
_git_query_cache: ContextVar[dict[tuple[Any, ...], tuple[_GitResult, frozenset[Path]]] | None] = ContextVar(
    "impl_package_git_query_cache", default=None,
)


@contextmanager
def git_query_scope():
    if _git_query_cache.get() is not None:
        yield
        return
    token = _git_query_cache.set({})
    try:
        yield
    finally:
        _git_query_cache.reset(token)


def _cacheable_git_query(args: tuple[str, ...]) -> bool:
    if not args:
        return False
    command = args[0]
    if command == "rev-parse":
        return True
    if command == "merge-base":
        return len(args) == 4 and args[1] == "--is-ancestor"
    if command == "show":
        return len(args) == 2 and ":" in args[1]
    if command == "cat-file":
        return len(args) >= 3 and not any(arg.startswith("--batch") for arg in args)
    if command == "grep":
        return len(args) >= 9 and args[1:5] == ("-I", "-F", "-l", "-e") and args[7] == "--"
    if command == "diff":
        return len(args) >= 6 and args[1] == "--quiet" and args[4] == "--" and "--cached" not in args
    return (
        command == "hash-object"
        and "-w" not in args
        and "--stdin" not in args
        and "--stdin-paths" not in args
        and "--" in args
        and args.index("--") < len(args) - 1
    )


def _hash_object_paths(repo: Path, args: tuple[str, ...]) -> frozenset[Path]:
    if not args or args[0] != "hash-object" or not _cacheable_git_query(args):
        return frozenset()
    try:
        marker = args.index("--")
    except ValueError:
        return frozenset()
    return frozenset((repo / value).resolve() for value in args[marker + 1:] if value)


def _run_git_result(
    repo: Path, *args: str, encoding: str | None = None, errors: str | None = None,
) -> _GitResult:
    cache = _git_query_cache.get()
    query = _cacheable_git_query(args)
    key = (repo.resolve(), args, encoding, errors)
    if cache is not None and query and key in cache:
        return cache[key][0]

    options: dict[str, Any] = {"capture_output": True, "text": True, "check": False}
    if encoding is not None:
        options["encoding"] = encoding
    if errors is not None:
        options["errors"] = errors
    result = subprocess.run(["git", "-C", str(repo), *args], **options)
    value = (result.returncode, result.stdout, result.stderr)
    if cache is not None:
        if query:
            cache[key] = (value, _hash_object_paths(repo, args))
        else:
            cache.clear()
    return value


def _invalidate_working_tree_hash(path: Path) -> None:
    cache = _git_query_cache.get()
    if cache is None:
        return
    resolved = path.resolve()
    for key, (_, paths) in tuple(cache.items()):
        if resolved in paths:
            del cache[key]


def _run_git(repo: Path, *args: str) -> str:
    code, stdout, stderr = _run_git_result(repo, *args)
    if code != 0:
        raise StateError(stderr.strip() or stdout.strip() or "git command failed")
    return stdout.strip()


def _repo_root(package: Path) -> Path:
    return Path(_run_git(package, "rev-parse", "--show-toplevel")).resolve()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"{path} must contain a JSON object")
    return value


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        _invalidate_working_tree_hash(path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_iso_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{label} must be an ISO timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateError(f"{label} must be an ISO timestamp with a timezone") from exc
    if parsed.tzinfo is None:
        raise StateError(f"{label} must include a timezone")
    return value


def _repo_relative(repo: Path, value: str, field: str, *, must_exist: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{field} must be a non-empty repository-relative path")
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw.split("#", 1)[0])
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw) or raw.startswith("//") or ".." in path.parts or str(path) in {"", "."}:
        raise StateError(f"{field} must be a repository-relative path: {value!r}")
    resolved = (repo / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError as exc:
        raise StateError(f"{field} escapes the repository: {value!r}") from exc
    if must_exist and not resolved.exists():
        raise StateError(f"{field} does not exist: {path.as_posix()}")
    anchor = "#" + raw.split("#", 1)[1] if "#" in raw else ""
    return path.as_posix() + anchor


def _validate_commit(repo: Path, commit: str) -> str:
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise StateError(f"invalid Git commit ID: {commit!r}")
    return _run_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")


def _is_ancestor(repo: Path, revision: str, head: str) -> bool:
    code, _, stderr = _run_git_result(repo, "merge-base", "--is-ancestor", revision, head)
    if code == 0:
        return True
    if code == 1:
        return False
    raise StateError(stderr.strip() or "cannot determine Git ancestry")


def _state_format_version(state: Any) -> str:
    version = state.get("formatVersion") if isinstance(state, dict) else None
    if version != FORMAT_VERSION:
        raise StateError(f"format {version if version is not None else '(missing)'} is no longer supported; start a new package")
    return version


def require_current_format(package: Path) -> None:
    path = package / STATE_PATH
    if path.exists():
        _state_format_version(_load_json(path))
