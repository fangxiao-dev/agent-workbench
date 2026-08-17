# 目录结构规范

`agent-workbench` 是多宿主共享的 agent 能力仓库。仓库内的正式来源只放在顶层业务目录中，本机安装态和工具缓存不作为规范源。

```text
agent-workbench/
├── scripts/link_skill.py         # 多宿主 per-skill 安装入口
├── README.md
├── AGENTS.md                     # 仓库级 agent instructions
├── skills/                       # 独立正式 skills：自建和第三方
├── plugin-marketplace/           # 独立插件发布根
│   ├── .agents/plugins/          # Codex marketplace
│   ├── .claude-plugin/           # Claude marketplace
│   └── plugins/                  # 多公开 skill 套件及共享资源
├── agents/                       # subagents，安装到宿主 agents/
├── commands/                     # 宿主 command 提示文件，复制到宿主 commands/
├── templates/                    # 按需使用的模板，不由安装器自动生成项目文件
├── registry/                     # 第三方资产人工清单
├── docs/workbench-design/        # 当前实现规范
└── tests/                        # 安装器和工作流测试
```

## 核心目录

- `skills/` 是独立 skill 的仓库内正式来源。单公开入口的 router/bundle 仍可保留内部 `sub-skills/<name>/SUB-SKILL.md`，由公开入口按相对路径读取。
- `plugin-marketplace/` 是插件发布根。`plugins/impl-package/` 以扁平 `skills/<name>/SKILL.md` 暴露入口，并在插件根或各 skill 内共享 references、assets、scripts、src 和 evals；插件根 `agents/*.md` 是 Claude 原生 agent 定义，Codex 通过 `scripts/install_codex_agents.py` 将同一来源投影到全局 `.toml` roles；Codex 与 Claude 只分 manifest，不复制 skills payload。
- `plugin-marketplace/.agents/plugins/marketplace.json` 与 `plugin-marketplace/.claude-plugin/marketplace.json` 分别是 Codex、Claude 的插件索引；仓库根 `.agents/` 仍是缓存/运行态。
- `agents/` 存放 subagent 定义。安装器把每个 agent 目录链接到已选宿主的 `agents/`。
- `commands/` 存放宿主 command 提示文件。安装器把 command 文件复制到已选宿主的 `commands/`。是否可用 `/...` 唤出取决于具体宿主。
- `templates/` 存放可复用模板。当前 `CLAUDE.md.tpl` 由 `init-project-context` 按需使用，安装器不自动生成 `CLAUDE.md`。
- `registry/` 只登记第三方资产，方便人工审查、换机重装和来源追踪。

## 非规范源

以下目录或文件属于本机运行态、工具状态或临时对比位置，不作为仓库规范源：

- 仓库根 `.agents/`
- 仓库根 `.claude/`
- 仓库根 `.codex/`（若存在）
- 根目录 `skills-lock.json`
- `skills/.system/`

如果需要修改第三方 skill，修改 `skills/<name>/` 或 `plugin-marketplace/plugins/<plugin>/skills/<name>/` 中的正式副本。未来要和上游比较时，可以用 `npx skills` 拉取新版本到临时位置，再人工对比后决定是否更新正式副本。

## 安装目标

安装器支持 `claude`、`codex`、`grok` 三类宿主：

- `skills/` 暴露到宿主的 `skills/`
- `agents/*/` 暴露到宿主的 `agents/`
- `commands/*` 复制到宿主的 `commands/`
- `plugin-marketplace/plugins/*` 通过 Codex/Claude 原生 marketplace 与 plugin install 流程安装；`link_skill.py` 不扫描该目录

安装策略详见 `04-install-spec.md`。
