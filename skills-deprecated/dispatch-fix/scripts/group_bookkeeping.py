#!/usr/bin/env python3
"""Atomically validate and store grouped dispatch-fix facts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESULTS = {"working", "accepted", "blocked"}
TOP_LEVEL_KEYS = {
    "fix_id",
    "repository_root",
    "fix_base",
    "integration",
    "updated_at",
    "groups",
}
INTEGRATION_KEYS = {"branch", "worktree"}
GROUP_KEYS = {
    "id",
    "topic",
    "findings",
    "write_scope",
    "branch",
    "worktree",
    "worker",
    "source_commits",
    "integrated_commits",
    "focused_verification",
    "result",
    "conclusion",
}
FINDING_KEYS = {"id", "summary", "acceptance_points"}


class RecordError(ValueError):
    """Raised when grouped repair facts violate the lightweight contract."""


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


def _exact_keys(data: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(data))
    unexpected = sorted(set(data) - expected)
    if missing:
        raise RecordError(f"{label} missing required fields: {', '.join(missing)}")
    if unexpected:
        raise RecordError(f"{label} contains unexpected fields: {', '.join(unexpected)}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except FileNotFoundError as exc:
        raise RecordError(f"record not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecordError(f"invalid JSON in {path}: {exc.msg}") from exc


def validate_groups(data: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(data, TOP_LEVEL_KEYS, "groups")
    for key in ("fix_id", "repository_root", "fix_base", "updated_at"):
        _text(data[key], f"groups.{key}")

    integration = _object(data["integration"], "groups.integration")
    _exact_keys(integration, INTEGRATION_KEYS, "groups.integration")
    _text(integration["branch"], "groups.integration.branch")
    _text(integration["worktree"], "groups.integration.worktree")

    groups = _list(data["groups"], "groups.groups")
    if not groups:
        raise RecordError("groups.groups must not be empty")

    group_ids: list[str] = []
    finding_ids: list[str] = []
    branches: list[str] = []
    worktrees: list[str] = []
    source_commits: list[str] = []
    integrated_commits: list[str] = []

    for group_index, raw_group in enumerate(groups):
        label = f"groups.groups[{group_index}]"
        group = _object(raw_group, label)
        _exact_keys(group, GROUP_KEYS, label)
        group_ids.append(_text(group["id"], f"{label}.id"))
        _text(group["topic"], f"{label}.topic")
        branches.append(_text(group["branch"], f"{label}.branch"))
        worktrees.append(_text(group["worktree"], f"{label}.worktree"))
        _text(group["worker"], f"{label}.worker")
        _text_list(group["write_scope"], f"{label}.write_scope", allow_empty=False)
        source = _text_list(group["source_commits"], f"{label}.source_commits")
        integrated = _text_list(group["integrated_commits"], f"{label}.integrated_commits")
        focused = _text_list(group["focused_verification"], f"{label}.focused_verification")
        source_commits.extend(source)
        integrated_commits.extend(integrated)

        findings = _list(group["findings"], f"{label}.findings")
        if not findings:
            raise RecordError(f"{label}.findings must not be empty")
        for finding_index, raw_finding in enumerate(findings):
            finding_label = f"{label}.findings[{finding_index}]"
            finding = _object(raw_finding, finding_label)
            _exact_keys(finding, FINDING_KEYS, finding_label)
            finding_ids.append(_text(finding["id"], f"{finding_label}.id"))
            _text(finding["summary"], f"{finding_label}.summary")
            _text_list(
                finding["acceptance_points"],
                f"{finding_label}.acceptance_points",
                allow_empty=False,
            )

        if group["result"] not in RESULTS:
            raise RecordError(f"{label}.result must be one of: {', '.join(sorted(RESULTS))}")
        _text(group["conclusion"], f"{label}.conclusion", allow_empty=group["result"] == "working")
        if group["result"] == "accepted":
            if not source or len(source) != len(integrated):
                raise RecordError(f"{label} accepted commits must be non-empty and correspond one-to-one")
            if not focused:
                raise RecordError(f"{label} accepted group requires focused verification evidence")

    for values, label in (
        (group_ids, "group ids"),
        (finding_ids, "finding ids"),
        (branches, "group branches"),
        (worktrees, "group worktrees"),
        (source_commits, "source commits"),
        (integrated_commits, "integrated commits"),
    ):
        if len(values) != len(set(values)):
            raise RecordError(f"{label} must be unique")
    return data


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


def write_groups(records: Path, input_path: Path) -> dict[str, Any]:
    data = read_json(input_path)
    data["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    validate_groups(data)
    atomic_write_json(records / "groups.json", data)
    return data


def show_groups(records: Path) -> dict[str, Any]:
    return validate_groups(read_json(records / "groups.json"))


def summary(records: Path) -> dict[str, Any]:
    data = show_groups(records)
    results = [group["result"] for group in data["groups"]]
    return {
        "valid": True,
        "fix_id": data["fix_id"],
        "groups": len(results),
        "accepted": results.count("accepted"),
        "blocked": results.count("blocked"),
        "working": results.count("working"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically write, show, or validate grouped dispatch-fix facts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser("write", help="validate and atomically write groups.json")
    write.add_argument("--records", type=Path, required=True)
    write.add_argument("--input", type=Path, required=True)

    show = subparsers.add_parser("show", help="print validated groups.json")
    show.add_argument("--records", type=Path, required=True)

    validate = subparsers.add_parser("validate", help="validate groups.json and print a summary")
    validate.add_argument("--records", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "write":
            result = write_groups(args.records, args.input)
        elif args.command == "show":
            result = show_groups(args.records)
        else:
            result = summary(args.records)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
