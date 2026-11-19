"""`evidence impact`: which supporting evidence a runtime change reaches, and a ready carry-forward batch for the rest.

Read-only. Reuses `runtime_changed_files` (the same notion of "runtime change" as carry-forward / Gate staleness).

Coverage sources (a Spec table cannot gain a column under the 3.6 Spec contract, so the Entry / step cells carry it):
- Suite: `covers: <path>[, <path>...]` inside the Entry cell, else the directory of each `--spec <file>` in the Entry command.
- Journey run: `covers:` inside any step cell, else path-like tokens in 操作入口 / 观察表面 (substring match, so a route
  `/employees/new` matches `app/employees/new/page.tsx`). A step with nothing derivable makes the Journey count as affected.
"""
from __future__ import annotations

import posixpath
import re
import shlex
from pathlib import Path
from typing import Any

from situation import evidence_revision_coverage, runtime_changed_files

from .state_core import STATE_PATH, _load_json, _repo_root, _validate_commit

_COVERS_RE = re.compile(r"covers:\s*(.+)$", re.I)
_SPEC_RE = re.compile(r"--spec[=\s]+[`'\"]?([^\s`'\"]+)")
_TOKEN_RE = re.compile(r"(?<![\w.])/?[\w.\-\[\]()@]+(?:/[\w.\-\[\]()@]+)+")
_MAX_FILES = 5


def _norm(path: str) -> str:
    return path.strip().strip("`'\"").replace("\\", "/").removeprefix("./").rstrip("/")


def _explicit_covers(text: str) -> list[str] | None:
    match = _COVERS_RE.search(text)
    if not match:
        return None
    return [p for p in (_norm(x) for x in re.split(r"[,\s]+", match.group(1))) if p]


def suite_cover_paths(entry: str) -> list[str] | None:
    """Prefix paths a suite covers; None when nothing can be derived (conservative: affected)."""
    explicit = _explicit_covers(entry)
    if explicit is not None:
        return explicit or None
    dirs = [posixpath.dirname(_norm(m)) for m in _SPEC_RE.findall(entry)]
    dirs = [d for d in dirs if d]
    return dirs or None


def journey_cover_tokens(steps: list[dict[str, Any]]) -> list[str] | None:
    tokens: list[str] = []
    for step in steps:
        cells = [step["operationEntry"], step["observationSurface"]]
        explicit = [p for cell in cells for p in (_explicit_covers(cell) or [])]
        found = explicit or [_norm(t) for cell in cells for t in _TOKEN_RE.findall(cell.replace("`", ""))]
        if not found:
            return None
        tokens.extend(found)
    return tokens


def _hits(files: list[str], tokens: list[str], *, prefix: bool) -> list[str]:
    if prefix:
        return [f for f in files if any(f == t or f.startswith(t + "/") for t in tokens)]
    return [f for f in files if any(t.lstrip("/") in f for t in tokens)]


def _summarize(files: list[str]) -> str:
    shown = ", ".join(files[:_MAX_FILES])
    return shown + (f" 等 {len(files)} 个" if len(files) > _MAX_FILES else "")


def evidence_impact(package: Path, to: str, judged_by: str | None = None) -> dict[str, Any]:
    from .validate_state import _validate_state

    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    spec = summary["_journeySpec"]
    repo = _repo_root(package)
    target = _validate_commit(repo, to)
    package_rel = package.resolve().relative_to(repo).as_posix()
    judged = judged_by or "<judged-by>"
    cache: dict[str, list[str] | None] = {}

    def changed(revision: str) -> list[str] | None:
        if revision not in cache:
            cache[revision] = runtime_changed_files(repo, package_rel, revision, target)
        return cache[revision]

    def stale_records(key: str) -> list[dict[str, Any]]:
        return [
            r for r in state["evidenceIndex"].get(key, [])
            if r.get("conclusion") == "supporting" and not r.get("invalidatedBy")
            and evidence_revision_coverage(r, target, repo=repo, package=package) is None
        ]

    def union_changed(records: list[dict[str, Any]]) -> list[str] | None:
        files: set[str] = set()
        for record in records:
            part = changed(record["revision"])
            if part is None:
                return None
            files.update(part)
        return sorted(files)

    rerun: list[dict[str, Any]] = []
    carry: list[dict[str, Any]] = []
    current = 0

    def classify(unit: dict[str, Any], files: list[str] | None, hit: list[str], covers: list[str] | None) -> None:
        unit["changedFiles"] = files if files is not None else []
        if files is None or covers is None or hit:
            unit["reason"] = (
                "无法判定改动文件" if files is None else "无法推导覆盖路径，保守视为受影响" if covers is None
                else f"改动触及覆盖路径：{_summarize(hit)}"
            )
            rerun.append(unit)
        else:
            unit["reason"] = f"改动 {len(files)} 个运行时文件，均不在覆盖路径 {', '.join(covers)} 内：{_summarize(files)}"
            carry.append(unit)

    for suite_id, suite in spec["suites"].items():
        key = f"suite:{suite_id}"
        records = stale_records(key)
        if not records:
            current += 1
            continue
        files = union_changed(records)
        covers = suite_cover_paths(suite["entry"])
        hit = _hits(files or [], covers or [], prefix=True)
        unit = {"kind": "suite", "id": suite_id, "key": key, "select": f"key:{key}",
                "command": re.sub(r"\s*#?\s*covers:.*$", "", suite["entry"], flags=re.I).strip(),
                "covers": covers or []}
        classify(unit, files, hit, covers)

    runs: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for key, records in state["evidenceIndex"].items():
        if key.startswith("journey:"):
            run_id = key.split(":", 2)[1]
        elif key.startswith("run-setup:"):
            run_id = key.split(":", 1)[1]
        else:
            continue
        for record in stale_records(key):
            runs.setdefault(run_id, []).append((key, record))
    seen_runs = {k.split(":", 2)[1] if k.startswith("journey:") else k.split(":", 1)[1]
                 for k in state["evidenceIndex"] if k.startswith(("journey:", "run-setup:"))}
    current += len(seen_runs - runs.keys())
    for run_id, pairs in sorted(runs.items()):
        records = [r for _, r in pairs]
        journey_ids = sorted({r["journeyId"] for _, r in pairs if r.get("journeyId")}
                             | {r["journeyId"] for k, rs in state["evidenceIndex"].items() if k.startswith(f"journey:{run_id}:") for r in rs})
        files = union_changed(records)
        tokens: list[str] | None = []
        for journey in spec["journeys"]:
            if journey["id"] in journey_ids:
                part = journey_cover_tokens(journey["steps"])
                tokens = None if part is None or tokens is None else tokens + part
        hit = _hits(files or [], tokens or [], prefix=False)
        unit = {"kind": "run", "id": run_id, "key": f"run:{run_id}", "select": f"run:{run_id}",
                "journeys": journey_ids, "covers": tokens or [],
                "command": f"新开 run 重走 Journey {', '.join(journey_ids)} 受影响步骤并 evidence add（见 evidence add --help）"}
        classify(unit, files, hit, tokens)

    package_arg = shlex.quote(package_rel)
    carry_command = None
    if carry:
        parts = [f"impl_package_state.py --package {package_arg} evidence carry-forward --to {target} --judged-by {shlex.quote(judged)}"]
        for unit in carry:
            parts.append(f"--select {shlex.quote(unit['select'])} --reason {shlex.quote(unit['reason'])}")
        carry_command = " ".join(parts)
    return {"to": target, "rerun": rerun, "carry": carry, "carryCommand": carry_command, "current": current}


def render_impact(result: dict[str, Any]) -> str:
    lines = [f"evidence impact → {result['to'][:12]}（已有效 {result['current']} 项）"]
    lines.append(f"\n需重跑 ({len(result['rerun'])}):")
    lines += [f"  - {u['key']}：{u['reason']}\n      重跑：{u['command']}" for u in result["rerun"]] or ["  无"]
    lines.append(f"\n可沿用 ({len(result['carry'])}):")
    lines += [f"  - {u['key']}：{u['reason']}" for u in result["carry"]] or ["  无"]
    if result["carryCommand"]:
        lines.append(f"\n沿用命令：\n  {result['carryCommand']}")
    return "\n".join(lines)
