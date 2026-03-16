# Plugins / MCP

| Plugin | 宿主 | 来源 | 安装方式 | 配置入口 | 状态 | 备注 |
|--------|------|------|----------|----------|------|------|
| superpowers@claude-plugins-official | Claude plugin | marketplace `claude-plugins-official`，来源仓库 `anthropics/claude-plugins-official` | 先安装 marketplace `claude-plugins-official`，再安装并启用 `superpowers@claude-plugins-official` | `~/.claude/plugins/installed_plugins.json` 与 `~/.claude/settings.json` 的 `enabledPlugins` | ✅ 已装 | 当前版本 `5.0.2`；该安装单位同时提供多项 skills、1 个 agent 和 3 个 commands |
| openaiDeveloperDocs | Codex MCP server | OpenAI Developer Docs MCP | 在 Codex 配置 `mcp_servers.openaiDeveloperDocs.url = "https://developers.openai.com/mcp"` | `~/.codex/config.toml` | ✅ 已装 | 这是 Codex 侧的第三方集成，不属于本仓库自建内容 |

## 说明
- ✅ 已装：当前机器上已启用或可直接使用
- ⬜ 待装：列入计划但尚未安装
- ⏸️ 暂停：保留记录但当前未启用
- 自建插件或本仓库内置配置不登记在这里；这里只记录可独立安装的第三方插件 / MCP，且以“如何重装”为主
