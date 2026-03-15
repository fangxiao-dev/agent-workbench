# install.sh 规范

## 职责

将 Workbench 的内容安装到目标项目和全局 Claude Code 环境中。

## 调用方式

```bash
# 安装到当前目录
./install.sh

# 安装到指定目录
./install.sh /path/to/target-project
```

## 安装内容与目标位置

| 来源 | 目标 | 覆盖策略 |
|------|------|----------|
| `skills/*/` | `~/.claude/skills/` | 覆盖（取 workbench 最新版） |
| `scripts/` | `~/.claude/scripts/` | 覆盖 |
| `agents/` | `<target>/.claude/agents/` | 覆盖 |
| `commands/` | `<target>/.claude/commands/` | 覆盖 |
| `templates/CLAUDE.md.tpl` | `<target>/CLAUDE.md` | **不覆盖**已有文件 |

## 完整实现

```bash
#!/bin/bash
set -e

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$(pwd)}"

echo "🔧 Workbench → $TARGET"
echo ""

# ── 1. 全局 skills → ~/.claude/skills/ ──────────────────────────
echo "📂 安装 skills 到 ~/.claude/skills/"
mkdir -p "$HOME/.claude/skills"

for skill_dir in "$WORKBENCH_DIR"/skills/*/; do
  [ -d "$skill_dir" ] || continue
  name=$(basename "$skill_dir")
  cp -r "$skill_dir" "$HOME/.claude/skills/$name"
  echo "  ✅ $name"
done

# ── 2. 共用脚本 → ~/.claude/scripts/ ────────────────────────────
if [ -d "$WORKBENCH_DIR/scripts" ]; then
  echo ""
  echo "📂 安装共用脚本到 ~/.claude/scripts/"
  mkdir -p "$HOME/.claude/scripts"
  cp -r "$WORKBENCH_DIR/scripts/." "$HOME/.claude/scripts/"
  echo "  ✅ scripts/"
fi

# ── 3. 项目级 .claude/ 结构 ──────────────────────────────────────
echo ""
echo "📁 初始化 $TARGET/.claude/"
mkdir -p "$TARGET/.claude/agents" \
         "$TARGET/.claude/commands" \
         "$TARGET/.claude/skills"

# agents
if [ -d "$WORKBENCH_DIR/agents" ]; then
  cp -r "$WORKBENCH_DIR/agents/." "$TARGET/.claude/agents/"
  echo "  ✅ agents/"
fi

# commands
if [ -d "$WORKBENCH_DIR/commands" ]; then
  cp -r "$WORKBENCH_DIR/commands/." "$TARGET/.claude/commands/"
  echo "  ✅ commands/"
fi

# ── 4. CLAUDE.md（不覆盖已有的）────────────────────────────────
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
echo "✅ 完成。在 Claude Code 里运行 /audit 开始检查。"
```

## 注意事项

生成 install.sh 时：
- 文件开头加 `set -e`，任何步骤失败立即退出
- 每一步都有 echo 输出，方便 debug
- 对"不覆盖"的文件，输出 ⏭️ 提示，不静默跳过
