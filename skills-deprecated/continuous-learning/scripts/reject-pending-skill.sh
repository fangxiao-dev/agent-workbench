#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$(cd "$SCRIPT_DIR/.." && pwd)/config.json"
PROPOSAL="${1:-}"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo '{"error":"python_not_found"}'
  exit 1
fi

cmd=("$PYTHON_BIN" "$SCRIPT_DIR/pending_manager.py" --config "$CONFIG_FILE" reject)
if [ -n "$PROPOSAL" ]; then
  cmd+=(--proposal "$PROPOSAL")
fi
"${cmd[@]}"
