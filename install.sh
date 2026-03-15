#!/usr/bin/env bash
set -e

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$(pwd)}"

echo "🔧 Workbench: $WORKBENCH_DIR"
echo "📁 Target project: $TARGET"
echo ""

# Helper: 创建软链接，先清除同名旧链接或目录
_link() {
  local src="$1" dst="$2"
  [ -L "$dst" ] && rm "$dst"
  [ -e "$dst" ] && rm -rf "$dst"
  ln -s "$src" "$dst"
}

# ── 1. Skills → ~/.claude/skills/ (symlinks) ─────────────────────
echo "🔗 链接 skills 到 ~/.claude/skills/"
mkdir -p "$HOME/.claude/skills"
for skill_dir in "$WORKBENCH_DIR"/skills/*/; do
  [ -d "$skill_dir" ] || continue
  name=$(basename "$skill_dir")
  _link "$WORKBENCH_DIR/skills/$name" "$HOME/.claude/skills/$name"
  echo "  ✅ $name"
done

# ── 2. Agents → ~/.claude/agents/ (symlinks) ─────────────────────
echo ""
echo "🔗 链接 agents 到 ~/.claude/agents/"
mkdir -p "$HOME/.claude/agents"
for agent_dir in "$WORKBENCH_DIR"/agents/*/; do
  [ -d "$agent_dir" ] || continue
  name=$(basename "$agent_dir")
  _link "$WORKBENCH_DIR/agents/$name" "$HOME/.claude/agents/$name"
  echo "  ✅ $name"
done

# ── 3. Commands → ~/.claude/commands/ (symlinks) ──────────────────
echo ""
echo "🔗 链接 commands 到 ~/.claude/commands/"
mkdir -p "$HOME/.claude/commands"
for cmd_file in "$WORKBENCH_DIR"/commands/*; do
  [ -f "$cmd_file" ] || continue
  name=$(basename "$cmd_file")
  _link "$cmd_file" "$HOME/.claude/commands/$name"
  echo "  ✅ $name"
done

# ── 4. CLAUDE.md（不覆盖已有的）─────────────────────────────────
echo ""
if [ ! -f "$TARGET/CLAUDE.md" ]; then
  PROJECT_NAME=$(basename "$TARGET")
  sed "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" \
    "$WORKBENCH_DIR/templates/CLAUDE.md.tpl" > "$TARGET/CLAUDE.md"
  echo "📝 CLAUDE.md 已生成（来自模板）"
else
  echo "⏭️  CLAUDE.md 已存在，跳过（运行 /audit 检查质量）"
fi

# ── 5. .gitignore 补丁 ───────────────────────────────────────────
GITIGNORE="$TARGET/.gitignore"
touch "$GITIGNORE"
if ! grep -q ".claude/settings.local.json" "$GITIGNORE"; then
  echo ".claude/settings.local.json" >> "$GITIGNORE"
  echo "📝 .gitignore 已更新"
fi

echo ""
echo "✅ 完成。在任意项目的 Claude Code 里运行 /audit 开始检查。"
