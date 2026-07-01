#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 0 ]; then
  ROOTS=("$@")
else
  ROOTS=(
    "$HOME/.claude/skills"
    "$HOME/.codex/skills"
    "$HOME/.gemini/skills"
    "$HOME/.agents/skills"
  )
fi

skill_name_from_file() {
  local skill_file="$1"
  local fallback="$2"
  local name
  name="$(sed -n "s/^name:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$skill_file" | head -n 1)"
  if [ -n "$name" ]; then
    printf "%s" "$name"
  else
    printf "%s" "$fallback"
  fi
}

for root in "${ROOTS[@]}"; do
  echo "$root:"
  if [ ! -d "$root" ]; then
    echo "  (missing)"
    continue
  fi

  found=0
  while IFS= read -r skill_file; do
    skill_dir="$(dirname "$skill_file")"
    relative="${skill_dir#"$root"/}"
    case "/$relative/" in
      */.*/*) continue ;;
    esac
    name="$(skill_name_from_file "$skill_file" "$relative")"
    found=1
    echo "  $name -> $relative"
  done < <(find -L "$root" -type f -name SKILL.md | sort)

  if [ "$found" -eq 0 ]; then
    echo "  (none)"
  fi
done
