#!/usr/bin/env bash
set -euo pipefail

skill_name=""
package=""
target_dir=""
source_type="github"
source_url=""
install_method="npx skills add"
force="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill-name) skill_name="$2"; shift 2 ;;
    --package) package="$2"; shift 2 ;;
    --target-dir) target_dir="$2"; shift 2 ;;
    --source-type) source_type="$2"; shift 2 ;;
    --source-url) source_url="$2"; shift 2 ;;
    --install-method) install_method="$2"; shift 2 ;;
    --force) force="true"; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$skill_name" || -z "$package" || -z "$target_dir" ]]; then
  echo "Required: --skill-name, --package, --target-dir" >&2
  exit 1
fi

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
target_root="$repo_root/$target_dir"
target_path="$target_root/$skill_name"
registry_md="$repo_root/registry/third-party-skills.md"
registry_lock="$repo_root/registry/skills.lock.json"

resolve_installed_skill_path() {
  local candidates=(
    "$repo_root/.claude/skills/$skill_name"
    "$HOME/.claude/skills/$skill_name"
    "$HOME/.agents/skills/$skill_name"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -e "$candidate" ]]; then
      cd "$candidate" && pwd
      return 0
    fi
  done
  echo "Installed skill '$skill_name' not found under .claude/skills or .agents/skills." >&2
  exit 1
}

installed_path="$(resolve_installed_skill_path)"
mkdir -p "$target_root"
if [[ -e "$target_path" ]]; then
  if [[ "$force" != "true" ]]; then
    echo "Target path already exists: $target_path. Re-run with --force to overwrite." >&2
    exit 1
  fi
  rm -rf "$target_path"
fi
cp -R "$installed_path" "$target_path"

python - "$registry_lock" "$registry_md" "$skill_name" "$package" "$target_dir" "$source_type" "$source_url" "$install_method" <<'PY'
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

lock_path, md_path, skill_name, package, target_dir, source_type, source_url, install_method = sys.argv[1:]
lock_path = Path(lock_path)
md_path = Path(md_path)
match = re.match(r"^(?P<owner>[^/]+)/(?P<repo>[^@]+)@(?P<skill>.+)$", package)
source = f"{match.group('owner')}/{match.group('repo')}" if match else package
source_url = source_url or (f"https://github.com/{match.group('owner')}/{match.group('repo')}.git" if match else None)

lock_state = json.loads(lock_path.read_text(encoding="utf-8"))
entry = {
    "name": skill_name,
    "host": "vendored",
    "source": source,
    "sourceType": source_type,
    "sourceUrl": source_url,
    "upstreamPath": f"skills/{skill_name}/SKILL.md",
    "localPath": f"{target_dir.rstrip('/')}/{skill_name}",
    "installMethod": "vendored into this repository",
    "installCommand": f"{install_method} {package} -g -y",
    "updateCommand": None,
    "configSource": "registry/skills.lock.json",
    "status": "installed",
    "installedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    "lastUpdatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    "managedBy": "registry/skills.lock.json",
    "notes": "Vendored from a locally installed skill after search/recommendation via find-skills.",
}

skills = lock_state.get("skills", [])
for item in skills:
    if item.get("name") == skill_name:
        item.update(entry)
        break
else:
    skills.append(entry)
lock_state["skills"] = skills
lock_path.write_text(json.dumps(lock_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

row = f"| {skill_name} | vendored in this repo | `{source}` | ✅ 已装 | 已收录到 `{target_dir.rstrip('/')}/{skill_name}/`；上游元数据见 `registry/skills.lock.json` |"
lines = md_path.read_text(encoding="utf-8").splitlines()
updated = False
out = []
for line in lines:
    if line.startswith(f"| {skill_name} |"):
        out.append(row)
        updated = True
    else:
        out.append(line)
if not updated:
    result = []
    inserted = False
    for line in out:
        result.append(line)
        if not inserted and line == "|-------|------|------|------|------|":
            result.append(row)
            inserted = True
    out = result
md_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

echo "Imported third-party skill:"
echo "  - Name: $skill_name"
echo "  - Source: $installed_path"
echo "  - Target: $target_path"
