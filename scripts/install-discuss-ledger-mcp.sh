#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKBENCH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_PATH="$WORKBENCH_DIR/skills/discuss-ledger/mcp_server.py"
KNOWN_HOSTS="claude codex"
TARGET=""
REQUESTED_HOSTS=()

normalize_input_path() {
  local value="$1"
  if command -v cygpath >/dev/null 2>&1 && [[ "$value" =~ ^[A-Za-z]:[\\/].* ]]; then
    cygpath -u "$value"
  else
    printf '%s' "$value"
  fi
}

host_path() {
  local value="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$value"
  else
    printf '%s' "$value"
  fi
}

is_known_host() {
  local value="$1"
  local host
  for host in $KNOWN_HOSTS; do
    if [ "$host" = "$value" ]; then
      return 0
    fi
  done
  return 1
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
TARGET="$(normalize_input_path "$TARGET")"
TARGET="$(cd "$TARGET" && pwd)"
TARGET_HOST="$(host_path "$TARGET")"
WORKBENCH_HOST="$(host_path "$WORKBENCH_DIR")"
SERVER_HOST="$(host_path "$SERVER_PATH")"

if [ "${#REQUESTED_HOSTS[@]}" -eq 0 ]; then
  REQUESTED_HOSTS=(codex claude)
fi

toml_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

install_codex_mcp() {
  local codex_dir="$TARGET/.codex"
  local config_path="$codex_dir/config.toml"
  mkdir -p "$codex_dir"

  local server root cwd expected
  server="$(toml_escape "$SERVER_HOST")"
  root="$(toml_escape "$TARGET_HOST")"
  cwd="$(toml_escape "$WORKBENCH_HOST")"
  expected="[mcp_servers.discussLedger]
command = \"uv\"
args = [\"run\", \"python\", \"$server\", \"--root\", \"$root\"]
cwd = \"$cwd\""

  if [ -f "$config_path" ] && grep -q '^\[mcp_servers\.discussLedger\]' "$config_path"; then
    if grep -Fq "$expected" "$config_path"; then
      echo "[*] codex discussLedger MCP already configured, skipped"
      return 0
    fi
    echo "[WARN] codex discussLedger MCP exists with different settings, skipped"
    return 0
  fi

  if [ -s "$config_path" ] && [ "$(tail -c 1 "$config_path")" != "" ]; then
    printf '\n' >> "$config_path"
  fi
  printf '%s\n' "$expected" >> "$config_path"
  echo "[OK] codex discussLedger MCP configured at $config_path"
}

write_claude_snippet() {
  cat <<EOF
[WARN] claude not found on PATH. Add this to project .mcp.json if needed:
{
  "mcpServers": {
    "discuss-ledger": {
      "command": "uv",
      "args": ["run", "python", "$SERVER_HOST", "--root", "$TARGET_HOST"],
      "cwd": "$WORKBENCH_HOST"
    }
  }
}
EOF
}

install_claude_mcp() {
  if ! command -v claude >/dev/null 2>&1; then
    write_claude_snippet
    return 0
  fi
  (cd "$TARGET" && claude mcp add --scope project discuss-ledger -- uv run python "$SERVER_HOST" --root "$TARGET_HOST")
  echo "[OK] claude discuss-ledger MCP registered"
}

for host in "${REQUESTED_HOSTS[@]}"; do
  case "$host" in
    codex) install_codex_mcp ;;
    claude) install_claude_mcp ;;
    *) echo "[X] Unsupported host: $host" >&2; exit 1 ;;
  esac
done
