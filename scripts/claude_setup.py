#!/usr/bin/env python3
"""Audit the Agent Workbench content installed in the Claude host (read-only).

The audit inventories the plugin payload installed through the native
``claude plugin`` CLI and the skill links under the Claude home's
``skills/`` directory. It never mutates host state: plugin lifecycle stays
on the native CLI and skill repairs go through ``link_skill.py``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence

import link_skill
from host_setup_core import (
    STATUS_ORDER,
    AuditItem,
    AuditResult,
    SetupError,
    audit_linked_directory,
    blocked,
    diff_snapshots,
    render_audit,
    render_template,
    sha256_bytes,
    snapshot_tree,
    stale_workbench_links,
)


REPO_ROOT = link_skill.WORKBENCH_ROOT
MARKETPLACE_ROOT = REPO_ROOT / "plugin-marketplace"
MARKETPLACE_NAME = "agent-workbench"
TEMPLATE_PATH = REPO_ROOT / "templates" / "claude-setup-report.md.tpl"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DRIFT = 2


def _run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    command = shutil.which(str(args[0]))
    if command is None:
        raise SetupError(f"cannot find the {args[0]} CLI on PATH")
    try:
        return subprocess.run(
            [command, *args[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise SetupError(f"cannot run {' '.join(args)}: {exc}") from exc


def _run_json_list(args: Sequence[str]) -> list[dict[str, Any]]:
    result = _run(args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise SetupError(f"{' '.join(args)} failed: {detail}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError(f"{' '.join(args)} returned invalid JSON") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SetupError(f"{' '.join(args)} returned a non-list JSON value")
    return value


def _expected_plugins() -> list[dict[str, Any]]:
    manifest_path = MARKETPLACE_ROOT / ".claude-plugin" / "marketplace.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"cannot read workbench marketplace: {exc}") from exc
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        raise SetupError("workbench marketplace has no plugins list")

    expected: list[dict[str, Any]] = []
    for item in plugins:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SetupError("workbench marketplace contains an invalid plugin entry")
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise SetupError(f"plugin {item['name']} does not have a source path")
        source_path = (MARKETPLACE_ROOT / source).resolve()
        try:
            source_path.relative_to(MARKETPLACE_ROOT.resolve())
        except ValueError as exc:
            raise SetupError(f"plugin {item['name']} escapes the marketplace root") from exc
        plugin_manifest = source_path / ".claude-plugin" / "plugin.json"
        try:
            plugin_data = json.loads(plugin_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SetupError(f"cannot read plugin manifest {plugin_manifest}: {exc}") from exc
        version = str(plugin_data.get("version", "unknown"))
        entry_version = item.get("version")
        if isinstance(entry_version, str) and entry_version != version:
            raise SetupError(
                f"plugin {item['name']} marketplace entry version {entry_version} "
                f"does not match plugin manifest version {version}"
            )
        expected.append({"name": item["name"], "source": source_path, "version": version})
    return expected


def _marketplace_entries() -> list[dict[str, Any]]:
    return _run_json_list(["claude", "plugin", "marketplace", "list", "--json"])


def _installed_plugins() -> list[dict[str, Any]]:
    return _run_json_list(["claude", "plugin", "list", "--json"])


def audit_plugins() -> tuple[list[AuditItem], bool]:
    try:
        expected_plugins = _expected_plugins()
    except SetupError as exc:
        return [blocked("plugin", "agent-workbench", str(exc))], True

    try:
        marketplaces = _marketplace_entries()
    except SetupError as exc:
        return [blocked("plugin", item["name"], str(exc)) for item in expected_plugins], True
    registered = next(
        (entry for entry in marketplaces if entry.get("name") == MARKETPLACE_NAME), None
    )
    if registered is None:
        return [
            AuditItem(
                kind="plugin",
                name=item["name"],
                status="MISSING",
                expected_path=str(item["source"]),
                note=f"marketplace {MARKETPLACE_NAME} is not registered",
            )
            for item in expected_plugins
        ], False
    root_text = registered.get("path") or registered.get("installLocation")
    registered_root = Path(root_text) if isinstance(root_text, str) and root_text else None
    if registered_root is None:
        return [
            blocked("plugin", item["name"], "claude marketplace list JSON has no path")
            for item in expected_plugins
        ], True
    if not link_skill.same_path(registered_root, MARKETPLACE_ROOT):
        return [
            AuditItem(
                kind="plugin",
                name=item["name"],
                status="INSTALL-MISMATCH",
                expected_path=str(MARKETPLACE_ROOT),
                actual_path=str(registered_root),
                note=f"marketplace {MARKETPLACE_NAME} points elsewhere",
            )
            for item in expected_plugins
        ], False

    try:
        installed = _installed_plugins()
    except SetupError as exc:
        return [blocked("plugin", item["name"], str(exc)) for item in expected_plugins], True

    results: list[AuditItem] = []
    for expected in expected_plugins:
        plugin_id = f"{expected['name']}@{MARKETPLACE_NAME}"
        entries = [entry for entry in installed if entry.get("id") == plugin_id]
        try:
            wanted = snapshot_tree(expected["source"])
        except SetupError as exc:
            results.append(blocked("plugin", expected["name"], str(exc)))
            continue
        if not entries:
            results.append(
                AuditItem(
                    kind="plugin",
                    name=expected["name"],
                    status="MISSING",
                    expected_sha=wanted.sha256,
                    expected_path=str(expected["source"]),
                    note=f"source version {expected['version']}; plugin is not installed",
                )
            )
            continue
        if len(entries) > 1:
            scopes = ", ".join(str(entry.get("scope", "unknown")) for entry in entries)
            results.append(
                AuditItem(
                    kind="plugin",
                    name=expected["name"],
                    status="INSTALL-MISMATCH",
                    expected_path=str(expected["source"]),
                    note=f"plugin is installed in multiple scopes: {scopes}",
                )
            )
            continue
        actual = entries[0]
        installed_version = str(actual.get("version", "unknown"))
        scope = str(actual.get("scope", "unknown"))
        install_path_text = actual.get("installPath")
        if not isinstance(install_path_text, str) or not install_path_text:
            results.append(
                blocked("plugin", expected["name"], "claude plugin list JSON has no installPath")
            )
            continue
        cache = Path(install_path_text)
        if not cache.is_dir():
            results.append(
                AuditItem(
                    kind="plugin",
                    name=expected["name"],
                    status="MISSING",
                    expected_sha=wanted.sha256,
                    expected_path=str(expected["source"]),
                    actual_path=str(cache),
                    note=f"installed version {installed_version}; cache directory is missing",
                )
            )
            continue
        try:
            found = snapshot_tree(cache)
        except SetupError as exc:
            results.append(blocked("plugin", expected["name"], str(exc)))
            continue
        status = "MATCH" if wanted.sha256 == found.sha256 else "DRIFT"
        note = f"source version {expected['version']}; installed version {installed_version} (scope {scope})"
        if actual.get("enabled") is not True:
            status = "INSTALL-MISMATCH"
            note += "; plugin is disabled"
        results.append(
            AuditItem(
                kind="plugin",
                name=expected["name"],
                status=status,
                expected_sha=wanted.sha256,
                actual_sha=found.sha256,
                expected_path=str(expected["source"]),
                actual_path=str(cache),
                note=note,
                differences=diff_snapshots(wanted, found),
            )
        )
    return results, any(item.status == "BLOCKED" for item in results)


def audit_claude(claude_home: Path) -> AuditResult:
    items, operational_error = audit_plugins()
    skills_dir = claude_home / "skills"
    skill_sources = link_skill.list_all_skill_sources()
    for source in skill_sources:
        item = audit_linked_directory("skill", source.name, source, skills_dir / source.name)
        items.append(item)
        operational_error = operational_error or item.status == "BLOCKED"
    stale_skills = stale_workbench_links(
        "skill", skills_dir, REPO_ROOT / "skills", {source.name for source in skill_sources}
    )
    items.extend(stale_skills)
    operational_error = operational_error or any(item.status == "BLOCKED" for item in stale_skills)
    return AuditResult(items=items, operational_error=operational_error)


def audit_fingerprint(result: AuditResult, claude_home: Path) -> str:
    payload = {
        "schema": "agent-workbench.claude-audit.v1",
        "claude_home": str(claude_home),
        "operational_error": result.operational_error,
        "items": [
            {
                "kind": item.kind,
                "name": item.name,
                "status": item.status,
                "expected_sha": item.expected_sha,
                "actual_sha": item.actual_sha,
                "expected_path": item.expected_path,
                "actual_path": item.actual_path,
            }
            for item in sorted(result.items, key=lambda value: (value.kind, value.name))
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def render_report(
    *,
    mode: str,
    audit: AuditResult | None = None,
    claude_home: Path | None = None,
    report_sha: str = "—",
) -> str:
    if audit is None:
        summary = "未发现差异"
        body = "未运行。"
    else:
        counts = {status: sum(item.status == status for item in audit.items) for status in STATUS_ORDER}
        summary = ", ".join(f"{status}: {count}" for status, count in counts.items() if count)
        body = f"## 差异\n\n{render_audit(audit)}"
    return render_template(
        TEMPLATE_PATH,
        {
            "mode": mode,
            "summary": summary or "未发现差异",
            "claude_home": str(claude_home) if claude_home is not None else "—",
            "report_sha": report_sha,
            "body": body,
        },
    )


def _write_report(report: str, output: Path | None) -> None:
    if output is None:
        print(report, end="")
        return
    output = output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(output)


def default_claude_home() -> Path:
    value = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(value).expanduser().absolute() if value else Path.home() / ".claude"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    audit_parser = subparsers.add_parser(
        "audit", help="report Agent Workbench content installed in Claude"
    )
    audit_parser.add_argument("--output", type=Path)
    audit_parser.add_argument("--claude-home", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        claude_home = (
            args.claude_home.expanduser().absolute() if args.claude_home else default_claude_home()
        )
        result = audit_claude(claude_home)
        result_sha = audit_fingerprint(result, claude_home)
        _write_report(
            render_report(mode="audit", audit=result, claude_home=claude_home, report_sha=result_sha),
            args.output,
        )
        if result.operational_error:
            return EXIT_ERROR
        return EXIT_OK if result.clean else EXIT_DRIFT
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
