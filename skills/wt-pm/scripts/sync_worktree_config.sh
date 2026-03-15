#!/usr/bin/env bash
# sync_worktree_config.sh
#
# Sync shared config files (.agents/, .claude/rules/, CLAUDE.md, AGENTS.md, etc.)
# from the current worktree to all other worktrees of the same repo.
#
# Usage:
#   bash scripts/sync_worktree_config.sh           # dry-run (preview only)
#   bash scripts/sync_worktree_config.sh --apply    # actually copy files
#   bash scripts/sync_worktree_config.sh --apply --exclude dev  # skip 'dev' worktree

set -euo pipefail

SYNC_ITEMS=(
  ".agents/"
  ".claude/rules/"
  ".claude/skills/"
  ".env"
  ".env.docker"
  "frontend/.env.local"
)

DRY_RUN=true
EXCLUDES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)  DRY_RUN=false; shift ;;
    --exclude)
      EXCLUDES+=("$2"); shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--apply] [--exclude <worktree-dir-name>]..."
      echo ""
      echo "  --apply     Actually copy files (default is dry-run)"
      echo "  --exclude   Skip a worktree by its directory basename"
      echo ""
      echo "Syncs from current worktree to all others:"
      for item in "${SYNC_ITEMS[@]}"; do echo "  $item"; done
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

SRC="$(git rev-parse --show-toplevel)"
echo "Source: $SRC"
echo "Mode:   $(if $DRY_RUN; then echo 'DRY-RUN (use --apply to execute)'; else echo 'APPLY'; fi)"
echo ""

TARGETS=()
while IFS= read -r line; do
  wt_path="$(echo "$line" | awk '{print $1}')"
  [[ "$wt_path" == "$SRC" ]] && continue
  wt_basename="$(basename "$wt_path")"
  skip=false
  for ex in "${EXCLUDES[@]+"${EXCLUDES[@]}"}"; do
    [[ "$wt_basename" == "$ex" ]] && skip=true && break
  done
  $skip && echo "  SKIP: $wt_path (excluded)" && continue
  TARGETS+=("$wt_path")
done < <(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //')

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "No target worktrees found."
  exit 0
fi

echo "Targets:"
for t in "${TARGETS[@]}"; do echo "  $t"; done
echo ""

copy_item() {
  local src_path="$1"
  local dst_path="$2"
  local is_dir="$3"

  if $DRY_RUN; then
    if [[ "$is_dir" == "true" ]]; then
      echo "  [dry-run] rsync $src_path -> $dst_path"
    else
      echo "  [dry-run] cp $src_path -> $dst_path"
    fi
    return
  fi

  if [[ "$is_dir" == "true" ]]; then
    mkdir -p "$dst_path"
    cp -r "$src_path"* "$dst_path" 2>/dev/null || true
    echo "  COPIED dir: $src_path -> $dst_path"
  else
    mkdir -p "$(dirname "$dst_path")"
    cp "$src_path" "$dst_path"
    echo "  COPIED file: $src_path -> $dst_path"
  fi
}

changed=0
for target in "${TARGETS[@]}"; do
  echo "── Syncing to: $(basename "$target") ──"
  for item in "${SYNC_ITEMS[@]}"; do
    src_full="$SRC/$item"
    dst_full="$target/$item"

    if [[ ! -e "$src_full" ]]; then
      echo "  SKIP: $item (not found in source)"
      continue
    fi

    if [[ "$item" == */ ]]; then
      copy_item "$src_full" "$dst_full" "true"
    else
      copy_item "$src_full" "$dst_full" "false"
    fi
    ((changed++)) || true
  done
  echo ""
done

if $DRY_RUN; then
  echo "Dry-run complete. $changed item(s) would be synced."
  echo "Run with --apply to execute."
else
  echo "Done. $changed item(s) synced."
fi
