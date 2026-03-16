---
name: verify-registry-state
description: 检查 registry 中登记的第三方 skills 和 plugins 是否在当前机器可用，并刷新状态为“已装 / 未装”。
user-invocable: true
---

# verify-registry-state

用于在陌生机器、初始化后或变更后，统一检查 `registry/` 中登记的第三方资产是否存在，并把状态刷新回清单文件。

## 检查范围

- `registry/skills.md`
- `registry/skills.lock.json`
- `registry/plugins.md`

## 状态约定

- `✅ 已装`
- `⬜ 未装`

只维护这两种状态，不引入其他中间态。

## 检查规则

### Skills

优先检查 `registry/skills.lock.json` 中声明的本地路径是否存在；如果不存在，再根据 `host` 检查外部管理状态。

当前支持：
- `.agents`：检查 `~/.agents/.skill-lock.json`

### Plugins / MCP

当前支持：
- `Claude plugin`：同时检查 `~/.claude/settings.json` 中是否启用，以及 `~/.claude/plugins/installed_plugins.json` 中是否已安装
- `Codex MCP server`：检查 `~/.codex/config.toml` 中是否存在对应 server 名称

## 执行方式

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File skills/verify-registry-state/scripts/verify-registry-state.ps1
```

Linux / macOS:

```bash
bash skills/verify-registry-state/scripts/verify-registry-state.sh
```

## 预期结果

- 刷新 `registry/skills.md` 的状态列
- 刷新 `registry/plugins.md` 的状态列
- 不自动安装缺失项
- 如果发现缺失项，后续再根据 `registry` 和 lock 文件决定是否安装或同步

