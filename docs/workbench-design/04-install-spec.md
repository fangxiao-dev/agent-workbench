# 安装器规范

`install.sh` 和 `install.ps1` 负责把 workbench 能力暴露给已选 agent 宿主。当前支持宿主：

- `claude`
- `codex`
- `gemini`

## 调用方式

默认安装到当前目录，并自动发现本机存在的已知宿主：

```bash
bash /path/to/agent-workbench/install.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\install.ps1
```

也可以显式指定目标项目和宿主：

```bash
bash /path/to/agent-workbench/install.sh /path/to/project claude codex gemini
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\install.ps1 D:\path\to\project claude codex gemini
```

## 安装内容

| 来源 | 目标 | 机制 |
|------|------|------|
| `skills/` | `<host-root>/skills/` | Windows junction；Bash/Unix symlink |
| `agents/*/` | `<host-root>/agents/<name>/` | Windows junction；Bash/Unix symlink |
| `commands/*` | `<host-root>/commands/<name>` | 复制文件 |

`skills/` 可以包含直接 skill（`skills/<name>/SKILL.md`）和 bundle skill（`skills/<bundle>/<name>/SKILL.md`）。安装器保持非破坏策略：Windows 暴露整个 `skills/`，Bash/Unix 链接顶层目录，因此 bundle 作为一个顶层目录暴露，内部 skill 通过递归发现或宿主扫描读取。

`backfill-stable-docs` 随公共 `skills/` 暴露给宿主。Codex 通过 `$backfill-stable-docs` 调用；安装器不注册 marketplace、不调用 Codex Plugin CLI，也不清理用户的 Plugin 状态。

宿主根目录：

- `claude` -> `~/.claude`
- `codex` -> `~/.codex`
- `gemini` -> `~/.gemini`

## 冲突策略

安装器是非破坏性的：

- 目标不存在：创建链接或复制文件。
- 目标已经指向当前 workbench：跳过并报告 `already linked` 或 `already copied`。
- 目标存在但内容或目标不同：跳过并报告 `conflict`。
- 不删除、不覆盖已有目录、文件或其他链接。

`commands/` 使用复制，因此 command 内容变更后需要重跑安装器同步。

## `.gitignore` 处理

安装器会确保目标项目 `.gitignore` 包含：

```gitignore
.claude/settings.local.json
```

该文件是 Claude 的本机权限状态，不应提交到项目仓库。

## 独立 MCP 注册脚本

主安装器只安装 skills、agents、commands，不自动注册项目级 MCP server。需要启用 `discuss-ledger` MCP 时，使用独立脚本：

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

约束：

- host 参数仅支持 `codex` / `claude`
- Codex 只写目标项目内 `.codex/config.toml` 的 `[mcp_servers.discussLedger]`
- 注册命令使用 `uv run python <mcp_server.py> --root <target-project>`，`cwd` 为 workbench 根目录
- 如果 Codex 已存在不同的 `discussLedger` 配置，跳过并报告冲突，不覆盖
- Claude 优先执行 `claude mcp add --scope project discuss-ledger -- uv run python <mcp_server.py> --root <target-project>`
- 如果 `claude` CLI 不存在，打印 `.mcp.json` 片段并成功退出
- MCP server 不向 agent 暴露 `set_next`；下一位发言者由用户或编排器通过 CLI/core 指定

## 维护要求

新增宿主时必须同步更新：

- `install.sh`
- `install.ps1`
- `tests/install.ps1`
- `README.md`

安装器行为变化时，同步更新本文档。
