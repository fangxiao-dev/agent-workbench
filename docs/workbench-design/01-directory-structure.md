# 目录结构规范

`agent-workbench` 是多宿主共享的 agent 能力仓库。仓库内的正式来源只放在顶层业务目录中，本机安装态和工具缓存不作为规范源。

```text
agent-workbench/
├── install.sh / install.ps1      # 多宿主安装入口
├── README.md
├── AGENTS.md                     # 仓库级 agent instructions
├── skills/                       # 所有正式 skills：自建和第三方都在这里
├── agents/                       # subagents，安装到宿主 agents/
├── commands/                     # slash commands，复制到宿主 commands/
├── templates/                    # 按需使用的模板，不由安装器自动生成项目文件
├── registry/                     # 第三方资产人工清单
├── docs/workbench-design/        # 当前实现规范
└── tests/                        # 安装器和工作流测试
```

## 核心目录

- `skills/` 是 skill 的唯一仓库内正式来源。自建 skill 和第三方 skill 都直接落在这里，再由安装器暴露给 `claude`、`codex`、`gemini`。
- `agents/` 存放 subagent 定义。安装器把每个 agent 目录链接到已选宿主的 `agents/`。
- `commands/` 存放 slash command 文件。安装器把 command 文件复制到已选宿主的 `commands/`。当前包括 `/audit` 和 `/discuss`。
- `templates/` 存放可复用模板。当前 `CLAUDE.md.tpl` 由 `init-project-context` 按需使用，安装器不自动生成 `CLAUDE.md`。
- `registry/` 只登记第三方资产，方便人工审查、换机重装和来源追踪。

## 非规范源

以下目录或文件属于本机运行态、工具状态或临时对比位置，不作为仓库规范源：

- `.agents/`
- 仓库根 `.claude/`
- 仓库根 `.codex/`、`.gemini/`（若存在）
- 根目录 `skills-lock.json`
- `skills/.system/`

如果需要修改第三方 skill，修改 `skills/<name>/` 中的正式副本。未来要和上游比较时，可以用 `npx skills` 拉取新版本到临时位置，再人工对比后决定是否更新 `skills/<name>/`。

## 安装目标

安装器支持 `claude`、`codex`、`gemini` 三类宿主：

- `skills/` 暴露到宿主的 `skills/`
- `agents/*/` 暴露到宿主的 `agents/`
- `commands/*` 复制到宿主的 `commands/`

安装策略详见 `04-install-spec.md`。
