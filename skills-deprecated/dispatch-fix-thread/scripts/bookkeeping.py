#!/usr/bin/env python3
"""Deprecated dispatch-fix-thread bookkeeping preserved for historical audit."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUSES = {"working", "ready", "blocked"}
GROUP_RESULTS = {"working", "accepted", "blocked"}


class RecordError(ValueError):
    """Raised when a record is missing or violates the lightweight contract."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecordError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RecordError(f"{label} must be a list")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise RecordError(f"{label} must be a non-empty string")
    return value


def _text_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    items = _list(value, label)
    if not allow_empty and not items:
        raise RecordError(f"{label} must not be empty")
    for index, item in enumerate(items):
        _text(item, f"{label}[{index}]")
    return items


def read_json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except FileNotFoundError as exc:
        raise RecordError(f"record not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecordError(f"invalid JSON in {path}: {exc.msg}") from exc


def _require_keys(data: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise RecordError(f"{label} missing required fields: {', '.join(missing)}")


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    _require_keys(
        request,
        (
            "fix_id",
            "repository_root",
            "reviewed_head",
            "parent",
            "findings",
            "allowed_scope",
            "focused_verification",
            "remaining_verification",
            "excluded_side_effects",
            "fixer_target",
        ),
        "request",
    )
    _text(request["fix_id"], "request.fix_id")
    _text(request["repository_root"], "request.repository_root")
    _text(request["reviewed_head"], "request.reviewed_head")

    parent = _object(request["parent"], "request.parent")
    _require_keys(parent, ("thread_id", "branch"), "request.parent")
    _text(parent["thread_id"], "request.parent.thread_id")
    _text(parent["branch"], "request.parent.branch")

    findings = _list(request["findings"], "request.findings")
    if not findings:
        raise RecordError("request.findings must not be empty")
    finding_ids: list[str] = []
    for index, raw_finding in enumerate(findings):
        finding = _object(raw_finding, f"request.findings[{index}]")
        _require_keys(finding, ("id", "summary", "acceptance_points"), f"request.findings[{index}]")
        finding_ids.append(_text(finding["id"], f"request.findings[{index}].id"))
        _text(finding["summary"], f"request.findings[{index}].summary")
        _text_list(
            finding["acceptance_points"],
            f"request.findings[{index}].acceptance_points",
            allow_empty=False,
        )
    if len(finding_ids) != len(set(finding_ids)):
        raise RecordError("request.findings ids must be unique")

    _text_list(request["allowed_scope"], "request.allowed_scope", allow_empty=False)
    _text_list(request["focused_verification"], "request.focused_verification")
    _text_list(request["remaining_verification"], "request.remaining_verification")
    _text_list(request["excluded_side_effects"], "request.excluded_side_effects")
    if "findings_source" in request and request["findings_source"] is not None:
        _text(request["findings_source"], "request.findings_source")

    target = _object(request["fixer_target"], "request.fixer_target")
    _require_keys(target, ("worktree", "branch", "expected_head"), "request.fixer_target")
    _text(target["worktree"], "request.fixer_target.worktree")
    _text(target["branch"], "request.fixer_target.branch")
    _text(target["expected_head"], "request.fixer_target.expected_head")
    if target["expected_head"] != request["reviewed_head"]:
        raise RecordError("request.fixer_target.expected_head must equal request.reviewed_head")
    return request


def validate_state(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    validate_request(request)
    _require_keys(
        state,
        (
            "fix_id",
            "status",
            "updated_at",
            "fixer",
            "groups",
            "focused_verification",
            "remaining_verification",
            "blocker",
        ),
        "state",
    )
    if _text(state["fix_id"], "state.fix_id") != request["fix_id"]:
        raise RecordError("state.fix_id does not match request.fix_id")
    if state["status"] not in STATUSES:
        raise RecordError(f"state.status must be one of: {', '.join(sorted(STATUSES))}")
    _text(state["updated_at"], "state.updated_at")

    fixer = _object(state["fixer"], "state.fixer")
    _require_keys(fixer, ("thread_id", "worktree", "branch", "head"), "state.fixer")
    for key in ("thread_id", "worktree", "branch", "head"):
        _text(fixer[key], f"state.fixer.{key}")
    target = request["fixer_target"]
    if fixer["worktree"] != target["worktree"]:
        raise RecordError("state.fixer.worktree does not match request.fixer_target.worktree")
    if fixer["branch"] != target["branch"]:
        raise RecordError("state.fixer.branch does not match request.fixer_target.branch")

    request_ids = {finding["id"] for finding in request["findings"]}
    seen_bugs: list[str] = []
    groups = _list(state["groups"], "state.groups")
    group_ids: list[str] = []
    for index, raw_group in enumerate(groups):
        label = f"state.groups[{index}]"
        group = _object(raw_group, label)
        _require_keys(
            group,
            (
                "id",
                "bugs",
                "base",
                "worktree",
                "branch",
                "worker",
                "source_commits",
                "integrated_commits",
                "result",
                "conclusion",
            ),
            label,
        )
        group_ids.append(_text(group["id"], f"{label}.id"))
        bugs = _text_list(group["bugs"], f"{label}.bugs", allow_empty=False)
        unknown = sorted(set(bugs) - request_ids)
        if unknown:
            raise RecordError(f"{label}.bugs contains unknown findings: {', '.join(unknown)}")
        seen_bugs.extend(bugs)
        for key in ("base", "worktree", "branch", "worker"):
            _text(group[key], f"{label}.{key}")
        source = _text_list(group["source_commits"], f"{label}.source_commits")
        integrated = _text_list(group["integrated_commits"], f"{label}.integrated_commits")
        if group["result"] not in GROUP_RESULTS:
            raise RecordError(f"{label}.result must be one of: {', '.join(sorted(GROUP_RESULTS))}")
        _text(group["conclusion"], f"{label}.conclusion", allow_empty=group["result"] == "working")
        if group["result"] == "accepted":
            if not source or len(source) != len(integrated):
                raise RecordError(f"{label} accepted commits must be non-empty and correspond one-to-one")
    if len(group_ids) != len(set(group_ids)):
        raise RecordError("state.groups ids must be unique")
    if len(seen_bugs) != len(set(seen_bugs)):
        raise RecordError("a finding may belong to only one group")

    _list(state["focused_verification"], "state.focused_verification")
    _text_list(state["remaining_verification"], "state.remaining_verification")
    if state["remaining_verification"] != request["remaining_verification"]:
        raise RecordError("state.remaining_verification must match request.remaining_verification")

    if state["status"] == "ready":
        if set(seen_bugs) != request_ids:
            missing = sorted(request_ids - set(seen_bugs))
            raise RecordError(f"ready state does not cover findings: {', '.join(missing)}")
        if any(group["result"] != "accepted" for group in groups):
            raise RecordError("ready state requires every group to be accepted")
        source_commits = [commit for group in groups for commit in group["source_commits"]]
        integrated_commits = [commit for group in groups for commit in group["integrated_commits"]]
        if len(source_commits) != len(set(source_commits)):
            raise RecordError("ready state source commits must be unique across groups")
        if len(integrated_commits) != len(set(integrated_commits)):
            raise RecordError("ready state integrated commits must be unique across groups")
        if not integrated_commits or integrated_commits[-1] != fixer["head"]:
            raise RecordError("ready state final integrated commit must equal state.fixer.head")
        if request["focused_verification"] and not state["focused_verification"]:
            raise RecordError("ready state requires focused verification evidence")
        if state["blocker"] is not None:
            raise RecordError("ready state.blocker must be null")
    elif state["status"] == "blocked":
        _text(state["blocker"], "state.blocker")
    elif state["blocker"] is not None:
        _text(state["blocker"], "state.blocker")
    return state


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def atomic_create_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, path)
        except FileExistsError as exc:
            raise RecordError(f"immutable request already exists: {path}") from exc
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def create_request(records: Path, input_path: Path) -> dict[str, Any]:
    destination = records / "request.json"
    request = validate_request(read_json(input_path))
    atomic_create_json(destination, request)
    return request


def write_state(records: Path, input_path: Path) -> dict[str, Any]:
    request = validate_request(read_json(records / "request.json"))
    state = read_json(input_path)
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    validate_state(state, request)
    atomic_write_json(records / "state.json", state)
    return state


def fixer_view(records: Path) -> dict[str, Any]:
    request = validate_request(read_json(records / "request.json"))
    state_path = records / "state.json"
    state = validate_state(read_json(state_path), request) if state_path.exists() else None
    return {"request": request, "state": state}


def parent_view(records: Path) -> dict[str, Any]:
    request = validate_request(read_json(records / "request.json"))
    state = validate_state(read_json(records / "state.json"), request)
    if state["status"] not in {"ready", "blocked"}:
        raise RecordError("parent view requires terminal state: ready or blocked")
    integrated = [commit for group in state["groups"] for commit in group["integrated_commits"]]
    return {
        "fix_id": request["fix_id"],
        "status": state["status"],
        "updated_at": state["updated_at"],
        "reviewed_head": request["reviewed_head"],
        "fixer": state["fixer"],
        "commit_range": {
            "base": request["reviewed_head"],
            "head": state["fixer"]["head"],
            "integrated_commits": integrated,
        },
        "groups": [
            {
                "id": group["id"],
                "bugs": group["bugs"],
                "source_commits": group["source_commits"],
                "integrated_commits": group["integrated_commits"],
                "result": group["result"],
                "conclusion": group["conclusion"],
            }
            for group in state["groups"]
        ],
        "focused_verification": state["focused_verification"],
        "remaining_verification": state["remaining_verification"],
        "blocker": state["blocker"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, validate, update, and project dispatch-fix-thread records."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-request", help="create immutable request.json")
    create.add_argument("--records", type=Path, required=True)
    create.add_argument("--input", type=Path, required=True)

    write = subparsers.add_parser("write-state", help="validate and atomically replace state.json")
    write.add_argument("--records", type=Path, required=True)
    write.add_argument("--input", type=Path, required=True)

    show = subparsers.add_parser("show", help="print a validated fixer or parent view")
    show.add_argument("--records", type=Path, required=True)
    show.add_argument("--view", choices=("fixer", "parent"), required=True)

    validate = subparsers.add_parser("validate", help="validate records and print a short result")
    validate.add_argument("--records", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create-request":
            result = create_request(args.records, args.input)
        elif args.command == "write-state":
            result = write_state(args.records, args.input)
        elif args.command == "show":
            result = fixer_view(args.records) if args.view == "fixer" else parent_view(args.records)
        else:
            view = fixer_view(args.records)
            result = {
                "valid": True,
                "fix_id": view["request"]["fix_id"],
                "status": view["state"]["status"] if view["state"] else "not-started",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
