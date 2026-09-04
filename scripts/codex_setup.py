#!/usr/bin/env python3
"""Report Agent Workbench updates and audit/apply its Codex installation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

import link_skill


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_ROOT = REPO_ROOT / "plugin-marketplace"
MARKETPLACE_NAME = "agent-workbench"
TEMPLATE_PATH = REPO_ROOT / "templates" / "codex-setup-report.md.tpl"
ROLE_INSTALLER = (
    MARKETPLACE_ROOT / "plugins" / "impl-package" / "scripts" / "install_codex_agents.py"
)
IGNORED_DIRS = {".git", ".pytest_cache", "__pycache__"}
IGNORED_FILES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
STATUS_ORDER = ("BLOCKED", "DRIFT", "MISSING", "INSTALL-MISMATCH")
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DRIFT = 2


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    sha256: str
    entries: dict[str, str]


@dataclass
class AuditItem:
    kind: str
    name: str
    status: str
    expected_sha: str = "—"
    actual_sha: str = "—"
    expected_path: str = "—"
    actual_path: str = "—"
    note: str = ""
    differences: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    items: list[AuditItem]
    operational_error: bool = False

    @property
    def clean(self) -> bool:
        return not self.operational_error and all(item.status == "MATCH" for item in self.items)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_content(content: bytes) -> str:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        canonical = content
    else:
        canonical = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(canonical)


def _ignored(path: Path) -> bool:
    return (
        path.name in IGNORED_DIRS
        or path.name in IGNORED_FILES
        or path.suffix.lower() in IGNORED_SUFFIXES
    )


def snapshot_tree(root: Path) -> Snapshot:
    root = Path(root)
    if not root.is_dir():
        raise SetupError(f"directory is unavailable: {root}")

    entries: dict[str, str] = {}

    def visit(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise SetupError(f"cannot read directory {directory}: {exc}") from exc
        for child in children:
            if _ignored(child):
                continue
            relative = child.relative_to(root).as_posix()
            if link_skill.is_link(child):
                target = link_skill.link_target(child)
                target_text = str(target) if target is not None else "<unresolved>"
                entries[relative] = f"link:{_sha256_bytes(target_text.encode('utf-8'))}"
                continue
            try:
                if child.is_dir():
                    visit(child)
                elif child.is_file():
                    entries[relative] = f"file:{_sha256_content(child.read_bytes())}"
            except OSError as exc:
                raise SetupError(f"cannot hash {child}: {exc}") from exc

    visit(root)
    digest = hashlib.sha256()
    for relative, identity in sorted(entries.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(identity.encode("ascii"))
        digest.update(b"\n")
    return Snapshot(digest.hexdigest(), entries)


def snapshot_content(name: str, content: bytes) -> Snapshot:
    digest = _sha256_content(content)
    return Snapshot(digest, {name: f"file:{digest}"})


def diff_snapshots(expected: Snapshot, actual: Snapshot) -> list[str]:
    differences: list[str] = []
    for path in sorted(set(expected.entries) | set(actual.entries)):
        wanted = expected.entries.get(path)
        found = actual.entries.get(path)
        if wanted == found:
            continue
        if wanted is None:
            differences.append(f"A {path} | actual {found}")
        elif found is None:
            differences.append(f"D {path} | expected {wanted}")
        else:
            differences.append(f"M {path} | expected {wanted} | actual {found}")
    return differences


def _run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            cwd=cwd or REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise SetupError(f"cannot run {' '.join(args)}: {exc}") from exc


def _run_json(
    args: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = _run(args, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise SetupError(f"{' '.join(args)} failed: {detail}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError(f"{' '.join(args)} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise SetupError(f"{' '.join(args)} returned a non-object JSON value")
    return value


def _git(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args])


def _resolve_commit(ref: str) -> str:
    result = _git(["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        raise SetupError(f"cannot resolve Git commit {ref!r}; pass --from <sha> explicitly")
    return result.stdout.strip()


def _path_group(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("plugin-marketplace/"):
        return "plugins"
    for group in ("skills", "agents", "scripts", "docs"):
        if normalized == group or normalized.startswith(f"{group}/"):
            return group
    if normalized in {"README.md", "AGENTS.md"}:
        return "docs"
    return "other"


def pull_diff(from_ref: str, to_ref: str) -> dict[str, Any]:
    before = _resolve_commit(from_ref)
    after = _resolve_commit(to_ref)
    ancestor = _git(["merge-base", "--is-ancestor", before, after])
    if ancestor.returncode != 0:
        raise SetupError(
            f"{from_ref!r} is not an ancestor of {to_ref!r}; pass the real pull baseline with --from"
        )

    commits_result = _git(["log", "--reverse", "--format=%H%x09%s", f"{before}..{after}"])
    changes_result = _git(["diff", "--name-status", "--find-renames", f"{before}..{after}"])
    stat_result = _git(["diff", "--shortstat", f"{before}..{after}"])
    dirty_result = _git(["status", "--porcelain=v1"])
    for result, label in (
        (commits_result, "git log"),
        (changes_result, "git diff"),
        (stat_result, "git diff --shortstat"),
        (dirty_result, "git status"),
    ):
        if result.returncode != 0:
            raise SetupError(f"{label} failed: {(result.stderr or result.stdout).strip()}")

    commits = [line.split("\t", 1) for line in commits_result.stdout.splitlines() if line]
    groups: dict[str, list[str]] = {name: [] for name in ("plugins", "skills", "agents", "scripts", "docs", "other")}
    for line in changes_result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) >= 3:
            display = f"{status} {fields[1]} -> {fields[2]}"
            group_path = fields[2]
        else:
            display = f"{status} {fields[1]}"
            group_path = fields[1]
        groups[_path_group(group_path)].append(display)

    dirty = [line for line in dirty_result.stdout.splitlines() if line]
    return {
        "before": before,
        "after": after,
        "commits": commits,
        "groups": groups,
        "stat": stat_result.stdout.strip() or "no file changes",
        "dirty": dirty,
    }


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SetupError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _expected_plugins() -> list[dict[str, Any]]:
    manifest_path = MARKETPLACE_ROOT / ".agents" / "plugins" / "marketplace.json"
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
        if not isinstance(source, dict) or source.get("source") != "local" or not isinstance(source.get("path"), str):
            raise SetupError(f"plugin {item['name']} does not have a local source path")
        source_path = (MARKETPLACE_ROOT / source["path"]).resolve()
        try:
            source_path.relative_to(MARKETPLACE_ROOT.resolve())
        except ValueError as exc:
            raise SetupError(f"plugin {item['name']} escapes the marketplace root") from exc
        plugin_manifest = source_path / ".codex-plugin" / "plugin.json"
        try:
            plugin_data = json.loads(plugin_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SetupError(f"cannot read plugin manifest {plugin_manifest}: {exc}") from exc
        expected.append(
            {
                "name": item["name"],
                "source": source_path,
                "version": str(plugin_data.get("version", "unknown")),
            }
        )
    return expected


def _codex_env(codex_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return env


def _marketplace_root(data: dict[str, Any]) -> Path | None:
    entries = data.get("marketplaces")
    if not isinstance(entries, list):
        raise SetupError("codex marketplace list JSON has no marketplaces list")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == MARKETPLACE_NAME:
            root = entry.get("root")
            return Path(root) if isinstance(root, str) else None
    return None


def _blocked(kind: str, name: str, note: str) -> AuditItem:
    return AuditItem(kind=kind, name=name, status="BLOCKED", note=note)


def _path_is_within(path: Path, root: Path) -> bool:
    path_key = link_skill.normalize_path_key(path)
    root_key = link_skill.normalize_path_key(root)
    try:
        return os.path.commonpath([path_key, root_key]) == root_key
    except ValueError:
        return False


def _stale_workbench_links(
    kind: str,
    installed_root: Path,
    source_root: Path,
    expected_names: set[str],
) -> list[AuditItem]:
    if not installed_root.is_dir():
        return []
    results: list[AuditItem] = []
    try:
        children = list(installed_root.iterdir())
    except OSError as exc:
        return [_blocked(kind, installed_root.name, f"cannot enumerate {installed_root}: {exc}")]
    for child in sorted(children, key=lambda value: value.name.lower()):
        if child.name in expected_names or not link_skill.is_link(child):
            continue
        target = link_skill.link_target(child)
        if target is None or not _path_is_within(target, source_root):
            continue
        results.append(
            AuditItem(
                kind=kind,
                name=child.name,
                status="INSTALL-MISMATCH",
                expected_path="removed from current workbench inventory",
                actual_path=str(child),
                note=f"stale workbench link points to {target}",
            )
        )
    return results


def audit_plugins(codex_home: Path) -> tuple[list[AuditItem], bool]:
    try:
        expected_plugins = _expected_plugins()
    except SetupError as exc:
        return [_blocked("plugin", "agent-workbench", str(exc))], True

    env = _codex_env(codex_home)
    try:
        marketplaces = _run_json(["codex", "plugin", "marketplace", "list", "--json"], env=env)
        root = _marketplace_root(marketplaces)
    except SetupError as exc:
        return [_blocked("plugin", item["name"], str(exc)) for item in expected_plugins], True

    if root is None:
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
    if not link_skill.same_path(root, MARKETPLACE_ROOT):
        return [
            AuditItem(
                kind="plugin",
                name=item["name"],
                status="INSTALL-MISMATCH",
                expected_path=str(MARKETPLACE_ROOT),
                actual_path=str(root),
                note=f"marketplace {MARKETPLACE_NAME} points elsewhere",
            )
            for item in expected_plugins
        ], False

    try:
        listing = _run_json(
            ["codex", "plugin", "list", "--marketplace", MARKETPLACE_NAME, "--json"], env=env
        )
    except SetupError as exc:
        return [_blocked("plugin", item["name"], str(exc)) for item in expected_plugins], True
    installed_values = listing.get("installed")
    if not isinstance(installed_values, list):
        return [_blocked("plugin", item["name"], "codex plugin list JSON has no installed list") for item in expected_plugins], True
    installed = {
        item.get("name"): item
        for item in installed_values
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    results: list[AuditItem] = []
    for expected in expected_plugins:
        source = expected["source"]
        actual = installed.get(expected["name"])
        try:
            wanted = snapshot_tree(source)
        except SetupError as exc:
            results.append(_blocked("plugin", expected["name"], str(exc)))
            continue
        if actual is None:
            results.append(
                AuditItem(
                    kind="plugin",
                    name=expected["name"],
                    status="MISSING",
                    expected_sha=wanted.sha256,
                    expected_path=str(source),
                    note=f"source version {expected['version']}; plugin is not installed",
                )
            )
            continue
        installed_version = str(actual.get("version", "unknown"))
        cache = codex_home / "plugins" / "cache" / MARKETPLACE_NAME / expected["name"] / installed_version
        if not cache.is_dir():
            results.append(
                AuditItem(
                    kind="plugin",
                    name=expected["name"],
                    status="MISSING",
                    expected_sha=wanted.sha256,
                    expected_path=str(source),
                    actual_path=str(cache),
                    note=f"installed version {installed_version}; cache directory is missing",
                )
            )
            continue
        try:
            found = snapshot_tree(cache)
        except SetupError as exc:
            results.append(_blocked("plugin", expected["name"], str(exc)))
            continue
        status = "MATCH" if wanted.sha256 == found.sha256 else "DRIFT"
        note = f"source version {expected['version']}; installed version {installed_version}"
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
                expected_path=str(source),
                actual_path=str(cache),
                note=note,
                differences=diff_snapshots(wanted, found),
            )
        )
    return results, any(item.status == "BLOCKED" for item in results)


def _audit_linked_directory(kind: str, name: str, source: Path, destination: Path) -> AuditItem:
    try:
        wanted = snapshot_tree(source)
    except SetupError as exc:
        return _blocked(kind, name, str(exc))
    if not destination.exists() and not link_skill.is_link(destination):
        return AuditItem(
            kind=kind,
            name=name,
            status="MISSING",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
        )
    if link_skill.is_link(destination):
        target = link_skill.link_target(destination)
        if target is not None and link_skill.same_path(target, source):
            return AuditItem(
                kind=kind,
                name=name,
                status="MATCH",
                expected_sha=wanted.sha256,
                actual_sha=wanted.sha256,
                expected_path=str(source),
                actual_path=str(destination),
                note=f"linked to {target}",
            )
        return AuditItem(
            kind=kind,
            name=name,
            status="INSTALL-MISMATCH",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
            note=f"link points to {target or '<unresolved>'}",
        )
    if not destination.is_dir():
        return AuditItem(
            kind=kind,
            name=name,
            status="INSTALL-MISMATCH",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
            note="destination is not a directory link",
        )
    try:
        found = snapshot_tree(destination)
    except SetupError as exc:
        return _blocked(kind, name, str(exc))
    return AuditItem(
        kind=kind,
        name=name,
        status="INSTALL-MISMATCH",
        expected_sha=wanted.sha256,
        actual_sha=found.sha256,
        expected_path=str(source),
        actual_path=str(destination),
        note="destination is a real directory; it will not follow workbench updates",
        differences=diff_snapshots(wanted, found),
    )


def _expected_agent_sources() -> list[Path]:
    root = REPO_ROOT / "agents"
    return sorted(
        (item.resolve() for item in root.iterdir() if item.is_dir() and not item.name.startswith(".")),
        key=lambda path: path.name.lower(),
    )


def _expected_roles() -> tuple[dict[str, bytes], str]:
    module = _load_module(ROLE_INSTALLER, "codex_setup_role_installer")
    values = {
        f"{profile.name}.toml": module.render_codex_role(profile).encode("utf-8")
        for profile in module.load_profiles()
    }
    return values, module.MANAGED_MARKER


def _audit_role(name: str, content: bytes, marker: str, destination: Path) -> AuditItem:
    wanted = snapshot_content(name, content)
    if not destination.exists() and not link_skill.is_link(destination):
        return AuditItem(
            kind="role",
            name=name,
            status="MISSING",
            expected_sha=wanted.sha256,
            expected_path="generated by install_codex_agents.py",
            actual_path=str(destination),
        )
    if link_skill.is_link(destination) or not destination.is_file():
        return AuditItem(
            kind="role",
            name=name,
            status="INSTALL-MISMATCH",
            expected_sha=wanted.sha256,
            expected_path="generated by install_codex_agents.py",
            actual_path=str(destination),
            note="destination is not a regular managed file",
        )
    try:
        actual_content = destination.read_bytes()
    except OSError as exc:
        return _blocked("role", name, f"cannot read {destination}: {exc}")
    found = snapshot_content(name, actual_content)
    if wanted.sha256 == found.sha256:
        status = "MATCH"
        note = "managed projection matches"
    elif actual_content.startswith(f"{marker}\n".encode("utf-8")):
        status = "DRIFT"
        note = "managed projection differs"
    else:
        status = "INSTALL-MISMATCH"
        note = "existing file is not managed by Agent Workbench"
    return AuditItem(
        kind="role",
        name=name,
        status=status,
        expected_sha=wanted.sha256,
        actual_sha=found.sha256,
        expected_path="generated by install_codex_agents.py",
        actual_path=str(destination),
        note=note,
        differences=[] if status == "MATCH" else [f"M {name} | expected file:{wanted.sha256} | actual file:{found.sha256}"],
    )


def audit_codex(codex_home: Path) -> AuditResult:
    items, operational_error = audit_plugins(codex_home)
    skills_dir = codex_home / "skills"
    skill_sources = link_skill.list_all_skill_sources()
    for source in skill_sources:
        item = _audit_linked_directory("skill", source.name, source, skills_dir / source.name)
        items.append(item)
        operational_error = operational_error or item.status == "BLOCKED"
    stale_skills = _stale_workbench_links(
        "skill", skills_dir, REPO_ROOT / "skills", {source.name for source in skill_sources}
    )
    items.extend(stale_skills)
    operational_error = operational_error or any(item.status == "BLOCKED" for item in stale_skills)

    agents_dir = codex_home / "agents"
    try:
        agent_sources = _expected_agent_sources()
    except OSError as exc:
        items.append(_blocked("agent", "agents", f"cannot enumerate repository agents: {exc}"))
        operational_error = True
    else:
        for source in agent_sources:
            item = _audit_linked_directory("agent", source.name, source, agents_dir / source.name)
            items.append(item)
            operational_error = operational_error or item.status == "BLOCKED"
        stale_agents = _stale_workbench_links(
            "agent", agents_dir, REPO_ROOT / "agents", {source.name for source in agent_sources}
        )
        items.extend(stale_agents)
        operational_error = operational_error or any(item.status == "BLOCKED" for item in stale_agents)

    try:
        roles, marker = _expected_roles()
    except Exception as exc:  # renderer is an external repository contract
        items.append(_blocked("role", "review-track-*", f"cannot render expected roles: {exc}"))
        operational_error = True
    else:
        for name, content in sorted(roles.items()):
            item = _audit_role(name, content, marker, agents_dir / name)
            items.append(item)
            operational_error = operational_error or item.status == "BLOCKED"
    return AuditResult(items=items, operational_error=operational_error)


def audit_fingerprint(result: AuditResult, codex_home: Path) -> str:
    payload = {
        "schema": "agent-workbench.codex-audit.v1",
        "codex_home": str(codex_home),
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
    return _sha256_bytes(canonical.encode("utf-8"))


def _command_action(args: Sequence[str], *, env: dict[str, str] | None = None) -> tuple[bool, str]:
    result = _run(args, env=env)
    command = " ".join(str(value) for value in args)
    if result.returncode == 0:
        return True, f"PASS `{command}`"
    detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip().replace("\n", " ")
    return False, f"FAIL `{command}` — {detail}"


def _apply_agents(codex_home: Path) -> tuple[bool, list[str]]:
    actions: list[str] = []
    for source in _expected_agent_sources():
        result = link_skill.link_one(source, codex_home / "agents" / source.name)
        action = result["action"]
        note = f" ({result['message']})" if result.get("message") else ""
        actions.append(f"{action.upper()} agent `{source.name}`{note}")
        if action in {"conflict", "error"}:
            return False, actions
    return True, actions


def apply_codex(pre: AuditResult, codex_home: Path) -> tuple[list[str], bool]:
    actions: list[str] = []
    env = _codex_env(codex_home)
    plugin_items = [item for item in pre.items if item.kind == "plugin" and item.status != "MATCH"]
    if plugin_items:
        try:
            marketplaces = _run_json(["codex", "plugin", "marketplace", "list", "--json"], env=env)
            root = _marketplace_root(marketplaces)
        except SetupError as exc:
            actions.append(f"FAIL marketplace inspection — {exc}")
            return actions, False
        if root is not None and not link_skill.same_path(root, MARKETPLACE_ROOT):
            actions.append(
                f"BLOCKED marketplace `{MARKETPLACE_NAME}` points to `{root}`, expected `{MARKETPLACE_ROOT}`"
            )
            return actions, False
        if root is None:
            ok, message = _command_action(
                ["codex", "plugin", "marketplace", "add", "--json", str(MARKETPLACE_ROOT)], env=env
            )
            actions.append(message)
            if not ok:
                return actions, False
        for plugin in _expected_plugins():
            ok, message = _command_action(
                ["codex", "plugin", "add", "--json", f"{plugin['name']}@{MARKETPLACE_NAME}"], env=env
            )
            actions.append(message)
            if not ok:
                return actions, False

    if any(item.kind == "skill" and item.status != "MATCH" for item in pre.items):
        ok, message = _command_action(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "link_skill.py"),
                "--all",
                "--to",
                str(codex_home / "skills"),
                "--json",
            ],
            env=env,
        )
        actions.append(message)
        if not ok:
            return actions, False

    if any(item.kind == "agent" and item.status != "MATCH" for item in pre.items):
        ok, agent_actions = _apply_agents(codex_home)
        actions.extend(agent_actions)
        if not ok:
            return actions, False

    if any(item.kind == "role" and item.status != "MATCH" for item in pre.items):
        ok, message = _command_action(
            [
                sys.executable,
                str(ROLE_INSTALLER),
                "--target",
                str(codex_home / "agents"),
                "--force",
            ],
            env=env,
        )
        actions.append(message)
        if not ok:
            return actions, False
    if not actions:
        actions.append("SKIP installation already matches the workbench")
    return actions, True


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_pull(data: dict[str, Any] | None) -> str:
    if data is None:
        return "未运行。"
    lines = [
        f"- Pull 前：`{data['before']}`",
        f"- Pull 后：`{data['after']}`",
        f"- 统计：{data['stat']}",
        "",
        "### Commits",
        "",
    ]
    lines.extend(
        f"- `{commit}` {subject}" for commit, subject in data["commits"]
    )
    if not data["commits"]:
        lines.append("- 无新增 commit")
    for group, changes in data["groups"].items():
        if not changes:
            continue
        lines.extend(["", f"### {group}", ""])
        lines.extend(f"- `{_escape(change)}`" for change in changes)
    return "\n".join(lines)


def _render_audit(result: AuditResult | None) -> str:
    if result is None:
        return "未运行。"
    sections: list[str] = []
    for status in STATUS_ORDER:
        items = [item for item in result.items if item.status == status]
        if not items:
            continue
        sections.extend(
            [
                f"### {status} ({len(items)})",
                "",
                "| 类型 | 名称 | 安装位置 |",
                "|---|---|---|",
            ]
        )
        for item in items:
            sections.append(
                f"| {_escape(item.kind)} | `{_escape(item.name)}` | `{_escape(item.actual_path)}` |"
            )
        sections.append("")
    return "\n".join(sections).rstrip() or "未发现差异。"


def _render_workspace(dirty: list[str]) -> str:
    if not dirty:
        return "工作树 clean。"
    return "工作树存在以下未提交路径；它们未混入 pull commit 增量：\n\n" + "\n".join(
        f"- `{_escape(line)}`" for line in dirty
    )


def _render_actions(actions: list[str]) -> str:
    if not actions:
        return "未执行 apply。"
    return "\n".join(f"- {line}" for line in actions)


def render_report(
    *,
    mode: str,
    pull: dict[str, Any] | None = None,
    audit: AuditResult | None = None,
    actions: list[str] | None = None,
    codex_home: Path | None = None,
    report_sha: str = "—",
) -> str:
    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"cannot read report template {TEMPLATE_PATH}: {exc}") from exc
    dirty = pull["dirty"] if pull is not None else _git(["status", "--porcelain=v1"]).stdout.splitlines()
    if audit is None:
        summary = f"Pull commits: {len(pull['commits']) if pull else 0}"
        body = f"## Pull 增量\n\n{_render_pull(pull)}\n\n## 当前工作树\n\n{_render_workspace(dirty)}"
    else:
        counts = {status: sum(item.status == status for item in audit.items) for status in STATUS_ORDER}
        summary = ", ".join(f"{status}: {count}" for status, count in counts.items() if count)
        body = f"## 差异\n\n{_render_audit(audit)}"
        if actions:
            body += f"\n\n## Apply 动作\n\n{_render_actions(actions)}"
    values = {
        "mode": mode,
        "summary": summary or "未发现差异",
        "codex_home": str(codex_home) if codex_home is not None else "—",
        "report_sha": report_sha,
        "body": body,
    }
    report = template
    for key, value in values.items():
        report = report.replace(f"{{{{{key}}}}}", value)
    if "{{" in report or "}}" in report:
        raise SetupError("report template contains an unresolved placeholder")
    return report.rstrip() + "\n"


def _write_report(report: str, output: Path | None) -> None:
    if output is None:
        print(report, end="")
        return
    output = output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(output)


def default_codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    return Path(value).expanduser().absolute() if value else Path.home() / ".codex"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    pull_parser = subparsers.add_parser("pull-diff", help="report the last pulled Git increment")
    pull_parser.add_argument("--from", dest="from_ref", default="ORIG_HEAD")
    pull_parser.add_argument("--to", dest="to_ref", default="HEAD")
    pull_parser.add_argument("--output", type=Path)

    audit_parser = subparsers.add_parser("audit", help="report Agent Workbench content installed in Codex")
    audit_parser.add_argument("--output", type=Path)
    audit_parser.add_argument("--codex-home", type=Path)

    apply_parser = subparsers.add_parser("apply", help="apply a previously reported Codex audit")
    apply_parser.add_argument("--expect-report", required=True, help="audit SHA printed by the preceding audit")
    apply_parser.add_argument("--output", type=Path)
    apply_parser.add_argument("--codex-home", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.mode == "pull-diff":
            data = pull_diff(args.from_ref, args.to_ref)
            _write_report(render_report(mode="pull-diff", pull=data), args.output)
            return EXIT_OK

        codex_home = args.codex_home.expanduser().absolute() if args.codex_home else default_codex_home()
        pre = audit_codex(codex_home)
        pre_sha = audit_fingerprint(pre, codex_home)
        if args.mode == "audit":
            _write_report(
                render_report(
                    mode="audit",
                    audit=pre,
                    codex_home=codex_home,
                    report_sha=pre_sha,
                ),
                args.output,
            )
            if pre.operational_error:
                return EXIT_ERROR
            return EXIT_OK if pre.clean else EXIT_DRIFT

        if args.expect_report != pre_sha:
            actions = [
                f"BLOCKED 当前审计 SHA `{pre_sha}` 与 `--expect-report {args.expect_report}` 不一致；请重新运行 audit"
            ]
            _write_report(
                render_report(
                    mode="apply blocked",
                    audit=pre,
                    actions=actions,
                    codex_home=codex_home,
                    report_sha=pre_sha,
                ),
                args.output,
            )
            return EXIT_ERROR

        actions, apply_ok = apply_codex(pre, codex_home)
        result = audit_codex(codex_home)
        result_sha = audit_fingerprint(result, codex_home)
        _write_report(
            render_report(
                mode="apply",
                audit=result,
                actions=[f"PASS accepted audit SHA `{pre_sha}`", *actions],
                codex_home=codex_home,
                report_sha=result_sha,
            ),
            args.output,
        )
        if result.operational_error or not apply_ok:
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
