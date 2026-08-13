#!/usr/bin/env python3
"""Registry, routing and preflight projection for thread-harness."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import ledger_runtime as rt
from ledger_runtime import *
from broker_contract import node_kind, validate_broker_config
from package_adapter import PackageAdapterError, read_package_facts, read_package_observation

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

def broker_config_issues(registry: dict) -> list[tuple[str, str]]:
    return validate_broker_config(registry)[1]

def require_broker_config(registry: dict) -> dict:
    config, issues = validate_broker_config(registry)
    if issues or config is None:
        detail = "; ".join(f"{tag}: {value}" for tag, value in issues)
        raise LedgerError(f"invalid broker configuration: {detail}")
    return config

def format_broker_config_issues(issues: list[tuple[str, str]]) -> str:
    return "; ".join(f"{tag}={detail}" for tag, detail in issues) or "unknown"

def package_entry_value(value: dict) -> str | None:
    entry = value.get("package_entry")
    return entry if isinstance(entry, str) and entry.strip() else None

def package_facts_for_node(node: dict) -> dict:
    entry = package_entry_value(node)
    if not entry:
        raise PackageAdapterError(f"node {node['name']} has no package_entry")
    return read_package_facts(entry, current_session_id=node.get("session_id"))

def package_observation_for_node(node: dict) -> tuple[dict, list[tuple[str, str]]]:
    entry = package_entry_value(node)
    if not entry:
        raise PackageAdapterError(f"node {node['name']} has no package_entry")
    return read_package_observation(entry, current_session_id=node.get("session_id"))

def configure_routing(args) -> None:
    """Resolve the explicit registry path, with legacy coordination-id fallback."""

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
        rt.ACTIVE_REGISTRY_PATH = path
        args.coordination_id = registry_coordination_id
        return

    rt.ACTIVE_REGISTRY_PATH = None
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
                    "branch": value.get("branch") if isinstance(value.get("branch"), str) else None,
                    "package_entry": package_entry_value(value),
                    "node_type": "controller" if role == "controller" else node_kind(value),
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
                "package_entry": package_entry_value(controller),
                "node_type": "controller",
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
                "package_entry": package_entry_value(value),
                "node_type": node_kind(value),
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

def preflight_broker_and_packages(
    registry: dict,
    config: dict | None,
    nodes: list[dict],
    issues: list[tuple[str, str]],
    warnings: list[tuple[str, str]],
) -> None:
    if config is None:
        return
    active_children = [
        node for node in nodes
        if node["role"] == "child" and node.get("active", True)
    ]
    if config["profile"] == "solo" and len(active_children) != 1:
        issues.append(("solo_child_count", f"active_children={len(active_children)} expected=1"))

    for node in active_children:
        entry = node.get("package_entry")
        if config["profile"] == "solo" and not entry:
            issues.append(("solo_package_entry_missing", node["name"]))
        if node.get("node_type") == "task" and not entry:
            issues.append(("task_package_entry_missing", node["name"]))
        if not entry:
            continue
        entry_path = Path(entry).expanduser()
        if not entry_path.is_absolute():
            issues.append(("package_entry_not_absolute", f"{node['name']} -> {entry}"))
            continue
        try:
            facts, package_warnings = package_observation_for_node(node)
        except (OSError, PackageAdapterError) as exc:
            issues.append(("package_entry_invalid", f"{node['name']} -> {entry} ({exc})"))
            continue
        warnings.extend(
            (tag, f"{node['name']} -> {detail}")
            for tag, detail in package_warnings
        )
        worktree = node.get("worktree")
        if isinstance(worktree, str) and worktree.strip():
            if normalized_worktree(facts["worktree"]) != normalized_worktree(worktree):
                issues.append(
                    (
                        "package_worktree_mismatch",
                        f"{node['name']} registry={worktree} package={facts['worktree']}",
                    )
                )

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

__all__ = [name for name in globals() if not name.startswith("_")]
