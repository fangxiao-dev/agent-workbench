#!/usr/bin/env python3
"""Collect deterministic Stable Docs backfill source inventory from Git."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence


class CollectorError(RuntimeError):
    """Raised when source inventory cannot be collected safely."""


def _git(root: Path, *args: str, allow_empty: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CollectorError(f"git {' '.join(args)} failed in {root}: {detail}")
    output = completed.stdout.strip()
    if not output and not allow_empty:
        raise CollectorError(f"git {' '.join(args)} returned no result in {root}")
    return output


def _require_git_repository(path: Path, label: str) -> Path:
    root = path.resolve()
    if not root.is_dir():
        raise CollectorError(f"{label} is not a directory: {root}")
    try:
        top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    except CollectorError as error:
        raise CollectorError(f"{label} is not a Git repository: {root}") from error
    if top_level != root:
        raise CollectorError(f"{label} must be the Git top level: {root}")
    return root


def _resolve_commit(root: Path, value: str, label: str) -> str:
    try:
        return _git(root, "rev-parse", "--verify", f"{value}^{{commit}}")
    except CollectorError as error:
        raise CollectorError(f"{label} does not resolve to a commit: {value}") from error


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise CollectorError(
        "git merge-base --is-ancestor failed: "
        + (completed.stderr.strip() or completed.stdout.strip())
    )


def _normalize_repository_identity(remote: str) -> str:
    value = remote.strip().replace("\\", "/")
    if value.endswith(".git"):
        value = value[:-4]
    if "://" in value:
        value = value.split("://", 1)[1]
        parts = value.split("/", 1)
        value = parts[1] if len(parts) == 2 else parts[0]
    elif re.match(r"^[^@]+@[^:]+:", value):
        value = value.split(":", 1)[1]
    return value.strip("/").lower()


def _parse_method_ref(value: str) -> tuple[str, str]:
    if "@" not in value:
        raise CollectorError("method ref must use <repository-identity>@<commit>")
    identity, commit = value.rsplit("@", 1)
    identity = identity.strip().strip("/").lower()
    commit = commit.strip()
    if not identity or not commit:
        raise CollectorError("method ref must use <repository-identity>@<commit>")
    return identity, commit


def _validate_method_ref(method_root: Path, method_ref: str) -> dict[str, str]:
    expected_identity, requested_commit = _parse_method_ref(method_ref)
    remote = _git(method_root, "remote", "get-url", "origin")
    actual_identity = _normalize_repository_identity(remote)
    if actual_identity != expected_identity:
        raise CollectorError(
            "method repository identity mismatch: "
            f"expected {expected_identity}, found {actual_identity}"
        )
    commit = _resolve_commit(method_root, requested_commit, "method commit")
    return {"repository": expected_identity, "commit": commit}


def _package_names(project_root: Path, source_head: str) -> list[str]:
    output = _git(
        project_root,
        "ls-tree",
        "-d",
        "--name-only",
        f"{source_head}:docs/implementations",
        allow_empty=True,
    )
    names = [line.strip() for line in output.splitlines() if line.strip()]
    if not names:
        raise CollectorError("no tracked implementation packages at source HEAD")
    return sorted(names)


def _package_files(project_root: Path, source_head: str, package_id: str) -> list[str]:
    package_path = f"docs/implementations/{package_id}"
    output = _git(
        project_root,
        "ls-tree",
        "-r",
        "--name-only",
        source_head,
        "--",
        package_path,
        allow_empty=True,
    )
    files = [line.strip() for line in output.splitlines() if line.strip()]
    if not files:
        raise CollectorError(f"package has no tracked files at source HEAD: {package_id}")
    return sorted(files)


def _package_activity(
    project_root: Path, source_head: str, package_id: str
) -> tuple[str, int]:
    package_path = f"docs/implementations/{package_id}"
    output = _git(
        project_root,
        "log",
        "-1",
        "--format=%H%x09%ct",
        source_head,
        "--",
        package_path,
    )
    commit, epoch = output.split("\t", 1)
    return commit, int(epoch)


def _package_tree(project_root: Path, source_head: str, package_id: str) -> str:
    return _git(
        project_root,
        "rev-parse",
        f"{source_head}:docs/implementations/{package_id}",
    )


def _changed_after_watermark(
    project_root: Path, watermark: str, source_head: str, package_id: str
) -> bool:
    package_path = f"docs/implementations/{package_id}"
    output = _git(
        project_root,
        "log",
        "-1",
        "--format=%H",
        f"{watermark}..{source_head}",
        "--",
        package_path,
        allow_empty=True,
    )
    return bool(output)


def collect_inventory(
    *,
    project_root: Path | str,
    source_head: str,
    project_watermark: str,
    method_root: Path | str,
    method_ref: str,
    fixture_count: int,
    carry_forward: Sequence[str],
) -> dict[str, object]:
    project = _require_git_repository(Path(project_root), "project root")
    method = _require_git_repository(Path(method_root), "method root")
    if fixture_count < 0:
        raise CollectorError("fixture count cannot be negative")

    resolved_head = _resolve_commit(project, source_head, "source HEAD")
    resolved_watermark = _resolve_commit(
        project, project_watermark, "project watermark"
    )
    if not _is_ancestor(project, resolved_watermark, resolved_head):
        raise CollectorError(
            f"project watermark {resolved_watermark} is not an ancestor of {resolved_head}"
        )
    method_state = _validate_method_ref(method, method_ref)

    rows: list[dict[str, object]] = []
    for package_id in _package_names(project, resolved_head):
        files = _package_files(project, resolved_head, package_id)
        activity_commit, activity_epoch = _package_activity(
            project, resolved_head, package_id
        )
        prefix = f"docs/implementations/{package_id}/"
        semantic_sources = [
            f"{prefix}{name}"
            for name in ("design.md", "spec.md")
            if f"{prefix}{name}" in files
        ]
        findings_path = f"{prefix}findings.md"
        supplemental_findings = [findings_path] if findings_path in files else []
        rows.append(
            {
                "package_id": package_id,
                "activity_commit": activity_commit,
                "activity_epoch": activity_epoch,
                "tree": _package_tree(project, resolved_head, package_id),
                "semantic_sources": semantic_sources,
                "supplemental_findings": supplemental_findings,
                "gate_paths": [f"{prefix}gate.md"]
                if f"{prefix}gate.md" in files
                else [],
            }
        )

    rows.sort(key=lambda row: (-int(row["activity_epoch"]), str(row["package_id"])))
    if fixture_count > len(rows):
        raise CollectorError(
            f"fixture count {fixture_count} exceeds package count {len(rows)}"
        )
    fixtures = [str(row["package_id"]) for row in rows[:fixture_count]]
    fixture_set = set(fixtures)

    known_packages = {str(row["package_id"]) for row in rows}
    carry = sorted(set(carry_forward))
    unknown_carry = sorted(set(carry) - known_packages)
    if unknown_carry:
        raise CollectorError(
            "carry-forward packages do not exist at source HEAD: "
            + ", ".join(unknown_carry)
        )

    watermark_new = sorted(
        str(row["package_id"])
        for row in rows
        if _changed_after_watermark(
            project, resolved_watermark, resolved_head, str(row["package_id"])
        )
    )
    eligible = sorted(set(watermark_new) | set(carry))

    for row in rows:
        package_id = str(row["package_id"])
        row["protected_fixture"] = package_id in fixture_set
        row["carry_forward"] = package_id in carry
        row["watermark_new"] = package_id in watermark_new

    return {
        "schema_version": 1,
        "method_activation": method_state,
        "project": {
            "repository": _normalize_repository_identity(
                _git(project, "remote", "get-url", "origin", allow_empty=True)
            )
            if _git(project, "remote", allow_empty=True)
            else None,
            "source_head": resolved_head,
            "watermark": resolved_watermark,
        },
        "package_count": len(rows),
        "fixture_count": fixture_count,
        "protected_fixtures": fixtures,
        "bootstrap_targets": [
            str(row["package_id"])
            for row in rows
            if str(row["package_id"]) not in fixture_set
        ],
        "carry_forward": carry,
        "watermark_new_packages": watermark_new,
        "eligible_packages": eligible,
        "packages": rows,
    }


def _render_markdown(inventory: dict[str, object]) -> str:
    project = inventory["project"]
    assert isinstance(project, dict)
    lines = [
        "# Stable Docs Backfill Source Inventory",
        "",
        f"- Source HEAD: `{project['source_head']}`",
        f"- Project watermark: `{project['watermark']}`",
        f"- Packages: {inventory['package_count']}",
        f"- Protected fixtures: {inventory['fixture_count']}",
        "",
        "| Package | Activity commit | Semantic sources | Supplemental findings | Fixture | Carry-forward | Watermark-new |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    packages = inventory["packages"]
    assert isinstance(packages, list)
    for row in packages:
        assert isinstance(row, dict)
        lines.append(
            "| {package_id} | `{activity_commit}` | {semantic} | {findings} | {fixture} | {carry} | {new} |".format(
                package_id=row["package_id"],
                activity_commit=row["activity_commit"],
                semantic="<br>".join(row["semantic_sources"]) or "none",
                findings="<br>".join(row["supplemental_findings"]) or "none",
                fixture="yes" if row["protected_fixture"] else "no",
                carry="yes" if row["carry_forward"] else "no",
                new="yes" if row["watermark_new"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def _path_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--project-watermark", required=True)
    parser.add_argument("--method-root", type=Path, required=True)
    parser.add_argument("--method-ref", required=True)
    parser.add_argument("--fixture-count", type=int, default=0)
    parser.add_argument("--carry-forward", action="append", default=[])
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = collect_inventory(
            project_root=args.project_root,
            source_head=args.source_head,
            project_watermark=args.project_watermark,
            method_root=args.method_root,
            method_ref=args.method_ref,
            fixture_count=args.fixture_count,
            carry_forward=args.carry_forward,
        )
        rendered = (
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else _render_markdown(inventory)
        )
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            project_root = Path(args.project_root).resolve()
            output = args.output.resolve()
            if not _path_under(project_root, output):
                raise CollectorError("output path must remain under project root")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
        return 0
    except CollectorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
