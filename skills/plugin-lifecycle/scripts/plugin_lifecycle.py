#!/usr/bin/env python3
"""Plan and execute local plugin lifecycle operations for three agent hosts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HOSTS = ("codex", "claude", "grok")
ACTIONS = ("validate", "refresh", "reinstall", "upgrade")
SCOPES = ("user", "project", "local", "managed")
DEFAULT_TIMEOUT_S = 600


class ConfigError(ValueError):
    """A user-fixable configuration error."""


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in config: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("config root must be an object")
    return payload


def require_object(parent: Mapping[str, Any], key: str, where: str) -> Dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{where}.{key} must be an object")
    return dict(value)


def require_string(parent: Mapping[str, Any], key: str, where: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def load_plugin_manifests(plugin_root: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifests: List[Dict[str, Any]] = []
    for relative in (Path(".codex-plugin/plugin.json"), Path(".claude-plugin/plugin.json")):
        path = plugin_root / relative
        if not path.is_file():
            raise ConfigError(f"missing plugin manifest: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"invalid plugin manifest: {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConfigError(f"plugin manifest must be an object: {path}")
        manifests.append(value)
    return manifests[0], manifests[1]


def validate_config(payload: Mapping[str, Any], selected: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    plugin = require_object(payload, "plugin", "config")
    name = require_string(plugin, "name", "config.plugin")
    if any(char in name for char in ("/", "\\", "@")):
        raise ConfigError("config.plugin.name must be a plugin name, not a path or selector")
    root = expand_path(require_string(plugin, "root", "config.plugin"))
    if not root.is_dir():
        raise ConfigError(f"plugin root is not a directory: {root}")
    expected_version = require_string(plugin, "expected_version", "config.plugin")
    marketplace = require_string(plugin, "marketplace", "config.plugin")
    marketplace_root_value = plugin.get("marketplace_root")
    marketplace_root: Optional[Path] = None
    if marketplace_root_value is not None:
        if not isinstance(marketplace_root_value, str) or not marketplace_root_value.strip():
            raise ConfigError("config.plugin.marketplace_root must be a non-empty string when set")
        marketplace_root = expand_path(marketplace_root_value)
        if not marketplace_root.is_dir():
            raise ConfigError(f"marketplace_root is not a directory: {marketplace_root}")

    codex_manifest, claude_manifest = load_plugin_manifests(root)
    manifest_names = {codex_manifest.get("name"), claude_manifest.get("name")}
    if manifest_names != {name}:
        names_for_error = sorted((str(value) for value in manifest_names))
        raise ConfigError(f"plugin manifest names {names_for_error} do not match {name!r}")
    versions = {codex_manifest.get("version"), claude_manifest.get("version")}
    if versions != {expected_version}:
        versions_for_error = sorted((str(value) for value in versions))
        raise ConfigError(f"plugin manifest versions {versions_for_error} do not match {expected_version!r}")
    if marketplace_root is not None:
        for relative, label in (
            (Path(".claude-plugin/marketplace.json"), "Claude"),
            (Path(".agents/plugins/marketplace.json"), "Codex"),
        ):
            marketplace_path = marketplace_root / relative
            if not marketplace_path.is_file():
                raise ConfigError(f"missing {label} marketplace manifest: {marketplace_path}")
            try:
                market_payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigError(f"invalid {label} marketplace manifest: {marketplace_path}: {exc}") from exc
            entries = market_payload.get("plugins", []) if isinstance(market_payload, dict) else []
            matching = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == name]
            if len(matching) != 1:
                raise ConfigError(f"{label} marketplace must contain exactly one plugin entry for {name!r}")
            if label == "Claude" and matching[0].get("version") not in (None, expected_version):
                raise ConfigError(f"Claude marketplace version does not match {expected_version!r}")

    hosts_payload = require_object(payload, "hosts", "config")
    requested = set(selected or HOSTS)
    if not requested.issubset(set(HOSTS)):
        unknown = sorted(requested - set(HOSTS))
        raise ConfigError(f"unknown host(s): {', '.join(unknown)}")
    hosts: Dict[str, Dict[str, Any]] = {}
    for host in HOSTS:
        entry = hosts_payload.get(host, {})
        if not isinstance(entry, dict):
            raise ConfigError(f"config.hosts.{host} must be an object")
        enabled = entry.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ConfigError(f"config.hosts.{host}.enabled must be boolean")
        if host in requested and enabled:
            executable = require_string(entry, "executable", f"config.hosts.{host}")
            if host in ("codex", "claude"):
                host_marketplace = str(entry.get("marketplace", marketplace)).strip()
                if not host_marketplace:
                    raise ConfigError(f"config.hosts.{host}.marketplace must be non-empty")
            if host == "claude":
                scope = entry.get("scope", "user")
                if scope not in SCOPES:
                    raise ConfigError(f"config.hosts.claude.scope must be one of {', '.join(SCOPES)}")
            if host == "grok":
                source = require_string(entry, "source", "config.hosts.grok")
                source_path = expand_path(source)
                if not source_path.is_dir():
                    raise ConfigError(f"config.hosts.grok.source is not a directory: {source_path}")
            hosts[host] = dict(entry, executable=executable)
        elif host in requested and not enabled:
            raise ConfigError(f"selected host {host} is not enabled")
    if not hosts:
        raise ConfigError("no enabled hosts selected")
    return {
        "name": name,
        "root": root,
        "marketplace": marketplace,
        "marketplace_root": marketplace_root,
        "expected_version": expected_version,
        "manifest_versions": {
            "codex": codex_manifest.get("version"),
            "claude": claude_manifest.get("version"),
        },
        "hosts": hosts,
    }


def selector(config: Mapping[str, Any], host: str) -> str:
    entry = config["hosts"][host]
    marketplace = entry.get("marketplace", config["marketplace"])
    return f"{config['name']}@{marketplace}"


def command_plan(config: Mapping[str, Any], action: str, host: str) -> List[List[str]]:
    entry = config["hosts"][host]
    exe = str(entry["executable"])
    name = str(config["name"])
    marketplace_root = config.get("marketplace_root")
    if host == "codex":
        install = [exe, "plugin", "add", selector(config, host)]
        if action == "reinstall":
            return [[exe, "plugin", "remove", selector(config, host)], install]
        if action in ("refresh", "upgrade"):
            if marketplace_root is None:
                return [[exe, "plugin", "marketplace", "upgrade", entry.get("marketplace", config["marketplace"])], install]
            return [install]
    if host == "claude":
        scope = str(entry.get("scope", "user"))
        install = [exe, "plugin", "install", selector(config, host), "--scope", scope]
        if action == "reinstall":
            return [[exe, "plugin", "uninstall", selector(config, host), "--scope", scope, "--yes"], install]
        update = [exe, "plugin", "update", selector(config, host), "--scope", scope]
        if action in ("refresh", "upgrade"):
            prefix = [[exe, "plugin", "marketplace", "update", entry.get("marketplace", config["marketplace"])] ] if marketplace_root is not None else []
            return prefix + [update]
    if host == "grok":
        source = str(expand_path(str(entry["source"])))
        if action == "reinstall":
            return [[exe, "plugin", "uninstall", name], [exe, "plugin", "install", source, "--trust"]]
        if action in ("refresh", "upgrade"):
            return [[exe, "plugin", "update", name]]
    raise ConfigError(f"unsupported action {action!r} for host {host!r}")


def run_command(argv: Sequence[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def execute_host(config: Mapping[str, Any], action: str, host: str, apply: bool, timeout_s: int) -> Dict[str, Any]:
    commands = command_plan(config, action, host) if action != "validate" else []
    result: Dict[str, Any] = {
        "host": host,
        "status": "done" if action == "validate" else ("planned" if not apply else "done"),
        "commands": commands,
        "stdout": "",
        "stderr": "",
        "error": None,
    }
    if action == "validate" or not apply:
        return result
    stdout: List[str] = []
    stderr: List[str] = []
    for command in commands:
        try:
            completed = run_command(command, timeout_s)
        except subprocess.TimeoutExpired as exc:
            result["status"] = "failed"
            result["error"] = {"code": "timeout", "message": str(exc)}
            break
        except OSError as exc:
            result["status"] = "failed"
            result["error"] = {"code": "exec_error", "message": str(exc)}
            break
        stdout.append(completed.stdout or "")
        stderr.append(completed.stderr or "")
        if completed.returncode != 0:
            result["status"] = "failed"
            result["error"] = {
                "code": "command_failed",
                "message": f"command exited with {completed.returncode}",
                "returncode": completed.returncode,
            }
            break
    result["stdout"] = "".join(stdout)
    result["stderr"] = "".join(stderr)
    return result


def build_output(config: Mapping[str, Any], action: str, selected: Sequence[str], apply: bool, timeout_s: int) -> Dict[str, Any]:
    hosts = [execute_host(config, action, host, apply, timeout_s) for host in selected]
    ok = all(item["status"] in ("done", "planned") for item in hosts)
    if not apply and action != "validate":
        ok = True
    return {
        "ok": ok,
        "action": action,
        "plugin": {
            "name": config["name"],
            "root": str(config["root"]),
            "expected_version": config["expected_version"],
            "version_validated": True,
            "manifest_versions": config["manifest_versions"],
        },
        "hosts": hosts,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate, refresh, reinstall, or upgrade a local plugin.")
    parser.add_argument("--config", required=True, help="External JSON lifecycle configuration")
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--host", nargs="+", choices=HOSTS, help="Limit operation to selected hosts")
    parser.add_argument("--apply", action="store_true", help="Execute commands; default is dry-run")
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    return parser.parse_args(argv)


def enabled_hosts(payload: Mapping[str, Any]) -> List[str]:
    hosts = payload.get("hosts")
    if not isinstance(hosts, dict):
        raise ConfigError("config.hosts must be an object")
    return [host for host in HOSTS if isinstance(hosts.get(host), dict) and hosts[host].get("enabled")]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        payload = read_json(expand_path(args.config))
        selected = args.host or enabled_hosts(payload)
        config = validate_config(payload, selected)
        output = build_output(config, args.action, selected, args.apply, args.timeout_s)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output["ok"] else 1
    except ConfigError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "action": getattr(args, "action", None),
                    "plugin": None,
                    "hosts": [],
                    "error": {"code": "config_error", "message": str(exc)},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
