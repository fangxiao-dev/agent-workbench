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

from stable_docs_config import (
    ConfigError,
    load_plugin_identity,
    load_repository_config,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


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


def _require_git_repository(path: Path | str) -> Path:
    root = Path(path).resolve()
    if not root.is_dir():
        raise CollectorError(f"project root is not a directory: {root}")
    try:
        top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    except CollectorError as error:
        raise CollectorError(f"project root is not a Git repository: {root}") from error
    if top_level != root:
        raise CollectorError(f"project root must be the Git top level: {root}")
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
    if completed.returncode in (0, 1):
        return completed.returncode == 0
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


def _portable_origin_identity(root: Path) -> str:
    try:
        identity = _normalize_repository_identity(_git(root, "remote", "get-url", "origin"))
    except CollectorError as error:
        raise CollectorError("project origin must resolve to owner/repository") from error
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*", identity) is None:
        raise CollectorError("project origin must resolve to portable owner/repository identity")
    return identity


def _package_names(root: Path, head: str, implementations: str) -> list[str]:
    output = _git(
        root,
        "ls-tree",
        "-d",
        "--name-only",
        f"{head}:{implementations}",
        allow_empty=True,
    )
    names = sorted(line.strip() for line in output.splitlines() if line.strip())
    if not names:
        raise CollectorError(f"no tracked implementation packages at {implementations}")
    return names


def _package_files(root: Path, head: str, package_path: str) -> list[str]:
    output = _git(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        head,
        "--",
        package_path,
        allow_empty=True,
    )
    files = sorted(line.strip() for line in output.splitlines() if line.strip())
    if not files:
        raise CollectorError(f"package has no tracked files at source HEAD: {package_path}")
    return files


def _package_activity(root: Path, head: str, package_path: str) -> tuple[str, int]:
    output = _git(root, "log", "-1", "--format=%H%x09%ct", head, "--", package_path)
    commit, epoch = output.split("\t", 1)
    return commit, int(epoch)


def _changed_package_ids(
    root: Path, watermark: str, head: str, implementations: str
) -> list[str]:
    output = _git(
        root,
        "log",
        "--pretty=format:",
        "--name-only",
        f"{watermark}..{head}",
        "--",
        implementations,
        allow_empty=True,
    )
    prefix = implementations.split("/")
    package_ids: set[str] = set()
    for line in output.splitlines():
        parts = line.strip().replace("\\", "/").split("/")
        if len(parts) > len(prefix) and parts[: len(prefix)] == prefix:
            package_ids.add(parts[len(prefix)])
    return sorted(package_ids)


def _is_excluded(package_path: str, excludes: Sequence[str]) -> bool:
    return any(package_path == path or package_path.startswith(path.rstrip("/") + "/") for path in excludes)


def collect_inventory(
    *,
    mode: str,
    project_root: Path | str,
    source_head: str,
    project_watermark: str,
    fixture_count: int = 0,
    carry_forward: Sequence[str] = (),
    config_path: Path | str | None = None,
    plugin_root: Path | str = PLUGIN_ROOT,
) -> dict[str, object]:
    project = _require_git_repository(project_root)
    if mode not in {"bootstrap", "steady-state"}:
        raise CollectorError(f"unsupported collection mode: {mode}")
    if fixture_count < 0:
        raise CollectorError("fixture count cannot be negative")
    if mode == "steady-state" and fixture_count:
        raise CollectorError("steady-state mode requires fixture count 0")
    if mode == "bootstrap" and carry_forward:
        raise CollectorError("bootstrap mode does not accept carry-forward packages")
    try:
        config, config_metadata = load_repository_config(project, config_path)
        method_state = load_plugin_identity(plugin_root)
    except ConfigError as error:
        raise CollectorError(str(error)) from error

    resolved_head = _resolve_commit(project, source_head, "source HEAD")
    resolved_watermark = _resolve_commit(project, project_watermark, "project watermark")
    if not _is_ancestor(project, resolved_watermark, resolved_head):
        raise CollectorError(
            f"project watermark {resolved_watermark} is not an ancestor of {resolved_head}"
        )
    project_identity = _portable_origin_identity(project)
    configured_identity = config.get("repository")
    if configured_identity and configured_identity != project_identity:
        raise CollectorError(
            f"configured repository mismatch: expected {configured_identity}, found {project_identity}"
        )

    implementations = str(config["implementationsPath"])
    excludes = list(config["excludePaths"])
    rows: list[dict[str, object]] = []
    for package_id in _package_names(project, resolved_head, implementations):
        package_path = f"{implementations}/{package_id}"
        if _is_excluded(package_path, excludes):
            continue
        files = _package_files(project, resolved_head, package_path)
        activity_commit, activity_epoch = _package_activity(project, resolved_head, package_path)
        semantic = [f"{package_path}/{name}" for name in ("design.md", "spec.md") if f"{package_path}/{name}" in files]
        findings = f"{package_path}/findings.md"
        rows.append(
            {
                "package_id": package_id,
                "activity_commit": activity_commit,
                "activity_epoch": activity_epoch,
                "tree": _git(project, "rev-parse", f"{resolved_head}:{package_path}"),
                "semantic_sources": semantic,
                "supplemental_findings": [findings] if findings in files else [],
                "supplemental_evidence": (
                    [{"path": findings, "blob": _git(project, "rev-parse", f"{resolved_head}:{findings}")}]
                    if findings in files
                    else []
                ),
                "gate_paths": [f"{package_path}/gate.md"] if f"{package_path}/gate.md" in files else [],
            }
        )
    rows.sort(key=lambda row: (-int(row["activity_epoch"]), str(row["package_id"])))
    if fixture_count > len(rows):
        raise CollectorError(f"fixture count {fixture_count} exceeds package count {len(rows)}")

    fixtures = [str(row["package_id"]) for row in rows[:fixture_count]] if mode == "bootstrap" else []
    known = {str(row["package_id"]) for row in rows}
    changed = [
        package_id
        for package_id in _changed_package_ids(
            project, resolved_watermark, resolved_head, implementations
        )
        if not _is_excluded(f"{implementations}/{package_id}", excludes)
    ]
    removed = sorted(set(changed) - known)
    carry = sorted(set(carry_forward))
    unknown_carry = sorted(set(carry) - known)
    if unknown_carry:
        raise CollectorError(
            "carry-forward packages do not exist at source HEAD: " + ", ".join(unknown_carry)
        )
    watermark_new = sorted(set(changed) & known)
    bootstrap_targets = [str(row["package_id"]) for row in rows if row["package_id"] not in set(fixtures)] if mode == "bootstrap" else []
    eligible = bootstrap_targets if mode == "bootstrap" else sorted(set(watermark_new) | set(carry))
    for row in rows:
        package_id = str(row["package_id"])
        row["protected_fixture"] = package_id in fixtures
        row["carry_forward"] = package_id in carry
        row["watermark_new"] = package_id in watermark_new

    return {
        "schema_version": 2,
        "mode": mode,
        "method_activation": method_state,
        "config": {
            "schema_version": config["schemaVersion"],
            "source": config_metadata["source"],
            "sha256": config_metadata["sha256"],
            "implementations_path": implementations,
        },
        "project": {
            "repository": project_identity,
            "source_head": resolved_head,
            "watermark": resolved_watermark,
        },
        "package_count": len(rows),
        "fixture_count": fixture_count,
        "protected_fixtures": fixtures,
        "bootstrap_targets": bootstrap_targets,
        "carry_forward": carry,
        "watermark_new_packages": watermark_new,
        "removed_packages": removed,
        "eligible_removed_packages": removed,
        "eligible_packages": eligible,
        "packages": rows,
    }


def _render_markdown(inventory: dict[str, object]) -> str:
    project = inventory["project"]
    method = inventory["method_activation"]
    assert isinstance(project, dict) and isinstance(method, dict)
    lines = [
        "# Stable Docs Backfill Source Inventory",
        "",
        f"- Method: `{method['plugin']}@{method['version']}`",
        f"- Source HEAD: `{project['source_head']}`",
        f"- Project watermark: `{project['watermark']}`",
        f"- Packages: {inventory['package_count']}",
        f"- Removed packages requiring disposition: {len(inventory['removed_packages'])}",
        "",
        "| Package | Activity commit | Semantic sources | Findings | Fixture | Carry-forward | Watermark-new |",
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
    parser.add_argument("--mode", choices=("bootstrap", "steady-state"), required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--project-watermark", required=True)
    parser.add_argument("--fixture-count", type=int, default=0)
    parser.add_argument("--carry-forward", action="append", default=[])
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = collect_inventory(
            mode=args.mode,
            project_root=args.project_root,
            config_path=args.config,
            source_head=args.source_head,
            project_watermark=args.project_watermark,
            fixture_count=args.fixture_count,
            carry_forward=args.carry_forward,
        )
        rendered = json.dumps(inventory, indent=2, sort_keys=True) + "\n" if args.format == "json" else _render_markdown(inventory)
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            project = Path(args.project_root).resolve()
            output = args.output.resolve()
            if not _path_under(project, output):
                raise CollectorError("output path must remain under project root")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
        return 0
    except (CollectorError, ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
