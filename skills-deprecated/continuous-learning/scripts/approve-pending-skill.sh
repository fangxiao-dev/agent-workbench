#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
CONFIG_FILE="$SKILL_DIR/config.json"
PROPOSAL="${1:-}"
SKILL_NAME="${2:-}"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo '{"error":"python_not_found"}'
  exit 1
fi

cmd=("$PYTHON_BIN" "$SCRIPT_DIR/pending_manager.py" --config "$CONFIG_FILE" approve)
if [ -n "$PROPOSAL" ]; then
  cmd+=(--proposal "$PROPOSAL")
fi
if [ -n "$SKILL_NAME" ]; then
  cmd+=(--skill-name "$SKILL_NAME")
fi
"${cmd[@]}"

bash "$REPO_ROOT/install.sh"
