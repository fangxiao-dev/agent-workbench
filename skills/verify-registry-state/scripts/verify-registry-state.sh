#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SKILLS_MD="$REPO_ROOT/registry/skills.md"
SKILLS_LOCK="$REPO_ROOT/registry/skills.lock.json"
PLUGINS_MD="$REPO_ROOT/registry/plugins.md"
AGENTS_LOCK="$HOME/.agents/.skill-lock.json"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CLAUDE_INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
CODEX_CONFIG="$HOME/.codex/config.toml"

python - "$SKILLS_MD" "$SKILLS_LOCK" "$PLUGINS_MD" "$AGENTS_LOCK" "$CLAUDE_SETTINGS" "$CLAUDE_INSTALLED_PLUGINS" "$CODEX_CONFIG" "$REPO_ROOT" <<'PY'
import json
import sys
from pathlib import Path

skills_md, skills_lock, plugins_md, agents_lock, claude_settings, claude_plugins, codex_config, repo_root = sys.argv[1:]
repo_root = Path(repo_root)

def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

skills_state = load_json(skills_lock) or {"skills": []}
agents_state = load_json(agents_lock) or {}
settings_state = load_json(claude_settings) or {}
plugins_state = load_json(claude_plugins) or {}
codex_text = Path(codex_config).read_text(encoding="utf-8") if Path(codex_config).exists() else ""

skill_map = {entry["name"]: entry for entry in skills_state.get("skills", [])}

def skill_installed(name):
    entry = skill_map.get(name)
    if not entry:
        return None
    local_path = entry.get("localPath")
    if local_path and (repo_root / local_path).exists():
        return True
    return name in (agents_state.get("skills") or {})

def plugin_installed(name, host):
    if host == "Claude plugin":
        enabled = bool((settings_state.get("enabledPlugins") or {}).get(name))
        installed = name in (plugins_state.get("plugins") or {})
        return enabled and installed
    if host == "Codex MCP server":
        return name in codex_text
    return False

def update_table(path, resolver):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out = []
    status_index = None
    for line in lines:
        if line.startswith("|"):
            parts = line.split("|")
            if status_index is None:
                try:
                    status_index = parts.index(" 状态 ")
                except ValueError:
                    status_index = None
            if len(parts) >= 6 and parts[1].strip() not in {"Skill", "Plugin", "-------", "--------"}:
                name = parts[1].strip()
                host = parts[2].strip()
                status = resolver(name, host)
                if status is not None and status_index is not None:
                    parts[status_index] = f" {status} "
                    line = "|".join(parts)
        out.append(line)
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")

update_table(skills_md, lambda name, host: "✅ 已装" if skill_installed(name) else "⬜ 未装")
update_table(plugins_md, lambda name, host: "✅ 已装" if plugin_installed(name, host) else "⬜ 未装")
PY

echo "Registry 状态已刷新："
echo "  - $SKILLS_MD"
echo "  - $PLUGINS_MD"

