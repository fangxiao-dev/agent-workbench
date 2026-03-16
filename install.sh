#!/usr/bin/env bash
set -e

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET=""
REQUESTED_HOSTS=()

KNOWN_HOSTS="claude codex"

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
  mapfile -t REQUESTED_HOSTS < <(discover_hosts)
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

copy_file() {
  local src="$1"
  local dst="$2"
  local label="$3"

  if [ -e "$dst" ]; then
    if cmp -s "$src" "$dst"; then
      echo "  [*] $label -> already copied, skipped"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      return 0
    fi

    echo "  [WARN] $label -> conflict, skipped ($dst already exists)"
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
  local source_pattern="$4"
  local item_type="$5"
  local install_mode="$6"
  local dest_dir="$host_home/$kind"

  mkdir -p "$dest_dir"
  echo "$kind:"

  local matched=0
  local item
  for item in $source_pattern; do
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
      copy_file "$item" "$dest_dir/$name" "$name"
    else
      safe_link "$item" "$dest_dir/$name" "$name"
    fi
  done

  if [ "$matched" -eq 0 ]; then
    echo "  [*] no entries"
  fi
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
    install_collection "$host" "$host_home" "skills" "$WORKBENCH_DIR"/skills/*/ dir link
    install_collection "$host" "$host_home" "agents" "$WORKBENCH_DIR"/agents/*/ dir link
    install_collection "$host" "$host_home" "commands" "$WORKBENCH_DIR"/commands/* file copy
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
