# Registry 规范

## 定位

`registry/` 是纯粹的人类可读备忘清单，不参与任何脚本逻辑。
用途：记录你手动安装的第三方工具，方便换机器或重新初始化时查阅。

## 文件格式

### `registry/third-party-skills.md`

```markdown
# Third-party Skills

| Skill | 安装命令 | 状态 |
|-------|----------|------|
| creative-design/ui-design-system | `npx claude-code-templates@latest --skill creative-design/ui-design-system` | ⬜ 待装 |
| development-team/ui-ux-designer  | `npx claude-code-templates@latest --skill development-team/ui-ux-designer`  | ⬜ 待装 |

## 说明
- ✅ 已装：已手动安装到 ~/.claude/skills/
- ⬜ 待装：列入计划但尚未安装
- ⏸️ 暂停：曾经使用，暂时停用
```

### `registry/plugins.md`

```markdown
# Plugins / MCP

| Plugin | 安装方式 | 状态 |
|--------|----------|------|
| github-integration | `npx claude-code-templates@latest --mcp development/github-integration` | ⬜ 待装 |

## 说明
- ✅ 已装
- ⬜ 待装
- ⏸️ 暂停
```

## 生成要求

如果当前仓库里已有类似的清单文件（任何格式），将内容迁移到上述格式中，不要丢弃已有记录。
如果没有，生成上述空模板即可。

