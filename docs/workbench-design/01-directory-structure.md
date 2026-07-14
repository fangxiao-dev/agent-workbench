# 目录结构规范

`agent-workbench` 是多宿主共享的 agent 能力仓库。仓库内的正式来源只放在顶层业务目录中，本机安装态和工具缓存不作为规范源。

```text
agent-workbench/
├── install.sh / install.ps1      # 多宿主安装入口
├── README.md
├── AGENTS.md                     # 仓库级 agent instructions
├── skills/                       # 普通正式 skills：自建和第三方
├── plugins/                      # 自建、独立版本化的 Codex Plugins
├── .agents/plugins/marketplace.json # 本仓库 Codex marketplace manifest
├── agents/                       # subagents，安装到宿主 agents/
├── commands/                     # 宿主 command 提示文件，复制到宿主 commands/
├── templates/                    # 按需使用的模板，不由安装器自动生成项目文件
├── registry/                     # 第三方资产人工清单
├── docs/workbench-design/        # 当前实现规范
└── tests/                        # 安装器和工作流测试
```

## 核心目录

- `skills/` 是普通 skill 的仓库内正式来源。自建 skill 和第三方 skill 通常直接落在这里；相关能力也可以按 bundle 分组为 `skills/<bundle>/<skill>/SKILL.md`，例如 `feishu-skills/` 和 `lark-skills/`。
- `plugins/` 是本仓库自建 Codex Plugin 的唯一正式来源。Plugin 内附带的 skill 不在根 `skills/` 保留副本；当前 `stable-docs-backfill` 通过 Plugin 独立安装、升级和版本化。
- `.agents/plugins/marketplace.json` 是 `.agents/` 下唯一的正式来源例外，用于声明本仓库 Codex marketplace 及其 Plugin；`.agents/` 其余内容仍属于工具状态或缓存。
- `agents/` 存放 subagent 定义。安装器把每个 agent 目录链接到已选宿主的 `agents/`。
- `commands/` 存放宿主 command 提示文件。安装器把 command 文件复制到已选宿主的 `commands/`。是否可用 `/...` 唤出取决于具体宿主。
- `templates/` 存放可复用模板。当前 `CLAUDE.md.tpl` 由 `init-project-context` 按需使用，安装器不自动生成 `CLAUDE.md`。
- `registry/` 只登记第三方资产，方便人工审查、换机重装和来源追踪。

## 非规范源

以下目录或文件属于本机运行态、工具状态或临时对比位置，不作为仓库规范源：

- `.agents/`（`.agents/plugins/marketplace.json` 除外）
- 仓库根 `.claude/`
- 仓库根 `.codex/`、`.gemini/`（若存在）
- 根目录 `skills-lock.json`
- `skills/.system/`

如果需要修改第三方 skill，修改 `skills/<name>/` 或 `skills/<bundle>/<name>/` 中的正式副本。未来要和上游比较时，可以用 `npx skills` 拉取新版本到临时位置，再人工对比后决定是否更新正式副本。

## 安装目标

安装器支持 `claude`、`codex`、`gemini` 三类宿主：

- `skills/` 暴露到宿主的 `skills/`
- `agents/*/` 暴露到宿主的 `agents/`
- `commands/*` 复制到宿主的 `commands/`
- 仅选择 Codex 时，注册本仓库 marketplace，并安装或刷新 `stable-docs-backfill` Plugin；Claude/Gemini 不安装该 Plugin

安装策略详见 `04-install-spec.md`。
