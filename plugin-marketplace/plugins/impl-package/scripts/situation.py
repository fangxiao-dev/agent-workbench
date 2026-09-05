"""Situation derivation for the Impl-Package dev-with-track stage.

The situation table is deliberately kept outside this module.  This file only
loads it, reads the package facts named by the table contract, and renders a
deterministic projection. Render best-effort writes a digest credential unless
the caller explicitly requests a read-only projection; credential write failure
does not fail the render.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in incomplete installs
    yaml = None


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = PLUGIN_ROOT / "skills" / "dev-with-track" / "situations.yaml"
STAGE = "dev-with-track"
DIGEST_LENGTH = 12
STATE_REL = ".impl-package/state.json"
GATE_REL = "gate.md"
FINDINGS_REL = "execution-findings.md"
ACTIVE_TRAIL_NAME = "trail.jsonl"
SITUATION_DIGEST_NAME = "situation-digest.json"
TICKET_STATES = {"PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED"}
TERMINAL_GATE_VERDICTS = {"pass", "fail", "defer"}
REVIEW_PHASE_VALUES = ("initial", "finding-closure", "terminal-final")
REVIEW_TRACK_VALUES = ("Track A", "Track B", "Track C", "Track D")
REVIEW_PHASES = frozenset(REVIEW_PHASE_VALUES)
REVIEW_TRACKS = frozenset(REVIEW_TRACK_VALUES)
VALID_BASIS = {"cli", "prose", "observed"}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
PROTOCOLS_PATH = Path(__file__).resolve().parent / "impl_package_runtime" / "protocols.json"
_PROTOCOL_PLACEHOLDERS = {
    "{review_phase_values}": " | ".join(REVIEW_PHASE_VALUES),
    "{review_track_values}": " | ".join(REVIEW_TRACK_VALUES),
}
_PROTOCOL_REQUIRED_PLACEHOLDERS = {
    "ticket.review.required-trigger": tuple(_PROTOCOL_PLACEHOLDERS),
    "attempt.review.terminal-coverage-incomplete": tuple(_PROTOCOL_PLACEHOLDERS),
}
assert set(_PROTOCOL_PLACEHOLDERS) == {
    placeholder
    for placeholders in _PROTOCOL_REQUIRED_PLACEHOLDERS.values()
    for placeholder in placeholders
}
TICKET_ID_RE = re.compile(
    r"(?im)^\s*(?:\*\*)?(?:Ticket ID|Ticket ID（Ticket ID）)\s*[：:](?:\*\*)?\s*([^\s*]+)"
)
ATTEMPT_ID_RE = re.compile(
    r"(?im)^\s*(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)\s*[：:](?:\*\*)?\s*([^\s*]+)"
)
CLAIM_RE = re.compile(r"Stable claim ID：\s*`([^`]+)`")
ASCII_CLAIM_RE = re.compile(r"Stable claim ID\s*:\s*`([^`]+)`", re.I)
DEPENDENCY_HEADING_RE = re.compile(r"(?ms)^##\s+(?:阻塞依赖|Blocking Dependencies)\s*$\n(.*?)(?=^##\s+|\Z)")
FINDING_ID_RE = re.compile(r"\b(?:FINDING|FND|FIND|F)-[A-Za-z0-9][A-Za-z0-9._-]*\b", re.I)
BOOL_RE = re.compile(r"^(true|false|yes|no|1|0|是|否)$", re.I)
NUMERIC_COMPARISON_RE = re.compile(r"^(>=|<=|==|!=|>|<)\s*(-?(?:\d+(?:\.\d*)?|\.\d+))$")
LIVE_PACKAGE_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_])docs/implementations/([A-Za-z0-9][A-Za-z0-9._-]*)/"
)
RETIRED_PACKAGES_REL = "docs/implementations/retired.json"

# Facts are intentionally a closed namespace.  The aliases below are only for
# already-published legacy trail rows; new rows must use the canonical key.
FACT_KEYS = frozenset(
    {
        "package.validate.projection_drift",
        "attempt.session_resumed",
        "attempt.in_flight",
        "attempt.handoff_or_long_task",
        "attempt.integration_carrier_available",
        "attempt.integration_evidence_available",
        "attempt.manual_verification_owner",
        "attempt.manual_verification_result_present",
        "attempt.completion_claim_pending",
        "attempt.terminal_coverage_complete",
        "ticket.blocker_maybe_resolved",
        "ticket.no_longer_needed",
        "ticket.release_edge_rechecked",
        "ticket.review_required",
        "ticket.review_trigger",
        "ticket.post_fix_regression_pending",
        "review.canonical_summary",
        "review.terminal_summary",
        "evidence.sources_uniquely_decide",
        "git.comparison_head_fixed",
        "git.accepted_seam_changed",
        "trail.anchor_mismatch",
        "trail.bookkeeper_partial_write",
        "trail.checkpoint_projection_race",
        "trail.checkpoint_refresh_needed",
        "trail.envelope_valid",
        "trail.handoff_in_flight",
        "trail.handoff_recovery_needed",
        "trail.handoff_target_corrected",
        "trail.judgment_unfiled",
        "trail.reviewer_unavailable",
        "finding.closure_review_pending",
    }
)
FACT_KEY_ALIASES = {"ticket.judgment_unfiled": "trail.judgment_unfiled"}


def describe_unknown_fact_keys(keys: tuple[str, ...]) -> str:
    """Name the keys and, for near misses, the key that was probably meant."""
    parts = []
    for key in keys:
        close = get_close_matches(str(key), FACT_KEYS, n=1, cutoff=0.6)
        parts.append(f"{key} → 也许是 {close[0]}" if close else str(key))
    return (
        "；".join(parts)
        + "。表只消费封闭清单内的 key；其它事实写 evidenceIndex 或 ER judgment"
    )


def _unknown_fact_key_notice(keys: tuple[str, ...]) -> str:
    """The renderer ignores these rows rather than refusing to render."""
    return "trail.jsonl 含未知 fact key，已忽略这些行：" + describe_unknown_fact_keys(keys)

# Only defaults that preserve the fail-closed direction belong here.  A key
# absent from this mapping remains unknown when its fact channel is readable.
FACT_DEFAULTS: dict[str, Any] = {
    "ticket.release_edge_rechecked": False,
}


class SituationError(RuntimeError):
    """A fatal table, CLI, or package-location error."""


class TableError(SituationError):
    """A malformed situation table or an unsupported table extension."""

    def __init__(self, errors: Iterable[str], warnings: Iterable[str] = ()) -> None:
        self.errors = list(errors)
        self.warnings = list(warnings)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class Fact:
    value: Any = None
    known: bool = True
    reason: str | None = None
    ts: str | None = None
    seq: Any = None

    @classmethod
    def unknown(cls, reason: str) -> "Fact":
        return cls(value=None, known=False, reason=reason)

    def as_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": self.value,
            "status": "known" if self.known else "unknown",
        }
        if self.reason:
            result["reason"] = self.reason
        if self.ts is not None:
            result["ts"] = self.ts
        if self.seq is not None:
            result["seq"] = self.seq
        return result


@dataclass
class FileView:
    relative_path: str
    text: str | None = None
    error: str | None = None

    @property
    def present(self) -> bool:
        return self.text is not None or self.error is not None


@dataclass
class StateView:
    raw: dict[str, Any] | None
    valid: bool
    error: str | None
    attempt_id: str | None
    ticket_ids: list[str]


@dataclass
class TicketInfo:
    identifier: str
    relative_path: str | None
    text: str
    valid: bool
    claims: list[str] = field(default_factory=list)
    safety_claims: list[str] = field(default_factory=list)
    dependencies: list[tuple[str, str]] = field(default_factory=list)
    error: str | None = None


@dataclass
class TrailView:
    present: bool
    rows: list[dict[str, Any]]
    error: str | None = None
    facts: list["TrailFact"] = field(default_factory=list)
    unknown_fact_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrailFact:
    key: str
    value: Any
    subject: str | None
    ts: str | None
    seq: Any
    row_index: int


@dataclass
class GateView:
    present: bool
    verdict: str | None
    comparison_commit: str | None
    text: str = ""
    error: str | None = None


@dataclass
class FindingInfo:
    identifier: str
    block: str
    status: str | None = None
    track: str | None = None
    source: str | None = None
    source_recheck_pending: bool = False
    grading_pending: bool = False
    triage_pending: bool = False


@dataclass
class FindingsView:
    present: bool
    text: str
    findings: list[FindingInfo]
    error: str | None = None


@dataclass
class IntakeView:
    present: bool
    has_backlog: bool | None
    relative_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    projection_drift: bool
    source: str


@dataclass(frozen=True)
class CompactionPressureResult:
    data: dict[str, Any]
    source: str

    @property
    def high(self) -> bool:
        return bool(self.data["high"])


@dataclass
class Snapshot:
    package: Path
    reader: "PackageReader"
    state: StateView
    tickets: dict[str, TicketInfo]
    trail: TrailView
    gate: GateView
    findings: FindingsView
    intake: IntakeView
    validation_result: ValidationResult | None
    compaction_pressure: CompactionPressureResult | None
    head: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class TableModel:
    data: dict[str, Any]
    rows: list[dict[str, Any]]
    priority: list[list[str]]
    warnings: list[str]


def _load_protocols() -> dict[str, str]:
    fallback = {"default": ""}
    try:
        raw = json.loads(PROTOCOLS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return fallback
    try:
        assert isinstance(raw, dict)
        assert all(isinstance(key, str) and isinstance(value, str) for key, value in raw.items())
        assert isinstance(raw.get("default"), str)
        for slug, placeholders in _PROTOCOL_REQUIRED_PLACEHOLDERS.items():
            assert slug in raw
            assert all(placeholder in raw[slug] for placeholder in placeholders)
        protocols = {
            key: _expand_protocol(value)
            for key, value in raw.items()
        }
        assert all(
            placeholder not in value
            for value in protocols.values()
            for placeholder in _PROTOCOL_PLACEHOLDERS
        )
        return protocols
    except AssertionError:
        return fallback


def _expand_protocol(value: str) -> str:
    for placeholder, replacement in _PROTOCOL_PLACEHOLDERS.items():
        value = value.replace(placeholder, replacement)
    return value


_PROTOCOLS = _load_protocols()


@dataclass
class Candidate:
    row: dict[str, Any]
    subject: str
    context: "FactContext"
    when: dict[str, Fact]

    @property
    def slug(self) -> str:
        return str(self.row["slug"])

    @property
    def row_index(self) -> int:
        return int(self.row["_row_index"])

    def as_json(self) -> dict[str, Any]:
        actions = list(self.row.get("actions", []))
        return {
            "slug": self.slug,
            "protocol": _PROTOCOLS.get(self.slug, _PROTOCOLS["default"]),
            "subject": self.subject,
            "basis": self.row.get("basis"),
            "judgment": self.row.get("judgment"),
            "ask": self.row.get("ask"),
            "action_ids": [action.get("id") for action in actions],
            "actions": actions,
            "when": {key: fact.as_json() for key, fact in self.when.items()},
        }


@dataclass
class Undetermined:
    row: dict[str, Any]
    subject: str
    context: "FactContext"
    when: dict[str, Fact]

    def as_json(self) -> dict[str, Any]:
        unknown = {
            key: fact.reason or "值未知"
            for key, fact in self.when.items()
            if not fact.known
        }
        return {
            "slug": self.row["slug"],
            "subject": self.subject,
            "unknown_keys": sorted(unknown),
            "reasons": unknown,
            "when": {key: fact.as_json() for key, fact in self.when.items()},
        }


def _git_result(repo: Path, *arguments: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _find_git_root(path: Path) -> Path | None:
    probe = path if path.is_dir() else path.parent
    while True:
        if probe.exists():
            code, output, _ = _git_result(probe, "rev-parse", "--show-toplevel")
            if code == 0 and output:
                return Path(output).resolve()
        if probe.parent == probe:
            return None
        probe = probe.parent


def _safe_relative_path(base: Path, relative: str) -> Path:
    posix = PurePosixPath(relative.replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts:
        raise SituationError(f"package-relative path escapes package: {relative}")
    path = (base / Path(*posix.parts)).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise SituationError(f"package-relative path escapes package: {relative}") from exc
    return path


class PackageReader:
    """Read package files from the worktree or from one Git commit."""

    def __init__(self, package: Path, at: str | None) -> None:
        self.package = package.expanduser().resolve()
        self.at_input = at
        self.repo = _find_git_root(self.package)
        self.commit: str | None = None
        self.package_rel: PurePosixPath | None = None
        self.warnings: list[str] = []
        if at is not None:
            if self.repo is None:
                raise SituationError("--at requires <package> to be inside a Git repository")
            try:
                self.package_rel = PurePosixPath(self.package.relative_to(self.repo).as_posix())
            except ValueError as exc:
                raise SituationError("package is not inside the discovered Git repository") from exc
            code, output, error = _git_result(self.repo, "rev-parse", "--verify", f"{at}^{{commit}}")
            if code != 0 or not output:
                raise SituationError(f"cannot resolve --at commit {at!r}: {error or output}")
            self.commit = output
        elif not self.package.is_dir():
            raise SituationError(f"package directory does not exist: {self.package}")
        if self.repo is not None and self.package_rel is None:
            try:
                self.package_rel = PurePosixPath(self.package.relative_to(self.repo).as_posix())
            except ValueError:
                self.package_rel = None

    @property
    def at_label(self) -> str | None:
        return self.commit

    def read(self, relative: str) -> FileView:
        if self.commit is None:
            path = _safe_relative_path(self.package, relative)
            if not path.is_file():
                return FileView(relative)
            try:
                return FileView(relative, path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError) as exc:
                return FileView(relative, error=f"cannot read {path}: {exc}")

        assert self.repo is not None and self.package_rel is not None
        path = (self.package_rel / PurePosixPath(relative.replace("\\", "/"))).as_posix()
        code, output, error = _git_result(self.repo, "show", f"{self.commit}:{path}")
        if code != 0:
            return FileView(relative)
        return FileView(relative, output)

    def list_ticket_files(self) -> list[str]:
        if self.commit is None:
            directory = self.package / "tickets"
            if not directory.is_dir():
                return []
            return sorted(
                f"tickets/{child.name}"
                for child in directory.iterdir()
                if child.is_file() and child.suffix.lower() == ".md"
            )

        assert self.repo is not None and self.package_rel is not None
        prefix = (self.package_rel / "tickets").as_posix()
        code, output, _ = _git_result(self.repo, "ls-tree", "-r", "--name-only", self.commit, "--", prefix)
        if code != 0:
            return []
        result: list[str] = []
        for line in output.splitlines():
            path = PurePosixPath(line.strip())
            if path.parent.as_posix() == prefix and path.suffix.lower() == ".md":
                result.append(f"tickets/{path.name}")
        return sorted(result)

    def directory_has_entries(self, relative: str) -> bool | None:
        """Return whether an allowed package-relative queue directory is non-empty."""
        if self.commit is None:
            path = _safe_relative_path(self.package, relative)
            if not path.is_dir():
                return None
            try:
                return any(path.iterdir())
            except OSError as exc:
                self.warnings.append(f"无法读取 {path}: {exc}")
                return None
        assert self.repo is not None and self.package_rel is not None
        prefix = (self.package_rel / PurePosixPath(relative.replace("\\", "/"))).as_posix().rstrip("/") + "/"
        code, output, _ = _git_result(self.repo, "ls-tree", "-r", "--name-only", self.commit, "--", prefix)
        if code != 0:
            return None
        return bool(output.strip())

    def head(self) -> str | None:
        if self.commit is not None:
            return self.commit
        if self.repo is None:
            self.warnings.append("当前 package 不在 Git 仓库内，Git 相关 key 无法判定")
            return None
        code, output, error = _git_result(self.repo, "rev-parse", "HEAD")
        if code != 0 or not output:
            self.warnings.append(f"无法读取 Git HEAD：{error or output}")
            return None
        return output

    def resolve_commit(self, value: str) -> str | None:
        if self.repo is None:
            return None
        code, output, _ = _git_result(self.repo, "rev-parse", "--verify", f"{value}^{{commit}}")
        return output if code == 0 and output else None

    def diff_names(self, base: str) -> list[str] | None:
        if self.repo is None:
            return None
        right = self.commit or "HEAD"
        arguments = ["diff", "--name-only", f"{base}..{right}", "--"]
        if self.package_rel is not None:
            arguments.append(self.package_rel.as_posix())
        code, output, _ = _git_result(self.repo, *arguments)
        if code != 0:
            return None
        return [line.replace("\\", "/") for line in output.splitlines() if line.strip()]


def _read_repo_relative(reader: PackageReader, relative: str) -> FileView:
    """Read a repository-relative file from the worktree or --at commit."""
    if reader.repo is None:
        return FileView(relative, error="package 不在 Git 仓库内，无法读取 repository-relative 文件")
    if reader.commit is None:
        try:
            path = _safe_relative_path(reader.repo, relative)
            if not path.is_file():
                return FileView(relative, error=f"{relative} 不存在")
            return FileView(relative, path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, SituationError) as exc:
            return FileView(relative, error=f"cannot read {relative}: {exc}")
    code, output, error = _git_result(reader.repo, "show", f"{reader.commit}:{relative}")
    if code != 0:
        return FileView(relative, error=f"cannot read {relative} at {reader.commit}: {error or output}")
    return FileView(relative, output)


def _live_reference_document_paths(reader: PackageReader) -> list[str]:
    paths = ["decision.md", "spec.md", "plan.md"]
    if reader.commit is not None:
        assert reader.repo is not None and reader.package_rel is not None
        prefix = (reader.package_rel / "tickets").as_posix().rstrip("/") + "/"
        code, output, error = _git_result(
            reader.repo,
            "ls-tree",
            "-r",
            "--name-only",
            reader.commit,
            "--",
            prefix,
        )
        if code != 0:
            raise SituationError(f"cannot list {prefix} at {reader.commit}: {error or output}")
        for line in output.splitlines():
            path = PurePosixPath(line.strip())
            if path.as_posix().startswith(prefix) and path.suffix.lower() == ".md":
                paths.append(path.relative_to(reader.package_rel).as_posix())
        return paths

    directory = reader.package / "tickets"
    if not directory.is_dir():
        return paths
    try:
        for child in directory.rglob("*.md"):
            if child.is_file():
                paths.append(child.relative_to(reader.package).as_posix())
    except OSError as exc:
        raise SituationError(f"cannot list {directory}: {exc}") from exc
    return sorted(set(paths))


def _retired_package_ids(reader: PackageReader) -> tuple[set[str] | None, str | None]:
    view = _read_repo_relative(reader, RETIRED_PACKAGES_REL)
    if view.error or view.text is None:
        return None, view.error or f"{RETIRED_PACKAGES_REL} 为空"
    try:
        value = json.loads(view.text)
    except json.JSONDecodeError as exc:
        return None, f"{RETIRED_PACKAGES_REL} 不是合法 JSON：{exc}"
    if not isinstance(value, dict) or not isinstance(value.get("packages"), list):
        return None, f"{RETIRED_PACKAGES_REL} 缺少 packages list"
    package_ids: set[str] = set()
    for index, item in enumerate(value["packages"]):
        if not isinstance(item, dict) or not isinstance(item.get("package_id"), str) or not item["package_id"].strip():
            return None, f"{RETIRED_PACKAGES_REL} packages[{index}].package_id 无效"
        package_ids.add(item["package_id"])
    return package_ids, None


def _live_package_reference_fact(reader: PackageReader) -> Fact:
    try:
        document_paths = _live_reference_document_paths(reader)
        references: list[tuple[str, str, str]] = []
        current_package_id = reader.package.name
        for relative in document_paths:
            view = reader.read(relative)
            if view.error:
                return Fact.unknown(view.error)
            if view.text is None:
                continue
            for match in LIVE_PACKAGE_REFERENCE_RE.finditer(view.text):
                package_id = match.group(1)
                if package_id == current_package_id:
                    continue
                references.append((relative, match.group(0), package_id))

        retired_ids, error = _retired_package_ids(reader)
        if retired_ids is None:
            return Fact.unknown(error or f"无法读取 {RETIRED_PACKAGES_REL}")

        live_references = [
            (relative, path, package_id)
            for relative, path, package_id in references
            if package_id not in retired_ids
        ]
        if not live_references:
            return _fact_value(False)
        details = "; ".join(
            f"{relative}: {path}"
            for relative, path, _ in dict.fromkeys(live_references)
        )
        return _fact_value(True, reason=f"发现活体 package 引用：{details}")
    except (OSError, UnicodeError, SituationError) as exc:
        return Fact.unknown(f"无法扫描活体 package 引用：{exc}")


def live_package_reference_fact(package: Path) -> Fact:
    """Return the computed live-package reference fact for a worktree package."""
    try:
        return _live_package_reference_fact(PackageReader(package, None))
    except (OSError, UnicodeError, SituationError) as exc:
        return Fact.unknown(f"无法扫描活体 package 引用：{exc}")


def _active_trail_relative_path(attempt_id: str) -> str:
    """The renderer's input stays on the unnumbered, active trail path."""
    return f"execution/{attempt_id}/{ACTIVE_TRAIL_NAME}"


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        match = BOOL_RE.fullmatch(value.strip())
        if match:
            return match.group(1).lower() in {"true", "yes", "1", "是"}
    return None


def _canonical_fact_key(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    key = value.strip()
    return FACT_KEY_ALIASES.get(key, key)


def _timestamp_sort_key(value: str | None) -> tuple[int, int, float | str]:
    if not isinstance(value, str) or not value.strip():
        return (0, 0, 0.0)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, 0, parsed.astimezone(timezone.utc).timestamp())
    except ValueError:
        return (1, 1, raw)


def _sequence_sort_key(value: Any) -> tuple[int, int, float | str]:
    if value is None or isinstance(value, bool):
        return (0, 0, 0.0)
    try:
        return (1, 0, float(value))
    except (TypeError, ValueError):
        return (1, 1, str(value))


def _trail_fact_sort_key(fact: TrailFact) -> tuple[Any, ...]:
    return (_timestamp_sort_key(fact.ts), _sequence_sort_key(fact.seq), fact.row_index)


def _parse_state(view: FileView) -> StateView:
    if not view.present:
        return StateView(None, False, "state.json 不存在", None, [])
    if view.error:
        return StateView(None, False, view.error, None, [])
    assert view.text is not None
    try:
        raw = json.loads(view.text)
    except json.JSONDecodeError as exc:
        return StateView(None, False, f"state.json 不是合法 JSON：{exc}", None, [])
    if not isinstance(raw, dict):
        return StateView(None, False, "state.json 顶层不是 object", None, [])

    attempt_id: str | None = None
    attempt = raw.get("attempt")
    if isinstance(attempt, dict) and isinstance(attempt.get("id"), str):
        attempt_id = attempt["id"]
    ticket_ids: list[str] = []
    tickets = raw.get("tickets")
    if isinstance(tickets, dict):
        ticket_ids = sorted(str(identifier) for identifier in tickets)

    errors: list[str] = []
    expected = {"formatVersion", "attempt", "attemptHistory", "predecessors", "tickets", "evidenceIndex", "activeCheckpoints"}
    if set(raw) != expected:
        errors.append("顶层字段不符合 3.5 schema")
    if raw.get("formatVersion") != "3.5":
        errors.append("formatVersion 不是 3.5")
    if not isinstance(attempt, dict) or not attempt_id:
        errors.append("attempt.id 缺失")
    elif set(attempt) != {"id", "plan"} or not isinstance(attempt.get("plan"), str) or not attempt.get("plan"):
        errors.append("attempt 必须只含 id 与 plan")
    if not isinstance(raw.get("attemptHistory"), list):
        errors.append("attemptHistory 不是 list")
    predecessors = raw.get("predecessors")
    if predecessors is not None and (
        not isinstance(predecessors, list)
        or not predecessors
        or any(not isinstance(item, str) or not item.strip() for item in predecessors)
    ):
        errors.append("predecessors 必须是 null 或非空路径 list")
    if not isinstance(tickets, dict):
        errors.append("tickets 不是 object")
    else:
        for identifier, row in tickets.items():
            if not isinstance(identifier, str) or not isinstance(row, dict) or row.get("state") not in TICKET_STATES:
                errors.append(f"Ticket state 无效：{identifier}")
    if not isinstance(raw.get("evidenceIndex"), dict):
        errors.append("evidenceIndex 不是 object")
    if not isinstance(raw.get("activeCheckpoints"), dict):
        errors.append("activeCheckpoints 不是 object")
    error = "; ".join(errors) if errors else None
    return StateView(raw, not errors, error, attempt_id, ticket_ids)


def _state_ticket_errors(state: StateView, tickets: dict[str, TicketInfo]) -> list[str]:
    """Check the state portions that do not require reading projections."""
    if not state.valid or state.raw is None:
        return []
    raw = state.raw
    errors: list[str] = []
    ticket_rows = raw.get("tickets", {})
    for identifier, row in ticket_rows.items():
        if not isinstance(row, dict):
            continue
        status = row.get("state")
        if status == "RETIRED":
            allowed = {"state", "disposition", "evidence"}
            if row.get("disposition") == "superseded":
                allowed.add("successor")
            if set(row) != allowed or row.get("disposition") not in {"waived", "superseded"} or not isinstance(row.get("evidence"), str):
                errors.append(f"RETIRED Ticket {identifier} 的字段不符合 schema")
            if row.get("disposition") == "superseded" and row.get("successor") not in ticket_rows:
                errors.append(f"RETIRED superseded Ticket {identifier} 的 successor 不存在")
        elif status == "SATISFIED":
            acceptance = row.get("acceptance")
            if set(row) != {"state", "acceptance"} or not isinstance(acceptance, dict) or set(acceptance) != {"revision", "environment"}:
                errors.append(f"SATISFIED Ticket {identifier} 缺少合法 acceptance revision/environment")
            elif not COMMIT_RE.fullmatch(str(acceptance.get("revision", ""))) or not isinstance(acceptance.get("environment"), str) or not acceptance["environment"].strip():
                errors.append(f"SATISFIED Ticket {identifier} 的 acceptance revision/environment 无效")
        elif status == "BLOCKED":
            if set(row) != {"state", "evidence"} or not isinstance(row.get("evidence"), str):
                errors.append(f"BLOCKED Ticket {identifier} 缺少 evidence")
        elif status == "NEEDS-REVALIDATION":
            if set(row) not in ({"state"}, {"state", "evidence"}) or ("evidence" in row and not isinstance(row["evidence"], str)):
                errors.append(f"NEEDS-REVALIDATION Ticket {identifier} 的字段不符合 schema")
        elif status == "PENDING" and set(row) != {"state"}:
            errors.append(f"PENDING Ticket {identifier} 含额外字段")

    index = raw.get("evidenceIndex", {})
    if isinstance(index, dict):
        unknown_tickets = set(index) - set(ticket_rows)
        if unknown_tickets:
            errors.append("evidenceIndex 含未知 Ticket：" + ", ".join(sorted(unknown_tickets)))
        for identifier, claim_map in index.items():
            if not isinstance(claim_map, dict):
                errors.append(f"evidenceIndex[{identifier}] 不是 claim mapping")
                continue
            known_claims = set(tickets.get(identifier, TicketInfo(identifier, None, "", False)).claims)
            for claim, records in claim_map.items():
                if claim not in known_claims:
                    errors.append(f"evidenceIndex[{identifier}] 含未知 claim：{claim}")
                if not isinstance(records, list):
                    errors.append(f"evidenceIndex[{identifier}][{claim}] 不是 list")
                    continue
                for record in records:
                    required = {"timing", "artifact", "revision", "environment", "conclusion"}
                    if not isinstance(record, dict) or not required <= set(record):
                        errors.append(f"evidenceIndex[{identifier}][{claim}] evidence 字段不完整")
                        continue
                    if record.get("timing") not in {"early-falsification", "remaining-completion"}:
                        errors.append(f"evidenceIndex[{identifier}][{claim}] timing 无效")
                    if record.get("conclusion") not in {"supporting", "contradictory", "inconclusive"}:
                        errors.append(f"evidenceIndex[{identifier}][{claim}] conclusion 无效")
                    if not all(isinstance(record.get(field), str) and record.get(field).strip() for field in ("artifact", "revision", "environment")):
                        errors.append(f"evidenceIndex[{identifier}][{claim}] artifact/revision/environment 无效")
                    elif not COMMIT_RE.fullmatch(record["revision"]):
                        errors.append(f"evidenceIndex[{identifier}][{claim}] revision 不是 commit ID")
                    if "invalidatedBy" in record and record["invalidatedBy"] is not None and not isinstance(record["invalidatedBy"], str):
                        errors.append(f"evidenceIndex[{identifier}][{claim}] invalidatedBy 无效")

    checkpoints = raw.get("activeCheckpoints", {})
    if isinstance(checkpoints, dict):
        for subject, value in checkpoints.items():
            if subject != "attempt" and (not isinstance(subject, str) or not subject.startswith("ticket:") or subject.split(":", 1)[1] not in ticket_rows):
                errors.append(f"activeCheckpoints subject 无效：{subject}")
            if not isinstance(value, dict) or set(value) != {"next", "blocker", "evidence"}:
                errors.append(f"activeCheckpoints[{subject}] 字段不完整")
                continue
            if not isinstance(value.get("next"), str) or not value["next"].strip() or (value.get("blocker") is not None and not isinstance(value.get("blocker"), str)) or not isinstance(value.get("evidence"), list) or not all(isinstance(item, str) for item in value["evidence"]):
                errors.append(f"activeCheckpoints[{subject}] 值类型无效")

    graph = {identifier: [target for _, target in ticket.dependencies] for identifier, ticket in tickets.items()}
    for identifier, dependencies in graph.items():
        for target in dependencies:
            if target not in tickets:
                errors.append(f"Ticket {identifier} typed dependency 指向不存在的 {target}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            errors.append(f"Ticket dependency cycle at {identifier}")
            return
        if identifier in visited:
            return
        visiting.add(identifier)
        for target in graph.get(identifier, []):
            if target in graph:
                visit(target)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in graph:
        visit(identifier)
    return errors


def _parse_ticket(identifier: str, relative: str | None, text: str, expected_attempt: str | None) -> TicketInfo:
    if not text:
        return TicketInfo(identifier, relative, text, False, error="Ticket 文件为空")
    id_match = TICKET_ID_RE.search(text)
    parsed_identifier = id_match.group(1) if id_match else identifier
    if parsed_identifier != identifier:
        return TicketInfo(identifier, relative, text, False, error="Ticket ID 与文件/state 不一致")
    attempt_match = ATTEMPT_ID_RE.search(text)
    if expected_attempt and (not attempt_match or attempt_match.group(1) != expected_attempt):
        return TicketInfo(identifier, relative, text, False, error="Attempt ID 与当前 attempt 不一致")

    claims = list(dict.fromkeys(CLAIM_RE.findall(text) + ASCII_CLAIM_RE.findall(text)))
    safety_claims = [claim for claim in claims if claim.upper().startswith("INV-")]
    dependencies: list[tuple[str, str]] = []
    section = DEPENDENCY_HEADING_RE.search(text)
    if section:
        for line in section.group(1).splitlines():
            stripped = line.strip()
            if not stripped or stripped.lower() in {"- none", "- 无"}:
                continue
            match = re.fullmatch(r"-\s*(implementation|acceptance|release)\s*:\s*([^\s]+)", stripped, re.I)
            if match:
                dependencies.append((match.group(1).lower(), match.group(2)))
    return TicketInfo(
        identifier,
        relative,
        text,
        bool(claims),
        claims=claims,
        safety_claims=safety_claims,
        dependencies=dependencies,
    )


def _parse_trail(view: FileView) -> TrailView:
    if not view.present:
        return TrailView(False, [], None)
    if view.error:
        return TrailView(True, [], view.error)
    assert view.text is not None
    rows: list[dict[str, Any]] = []
    facts: list[TrailFact] = []
    errors: list[str] = []
    unknown_fact_keys: set[str] = set()

    def add_fact(
        row: dict[str, Any],
        row_index: int,
        key: Any,
        value: Any,
        ts: Any,
    ) -> None:
        canonical = _canonical_fact_key(key)
        if canonical is None:
            errors.append(f"trail.jsonl 第 {row_index} 行 fact 缺少非空 key")
            return
        if canonical not in FACT_KEYS:
            unknown_fact_keys.add(str(key))
            return
        if ts is not None and not isinstance(ts, str):
            errors.append(f"trail.jsonl 第 {row_index} 行 fact ts 不是字符串")
            ts = None
        facts.append(
            TrailFact(
                key=canonical,
                value=value,
                subject=row.get("subject") if isinstance(row.get("subject"), str) else None,
                ts=ts.strip() if isinstance(ts, str) and ts.strip() else None,
                seq=row.get("seq"),
                row_index=row_index,
            )
        )

    for number, line in enumerate(view.text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"trail.jsonl 第 {number} 行不是合法 JSON：{exc.msg}")
            continue
        if isinstance(value, dict):
            rows.append(value)
            kind = str(value.get("kind", "")).lower()
            if kind == "escape":
                # Escape is a structured event, not a fact. Keep the row
                # available to event consumers without requiring its fields.
                continue
            legacy_ts = value.get("ts", value.get("timestamp"))
            legacy_facts = value.get("facts")
            if legacy_facts is not None:
                if not isinstance(legacy_facts, dict):
                    errors.append(f"trail.jsonl 第 {number} 行 facts 不是 object")
                else:
                    for key, fact_value in legacy_facts.items():
                        add_fact(value, number, key, fact_value, legacy_ts)
            if kind == "fact" and legacy_facts is None:
                required = [name for name in ("key", "value", "ts") if name not in value]
                if required:
                    errors.append(
                        f"trail.jsonl 第 {number} 行 kind=fact 缺少字段：{', '.join(required)}"
                    )
                elif not isinstance(value.get("ts"), str) or not value["ts"].strip():
                    errors.append(f"trail.jsonl 第 {number} 行 kind=fact 的 ts 必须是非空字符串")
                else:
                    add_fact(value, number, value.get("key"), value.get("value"), value.get("ts"))
            elif kind == "fact" and any(name in value for name in ("key", "value", "ts")):
                errors.append(f"trail.jsonl 第 {number} 行 kind=fact 不得同时使用 facts 与 key/value/ts")
        else:
            errors.append(f"trail.jsonl 第 {number} 行不是 object")
    # An unknown key is ignored and reported, never fatal: the trail is append-only, so
    # refusing to render would leave the package permanently unnavigable over one row
    # that cannot be taken back.
    return TrailView(
        True,
        rows,
        "; ".join(errors) if errors else None,
        facts=facts,
        unknown_fact_keys=tuple(sorted(unknown_fact_keys)),
    )


def _parse_gate(view: FileView) -> GateView:
    if not view.present:
        return GateView(False, None, None)
    if view.error:
        return GateView(True, None, None, error=view.error)
    assert view.text is not None
    verdict_match = re.search(r"(?im)^-\s*(?:Verdict|判定)\s*[:：]\s*(pass|fail|blocked|defer|undecided)\s*$", view.text)
    commit_match = re.search(r"(?im)^-\s*(?:Comparison commit|比较提交)\s*[:：]\s*([0-9a-fA-F]{7,64})\s*$", view.text)
    if not verdict_match:
        return GateView(True, None, None, view.text, "gate.md 缺少 Verdict")
    return GateView(True, verdict_match.group(1).lower(), commit_match.group(1) if commit_match else None, view.text)


def _finding_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?im)^#{2,6}\s+(.+?)\s*$", text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end]
        identifier_match = FINDING_ID_RE.search(heading)
        if identifier_match:
            identifier = identifier_match.group(0).upper()
        elif re.search(r"发现|finding", heading, re.I) and not re.search(r"提升规则|promotion", heading, re.I):
            identifier = f"FINDING-{len(blocks) + 1}"
        else:
            continue
        blocks.append((identifier, block))
    return blocks


def _parse_finding(identifier: str, block: str) -> FindingInfo:
    status_match = re.search(r"(?im)^\s*[-*]?\s*(?:状态|Status)\s*[:：]\s*([^\n]+)", block)
    status = status_match.group(1).strip() if status_match else None
    track_match = re.search(r"(?i)\bTrack\s*([A-D])\b|\b轨道\s*([A-D])\b", block)
    track = next((item for item in track_match.groups() if item), None) if track_match else None
    source_match = re.search(r"(?im)^\s*[-*]?\s*(?:finding[_ -]?source|来源)\s*[:：]\s*([^\n]+)", block)
    source = source_match.group(1).strip() if source_match else None
    closed = bool(re.search(r"(?i)\b(?:closed|resolved|retired|complete)\b|已关闭|已解决|已完成", status or ""))
    explicit_pending = bool(re.search(r"(?i)source[_ -]?recheck\s*[:：=]?\s*pending|source recheck.*pending|待.*(?:复核|重查)", block))
    grade = re.search(r"(?i)\b(?:P[123]|editorial)\b|定级\s*[:：]\s*(?:P[123]|editorial)", block)
    grading_pending = not closed and ("grading_pending" in block or "待定级" in block or grade is None)
    route = bool(re.search(r"(?i)Decision|Spec|Execution Record|Durable Delta|已分流|分流到", block))
    triage_pending = not closed and (
        bool(re.search(r"(?i)triage\s*[:：=]?\s*pending|未分流|待分流", block)) or not route
    )
    return FindingInfo(
        identifier=identifier,
        block=block,
        status=status,
        track=track,
        source=source,
        source_recheck_pending=explicit_pending,
        grading_pending=grading_pending,
        triage_pending=triage_pending,
    )


def _parse_findings(view: FileView) -> FindingsView:
    if not view.present:
        return FindingsView(False, "", [])
    if view.error:
        return FindingsView(True, "", [], view.error)
    assert view.text is not None
    findings = [_parse_finding(identifier, block) for identifier, block in _finding_blocks(view.text)]
    return FindingsView(True, view.text, findings)


def _intake_candidates() -> tuple[str, ...]:
    return (
        ".impl-package/intake.jsonl",
        ".impl-package/intake-queue.jsonl",
        ".impl-package/intake.json",
        "execution/intake.jsonl",
        "execution/intake-queue.jsonl",
        "execution/intake.json",
        "intake.jsonl",
        "intake.json",
    )


def _intake_directory_candidates() -> tuple[str, ...]:
    return (
        ".impl-package/intake",
        ".impl-package/intake-queue",
        "execution/intake",
        "execution/intake-queue",
        "intake",
        "intake-queue",
    )


def _parse_intake(reader: PackageReader) -> IntakeView:
    for relative in _intake_candidates():
        view = reader.read(relative)
        if not view.present:
            continue
        if view.error:
            return IntakeView(True, None, relative, view.error)
        assert view.text is not None
        if not view.text.strip():
            return IntakeView(True, False, relative)
        try:
            value = json.loads(view.text)
            if isinstance(value, list):
                return IntakeView(True, bool(value), relative)
            if isinstance(value, dict):
                items = value.get("items", value.get("queue"))
                if isinstance(items, list):
                    return IntakeView(True, bool(items), relative)
        except json.JSONDecodeError:
            pass
        return IntakeView(True, bool([line for line in view.text.splitlines() if line.strip()]), relative)
    for relative in _intake_directory_candidates():
        entries = reader.directory_has_entries(relative)
        if entries is not None:
            return IntakeView(True, entries, relative)
    return IntakeView(False, None)


def _build_snapshot(
    reader: PackageReader,
    validation_result: ValidationResult | None = None,
    compaction_pressure: CompactionPressureResult | None = None,
) -> Snapshot:
    warnings = list(reader.warnings)
    state = _parse_state(reader.read(STATE_REL))
    ticket_files: dict[str, tuple[str, str]] = {}
    for relative in reader.list_ticket_files():
        view = reader.read(relative)
        if view.error:
            warnings.append(view.error)
            continue
        if view.text is None:
            continue
        id_match = TICKET_ID_RE.search(view.text)
        if id_match:
            ticket_files[id_match.group(1)] = (relative, view.text)

    tickets: dict[str, TicketInfo] = {}
    ids = sorted(set(state.ticket_ids) | set(ticket_files))
    for identifier in ids:
        if identifier in ticket_files:
            relative, text = ticket_files[identifier]
            ticket = _parse_ticket(identifier, relative, text, state.attempt_id)
        else:
            ticket = TicketInfo(identifier, None, "", False, error="Ticket 文件缺失")
        tickets[identifier] = ticket
        if not ticket.valid:
            warnings.append(f"{identifier}: {ticket.error or 'Ticket 文件无法解析'}")

    if state.valid:
        expected = set(state.ticket_ids)
        actual = set(tickets)
        if expected != actual or any(not tickets[key].valid for key in expected):
            state.valid = False
            state.error = "state 与 tickets/*.md 不一致或 Ticket 文件无法解析"
            warnings.append(state.error)
    state_errors = _state_ticket_errors(state, tickets)
    if state_errors:
        state.valid = False
        state.error = "; ".join(state_errors)
        warnings.extend(state_errors)

    attempt_id = state.attempt_id
    trail = TrailView(False, [])
    if attempt_id:
        trail = _parse_trail(reader.read(_active_trail_relative_path(attempt_id)))
        if trail.error:
            warnings.append(trail.error)
        if trail.unknown_fact_keys:
            warnings.append(_unknown_fact_key_notice(trail.unknown_fact_keys))
    gate = _parse_gate(reader.read(GATE_REL))
    if gate.error:
        warnings.append(gate.error)
    findings = _parse_findings(reader.read(FINDINGS_REL))
    if findings.error:
        warnings.append(findings.error)
    intake = _parse_intake(reader)
    if intake.error:
        warnings.append(intake.error)
    return Snapshot(
        package=reader.package,
        reader=reader,
        state=state,
        tickets=tickets,
        trail=trail,
        gate=gate,
        findings=findings,
        intake=intake,
        validation_result=validation_result,
        compaction_pressure=compaction_pressure,
        head=reader.head(),
        warnings=warnings,
    )


def _fact_value(
    value: Any,
    reason: str | None = None,
    *,
    ts: str | None = None,
    seq: Any = None,
) -> Fact:
    return Fact(value=value, known=True, reason=reason, ts=ts, seq=seq)


def _evidence_link(record: dict[str, Any]) -> tuple[str, str, str, str] | None:
    def string(*names: str) -> str | None:
        for name in names:
            value = record.get(name)
            if isinstance(value, str) and value.strip():
                return value
        return None

    artifact = string("artifact", "ref", "evidence_ref", "evidence", "direct_evidence")
    claim = string("claim", "claim_id", "claimId")
    revision = string("revision", "commit", "head")
    environment = string("environment", "env")
    if None in {artifact, claim, revision, environment}:
        return None
    return artifact, claim, revision, environment


def _evidence_invalidated(record: dict[str, Any]) -> bool:
    return bool(record.get("invalidatedBy") or record.get("invalidated"))


def _event_kind(row: dict[str, Any]) -> str:
    return str(row.get("kind", "")).lower()


def _result_event(row: dict[str, Any]) -> bool:
    return _event_kind(row) in {"result", "worker-return"}


def _event_identifier(row: dict[str, Any]) -> str | None:
    for name in ("seq", "id", "dispatch_id", "dispatchId", "decision_id", "decisionId"):
        value = row.get(name)
        if value is not None:
            return str(value)
    return None


def _dispatch_is_running(row: dict[str, Any]) -> bool:
    return (
        _event_kind(row) == "dispatch"
        and str(row.get("outcome", "")).upper() == "RUNNING"
        and _parse_bool(row.get("returned")) is False
    )


class FactContext:
    """Facts for one package/attempt/ticket/finding subject."""

    def __init__(self, snapshot: Snapshot, kind: str, identifier: str) -> None:
        self.snapshot = snapshot
        self.kind = kind
        self.identifier = identifier

    @property
    def subject(self) -> str:
        if self.kind == "ticket":
            return f"ticket:{self.identifier}"
        if self.kind == "finding":
            return f"finding:{self.identifier}"
        return self.kind

    @property
    def ticket(self) -> TicketInfo | None:
        return self.snapshot.tickets.get(self.identifier) if self.kind == "ticket" else None

    def unknown(self, reason: str) -> Fact:
        return Fact.unknown(reason)

    def _missing_fact(self, key: str) -> Fact:
        if not self.snapshot.trail.present or self.snapshot.trail.error:
            return self.unknown("trail.jsonl 不存在或无法读取")
        if self._trail_is_empty():
            return self.unknown("trail.jsonl 没有事件")
        if key in FACT_DEFAULTS:
            value = FACT_DEFAULTS[key]
            return _fact_value(value, reason=f"{key} 未声明，采用 fail-closed 缺省值 {value}")
        return self.unknown(f"{key} 缺少 kind=fact 的显式声明")

    def state(self) -> dict[str, Any] | None:
        if not self.snapshot.state.valid:
            return None
        return self.snapshot.state.raw

    def state_required(self) -> Fact | None:
        if self.snapshot.state.valid:
            return None
        return self.unknown(self.snapshot.state.error or "state.json 无法判定")

    def state_ticket(self) -> dict[str, Any] | None:
        state = self.state()
        if state is None or self.kind != "ticket":
            return None
        row = state.get("tickets", {}).get(self.identifier)
        return row if isinstance(row, dict) else None

    def evidence_records(self) -> list[dict[str, Any]] | None:
        state = self.state()
        if state is None or self.kind != "ticket":
            return None
        index = state.get("evidenceIndex", {})
        if not isinstance(index, dict):
            return None
        claim_map = index.get(self.identifier, {})
        if not isinstance(claim_map, dict):
            return None
        records: list[dict[str, Any]] = []
        for claim, values in claim_map.items():
            if isinstance(values, list):
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    record = dict(item)
                    record.setdefault("claim", claim)
                    records.append(record)
        return records

    def _subject_rows(self, *, all_attempt_rows: bool = False) -> list[dict[str, Any]] | None:
        if not self.snapshot.trail.present or self.snapshot.trail.error:
            return None
        rows = self.snapshot.trail.rows
        if self.kind == "ticket":
            accepted = {self.subject, self.identifier}
            return [row for row in rows if row.get("subject") in accepted]
        if self.kind == "finding":
            accepted = {self.subject, self.identifier}
            return [row for row in rows if row.get("subject") in accepted]
        if all_attempt_rows:
            return rows
        return [row for row in rows if row.get("subject") in {None, "", "attempt"}]

    def _trail_is_empty(self) -> bool:
        trail = self.snapshot.trail
        return trail.error is None and (not trail.present or not trail.rows)

    def _observation_rows(self, *, all_attempt_rows: bool = False) -> list[dict[str, Any]] | None:
        rows = self._subject_rows(all_attempt_rows=all_attempt_rows)
        if rows is None and self._trail_is_empty():
            return []
        return rows

    def _fact_subject_matches(self, subject: str | None) -> bool:
        if self.kind == "ticket":
            return subject in {self.subject, self.identifier}
        if self.kind == "finding":
            return subject in {self.subject, self.identifier}
        return subject in {None, "", "attempt"}

    def _latest_fact(self, key: str) -> Fact | None:
        canonical = _canonical_fact_key(key)
        if canonical is None or not self.snapshot.trail.present or self.snapshot.trail.error:
            return None
        entries = [
            fact
            for fact in self.snapshot.trail.facts
            if fact.key == canonical and self._fact_subject_matches(fact.subject)
        ]
        if not entries:
            return None
        latest = max(entries, key=_trail_fact_sort_key)
        value = latest.value
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        return _fact_value(value, ts=latest.ts, seq=latest.seq)

    def _explicit(self, key: str) -> Fact | None:
        typed = self._latest_fact(key)
        if typed is not None:
            return typed
        rows = self._subject_rows()
        if rows is not None:
            aliases = (key, key.replace(".", "_"), key.rsplit(".", 1)[-1])
            for row in reversed(rows):
                containers: list[dict[str, Any]] = [row]
                for name in ("facts", "when", "derived"):
                    value = row.get(name)
                    if isinstance(value, dict):
                        containers.append(value)
                for container in containers:
                    for alias in aliases:
                        if alias in container:
                            parsed = container[alias]
                            if isinstance(parsed, dict) and "value" in parsed:
                                parsed = parsed["value"]
                            return _fact_value(parsed)
        if self.ticket is not None:
            for alias in (key, key.replace(".", "_"), key.rsplit(".", 1)[-1]):
                match = re.search(
                    rf"(?im)^\s*[-*]?\s*`?{re.escape(alias)}`?\s*[:：=]\s*([^\n]+)",
                    self.ticket.text,
                )
                if match:
                    raw = match.group(1).strip().strip("`")
                    boolean = _parse_bool(raw)
                    return _fact_value(boolean if boolean is not None else raw)
        return None

    def _explicit_bool(self, key: str) -> Fact | None:
        fact = self._explicit(key)
        if fact is None:
            return None
        value = _parse_bool(fact.value)
        if value is not None:
            return _fact_value(value, ts=fact.ts, seq=fact.seq)
        if fact.ts is not None or fact.seq is not None:
            return Fact(None, False, f"{key} 的显式值不是布尔值", fact.ts, fact.seq)
        return self.unknown(f"{key} 的显式值不是布尔值")

    def active_checkpoint_present(self) -> Fact:
        state = self.state()
        if state is None:
            return self.state_required() or self.unknown("state.json 无法判定")
        checkpoints = state.get("activeCheckpoints", {})
        if not isinstance(checkpoints, dict):
            return self.unknown("activeCheckpoints 不是 object")
        subject = self.subject
        return _fact_value(subject in checkpoints)

    def _release(self, identifier: str, visiting: set[str] | None = None) -> bool | None:
        state = self.state()
        if state is None:
            return None
        tickets = state.get("tickets")
        if not isinstance(tickets, dict) or identifier not in tickets:
            return None
        visiting = set() if visiting is None else visiting
        if identifier in visiting:
            return False
        visiting.add(identifier)
        row = tickets[identifier]
        if not isinstance(row, dict):
            return None
        status = row.get("state")
        if status == "SATISFIED":
            return True
        if status != "RETIRED":
            return False
        if row.get("disposition") == "waived":
            return True
        successor = row.get("successor")
        return self._release(successor, visiting) if isinstance(successor, str) else False

    def dependency_released(self, kind: str) -> Fact:
        if self.state() is None:
            return self.state_required() or self.unknown("state.json 无法判定")
        if self.ticket is None or not self.ticket.valid:
            return self.unknown("Ticket 文件缺失或无法解析 typed dependency")
        values = [self._release(target) for edge, target in self.ticket.dependencies if edge == kind]
        if any(value is None for value in values):
            return self.unknown(f"{kind} dependency 的 Ticket 状态无法判定")
        return _fact_value(all(values))

    def ready_ticket_ids(self) -> Fact:
        state = self.state()
        if state is None:
            return self.state_required() or self.unknown("state.json 无法判定")
        if not self.snapshot.tickets or any(not ticket.valid for ticket in self.snapshot.tickets.values()):
            return self.unknown("Ticket 文件集合不完整")
        ready: list[str] = []
        for identifier, row in state.get("tickets", {}).items():
            if not isinstance(row, dict) or row.get("state") != "PENDING":
                continue
            ticket = self.snapshot.tickets.get(identifier)
            if ticket is None:
                return self.unknown(f"缺少 Ticket {identifier}")
            values = [self._release(target) for edge, target in ticket.dependencies if edge == "implementation"]
            if any(value is None for value in values):
                return self.unknown(f"Ticket {identifier} 的 implementation dependency 无法判定")
            if all(values):
                ready.append(identifier)
        return _fact_value(ready)

    def ticket_evidence_groups(self) -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]] | None:
        records = self.evidence_records()
        if records is None:
            return None
        groups: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for record in records:
            revision = record.get("revision")
            environment = record.get("environment")
            claim = record.get("claim")
            if not isinstance(revision, str) or not isinstance(environment, str) or not isinstance(claim, str):
                continue
            if record.get("invalidatedBy"):
                continue
            groups[(revision, environment)][claim].append(record)
        return groups

    def revision_parseable(self, revision: str) -> bool | None:
        if self.snapshot.reader.repo is None:
            return None
        return self.snapshot.reader.resolve_commit(revision) is not None

    def acceptance_pair(self) -> tuple[str, str] | None:
        row = self.state_ticket()
        if isinstance(row, dict):
            acceptance = row.get("acceptance")
            if isinstance(acceptance, dict) and isinstance(acceptance.get("revision"), str) and isinstance(acceptance.get("environment"), str):
                return acceptance["revision"], acceptance["environment"]
            if row.get("state") != "PENDING":
                return None
        groups = self.ticket_evidence_groups()
        if groups:
            for revision, environment in groups:
                if self.revision_parseable(revision) is not False:
                    return revision, environment
        return None

    def last_outcome(self) -> Fact:
        rows = self._observation_rows()
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in reversed(rows):
            if _result_event(row) and isinstance(row.get("outcome"), str):
                return _fact_value(row["outcome"])
        for row in reversed(rows):
            if isinstance(row.get("outcome"), str):
                return _fact_value(row["outcome"])
        return _fact_value(None)

    def _all_relevant_rows(self) -> list[dict[str, Any]] | None:
        rows = self._subject_rows(all_attempt_rows=self.kind == "attempt")
        if rows is None:
            return None
        if self.kind == "attempt":
            return rows
        return rows

    def _actions_since_checkpoint(self) -> Fact:
        rows = self._subject_rows()
        if rows is None or self._trail_is_empty():
            return self.unknown("trail.jsonl 不存在或无法读取")
        checkpoint = self.active_checkpoint_present()
        if checkpoint.known and not checkpoint.value:
            return _fact_value(0)
        markers = []
        for index, row in enumerate(rows):
            chosen = str(row.get("chosen", ""))
            situation = str(row.get("situation", ""))
            if (
                _event_kind(row) == "checkpoint"
                or "checkpoint" in chosen.lower()
                or "checkpoint" in situation.lower()
                or row.get("checkpoint") is True
            ):
                markers.append(index)
        if markers:
            return _fact_value(len(rows) - markers[-1] - 1)
        if checkpoint.known and checkpoint.value:
            # The active checkpoint is durable state.  A legacy session fact
            # is only a compatibility declaration; every other typed fact or
            # action is evidence that the resumed session has already moved.
            def is_session_declaration(row: dict[str, Any]) -> bool:
                if row.get("key") == "attempt.session_resumed":
                    return True
                facts = row.get("facts")
                return isinstance(facts, dict) and set(facts) == {"attempt.session_resumed"}

            return _fact_value(sum(1 for row in rows if not is_session_declaration(row)))
        return _fact_value(0)

    def _last_ticket_terminal_transition(self) -> Fact:
        rows = self._subject_rows(all_attempt_rows=self.kind == "attempt")
        if rows is None:
            if self._trail_is_empty():
                return _fact_value(False)
            return self.unknown("trail.jsonl 不存在或无法读取")
        if self._trail_is_empty():
            return _fact_value(False)
        transitions = [
            row
            for row in rows
            if _event_kind(row) == "result"
            and row.get("transition") == "ticket-state"
            and isinstance(row.get("subject"), str)
            and row["subject"].startswith("ticket:")
        ]
        if not transitions:
            return _fact_value(False)
        last = transitions[-1]
        target = last.get("to", last.get("outcome"))
        return _fact_value(isinstance(target, str) and target.upper() in {"SATISFIED", "RETIRED"})

    def _open_dispatch(self) -> bool | None:
        rows = self._subject_rows()
        if rows is None or self._trail_is_empty():
            return None
        decisions = [row for row in rows if _event_kind(row) == "decision"]
        results = {
            str(row.get(name))
            for row in rows
            if _result_event(row)
            for name in ("of", "decision", "dispatch_id", "dispatchId", "decision_id", "decisionId")
            if row.get(name) is not None
        }
        for row in rows:
            if _dispatch_is_running(row):
                identifier = _event_identifier(row)
                if identifier is None or identifier not in results:
                    return True
        for row in decisions:
            chosen = str(row.get("chosen", ""))
            identifier = _event_identifier(row)
            if ("dispatch" in chosen or "sdd" in chosen) and identifier not in results:
                return True
        return False

    def _trail_signal(self, key: str) -> Fact:
        explicit = self._explicit_bool(key)
        if explicit is not None:
            return explicit
        return self._missing_fact(key)

    def _trail_availability(self, key: str) -> Fact:
        explicit = self._explicit_bool(key)
        if explicit is not None:
            return explicit
        return self._missing_fact(key)

    def _last_worker_mode(self) -> Fact:
        explicit = self._explicit("trail.last_worker_mode")
        if explicit is not None:
            value = str(explicit.value).lower()
            return _fact_value(value) if value in {"investigate", "implement", "fix", "verify", "review"} else explicit
        rows = self._observation_rows()
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in reversed(rows):
            containers: list[dict[str, Any]] = [row]
            for name in ("facts", "when", "derived", "worker", "envelope", "result"):
                value = row.get(name)
                if isinstance(value, dict):
                    containers.append(value)
            for container in containers:
                for name in ("worker_mode", "workerMode", "mode"):
                    value = container.get(name)
                    if isinstance(value, str) and value.lower() in {"investigate", "implement", "fix", "verify", "review"}:
                        return _fact_value(value.lower())
            chosen = str(row.get("chosen", ""))
            match = re.search(r"(?:worker[_ -]?mode|mode)\s*[:=]\s*(investigate|implement|fix|verify|review)\b", chosen, re.I)
            if match:
                return _fact_value(match.group(1).lower())
        return _fact_value(None)

    def _last_envelope_valid(self) -> Fact:
        explicit = self._explicit_bool("trail.envelope_valid")
        if explicit is not None:
            return explicit
        rows = self._subject_rows()
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in reversed(rows):
            containers: list[dict[str, Any]] = [row]
            for name in ("facts", "when", "derived", "envelope", "result"):
                value = row.get(name)
                if isinstance(value, dict):
                    containers.append(value)
            for container in containers:
                if "envelope_valid" in container or "envelopeValid" in container:
                    value = container.get("envelope_valid", container.get("envelopeValid"))
                    parsed = _parse_bool(value)
                    return _fact_value(parsed) if parsed is not None else self.unknown("trail.envelope_valid 不是布尔值")
        return self.unknown("trail.envelope_valid 没有列出的机械输入")

    def _decision_without_result(self) -> Fact:
        rows = self._observation_rows(all_attempt_rows=self.kind == "attempt")
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")

        decisions = {
            identifier
            for row in rows
            if _event_kind(row) == "decision"
            for identifier in [_event_identifier(row)]
            if identifier is not None
        }
        results = {
            str(row.get(name))
            for row in rows
            if _result_event(row)
            for name in ("of", "decision", "dispatch_id", "dispatchId", "decision_id", "decisionId")
            if row.get(name) is not None
        }
        pending_dispatch = any(
            _dispatch_is_running(row)
            and (_event_identifier(row) is None or _event_identifier(row) not in results)
            for row in rows
        )
        return _fact_value(bool(decisions - results) or pending_dispatch)

    def _direct_evidence_returned(self) -> bool | None:
        evidence = self.direct_evidence_payloads()
        return bool(evidence.value) if evidence.known else None

    def direct_evidence_payloads(self) -> Fact:
        """Return direct result evidence in the current ticket trail.

        A trail row may put the payload directly on the row, or under one of
        the historic `ref`/`evidence` aliases.  Keep the enclosing row as
        fallback metadata so an artifact payload can still pair with its
        claim, revision, and environment.
        """
        rows = self._observation_rows()
        if rows is None:
            return self.unknown(self.snapshot.trail.error or "trail.jsonl 不存在或无法读取")
        keys = ("ref", "evidence", "artifact", "evidence_ref", "direct_evidence")
        payloads: list[dict[str, Any]] = []
        for row in rows:
            if not _result_event(row):
                continue
            for key in keys:
                value = row.get(key)
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if not item:
                        continue
                    payload = dict(row)
                    if isinstance(item, dict):
                        payload.update(item)
                    elif isinstance(item, str):
                        payload.setdefault("artifact", item)
                    else:
                        payload.setdefault("artifact", item)
                    payloads.append(payload)
        return _fact_value(payloads)

    def _incomplete_count(self) -> Fact:
        rows = self._observation_rows()
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        count = 0
        for row in reversed(rows):
            if not _result_event(row):
                continue
            if row.get("outcome") == "INCOMPLETE":
                count += 1
            else:
                break
        return _fact_value(count)

    def _has_investigate(self) -> Fact:
        rows = self._observation_rows(all_attempt_rows=self.kind == "attempt")
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in rows:
            situation = str(row.get("situation", ""))
            chosen = str(row.get("chosen", ""))
            outcome = str(row.get("outcome", ""))
            if situation.startswith("ticket.investigate.") or "investigate" in chosen.lower() or outcome in {"EVIDENCE_GAP", "EVIDENCE_SUFFICIENT"}:
                return _fact_value(True)
        return _fact_value(False)

    def _has_investigate_dispatch(self) -> Fact:
        rows = self._subject_rows()
        if rows is None or self._trail_is_empty():
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in rows:
            kind = _event_kind(row)
            situation = str(row.get("situation", ""))
            chosen = str(row.get("chosen", ""))
            outcome = str(row.get("outcome", ""))
            if situation.startswith("ticket.investigate."):
                return _fact_value(True)
            if kind in {"decision", "dispatch"} and "investigate" in chosen.lower():
                return _fact_value(True)
            if kind in {"result", "worker-return"} and outcome in {"EVIDENCE_GAP", "EVIDENCE_SUFFICIENT"}:
                return _fact_value(True)
            containers: list[dict[str, Any]] = [row]
            for name in ("facts", "when", "derived", "worker", "envelope", "result"):
                value = row.get(name)
                if isinstance(value, dict):
                    containers.append(value)
            for container in containers:
                mode = container.get("worker_mode", container.get("workerMode", container.get("mode")))
                if isinstance(mode, str) and mode.lower() == "investigate" and kind in {"decision", "dispatch", "result", "worker-return"}:
                    return _fact_value(True)
        return _fact_value(False)

    def _has_early_falsification_evidence(self) -> Fact:
        records = self.evidence_records()
        if records is None:
            return self.state_required() or self.unknown("evidenceIndex 无法判定")
        return _fact_value(any(record.get("timing") == "early-falsification" for record in records))

    def _investigation_carrier_present(self) -> Fact:
        dispatched = self._has_investigate_dispatch()
        early_evidence = self._has_early_falsification_evidence()
        if dispatched.known and dispatched.value:
            return _fact_value(True)
        if early_evidence.known and early_evidence.value:
            return _fact_value(True)
        if not dispatched.known:
            return dispatched
        if not early_evidence.known:
            return early_evidence
        return _fact_value(False)

    def _investigation_context_clear(self) -> Fact:
        if self._trail_is_empty() or self.snapshot.trail.error:
            return self.unknown("trail.jsonl 不存在或无法读取")
        if self.kind != "ticket":
            return _fact_value(True)
        subjects = {None, "", "attempt", self.subject, self.identifier}
        if any(fact.subject in subjects for fact in self.snapshot.trail.facts):
            return _fact_value(False)
        return _fact_value(True)

    def _release_edge_present(self) -> Fact:
        if self.kind != "ticket":
            return self.unknown("该 key 需要 ticket subject")
        if self.ticket is None or not self.ticket.valid:
            return self.unknown("Ticket 文件缺失或无法解析 typed dependency")
        return _fact_value(any(kind == "release" for kind, _ in self.ticket.dependencies))

    def _finding_source(self) -> Fact:
        rows = self._observation_rows()
        if rows is None:
            return self.unknown("trail.jsonl 不存在或无法读取")
        for row in reversed(rows):
            if isinstance(row.get("finding_source"), str):
                return _fact_value(row["finding_source"])
            if isinstance(row.get("findingSource"), str):
                return _fact_value(row["findingSource"])
        return _fact_value(None)

    def _manual_or_explicit(self, key: str) -> Fact:
        explicit = self._explicit_bool(key)
        if explicit is not None:
            return explicit
        return self._missing_fact(key)

    def _finding(self) -> FindingInfo | None:
        if self.kind != "finding":
            return None
        for finding in self.snapshot.findings.findings:
            if finding.identifier == self.identifier:
                return finding
        return None

    def _git_since_last_trail(self) -> tuple[str | None, bool | None]:
        rows = self._subject_rows()
        if rows is None:
            return None, None
        for row in reversed(rows):
            head = row.get("head")
            if isinstance(head, str) and head:
                if self.snapshot.head is None:
                    return head, None
                return head, head != self.snapshot.head
        return None, None


# Every non-manual `when` key has a named parser.  Keep this registry explicit:
# check() uses it as the implementation coverage contract for the YAML table.
def _when_package_state_invalid(context: FactContext) -> Fact:
    return _fact_value(not context.snapshot.state.valid, context.snapshot.state.error)


def _when_package_references_live_package(context: FactContext) -> Fact:
    return _live_package_reference_fact(context.snapshot.reader)


def _load_validation_result(spec: str | None) -> ValidationResult | None:
    if spec is None:
        return None
    raw_spec = spec.strip()
    source = "inline"
    if raw_spec.startswith("{"):
        raw_text = raw_spec
    else:
        path = Path(spec)
        if not path.is_file():
            raise SituationError(f"validation result 文件不存在：{path}")
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise SituationError(f"无法读取 validation result：{path}: {exc}") from exc
        source = str(path.resolve())
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SituationError(f"validation result 不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise SituationError("validation result 顶层必须是 object")
    extra = sorted(set(value) - {"projection_drift", "source"})
    if extra:
        raise SituationError("validation result 含未知字段：" + ", ".join(extra))
    if not isinstance(value.get("projection_drift"), bool):
        raise SituationError("validation result.projection_drift 必须是 boolean")
    declared_source = value.get("source")
    if declared_source is not None:
        if not isinstance(declared_source, str) or not declared_source.strip():
            raise SituationError("validation result.source 必须是非空字符串")
        source = declared_source
    return ValidationResult(projection_drift=value["projection_drift"], source=source)


def _load_compaction_pressure(spec: str | None) -> CompactionPressureResult | None:
    if spec is None:
        return None
    raw_spec = spec.strip()
    source = "inline"
    if raw_spec.startswith("{"):
        raw_text = raw_spec
    else:
        path = Path(spec)
        if not path.is_file():
            raise SituationError(f"compaction pressure 文件不存在：{path}")
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise SituationError(f"无法读取 compaction pressure：{path}: {exc}") from exc
        source = str(path.resolve())
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SituationError(f"compaction pressure 不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise SituationError("compaction pressure 顶层必须是 object")
    allowed = {"compactions", "last_interval_min", "shrinking", "high", "explanation"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise SituationError("compaction pressure 含未知字段：" + ", ".join(extra))
    if not isinstance(value.get("high"), bool):
        raise SituationError("compaction pressure.high 必须是 boolean")
    compactions = value.get("compactions")
    if compactions is not None and (
        isinstance(compactions, bool) or not isinstance(compactions, int) or compactions < 0
    ):
        raise SituationError("compaction pressure.compactions 必须是非负整数")
    interval = value.get("last_interval_min")
    if interval is not None and (
        isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0
    ):
        raise SituationError("compaction pressure.last_interval_min 必须是非负数字或 null")
    shrinking = value.get("shrinking")
    if shrinking is not None and not isinstance(shrinking, bool):
        raise SituationError("compaction pressure.shrinking 必须是 boolean")
    explanation = value.get("explanation")
    if explanation is not None and (not isinstance(explanation, str) or not explanation.strip()):
        raise SituationError("compaction pressure.explanation 必须是非空字符串")
    return CompactionPressureResult(data=value, source=source)


def _when_package_validate_projection_drift(context: FactContext) -> Fact:
    validation = context.snapshot.validation_result
    if validation is not None:
        return _fact_value(validation.projection_drift)
    explicit = context._explicit_bool("package.validate.projection_drift")
    if explicit is not None:
        return explicit
    return context.unknown("缺少结构化 validation result 或 package.validate.projection_drift fact")


def _when_attempt_session_resumed(context: FactContext) -> Fact:
    if context.snapshot.trail.error:
        return context.unknown(context.snapshot.trail.error)
    checkpoint = context.active_checkpoint_present()
    if not checkpoint.known:
        return checkpoint
    if not checkpoint.value:
        return _fact_value(False)
    actions = context._actions_since_checkpoint()
    if not actions.known:
        return actions
    return _fact_value(actions.value == 0)


def _when_attempt_compaction_pressure_high(context: FactContext) -> Fact:
    pressure = context.snapshot.compaction_pressure
    if pressure is None:
        return context.unknown("缺少结构化 compaction pressure")
    return _fact_value(pressure.high)


def _when_attempt_active_checkpoint_present(context: FactContext) -> Fact:
    return context.active_checkpoint_present()


def _when_trail_actions_since_checkpoint(context: FactContext) -> Fact:
    return context._actions_since_checkpoint()


def _when_trail_last_ticket_terminal_transition(context: FactContext) -> Fact:
    return context._last_ticket_terminal_transition()


def _when_gate_terminal(context: FactContext) -> Fact:
    gate = context.snapshot.gate
    if gate.error:
        return context.unknown(gate.error)
    if not gate.present:
        return _fact_value(False)
    if gate.verdict is None:
        return context.unknown("gate.md 的 verdict 无法解析")
    return _fact_value(gate.verdict in TERMINAL_GATE_VERDICTS)


def _when_attempt_ready_ticket_count(context: FactContext) -> Fact:
    ready = context.ready_ticket_ids()
    if not ready.known:
        return ready
    return _fact_value(len(ready.value))


def _when_attempt_in_flight(context: FactContext) -> Fact:
    explicit = context._explicit_bool("attempt.in_flight")
    if explicit is not None:
        return explicit
    value = context._open_dispatch()
    return _fact_value(value) if value is not None else context.unknown("trail.jsonl 不存在或无法读取")


def _when_attempt_has_pending_ticket(context: FactContext) -> Fact:
    state = context.state()
    if state is None:
        return context.state_required() or context.unknown("state.json 无法判定")
    rows = state.get("tickets", {})
    return _fact_value(any(isinstance(row, dict) and row.get("state") == "PENDING" for row in rows.values()))


def _when_attempt_implementation_edges_held(context: FactContext) -> Fact:
    ready = context.ready_ticket_ids()
    pending = _when_attempt_has_pending_ticket(context)
    if not ready.known:
        return ready
    if not pending.known:
        return pending
    return _fact_value(bool(pending.value) and len(ready.value) == 0)


def _when_attempt_all_tickets_terminal(context: FactContext) -> Fact:
    state = context.state()
    if state is None:
        return context.state_required() or context.unknown("state.json 无法判定")
    rows = state.get("tickets", {})
    if not isinstance(rows, dict) or not rows:
        return _fact_value(False)
    return _fact_value(all(isinstance(row, dict) and row.get("state") in {"SATISFIED", "RETIRED"} for row in rows.values()))


def _when_ticket_state(context: FactContext) -> Fact:
    if context.kind != "ticket":
        return context.unknown("该 key 需要 ticket subject")
    row = context.state_ticket()
    if row is None:
        return context.state_required() or context.unknown(f"缺少 Ticket {context.identifier} 的 state")
    return _fact_value(row.get("state"))


def _when_ticket_blocker_maybe_resolved(context: FactContext) -> Fact:
    return context._manual_or_explicit("ticket.blocker_maybe_resolved")


def _when_trail_has_investigate(context: FactContext) -> Fact:
    return context._has_investigate()


def _when_ticket_investigation_carrier_present(context: FactContext) -> Fact:
    return context._investigation_carrier_present()


def _when_ticket_investigation_context_clear(context: FactContext) -> Fact:
    return context._investigation_context_clear()


def _when_evidence_count(context: FactContext) -> Fact:
    records = context.evidence_records()
    if records is None:
        return context.state_required() or context.unknown("evidenceIndex 无法判定")
    return _fact_value(len(records))


def _when_trail_last_outcome(context: FactContext) -> Fact:
    return context.last_outcome()


def _when_trail_handoff_in_flight(context: FactContext) -> Fact:
    return context._trail_signal("trail.handoff_in_flight")


def _when_trail_anchor_mismatch(context: FactContext) -> Fact:
    return context._trail_signal("trail.anchor_mismatch")


def _when_trail_handoff_recovery_needed(context: FactContext) -> Fact:
    return context._trail_signal("trail.handoff_recovery_needed")


def _when_trail_handoff_target_corrected(context: FactContext) -> Fact:
    return context._trail_signal("trail.handoff_target_corrected")


def _when_trail_checkpoint_refresh_needed(context: FactContext) -> Fact:
    return context._trail_signal("trail.checkpoint_refresh_needed")


def _when_trail_judgment_unfiled(context: FactContext) -> Fact:
    return context._trail_signal("trail.judgment_unfiled")


def _when_trail_checkpoint_projection_race(context: FactContext) -> Fact:
    return context._trail_signal("trail.checkpoint_projection_race")


def _when_trail_bookkeeper_partial_write(context: FactContext) -> Fact:
    return context._trail_signal("trail.bookkeeper_partial_write")


def _when_trail_reviewer_unavailable(context: FactContext) -> Fact:
    return context._trail_signal("trail.reviewer_unavailable")


def _when_trail_decision_without_result(context: FactContext) -> Fact:
    return context._decision_without_result()


def _when_evidence_sources_uniquely_decide(context: FactContext) -> Fact:
    return context._manual_or_explicit("evidence.sources_uniquely_decide")


def _when_ticket_review_required(context: FactContext) -> Fact:
    explicit = context._explicit_bool("ticket.review_required")
    if explicit is not None:
        return explicit
    rows = context._subject_rows()
    if rows is None or context._trail_is_empty():
        return context.unknown("trail.jsonl 不存在或无法读取")
    if any(str(row.get("review_state", "")).upper() == "PENDING_REVIEW" for row in rows):
        return _fact_value(True)
    if context.ticket is not None and re.search(r"(?i)review\s*[:：=]\s*required", context.ticket.text):
        return _fact_value(True)
    return _fact_value(False)


def _when_trail_direct_evidence_returned(context: FactContext) -> Fact:
    value = context._direct_evidence_returned()
    return _fact_value(value) if value is not None else context.unknown("trail.jsonl 不存在或无法读取")


def _when_evidence_indexed(context: FactContext) -> Fact:
    direct = context.direct_evidence_payloads()
    if not direct.known:
        return direct
    if not direct.value:
        return _fact_value(False)
    links = [_evidence_link(payload) for payload in direct.value]
    if any(link is None for link in links):
        return context.unknown("trail 直接证据缺少 artifact/claim/revision/environment 关联字段")
    records = context.evidence_records()
    if records is None:
        return context.state_required() or context.unknown("evidenceIndex 无法判定")
    indexed = {
        link
        for record in records
        if not _evidence_invalidated(record)
        for link in [_evidence_link(record)]
        if link is not None
    }
    return _fact_value(all(link in indexed for link in links))


def _when_ticket_review_trigger(context: FactContext) -> Fact:
    return context._manual_or_explicit("ticket.review_trigger")


def _when_ticket_safety_invariant_unfalsified(context: FactContext) -> Fact:
    if context.kind != "ticket" or context.ticket is None:
        return context.unknown("该 key 需要 ticket subject")
    if not context.ticket.valid:
        return context.unknown("Ticket 文件缺失或无法解析安全不变量")
    records = context.evidence_records()
    if records is None:
        return context.state_required() or context.unknown("evidenceIndex 无法判定")
    if not context.ticket.safety_claims:
        return _fact_value(False)
    active_claims = {
        str(record.get("claim"))
        for record in records
        if isinstance(record.get("claim"), str) and not record.get("invalidatedBy")
    }
    return _fact_value(not set(context.ticket.safety_claims) <= active_claims)


def _when_trail_incomplete_count(context: FactContext) -> Fact:
    return context._incomplete_count()


def _when_trail_last_worker_mode(context: FactContext) -> Fact:
    return context._last_worker_mode()


def _when_trail_envelope_valid(context: FactContext) -> Fact:
    return context._last_envelope_valid()


def _when_trail_finding_source(context: FactContext) -> Fact:
    return context._finding_source()


def _when_evidence_contradictory_unresolved(context: FactContext) -> Fact:
    if context.kind != "ticket" or context.ticket is None:
        return context.unknown("该 key 需要 ticket subject")
    if not context.ticket.valid:
        return context.unknown("Ticket 文件缺失或无法解析 required claims")
    records = context.evidence_records()
    if records is None:
        return context.state_required() or context.unknown("evidenceIndex 无法判定")
    pair = context.acceptance_pair()
    if pair is None:
        return _fact_value(False)
    revision, environment = pair
    required_claims = set(context.ticket.claims)
    return _fact_value(
        any(
            record.get("claim") in required_claims
            and record.get("revision") == revision
            and record.get("environment") == environment
            and record.get("conclusion") in {"contradictory", "inconclusive"}
            and not record.get("invalidatedBy")
            for record in records
        )
    )


def _when_evidence_all_required_claims_supported(context: FactContext) -> Fact:
    if context.kind != "ticket" or context.ticket is None:
        return context.unknown("该 key 需要 ticket subject")
    if not context.ticket.valid:
        return context.unknown("Ticket 文件缺失或无法解析 required claims")
    records = context.evidence_records()
    if records is None:
        return context.state_required() or context.unknown("evidenceIndex 无法判定")
    if not context.ticket.claims:
        return _fact_value(False)
    pair = context.acceptance_pair()
    if pair is not None:
        revision, environment = pair
        current = [
            record
            for record in records
            if record.get("revision") == revision
            and record.get("environment") == environment
            and not record.get("invalidatedBy")
        ]
        return _fact_value(
            all(any(record.get("claim") == claim and record.get("conclusion") == "supporting" for record in current) for claim in context.ticket.claims)
        )
    return _fact_value(False)


def _when_ticket_acceptance_edge_released(context: FactContext) -> Fact:
    return context.dependency_released("acceptance")


def _when_ticket_release_edge_present(context: FactContext) -> Fact:
    return context._release_edge_present()


def _when_ticket_acceptance_revision_parseable(context: FactContext) -> Fact:
    if context.kind != "ticket":
        return context.unknown("该 key 需要 ticket subject")
    pair = context.acceptance_pair()
    if pair is None:
        records = context.evidence_records()
        if records is None:
            return context.state_required() or context.unknown("evidenceIndex 无法判定")
        return _fact_value(False)
    parsed = context.revision_parseable(pair[0])
    if parsed is None:
        return context.unknown("当前 Git 仓库不可用，无法校验 acceptance revision")
    return _fact_value(parsed)


def _when_evidence_new_claim_conflict(context: FactContext) -> Fact:
    state = context.state()
    if state is None:
        return context.state_required() or context.unknown("state.json 无法判定")
    row = context.state_ticket()
    if row is None or row.get("state") != "SATISFIED":
        return _fact_value(False)
    return _when_evidence_contradictory_unresolved(context)


def _resolved_satisfied_acceptance_revision(context: FactContext) -> Fact:
    if context.kind != "ticket":
        return context.unknown("该 key 需要 ticket subject")
    row = context.state_ticket()
    if not isinstance(row, dict) or row.get("state") != "SATISFIED":
        return _fact_value(None)
    acceptance = row.get("acceptance")
    if not isinstance(acceptance, dict) or not isinstance(acceptance.get("revision"), str):
        return context.unknown("SATISFIED Ticket 缺少 acceptance revision")
    resolved = context.snapshot.reader.resolve_commit(acceptance["revision"])
    if resolved is None:
        return context.unknown("acceptance revision 不是当前 Git 可解析 commit")
    return _fact_value(resolved)


def _when_git_acceptance_revision_diverged(context: FactContext) -> Fact:
    if context.snapshot.head is None:
        return context.unknown("Git HEAD 无法读取")
    acceptance_revision = _resolved_satisfied_acceptance_revision(context)
    if not acceptance_revision.known:
        return acceptance_revision
    if acceptance_revision.value is None:
        return _fact_value(False)
    return _fact_value(acceptance_revision.value != context.snapshot.head)


def _diff_has_source_changes(context: FactContext, base: str, *, label: str) -> Fact:
    names = context.snapshot.reader.diff_names(base)
    if names is None:
        return context.unknown(f"无法读取 {label} 到当前 HEAD 的 Git diff")
    if not names:
        return context.unknown(f"{label} 到当前 HEAD 的 Git diff 为空，无法判定是否有源码变化")
    package_prefix = context.snapshot.reader.package_rel.as_posix() if context.snapshot.reader.package_rel else ""
    for name in names:
        relative = name.replace("\\", "/")
        if package_prefix and relative.startswith(package_prefix + "/"):
            relative = relative[len(package_prefix) + 1 :]
        path = PurePosixPath(relative)
        if relative == "docs" or relative.startswith("docs/"):
            continue
        if path.suffix.lower() == ".md":
            continue
        return _fact_value(True)
    return _fact_value(False)


def _when_git_accepted_seam_changed(context: FactContext) -> Fact:
    explicit = context._explicit_bool("git.accepted_seam_changed")
    if explicit is not None:
        return explicit
    if context.snapshot.head is None:
        return context.unknown("Git HEAD 无法读取")
    acceptance_revision = _resolved_satisfied_acceptance_revision(context)
    if not acceptance_revision.known:
        return acceptance_revision
    if acceptance_revision.value is None:
        return _fact_value(False)
    return _diff_has_source_changes(context, acceptance_revision.value, label="acceptance revision")


def _when_git_head_advanced_since_last_trail(context: FactContext) -> Fact:
    _, advanced = context._git_since_last_trail()
    return _fact_value(advanced) if advanced is not None else context.unknown("没有可用于比较的 trail head")


def _when_ticket_revalidation_pending(context: FactContext) -> Fact:
    return _when_ticket_state(context)


def _when_ticket_no_longer_needed(context: FactContext) -> Fact:
    explicit = context._explicit_bool("ticket.no_longer_needed")
    if explicit is not None:
        return explicit
    if context.ticket is not None and re.search(r"(?im)^\s*[-*]?\s*(?:no longer needed|不再需要)\s*[:：=]\s*(true|yes|是)\b", context.ticket.text):
        return _fact_value(True)
    return context.unknown("不再需要是业务判断，列出的机械输入没有裁决来源")


def _when_finding_review_track(context: FactContext) -> Fact:
    finding = context._finding()
    if not context.snapshot.findings.present:
        return context.unknown("execution-findings.md 不存在或无法读取")
    if finding is None:
        return context.unknown("找不到该 finding 的结构化记录")
    return _fact_value(finding.track)


def _when_finding_source_recheck_pending(context: FactContext) -> Fact:
    finding = context._finding()
    if not context.snapshot.findings.present:
        return context.unknown("execution-findings.md 不存在或无法读取")
    if finding is None:
        return context.unknown("找不到该 finding 的结构化记录")
    return _fact_value(finding.source_recheck_pending)


def _when_finding_closure_review_pending(context: FactContext) -> Fact:
    explicit = context._explicit_bool("finding.closure_review_pending")
    if explicit is not None:
        return explicit
    if not context.snapshot.findings.present:
        return context.unknown("execution-findings.md 不存在或无法读取")
    finding = context._finding()
    if finding is None:
        return context.unknown("找不到该 finding 的结构化记录")
    if re.search(r"(?i)closed|resolved|retired|complete|已关闭|已解决|已完成", finding.status or ""):
        return _fact_value(False)
    block = finding.block.lower()
    if re.search(r"closure.{0,30}(?:pending|awaiting)|(?:pending|awaiting).{0,30}closure", block):
        return _fact_value(True)
    return _fact_value(False)


def _when_finding_grading_pending(context: FactContext) -> Fact:
    finding = context._finding()
    if not context.snapshot.findings.present:
        return context.unknown("execution-findings.md 不存在或无法读取")
    if finding is None:
        return context.unknown("找不到该 finding 的结构化记录")
    return _fact_value(finding.grading_pending)


def _when_findings_triage_pending(context: FactContext) -> Fact:
    findings = context.snapshot.findings
    if not findings.present:
        return context.unknown("execution-findings.md 不存在或无法读取")
    if findings.error:
        return context.unknown(findings.error)
    return _fact_value(any(finding.triage_pending for finding in findings.findings))


def _when_attempt_near_terminal_gate(context: FactContext) -> Fact:
    terminal = _when_attempt_all_tickets_terminal(context)
    if not terminal.known:
        return terminal
    if terminal.value:
        return _fact_value(True)
    gate = context.snapshot.gate
    if gate.error:
        return context.unknown(gate.error)
    if not gate.present:
        return _fact_value(False)
    return _fact_value(gate.verdict is not None)


def _when_attempt_manual_verification_owner(context: FactContext) -> Fact:
    return context._manual_or_explicit("attempt.manual_verification_owner")


def _when_attempt_manual_verification_result_present(context: FactContext) -> Fact:
    return context._manual_or_explicit("attempt.manual_verification_result_present")


def _when_attempt_integration_evidence_available(context: FactContext) -> Fact:
    return context._trail_availability("attempt.integration_evidence_available")


def _when_attempt_integration_carrier_available(context: FactContext) -> Fact:
    return context._trail_availability("attempt.integration_carrier_available")


def _when_attempt_completion_claim_pending(context: FactContext) -> Fact:
    return context._manual_or_explicit("attempt.completion_claim_pending")


def _when_attempt_terminal_coverage_complete(context: FactContext) -> Fact:
    summary_fact = context._latest_fact("review.terminal_summary")
    legacy = context._explicit_bool("attempt.terminal_coverage_complete")
    if summary_fact is None and legacy is not None and legacy.known and legacy.value is False:
        return legacy
    near_terminal = _when_attempt_all_tickets_terminal(context)
    if not near_terminal.known:
        return near_terminal
    if near_terminal.value is not True:
        return context.unknown("尚未进入终审阶段，terminal-final coverage 暂不适用")

    summary = summary_fact.value if summary_fact is not None else None
    if not isinstance(summary, dict):
        return _fact_value(False, "缺少 review.terminal_summary fact")
    head = context.snapshot.head
    if not head or summary.get("comparisonHead") != head or not isinstance(summary.get("safetyApplicable"), bool):
        return _fact_value(False, "terminal_summary 的 comparisonHead 与当前 HEAD 不一致或缺少 safetyApplicable")
    run_id = summary.get("reviewRunId")
    results = summary.get("results")
    if not isinstance(run_id, str) or not run_id.strip() or not isinstance(results, list):
        return _fact_value(False, "terminal_summary 缺少 reviewRunId 或 results")
    required = {"Track A", "Track B", "Track C"}
    if summary["safetyApplicable"]:
        required.add("Track D")
    by_track = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("track"), str) or result["track"] not in REVIEW_TRACKS:
            return _fact_value(False, "terminal_summary 的 results 含未知 track")
        track = result["track"]
        if track in by_track or result.get("verdict") != "PASS":
            return _fact_value(False, f"{track} 重复出现或 verdict 不是 PASS")
        by_track[track] = result
    if not required <= by_track.keys():
        return _fact_value(False, f"缺少必需轨的 PASS：{sorted(required - by_track.keys())}")

    def artifact_text(value: Any) -> str | None:
        if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
            return None
        try:
            view = context.snapshot.reader.read(value)
        except (SituationError, OSError, ValueError):
            return None
        return view.text if not view.error else None

    artifacts = set()
    for track, result in by_track.items():
        reviewed_head = result.get("reviewedHead")
        report = artifact_text(result.get("artifact"))
        if not isinstance(reviewed_head, str) or not reviewed_head or not report:
            return _fact_value(False, f"{track} 缺少 reviewedHead 或报告文件读不到")
        artifact = _safe_relative_path(context.snapshot.package, result["artifact"])
        if artifact in artifacts:
            return _fact_value(False, f"{track} 的报告路径与其它轨重复：{artifact}")
        artifacts.add(artifact)
        header = dict(line.split(": ", 1) for line in report.splitlines()[:4] if ": " in line)
        if header != {"verdict": "PASS", "reviewed-head": reviewed_head, "review-run": run_id, "review-track": track}:
            return _fact_value(False, f"{track} 报告前四行头不匹配（verdict/reviewed-head/review-run/review-track）")
        if reviewed_head != head:
            # 复用判据由 parent 对照该轨输入裁决，保留同一 ReviewRun 的 PASS 和 delta 证据。
            if track == "Track A" or result.get("reused") is not True or not artifact_text(result.get("reuseEvidence")):
                return _fact_value(False, f"{track} 的 reviewedHead 非当前 HEAD，但缺少 reused 标记或 reuseEvidence")
    return _fact_value(True)


def _when_ticket_acceptance_conditions_satisfied(context: FactContext) -> Fact:
    supported = _when_evidence_all_required_claims_supported(context)
    conflicts = _when_evidence_contradictory_unresolved(context)
    if not supported.known:
        return supported
    if not conflicts.known:
        return conflicts
    return _fact_value(bool(supported.value) and not bool(conflicts.value))


def _when_ticket_release_edge_rechecked(context: FactContext) -> Fact:
    return context._trail_signal("ticket.release_edge_rechecked")


def _when_gate_stage7_complete(context: FactContext) -> Fact:
    gate = context.snapshot.gate
    if not gate.present:
        return context.unknown("gate.md 不存在")
    if gate.error:
        return context.unknown(gate.error)
    durable = re.search(r"(?ms)^##\s+Durable Deltas\s*$\n(.*?)(?=^##\s+|\Z)", gate.text)
    if durable is None:
        return _fact_value(False)
    body = durable.group(1)
    return _fact_value(bool(re.search(r"(?m)^-\s+(?!none\b|Reason:\s*none\b).+", body, re.I)))


def _when_attempt_terminal_gate_pending(context: FactContext) -> Fact:
    terminal = _when_attempt_all_tickets_terminal(context)
    if not terminal.known:
        return terminal
    if not terminal.value:
        return _fact_value(False)
    gate_terminal = _when_gate_terminal(context)
    if not gate_terminal.known:
        return gate_terminal
    return _fact_value(not gate_terminal.value)


def _when_gate_verdict(context: FactContext) -> Fact:
    gate = context.snapshot.gate
    if gate.error:
        return context.unknown(gate.error)
    if not gate.present:
        return context.unknown("gate.md 不存在")
    if gate.verdict is None:
        return context.unknown("gate.md 的 verdict 无法解析")
    return _fact_value(gate.verdict)


def _when_gate_present(context: FactContext) -> Fact:
    return _fact_value(context.snapshot.gate.present)


def _when_git_comparison_revision_matches_acceptance(context: FactContext) -> Fact:
    gate = context.snapshot.gate
    if gate.verdict == "pass":
        if not gate.comparison_commit:
            return context.unknown("pass gate 缺少 comparison commit")
        comparison_commit = gate.comparison_commit
    elif not gate.present:
        pending = _when_attempt_completion_claim_pending(context)
        if not pending.known:
            return pending
        if not pending.value:
            return _fact_value(False)
        if context.snapshot.head is None:
            return context.unknown("准备判 pass 时无法读取当前 Git HEAD")
        comparison_commit = context.snapshot.head
    else:
        return _fact_value(False)
    state = context.state()
    if state is None:
        return context.state_required() or context.unknown("state.json 无法判定")
    resolved_comparison = context.snapshot.reader.resolve_commit(comparison_commit)
    if resolved_comparison is None:
        return context.unknown("comparison commit 无法解析")
    for identifier, row in state.get("tickets", {}).items():
        if not isinstance(row, dict) or row.get("state") != "SATISFIED":
            continue
        acceptance = row.get("acceptance")
        if not isinstance(acceptance, dict) or not isinstance(acceptance.get("revision"), str):
            return context.unknown(f"Ticket {identifier} acceptance revision 无法解析")
        resolved_acceptance = context.snapshot.reader.resolve_commit(acceptance["revision"])
        if resolved_acceptance is None:
            return context.unknown(f"Ticket {identifier} acceptance revision 无法解析")
        if resolved_acceptance != resolved_comparison:
            return _fact_value(False)
    return _fact_value(True)


def _when_git_comparison_head_fixed(context: FactContext) -> Fact:
    return context._trail_availability("git.comparison_head_fixed")


def _when_git_contract_changed_since_last_trail(context: FactContext) -> Fact:
    base, advanced = context._git_since_last_trail()
    if base is None:
        return context.unknown("没有可用于比较的 trail head")
    if advanced is False:
        return _fact_value(False)
    names = context.snapshot.reader.diff_names(base)
    if names is None:
        return context.unknown("无法读取 trail head 到当前 HEAD 的 Git diff")
    package_prefix = context.snapshot.reader.package_rel.as_posix() if context.snapshot.reader.package_rel else ""
    contract_names = {"plan.md", "spec.md", "contract-design.md", "decision.md"}
    for name in names:
        relative = name[len(package_prefix) + 1 :] if package_prefix and name.startswith(package_prefix + "/") else name
        if relative in contract_names or relative.startswith("tickets/"):
            return _fact_value(True)
    return _fact_value(False)


def _when_attempt_handoff_or_long_task(context: FactContext) -> Fact:
    return context._manual_or_explicit("attempt.handoff_or_long_task")


def _when_intake_has_backlog(context: FactContext) -> Fact:
    intake = context.snapshot.intake
    if not intake.present:
        return context.unknown("intake 队列不存在")
    if intake.error:
        return context.unknown(intake.error)
    assert intake.has_backlog is not None
    return _fact_value(intake.has_backlog)


def _when_ticket_post_fix_regression_pending(context: FactContext) -> Fact:
    return context._trail_signal("ticket.post_fix_regression_pending")


WHEN_PARSERS: dict[str, Callable[[FactContext], Fact]] = {
    "package.state_invalid": _when_package_state_invalid,
    "package.references.live_package": _when_package_references_live_package,
    "package.validate.projection_drift": _when_package_validate_projection_drift,
    "attempt.session_resumed": _when_attempt_session_resumed,
    "attempt.compaction_pressure_high": _when_attempt_compaction_pressure_high,
    "attempt.active_checkpoint_present": _when_attempt_active_checkpoint_present,
    "trail.actions_since_checkpoint": _when_trail_actions_since_checkpoint,
    "trail.last_ticket_terminal_transition": _when_trail_last_ticket_terminal_transition,
    "gate.terminal": _when_gate_terminal,
    "attempt.ready_ticket_count": _when_attempt_ready_ticket_count,
    "attempt.in_flight": _when_attempt_in_flight,
    "attempt.has_pending_ticket": _when_attempt_has_pending_ticket,
    "attempt.implementation_edges_held": _when_attempt_implementation_edges_held,
    "attempt.all_tickets_terminal": _when_attempt_all_tickets_terminal,
    "ticket.state": _when_ticket_state,
    "ticket.blocker_maybe_resolved": _when_ticket_blocker_maybe_resolved,
    "trail.has_investigate": _when_trail_has_investigate,
    "ticket.investigation_carrier_present": _when_ticket_investigation_carrier_present,
    "ticket.investigation_context_clear": _when_ticket_investigation_context_clear,
    "evidence.count": _when_evidence_count,
    "trail.last_outcome": _when_trail_last_outcome,
    "trail.handoff_in_flight": _when_trail_handoff_in_flight,
    "trail.anchor_mismatch": _when_trail_anchor_mismatch,
    "trail.handoff_recovery_needed": _when_trail_handoff_recovery_needed,
    "trail.handoff_target_corrected": _when_trail_handoff_target_corrected,
    "trail.checkpoint_refresh_needed": _when_trail_checkpoint_refresh_needed,
    "trail.judgment_unfiled": _when_trail_judgment_unfiled,
    "trail.checkpoint_projection_race": _when_trail_checkpoint_projection_race,
    "trail.bookkeeper_partial_write": _when_trail_bookkeeper_partial_write,
    "trail.reviewer_unavailable": _when_trail_reviewer_unavailable,
    "trail.decision_without_result": _when_trail_decision_without_result,
    "evidence.sources_uniquely_decide": _when_evidence_sources_uniquely_decide,
    "ticket.review_required": _when_ticket_review_required,
    "trail.direct_evidence_returned": _when_trail_direct_evidence_returned,
    "evidence.indexed": _when_evidence_indexed,
    "ticket.review_trigger": _when_ticket_review_trigger,
    "ticket.safety_invariant_unfalsified": _when_ticket_safety_invariant_unfalsified,
    "trail.incomplete_count": _when_trail_incomplete_count,
    "trail.last_worker_mode": _when_trail_last_worker_mode,
    "trail.envelope_valid": _when_trail_envelope_valid,
    "trail.finding_source": _when_trail_finding_source,
    "evidence.contradictory_unresolved": _when_evidence_contradictory_unresolved,
    "evidence.all_required_claims_supported": _when_evidence_all_required_claims_supported,
    "ticket.acceptance_edge_released": _when_ticket_acceptance_edge_released,
    "ticket.release_edge_present": _when_ticket_release_edge_present,
    "ticket.acceptance_revision_parseable": _when_ticket_acceptance_revision_parseable,
    "evidence.new_claim_conflict": _when_evidence_new_claim_conflict,
    "git.acceptance_revision_diverged": _when_git_acceptance_revision_diverged,
    "git.head_advanced_since_last_trail": _when_git_head_advanced_since_last_trail,
    "ticket.no_longer_needed": _when_ticket_no_longer_needed,
    "finding.review_track": _when_finding_review_track,
    "finding.source_recheck_pending": _when_finding_source_recheck_pending,
    "finding.closure_review_pending": _when_finding_closure_review_pending,
    "finding.grading_pending": _when_finding_grading_pending,
    "findings.triage_pending": _when_findings_triage_pending,
    "attempt.near_terminal_gate": _when_attempt_near_terminal_gate,
    "attempt.manual_verification_owner": _when_attempt_manual_verification_owner,
    "attempt.manual_verification_result_present": _when_attempt_manual_verification_result_present,
    "attempt.integration_evidence_available": _when_attempt_integration_evidence_available,
    "attempt.integration_carrier_available": _when_attempt_integration_carrier_available,
    "attempt.completion_claim_pending": _when_attempt_completion_claim_pending,
    "attempt.terminal_coverage_complete": _when_attempt_terminal_coverage_complete,
    "ticket.acceptance_conditions_satisfied": _when_ticket_acceptance_conditions_satisfied,
    "ticket.release_edge_rechecked": _when_ticket_release_edge_rechecked,
    "gate.stage7_complete": _when_gate_stage7_complete,
    "attempt.terminal_gate_pending": _when_attempt_terminal_gate_pending,
    "gate.present": _when_gate_present,
    "gate.verdict": _when_gate_verdict,
    "git.comparison_revision_matches_acceptance": _when_git_comparison_revision_matches_acceptance,
    "git.accepted_seam_changed": _when_git_accepted_seam_changed,
    "git.comparison_head_fixed": _when_git_comparison_head_fixed,
    "git.contract_changed_since_last_trail": _when_git_contract_changed_since_last_trail,
    "attempt.handoff_or_long_task": _when_attempt_handoff_or_long_task,
    "intake.has_backlog": _when_intake_has_backlog,
    "ticket.post_fix_regression_pending": _when_ticket_post_fix_regression_pending,
}


def _yaml_text() -> str:
    if yaml is None:
        raise SituationError("缺少 PyYAML；仓库声明了 pyyaml>=6.0")
    try:
        return TABLE_PATH.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SituationError(f"无法读取正式 situations.yaml：{exc}") from exc


def _load_yaml(text: str, source: str) -> dict[str, Any]:
    if yaml is None:
        raise SituationError("缺少 PyYAML；仓库声明了 pyyaml>=6.0")
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TableError([f"{source}: YAML 解析失败：{exc}"]) from exc
    if not isinstance(value, dict):
        raise TableError([f"{source}: 顶层必须是 mapping"])
    return value


def _row_when_keys(rows: Iterable[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        when = row.get("when")
        if isinstance(when, dict):
            keys.update(str(key) for key in when)
    return keys


def _validate_table(data: dict[str, Any], source: str = "situations.yaml") -> TableModel:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("version") != 1:
        errors.append(f"{source}: version 必须是 1")
    if data.get("stage") != STAGE:
        errors.append(f"{source}: stage 必须是 {STAGE}")
    objects = data.get("objects")
    phases = data.get("phases")
    allowed = data.get("allowed")
    if not isinstance(objects, list) or not all(isinstance(item, str) for item in objects):
        errors.append(f"{source}: objects 必须是字符串 list")
        objects = []
    if not isinstance(phases, list) or not all(isinstance(item, str) for item in phases):
        errors.append(f"{source}: phases 必须是字符串 list")
        phases = []
    if not isinstance(allowed, dict):
        errors.append(f"{source}: allowed 必须是 mapping")
        allowed = {}
    rows_value = data.get("situations")
    if not isinstance(rows_value, list):
        errors.append(f"{source}: situations 必须是 list")
        rows_value = []

    rows: list[dict[str, Any]] = []
    slugs: dict[str, int] = {}
    actions: dict[str, str] = {}
    for index, raw_row in enumerate(rows_value):
        if not isinstance(raw_row, dict):
            errors.append(f"{source}: situations[{index}] 必须是 mapping")
            continue
        row = copy.deepcopy(raw_row)
        row["_row_index"] = index
        slug = row.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
            errors.append(f"{source}: situations[{index}] slug 不是合法三段式：{slug!r}")
        else:
            if slug in slugs:
                errors.append(f"{source}: slug 重复：{slug}")
            slugs[slug] = index
            object_name, phase, _ = slug.split(".")
            if object_name not in objects:
                errors.append(f"{source}: {slug} 的对象不在 objects 内")
            if phase not in phases:
                errors.append(f"{source}: {slug} 的环节不在 phases 内")
            allowed_phases = allowed.get(object_name)
            if not isinstance(allowed_phases, list) or phase not in allowed_phases:
                errors.append(f"{source}: {slug} 不在 allowed 对象×环节矩阵内")
        if row.get("basis") not in VALID_BASIS:
            errors.append(f"{source}: {slug or index} basis 无效")
        if not isinstance(row.get("judgment"), bool):
            errors.append(f"{source}: {slug or index} judgment 必须是 bool")
        if not isinstance(row.get("escape"), bool):
            errors.append(f"{source}: {slug or index} escape 必须是 bool")
        when = row.get("when")
        if when != "manual" and not isinstance(when, dict):
            errors.append(f"{source}: {slug or index} when 必须是 mapping 或 manual")
        if isinstance(when, dict):
            for key in when:
                if not isinstance(key, str):
                    errors.append(f"{source}: {slug or index} when key 必须是字符串")
        elif when != "manual":
            when = {}
        row_actions = row.get("actions")
        if not isinstance(row_actions, list) or not row_actions:
            errors.append(f"{source}: {slug or index} actions 必须是非空 list")
            row_actions = []
        default_count = 0
        for action_index, action in enumerate(row_actions):
            if not isinstance(action, dict) or not isinstance(action.get("id"), str) or not action.get("id"):
                errors.append(f"{source}: {slug or index} action[{action_index}] 缺少 id")
                continue
            action_id = action["id"]
            if action_id in actions:
                errors.append(f"{source}: action id 重复：{action_id}（{actions[action_id]} 与 {slug}）")
            actions[action_id] = str(slug or index)
            if "default" in action and not isinstance(action.get("default"), bool):
                errors.append(f"{source}: {slug or index} action {action_id} 的 default 必须是 bool")
            if action.get("default") is True:
                default_count += 1
        if default_count > 1:
            errors.append(f"{source}: {slug or index} default action 超过一个")
        rows.append(row)

    priority_value = data.get("priority")
    if not isinstance(priority_value, list) or not all(isinstance(group, list) for group in priority_value):
        errors.append(f"{source}: priority 必须是 list[list[str]]")
        priority_value = []
    elif len(priority_value) != 6:
        errors.append(f"{source}: priority 必须恰好包含 P0-P5 六个层")
    priority: list[list[str]] = []
    placements: dict[str, int] = {}
    for group_index, group in enumerate(priority_value):
        normalized: list[str] = []
        group_seen: set[str] = set()
        for slug in group:
            if not isinstance(slug, str):
                errors.append(f"{source}: priority[{group_index}] 含非字符串 slug")
                continue
            if slug in group_seen:
                errors.append(f"{source}: priority[{group_index}] 重复 slug：{slug}")
                continue
            group_seen.add(slug)
            normalized.append(slug)
            if slug not in slugs:
                errors.append(f"{source}: priority 引用了不存在的 slug：{slug}")
            previous_group = placements.get(slug)
            if previous_group is not None:
                errors.append(
                    f"{source}: {slug} 必须恰好属于一个层（同时出现在 P{previous_group} 与 P{group_index}）"
                )
            else:
                placements[slug] = group_index
        # P0 remains an ordered list.  P1-P5 are unordered sets; retain their
        # spelling order only for stable diagnostics, never as a rank.
        priority.append(normalized)
    unranked = sorted(set(slugs) - set(placements), key=lambda slug: slugs[slug])
    if unranked:
        errors.append("priority 层集合未覆盖全部行：" + ", ".join(unranked))

    unknown = sorted(_row_when_keys(rows) - set(WHEN_PARSERS))
    if unknown:
        errors.append("YAML 使用但解析器未实现的 when key：" + ", ".join(unknown))
    if errors:
        raise TableError(errors, warnings)
    return TableModel(data=data, rows=rows, priority=priority, warnings=warnings)


def _load_table_for_package(reader: PackageReader | None = None) -> TableModel:
    base = _validate_table(_load_yaml(_yaml_text(), str(TABLE_PATH)))
    if reader is None:
        return base
    override_view = reader.read("situations.yaml")
    if not override_view.present:
        return base
    if override_view.error:
        raise SituationError(override_view.error)
    assert override_view.text is not None
    override = _load_yaml(override_view.text, f"{reader.package}/situations.yaml")
    allowed_keys = {"extends", "skip", "add"}
    extra = sorted(set(override) - allowed_keys)
    if extra:
        raise TableError(["package situations.yaml 含未知字段：" + ", ".join(extra)])
    extends = override.get("extends", STAGE)
    if extends != STAGE:
        raise TableError([f"package situations.yaml extends 必须是 {STAGE}"])
    merged = copy.deepcopy(base.data)
    rows = list(merged["situations"])
    skip = override.get("skip", [])
    if not isinstance(skip, list) or not all(isinstance(item, str) for item in skip):
        raise TableError(["package situations.yaml skip 必须是字符串 list"])
    existing = {row["slug"] for row in rows}
    missing_skip = sorted(set(skip) - existing)
    if missing_skip:
        raise TableError(["package situations.yaml skip 引用了不存在的 slug：" + ", ".join(missing_skip)])
    rows = [row for row in rows if row["slug"] not in set(skip)]
    additions = override.get("add", [])
    if not isinstance(additions, list) or not all(isinstance(item, dict) for item in additions):
        raise TableError(["package situations.yaml add 必须是 situation mapping list"])
    for addition in additions:
        slug = addition.get("slug")
        if not isinstance(slug, str) or slug in {row.get("slug") for row in rows}:
            raise TableError([f"package situations.yaml add 的 slug 无效或重复：{slug!r}"])
        rows.append(copy.deepcopy(addition))
    merged["situations"] = rows
    merged["priority"] = [
        [slug for slug in group if slug not in set(skip)]
        for group in merged.get("priority", [])
    ]
    return _validate_table(merged, f"{reader.package}/situations.yaml（合并后）")


def _subject_specs(snapshot: Snapshot, rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    kinds = {str(row["slug"]).split(".", 1)[0] for row in rows}
    result: list[tuple[str, str]] = []
    if "package" in kinds:
        result.append(("package", "package"))
    if "attempt" in kinds:
        result.append(("attempt", "attempt"))
    if "ticket" in kinds:
        identifiers = sorted(snapshot.tickets) or ["*"]
        result.extend(("ticket", identifier) for identifier in identifiers)
    if "finding" in kinds:
        identifiers = [finding.identifier for finding in snapshot.findings.findings] or ["*"]
        result.extend(("finding", identifier) for identifier in sorted(identifiers))
    return result


def _compare(actual: Fact, expected: Any) -> tuple[bool, bool, str | None]:
    if not actual.known:
        return False, True, actual.reason or "值未知"
    if isinstance(expected, str):
        match = NUMERIC_COMPARISON_RE.fullmatch(expected.strip())
        if match:
            try:
                left = float(actual.value)
                right = float(match.group(2))
            except (TypeError, ValueError):
                return False, False, None
            operator = match.group(1)
            return {
                ">": left > right,
                ">=": left >= right,
                "<": left < right,
                "<=": left <= right,
                "==": left == right,
                "!=": left != right,
            }[operator], False, None
    return actual.value == expected, False, None


def _evaluate_row(row: dict[str, Any], context: FactContext) -> tuple[str, dict[str, Fact], list[str]]:
    when = row.get("when")
    if when == "manual":
        return "manual", {}, []
    assert isinstance(when, dict)
    values: dict[str, Fact] = {}
    unknown_reasons: list[str] = []
    false_found = False
    for key, expected in when.items():
        parser = WHEN_PARSERS[key]
        actual = parser(context)
        values[key] = actual
        matched, unknown, reason = _compare(actual, expected)
        if unknown:
            unknown_reasons.append(f"{key}: {reason}")
        elif not matched:
            false_found = True
    if false_found:
        return "false", values, []
    if unknown_reasons:
        return "unknown", values, unknown_reasons
    return "true", values, []


def _collect_when_values(
    table: TableModel,
    snapshot: Snapshot,
    contexts: dict[str, FactContext],
) -> dict[str, list[dict[str, Any]]]:
    keys = sorted(_row_when_keys(table.rows))
    result: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    for key in keys:
        parser = WHEN_PARSERS[key]
        prefix = key.split(".", 1)[0]
        # One value per subject is useful for ticket-scoped keys.  For global
        # keys, collapse to the canonical package/attempt subject below.
        if prefix in {"ticket", "evidence"}:
            selected = [context for context in contexts.values() if context.kind == "ticket"]
        elif prefix == "finding":
            selected = [context for context in contexts.values() if context.kind == "finding"]
        elif prefix == "trail":
            selected = [context for context in contexts.values() if context.kind in {"attempt", "ticket", "finding"}]
        elif prefix == "package":
            selected = [contexts.get("package")]
        elif prefix in {"attempt", "gate", "git", "findings", "intake"}:
            selected = [contexts.get("attempt") or contexts.get("package")]
        else:
            selected = []
        selected = [context for context in selected if context is not None]
        if not selected:
            dummy_kind = "ticket" if prefix in {"ticket", "evidence"} else "finding" if prefix == "finding" else "attempt"
            selected = [FactContext(snapshot, dummy_kind, "*")]
        seen: set[str] = set()
        for context in selected:
            subject = context.subject
            if subject in seen:
                continue
            seen.add(subject)
            result[key].append({"subject": subject, **parser(context).as_json()})
    return result


def _priority_layer_by_slug(table: TableModel) -> dict[str, int]:
    return {
        slug: layer
        for layer, group in enumerate(table.priority)
        for slug in group
    }


def _rows_for_diagnostics(table: TableModel) -> list[dict[str, Any]]:
    by_slug = {row["slug"]: row for row in table.rows}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in table.priority:
        for slug in group:
            if slug in by_slug and slug not in seen:
                ordered.append(by_slug[slug])
                seen.add(slug)
    return ordered


def _candidate_sort_key(candidate: Candidate, layer_by_slug: dict[str, int], p0_order: dict[str, int]) -> tuple[int, int, int, str]:
    layer = layer_by_slug[candidate.slug]
    return (
        layer,
        p0_order.get(candidate.slug, 0) if layer == 0 else candidate.row_index,
        candidate.row_index,
        candidate.subject,
    )


def _derive(table: TableModel, snapshot: Snapshot) -> dict[str, Any]:
    specs = _subject_specs(snapshot, table.rows)
    contexts: dict[str, FactContext] = {}
    for kind, identifier in specs:
        context = FactContext(snapshot, kind, identifier)
        contexts[context.subject] = context

    manual = [
        {
            "slug": row["slug"],
            "manual_reason": row.get("manual_reason"),
            "judgment": row.get("judgment"),
            "ask": row.get("ask"),
            "action_ids": [action.get("id") for action in row.get("actions", [])],
        }
        for row in table.rows
        if row.get("when") == "manual"
    ]
    candidates: list[Candidate] = []
    undetermined: list[Undetermined] = []
    by_slug = {row["slug"]: row for row in table.rows}
    for row in _rows_for_diagnostics(table):
        if row.get("when") == "manual":
            continue
        object_name = str(row["slug"]).split(".", 1)[0]
        for subject, context in contexts.items():
            if context.kind != object_name:
                continue
            status, values, reasons = _evaluate_row(row, context)
            if status == "true":
                candidates.append(Candidate(row, subject, context, values))
            elif status == "unknown":
                undetermined.append(Undetermined(row, subject, context, values))

    layer_by_slug = _priority_layer_by_slug(table)
    p0_order = {slug: index for index, slug in enumerate(table.priority[0])}
    candidates.sort(key=lambda item: _candidate_sort_key(item, layer_by_slug, p0_order))
    unique_candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate.slug, candidate.subject)
        if key not in seen:
            unique_candidates.append(candidate)
            seen.add(key)
    p0_matches = [candidate for candidate in unique_candidates if layer_by_slug[candidate.slug] == 0]
    if p0_matches:
        selected = p0_matches[0]
        parallel_matches: list[Candidate] = []
        other_matches = p0_matches[1:]
        suppressed_matches = [
            candidate for candidate in unique_candidates if layer_by_slug[candidate.slug] > 0
        ]
        highest_layer = 0
    else:
        selected = None
        highest_layer = min(
            (layer_by_slug[candidate.slug] for candidate in unique_candidates),
            default=None,
        )
        parallel_matches = [
            candidate
            for candidate in unique_candidates
            if layer_by_slug[candidate.slug] == highest_layer
        ] if highest_layer is not None else []
        other_matches = [
            candidate
            for candidate in unique_candidates
            if highest_layer is not None and layer_by_slug[candidate.slug] > highest_layer
        ]
        suppressed_matches = []

    if selected is None and not parallel_matches:
        unmatched_object = "attempt" if "attempt" in {str(row["slug"]).split(".", 1)[0] for row in table.rows} else "package"
        unmatched = f"{unmatched_object}.record.unmatched"
    else:
        unmatched = None

    return {
        "selected": selected.as_json() if selected else None,
        "parallel_matches": [candidate.as_json() for candidate in parallel_matches],
        "other_matches": [candidate.as_json() for candidate in other_matches],
        "suppressed_matches": [candidate.as_json() for candidate in suppressed_matches],
        "matches": [candidate.as_json() for candidate in unique_candidates],
        "highest_match_layer": f"P{highest_layer}" if highest_layer is not None else None,
        "manual": manual,
        "undetermined": [item.as_json() for item in undetermined],
        "unmatched": unmatched,
        "when_values": _collect_when_values(table, snapshot, contexts),
        "contexts": sorted(contexts),
        "table_warnings": table.warnings,
    }


def _subject_label(subject: str) -> str:
    if subject.startswith("ticket:"):
        return subject.split(":", 1)[1]
    if subject.startswith("finding:"):
        return subject.split(":", 1)[1]
    return subject


def _digest_candidate(
    item: dict[str, Any] | None,
    layer_by_slug: dict[str, int],
) -> dict[str, Any] | None:
    if item is None:
        return None
    slug = str(item["slug"])
    return {
        "slug": slug,
        "subject": item.get("subject"),
        "layer": layer_by_slug[slug],
        "action_ids": list(item.get("action_ids", [])),
    }


def _situation_digest(table: TableModel, result: dict[str, Any]) -> str:
    layer_by_slug = _priority_layer_by_slug(table)
    groups = {
        name: [
            _digest_candidate(item, layer_by_slug)
            for item in result.get(name, [])
        ]
        for name in ("parallel_matches", "other_matches", "suppressed_matches")
    }
    groups["selected"] = _digest_candidate(result.get("selected"), layer_by_slug)
    payload = {
        "match_groups": groups,
        "highest_match_layer": result.get("highest_match_layer"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def _write_situation_digest(reader: PackageReader, state: StateView, digest: str) -> None:
    try:
        if not state.attempt_id:
            raise OSError("current attempt is unavailable")
        state_path = reader.package / STATE_REL
        state_sha256 = hashlib.sha256(state_path.read_bytes()).hexdigest()
        credential_path = reader.package / "execution" / state.attempt_id / SITUATION_DIGEST_NAME
        credential_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "digest": digest,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "state_sha256": state_sha256,
        }
        with credential_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
    except OSError as exc:
        print(f"warning: could not write {SITUATION_DIGEST_NAME}: {exc}", file=sys.stderr)


def _render_human(
    result: dict[str, Any],
    snapshot: Snapshot,
    *,
    explain_undetermined: bool = False,
) -> str:
    selected = result.get("selected")
    lines: list[str] = []
    if selected:
        subject_label = _subject_label(selected["subject"])
        lines.append(f"处境: {selected['slug']}  ({subject_label})")
        actions = selected.get("actions", [])
        if actions:
            rendered_actions = []
            for index, action in enumerate(actions):
                rendered_actions.append(f"{chr(97 + index)}) {action.get('id')}")
            lines.append("可选: " + "  ".join(rendered_actions))
        if selected.get("judgment"):
            lines.append(f"判断点: {selected.get('ask') or '由主控选择合适动作'}")
        else:
            lines.append("判断点: 机械条件命中，优先执行默认动作")
    elif result.get("parallel_matches"):
        layer = result.get("highest_match_layer") or "P?"
        lines.append(f"处境层: {layer}（并列命中，由主控选择）")
        rendered = []
        for item in result["parallel_matches"]:
            subject_label = _subject_label(item["subject"])
            actions = "/".join(item.get("action_ids", [])) or "无动作"
            rendered.append(f"{item['slug']} ({subject_label}) [{actions}]")
        lines.append("并列处境: " + "  |  ".join(rendered))
        lines.append("判断点: 先选一个处境，再选其动作")
    else:
        lines.append(f"处境: {result.get('unmatched') or 'attempt.record.unmatched'}")

    others = result.get("other_matches", [])
    if others:
        labels = ", ".join(
            f"{item['slug']} ({_subject_label(item['subject'])})" for item in others
        )
        scope = "同层" if selected else "较低层"
        lines.append(f"secondary（{scope}）{len(others)} 个：{labels}")
    manual = result.get("manual", [])
    if manual:
        slugs = ", ".join(item["slug"] for item in manual)
        lines.append(f"需要主控自行判断是否进入: {slugs}")
    undetermined = result.get("undetermined", [])
    if undetermined:
        if explain_undetermined:
            preview = ", ".join(
                f"{item['slug']} ({_subject_label(item['subject'])})"
                for item in undetermined[:4]
            )
            suffix = " …" if len(undetermined) > 4 else ""
            lines.append(f"无法判定 {len(undetermined)} 行: {preview}{suffix}")
        else:
            lines.append(f"无法判定 {len(undetermined)} 行")
    if snapshot.warnings:
        lines.append(f"读取提示: {len(snapshot.warnings)} 条（JSON 模式含详情）")
    return "\n".join(lines)


def _json_result(
    table: TableModel,
    snapshot: Snapshot,
    derived: dict[str, Any],
    digest: str,
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "package": str(snapshot.package),
        "attempt": snapshot.state.attempt_id,
        "digest": digest,
        "unchanged": False,
        "at": snapshot.reader.at_label,
        "head": snapshot.head,
        "selected": derived["selected"],
        "parallel_matches": derived["parallel_matches"],
        "other_matches": derived["other_matches"],
        "suppressed_matches": derived["suppressed_matches"],
        "matches": derived["matches"],
        "highest_match_layer": derived["highest_match_layer"],
        "manual": derived["manual"],
        "undetermined": derived["undetermined"],
        "unmatched": derived["unmatched"],
        "when_values": derived["when_values"],
        "contexts": derived["contexts"],
        "sources": {
            "state": {"path": STATE_REL, "present": snapshot.state.raw is not None, "valid": snapshot.state.valid, "reason": snapshot.state.error},
            "trail": {"path": _active_trail_relative_path(snapshot.state.attempt_id) if snapshot.state.attempt_id else None, "present": snapshot.trail.present, "error": snapshot.trail.error},
            "gate": {"path": GATE_REL, "present": snapshot.gate.present, "verdict": snapshot.gate.verdict, "error": snapshot.gate.error},
            "findings": {"path": FINDINGS_REL, "present": snapshot.findings.present, "count": len(snapshot.findings.findings), "error": snapshot.findings.error},
            "intake": {"path": snapshot.intake.relative_path, "present": snapshot.intake.present, "error": snapshot.intake.error},
            "validation_result": (
                {
                    "projection_drift": snapshot.validation_result.projection_drift,
                    "source": snapshot.validation_result.source,
                }
                if snapshot.validation_result is not None
                else None
            ),
            "compaction_pressure": (
                {
                    **snapshot.compaction_pressure.data,
                    "source": snapshot.compaction_pressure.source,
                }
                if snapshot.compaction_pressure is not None
                else None
            ),
        },
        "warnings": [*table.warnings, *snapshot.warnings],
    }


def _format_when(when: Any) -> str:
    if when == "manual":
        return "manual"
    if not isinstance(when, dict):
        return repr(when)
    return ", ".join(f"{key}={value!r}" for key, value in when.items())


def _print_table(table: TableModel) -> str:
    rows_by_slug = {row["slug"]: row for row in table.rows}
    lines = [f"stage: {STAGE}", f"situations: {len(table.rows)}", ""]
    ranked: set[str] = set()
    for group_index, group in enumerate(table.priority, 1):
        group_rows = []
        for slug in group:
            if slug in ranked or slug not in rows_by_slug:
                continue
            ranked.add(slug)
            group_rows.append(rows_by_slug[slug])
        if not group_rows:
            continue
        kind = "ordered" if group_index == 1 else "set"
        lines.append(f"priority P{group_index - 1} ({kind}):")
        for row in group_rows:
            lines.append(
                f"  - {row['slug']} [{row['basis']}] "
                f"{'judgment' if row['judgment'] else 'default'}; when: {_format_when(row['when'])}; "
                f"actions: {', '.join(action['id'] for action in row['actions'])}"
            )
    unranked = sorted((row for row in table.rows if row["slug"] not in ranked), key=lambda row: row["_row_index"])
    if unranked:
        lines.append("priority tail (not listed in priority):")
        for row in unranked:
            lines.append(
                f"  - {row['slug']} [{row['basis']}] "
                f"{'judgment' if row['judgment'] else 'default'}; when: {_format_when(row['when'])}; "
                f"actions: {', '.join(action['id'] for action in row['actions'])}"
            )
    return "\n".join(lines)


def _check_table() -> int:
    try:
        table = _validate_table(_load_yaml(_yaml_text(), str(TABLE_PATH)))
    except TableError as exc:
        print("check: FAIL")
        for error in exc.errors:
            print(f"- {error}")
        for warning in exc.warnings:
            print(f"warning: {warning}")
        return 1
    except SituationError as exc:
        print(f"check: FAIL\n- {exc}")
        return 1
    nonmanual_keys = sorted(_row_when_keys(table.rows))
    print("check: PASS")
    print(f"- stage: {STAGE}")
    print(f"- situations: {len(table.rows)}")
    print(f"- implemented when keys: {len(nonmanual_keys)}")
    print(f"- priority groups: {len(table.priority)}")
    for warning in table.warnings:
        print(f"warning: {warning}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only dev-with-track situation derivation and table inspection.",
        epilog=(
            "when comparison syntax: booleans use exact true/false; strings and state enums "
            "use exact equality; numeric strings support >N, >=N, <N, <=N, ==N, !=N (for example >1 and >0). "
            "Missing trail/findings/intake inputs produce unknown, never false."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render", help="derive and render the current situation")
    render.add_argument("--package", type=Path, required=True)
    render.add_argument("--at", metavar="COMMIT", help="read package files at a Git commit without changing HEAD")
    render.add_argument(
        "--validation-result",
        metavar="JSON_OR_FILE",
        help="read-only JSON object {\"projection_drift\": boolean}, inline or from a file",
    )
    render.add_argument(
        "--compaction-pressure",
        metavar="JSON_OR_FILE",
        help="read-only JSON object with boolean high, inline or from a file",
    )
    render.add_argument(
        "--since",
        metavar="DIGEST",
        help="emit only a one-line unchanged marker when the digest matches",
    )
    render.add_argument(
        "--explain-undetermined",
        action="store_true",
        help="include the first undetermined situation slugs in human output",
    )
    render.add_argument(
        "--no-write-credential",
        action="store_true",
        help=f"derive without writing execution/<attempt>/{SITUATION_DIGEST_NAME}",
    )
    render.add_argument("--json", action="store_true", help="emit structured JSON")
    table = subparsers.add_parser("print-table", help="print the formal YAML table")
    table.add_argument("--stage", default=STAGE, choices=[STAGE])
    subparsers.add_parser("check", help="validate the formal YAML table")
    return parser


def _run_render(args: argparse.Namespace) -> int:
    reader = PackageReader(args.package, args.at)
    table = _load_table_for_package(reader)
    validation_result = _load_validation_result(args.validation_result)
    compaction_pressure = _load_compaction_pressure(args.compaction_pressure)
    snapshot = _build_snapshot(reader, validation_result, compaction_pressure)
    derived = _derive(table, snapshot)
    digest = _situation_digest(table, derived)
    if not args.no_write_credential:
        _write_situation_digest(reader, snapshot.state, digest)
    if args.since == digest:
        if args.json:
            print(
                json.dumps(
                    {
                        "digest": digest,
                        "unchanged": True,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        else:
            print(f"处境未变 (digest: {digest})")
        return 0
    if args.json:
        print(
            json.dumps(
                _json_result(table, snapshot, derived, digest),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        body = _render_human(
            derived,
            snapshot,
            explain_undetermined=args.explain_undetermined,
        )
        print(f"{body}\ndigest: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "check":
            return _check_table()
        if args.command == "print-table":
            table = _validate_table(_load_yaml(_yaml_text(), str(TABLE_PATH)))
            print(_print_table(table))
            return 0
        if args.command == "render":
            return _run_render(args)
        parser.error(f"unknown command: {args.command}")
    except TableError as exc:
        print("situation: FAIL", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        for warning in exc.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return 2
    except SituationError as exc:
        print(f"situation: FAIL\n- {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
