#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
MANAGER_PY="$SCRIPT_DIR/scripts/pending_manager.py"
MIN_SESSION_LENGTH=10
PYTHON_BIN=""

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if [ -f "$CONFIG_FILE" ] && [ -n "$PYTHON_BIN" ]; then
  MIN_SESSION_LENGTH=$("$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
print(int(data.get("min_session_length", 10)))
PY
)
fi

stdin_data="$(cat)"
transcript_path=""
if [ -n "$PYTHON_BIN" ]; then
  transcript_path="$("$PYTHON_BIN" - <<'PY' "$stdin_data"
import json
import sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw) if raw else {}
except Exception:
    data = {}
print(data.get("transcript_path", ""))
PY
)"
fi
if [ -z "$transcript_path" ]; then
  transcript_path="$(echo "$stdin_data" | sed -n 's/.*"transcript_path":"\([^"]*\)".*/\1/p' | head -1)"
fi
if [ -z "$transcript_path" ]; then
  transcript_path="${CLAUDE_TRANSCRIPT_PATH:-}"
fi

if [[ "$transcript_path" =~ ^[A-Za-z]:\\ ]]; then
  if command -v cygpath >/dev/null 2>&1; then
    transcript_path="$(cygpath -u "$transcript_path")"
  else
    drive="$(echo "$transcript_path" | cut -c1 | tr '[:upper:]' '[:lower:]')"
    rest="$(echo "$transcript_path" | cut -c3- | sed 's|\\|/|g')"
    transcript_path="/$drive/$rest"
  fi
fi

if [ -z "$transcript_path" ] || [ ! -f "$transcript_path" ]; then
  exit 0
fi

message_count="$(grep -c '"type":"user"' "$transcript_path" 2>/dev/null || echo "0")"

if [ "$message_count" -lt "$MIN_SESSION_LENGTH" ]; then
  echo "{\"event\":\"continuous_learning_skipped\",\"reason\":\"session_too_short\",\"messageCount\":$message_count,\"minSessionLength\":$MIN_SESSION_LENGTH}"
  exit 0
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "{\"event\":\"continuous_learning_skipped\",\"reason\":\"python_not_found\"}"
  exit 0
fi

"$PYTHON_BIN" "$MANAGER_PY" --config "$CONFIG_FILE" create --transcript "$transcript_path" --message-count "$message_count"
