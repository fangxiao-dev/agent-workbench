#!/usr/bin/env bash
set -euo pipefail

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET=""
REQUESTED_HOSTS=()

KNOWN_HOSTS="claude codex gemini"

is_known_host() {
  local value="$1"
  for host in $KNOWN_HOSTS; do
    if [ "$host" = "$value" ]; then
      return 0
    fi
  done
  return 1
}

resolve_host_home() {
  case "$1" in
    claude) printf '%s/.claude' "$HOME" ;;
    codex) printf '%s/.codex' "$HOME" ;;
    gemini) printf '%s/.gemini' "$HOME" ;;
    *) return 1 ;;
  esac
}

for arg in "$@"; do
  if is_known_host "$arg"; then
    REQUESTED_HOSTS+=("$arg")
  elif [ -z "$TARGET" ]; then
    TARGET="$arg"
  else
    echo "[X] Unknown argument: $arg" >&2
    exit 1
  fi
done

TARGET="${TARGET:-$(pwd)}"
TARGET="$(cd "$TARGET" && pwd)"

discover_hosts() {
  local discovered=()
  local host
  for host in $KNOWN_HOSTS; do
    local host_home
    host_home="$(resolve_host_home "$host")"
    if [ -d "$host_home" ]; then
      discovered+=("$host")
    fi
  done
  printf '%s\n' "${discovered[@]}"
}

if [ "${#REQUESTED_HOSTS[@]}" -eq 0 ]; then
  while IFS= read -r discovered_host; do
    if [ -n "$discovered_host" ]; then
      REQUESTED_HOSTS+=("$discovered_host")
    fi
  done < <(discover_hosts)
fi

INSTALLED_COUNT=0
SKIPPED_COUNT=0
CONFLICT_COUNT=0
HOSTS_PROCESSED=0

safe_link() {
  local src="$1"
  local dst="$2"
  local label="$3"

  if [ -L "$dst" ]; then
    local current_target
    current_target="$(readlink "$dst")"
    if [ "$current_target" = "$src" ]; then
      echo "  [*] $label -> already linked, skipped"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      return 0
    fi

    echo "  [WARN] $label -> conflict, skipped ($dst exists and points elsewhere)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  if [ -e "$dst" ]; then
    echo "  [WARN] $label -> conflict, skipped ($dst already exists)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  ln -s "$src" "$dst"
  echo "  [OK] $label -> installed"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
}

safe_copy_file() {
  local src="$1"
  local dst="$2"
  local label="$3"

  if [ -e "$dst" ]; then
    if [ -d "$dst" ]; then
      echo "  [WARN] $label -> conflict, skipped ($dst already exists as directory)"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
      return 0
    fi

    if cmp -s "$src" "$dst"; then
      echo "  [*] $label -> already copied, skipped"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      return 0
    fi

    echo "  [WARN] $label -> conflict, skipped ($dst already exists with different content)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  cp "$src" "$dst"
  echo "  [OK] $label -> installed"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
}

install_collection() {
  local host="$1"
  local host_home="$2"
  local kind="$3"
  local source_root="$4"
  local item_type="$5"
  local install_mode="$6"
  local dest_dir="$host_home/$kind"

  mkdir -p "$dest_dir"
  echo "$kind:"

  local matched=0
  local item
  for item in "$source_root"/*; do
    if [ ! -e "$item" ]; then
      continue
    fi
    if [ "$item_type" = "dir" ] && [ ! -d "$item" ]; then
      continue
    fi
    if [ "$item_type" = "file" ] && [ ! -f "$item" ]; then
      continue
    fi
    matched=1
    local name
    name="$(basename "$item")"
    if [ "$install_mode" = "copy" ]; then
      safe_copy_file "$item" "$dest_dir/$name" "$name"
    else
      safe_link "$item" "$dest_dir/$name" "$name"
    fi
  done

  if [ "$matched" -eq 0 ]; then
    echo "  [*] no entries"
  fi
}

remove_managed_legacy_codex_backfill_link() {
  local host_home="$1"
  local skills_root="$host_home/skills"
  local legacy_source="$WORKBENCH_DIR/skills/backfill-stable-docs"
  local legacy_destination="$skills_root/backfill-stable-docs"

  if [ -L "$skills_root" ] && [ "$(readlink "$skills_root")" = "$WORKBENCH_DIR/skills" ]; then
    return 0
  fi

  if [ -L "$legacy_destination" ] && [ "$(readlink "$legacy_destination")" = "$legacy_source" ]; then
    rm "$legacy_destination"
    echo "  [OK] legacy backfill-stable-docs link -> removed"
    INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
  fi
}

install_codex_plugin() {
  echo "plugin:"
  local marketplace_manifest="$WORKBENCH_DIR/.agents/plugins/marketplace.json"
  if [ ! -f "$marketplace_manifest" ]; then
    echo "  [WARN] stable-docs-backfill -> skipped (marketplace manifest is missing)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  if ! command -v codex >/dev/null 2>&1; then
    echo "  [WARN] stable-docs-backfill -> skipped (Codex CLI not found)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    return 0
  fi

  local marketplace_list_output
  local codex_error_file
  local codex_error_detail
  codex_error_file="$(mktemp)"
  if ! marketplace_list_output="$(codex plugin marketplace list --json 2>"$codex_error_file")"; then
    codex_error_detail="$(cat "$codex_error_file")"
    rm -f "$codex_error_file"
    echo "  [WARN] agent-workbench marketplace -> conflict, skipped (could not inspect marketplaces: $codex_error_detail)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi
  rm -f "$codex_error_file"

  local marketplace_state="missing"
  local python_command=""
  if command -v python3 >/dev/null 2>&1; then
    python_command="python3"
  elif command -v python >/dev/null 2>&1; then
    python_command="python"
  fi

  if [ -n "$python_command" ]; then
    if ! marketplace_state="$(printf '%s' "$marketplace_list_output" | "$python_command" -c 'import json, os, sys; data=json.load(sys.stdin); expected=os.path.normcase(os.path.realpath(sys.argv[1])); matches=[item for item in data.get("marketplaces", []) if item.get("name") == "agent-workbench"]; print("missing" if not matches else ("same" if os.path.normcase(os.path.realpath(matches[0].get("root", ""))) == expected else "conflict"))' "$WORKBENCH_DIR" 2>/dev/null)"; then
      marketplace_state="invalid"
    fi
  fi

  if [ "$marketplace_state" = "conflict" ]; then
    echo "  [WARN] agent-workbench marketplace -> conflict, skipped (name already points to another source)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  if [ "$marketplace_state" = "invalid" ]; then
    echo "  [WARN] agent-workbench marketplace -> conflict, skipped (Codex CLI returned invalid marketplace JSON)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi

  if [ "$marketplace_state" = "same" ]; then
    echo "  [*] agent-workbench marketplace -> already registered"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
  else
    local marketplace_output
    codex_error_file="$(mktemp)"
    if ! marketplace_output="$(codex plugin marketplace add "$WORKBENCH_DIR" --json 2>"$codex_error_file")"; then
      codex_error_detail="$(cat "$codex_error_file")"
      rm -f "$codex_error_file"
      echo "  [WARN] agent-workbench marketplace -> conflict, skipped ($codex_error_detail)"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
      return 0
    fi
    rm -f "$codex_error_file"

    echo "  [OK] agent-workbench marketplace -> registered"
    INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
  fi

  local plugin_output
  codex_error_file="$(mktemp)"
  if ! plugin_output="$(codex plugin add stable-docs-backfill@agent-workbench --json 2>"$codex_error_file")"; then
    codex_error_detail="$(cat "$codex_error_file")"
    rm -f "$codex_error_file"
    echo "  [WARN] stable-docs-backfill -> conflict, skipped ($codex_error_detail)"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    return 0
  fi
  rm -f "$codex_error_file"

  echo "  [OK] stable-docs-backfill -> installed/refreshed"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
}

echo "[INFO] Workbench: $WORKBENCH_DIR"
echo "[INFO] Target project: $TARGET"
echo ""

if [ "${#REQUESTED_HOSTS[@]}" -eq 0 ]; then
  echo "[WARN] No known host directories detected. Skipping host installation."
else
  for host in "${REQUESTED_HOSTS[@]}"; do
    host_home="$(resolve_host_home "$host")"
    HOSTS_PROCESSED=$((HOSTS_PROCESSED + 1))
    echo "Host: $host"
    echo "Root: $host_home"
    install_collection "$host" "$host_home" "skills" "$WORKBENCH_DIR/skills" dir link
    install_collection "$host" "$host_home" "agents" "$WORKBENCH_DIR/agents" dir link
    install_collection "$host" "$host_home" "commands" "$WORKBENCH_DIR/commands" file copy
    if [ "$host" = "codex" ]; then
      remove_managed_legacy_codex_backfill_link "$host_home"
      install_codex_plugin
    fi
    echo ""
  done
fi

GITIGNORE="$TARGET/.gitignore"
touch "$GITIGNORE"
if ! grep -q ".claude/settings.local.json" "$GITIGNORE"; then
  echo ".claude/settings.local.json" >> "$GITIGNORE"
  echo "[OK] .gitignore updated"
else
  echo "[*] .gitignore already contains .claude/settings.local.json"
fi

echo ""
echo "Summary:"
echo "Hosts processed: $HOSTS_PROCESSED"
echo "Installed: $INSTALLED_COUNT"
echo "Skipped: $SKIPPED_COUNT"
echo "Conflicts: $CONFLICT_COUNT"
