# agent-workbench

个人 Agentic Coding 基础设施工具库。这个仓库是 `claude`、`codex`、`gemini` 多宿主共享的 skills、agents、commands、安装器和治理文档的 source of truth。

**安装后能做什么？** → [docs/capabilities.md](docs/capabilities.md)

---

## 设计总览

`agent-workbench` 的目标是把可复用的 agent 能力集中维护，然后以非破坏方式暴露给不同宿主：

- `skills/` 保存所有正式 skill，包括自建 skill、审查过的第三方 skill、以及本地工作流知识库
- `agents/` 保存可安装到宿主的 subagent 定义，目前正式 subagent 是 `audit-agent-setup`
- `commands/` 保存宿主 command 提示文件；是否能用 `/...` 唤出取决于具体宿主
- `install.sh` / `install.ps1` 把这些能力安装到 `~/.claude`、`~/.codex`、`~/.gemini`
- `registry/` 只记录第三方资产来源和重装方式，不记录宿主本机状态
- `docs/workbench-design/` 保存当前实现规范，README 只做入口说明
- `tests/` 保存安装器和核心脚本测试

仓库根目录下的 `.agents/`、`.claude/`、`.pytest_cache/`、`skills-lock.json` 等属于本机运行态、工具状态或缓存，不作为规范源。

---

## 安装

```bash
# 在任意目标项目目录下执行
bash /path/to/agent-workbench/install.sh

# 显式只安装到指定宿主
bash /path/to/agent-workbench/install.sh /path/to/project claude codex gemini
```

```powershell
# 在任意目标项目目录下执行
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\install.ps1

# 显式只安装到指定宿主
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\install.ps1 D:\path\to\project claude codex gemini
```

Windows 使用 junction，通常不需要开发者模式；Bash/Unix 侧使用符号链接。

### Discuss Ledger MCP 注册

`discuss-ledger` 的 MCP server 不由主安装器自动注册。需要在目标项目里启用 Codex/Claude MCP 时，单独运行：

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

Codex 写入项目内 `.codex/config.toml` 的 `mcp_servers.discussLedger`；Claude 优先调用 `claude mcp add --scope project`。如果本机没有 `claude` CLI，脚本只打印可手动放入 `.mcp.json` 的片段，不会失败。注册后的 server 通过 workbench 根目录的 `uv run python` 启动，以使用仓库内声明的 `mcp[cli]` 依赖。

该 MCP 面向参与讨论的 agent 暴露 ledger 读写工具，但不暴露 `set_next`；下一位发言者仍由用户或编排器显式指定。

默认行为：

- 自动发现已知宿主目录并安装到这些宿主
- 当前内置宿主：`claude`、`codex`、`gemini`
- 也可以在命令后显式追加宿主名，只安装到指定宿主
- 遇到同名目标时不会删除或覆盖，而是跳过并报告冲突
- 确保目标项目 `.gitignore` 包含 `.claude/settings.local.json`

安装后的位置：

| 来源 | Windows `install.ps1` | Bash/Unix `install.sh` |
|------|------------------------|-------------------------|
| `skills/` | 整个目录 junction 到 `<host>/skills` | 每个 `skills/*/` 单独 symlink 到 `<host>/skills/<name>` |
| `agents/*/` | 每个 agent 目录 junction 到 `<host>/agents/<name>` | 每个 agent 目录 symlink 到 `<host>/agents/<name>` |
| `commands/*` | 复制到 `<host>/commands/<name>` | 复制到 `<host>/commands/<name>` |

宿主根目录：

| 宿主 | 根目录 |
|------|--------|
| `claude` | `~/.claude` |
| `codex` | `~/.codex` |
| `gemini` | `~/.gemini` |

> **约定**：把 agent-workbench 放在固定路径（如 `~/dev/agent-workbench`），不要随意移动——junction 依赖绝对路径。

---

## 日常使用

### 修改和同步

在 Windows 安装态下，宿主 `skills/` 整体指向本仓库；在 Bash/Unix 安装态下，每个 skill 目录单独链接过去。`agents/` 也是链接安装。`commands/` 使用复制，command 内容变更后需要重跑安装器同步。

新增 skill 后：

- Windows：如果宿主 `skills/` 是 workbench 整目录 junction，通常立即可见
- Bash/Unix：需要重跑安装器，把新的 `skills/<name>/` symlink 到宿主目录

### 核对宿主最终可见 skills

```powershell
powershell -ExecutionPolicy Bypass -File scripts/list-visible-skills.ps1
```

它会按宿主分别列出：

- `installed by workbench`
- `superpowers`
- `personal/global`
- `Merged visible set`

### 在任意项目里运行审查

```
/audit
```

触发 `audit-agent-setup` subagent，对当前项目的 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、agents、skills、commands 做深度质量审查，输出带改进建议的报告。

### 自动讨论目标文档

明确要求运行 `discuss-ledger` 的 local orchestrator，由当前 Codex 会话启动脚本，再自动调用 `codex,claude` 两个参与方轮流讨论。默认 `max-rounds=5`、`timeout-s=300`，直到一致、僵局或达到轮次上限停止。输出 ledger 位于目标项目的 `docs/exchange/discuss/`。

推荐说法：

```text
用 discuss orchestrator 审 docs/plan.md
```

或直接运行：

```powershell
python D:\CodeSpace\agent-workbench\skills\discuss-ledger\scripts\discuss_orchestrator.py --root D:\your\project --topic docs\plan.md
```

`commands/discuss.md` 只是可安装到宿主 command 目录的提示文件；它不保证在所有宿主里都能用 `/discuss` 唤出。

### 初始化项目上下文

`init-project-context` 用于新项目或上下文不足的项目：先稳定项目目标、交付物边界、术语和文档骨架，再进入实现规划。`templates/CLAUDE.md.tpl` 是这个流程按需使用的模板；安装器不会自动生成 `CLAUDE.md`。

### 多任务 / worktree 工作流

WT-PM 工作流拆成三个 skill：

| Skill | 场景 | 职责 |
|-------|------|------|
| `wt-pm` | 不确定当前阶段时 | 识别阶段并路由到 planning 或 dev |
| `wt-plan` | trunk 规划侧 | 任务定义、plan 三文件、branch/worktree handoff |
| `wt-dev` | task worktree 执行侧 | 加载 plan、实现、验证、回收和状态更新 |

不需要 worktree 隔离时，用 `planning-with-files` 维护 `plans/todo_current.md` 和每个 task 的 plan 文件。

### 用 Grill Me Smartly 审设计

当你想审一个方案，但希望先由 agent 代你调研代码事实时，使用 `grill-me-smartly`。

实际流程：

- 主 session 执行真正的 `grill-me` skill，一次只推进一个关键问题
- 常驻 answer-only subagent 代表你回答可通过本地文件、代码库、git 历史确认的问题
- 这个 subagent 在整个 review loop 期间保持打开，不是每个问题新派一个
- subagent 不使用任何 skill，只做事实调研和简短回答
- 主 session 把每轮问题、回答、证据和不确定性记录到 `docs/exchange/`
- 每解决一个问题后继续下一轮；只有决策树结束、需要你的真实偏好/风险取舍、或你要求停止时，才输出最终决策包

适合用来审实现计划、架构设计、迁移方案、复杂 debug 路线；不适合让 subagent 替你拍板产品意图或风险接受度。

### 保存 Session Handoff

当你要把当前上下文迁移到新会话时，使用 `handoff-new-session`。

默认 handoff 文件写到：

```text
docs/exchange/handoffs/handoff-<slug>-current.md
```

其中 `<slug>` 使用当前目标或工作流的 2-5 个小写 ASCII 词，例如 `checkout-integration`、`e2e-order-history`。默认刷新 rolling handoff；只有用户要求、审计冻结、长期分叉、或多个 child 必须从不同时间点恢复时，才额外写 timestamped 归档快照。

---

## 目录结构

```
agent-workbench/
├── AGENTS.md                   ← 仓库级 agent instructions，单一指令源
├── install.sh / install.ps1    ← 多宿主安装入口
├── skills/                     ← 正式 skills：自建、第三方、工作流知识库
│   ├── audit-agent-setup/      ← agent setup 审查知识库（rules + examples）
│   ├── grill-me-smartly/       ← grill-me + 常驻 answer-only subagent 设计审查
│   ├── handoff-new-session/    ← 会话上下文落盘和新会话接续提示词
│   ├── wt-pm/                  ← WT-PM 工作流知识库
│   │   ├── SKILL.md            ← 全流程编排入口 skill
│   │   ├── references/         ← 工作流参考文档
│   │   ├── rules/              ← 协作边界、DoD、planning 规则
│   │   ├── scripts/            ← plan_tracker.py、sync_worktree_config.*
│   │   └── templates/          ← 项目初始化模板（workplans/README.md 等）
│   ├── wt-plan/                ← trunk 规划阶段 skill
│   ├── wt-dev/                 ← worktree 开发阶段 skill
│   ├── planning-with-files/
│   └── ...
├── agents/                     ← subagents，安装到已选宿主的 agents/
│   └── audit-agent-setup/
│       └── agent.md
├── commands/                   ← 宿主 command 提示文件，安装到已选宿主的 commands/
│   └── audit.md
├── scripts/                    ← 仓库级辅助脚本，如 list-visible-skills.ps1
├── tests/                      ← 安装器和工作流测试
├── templates/
│   └── CLAUDE.md.tpl           ← 供 init-project-context 使用的模板
├── registry/
│   ├── third-party-skills.md   ← 第三方 skills 可复现清单
│   ├── plugins.md              ← 第三方 plugins / MCP 可复现清单
│   └── ...                     ← 只记录“安装单位”，不展开插件内每个文件
└── docs/workbench-design/      ← workbench 自身的设计规范
```

---

## 添加新 Skill

1. 在 `skills/` 下创建目录，加 `SKILL.md`（frontmatter 格式见 [docs/workbench-design/02-skills-spec.md](docs/workbench-design/02-skills-spec.md)）
2. skill 专属脚本放进该 skill 自己的 `scripts/` 目录，不要默认提取到仓库顶层

Windows 整目录 junction 安装态下，新 skill 通常立即对宿主可见；Bash/Unix 逐 skill symlink 安装态下，新增 skill 后需要重跑安装器。

第三方 skill 通过 `npx skills add <pkg> -g -y` 安装，会落入本仓库 `skills/` 目录；是否需要重跑安装器取决于上面的平台安装态。安装后在 `registry/third-party-skills.md` 补登记。

---

## 第三方资产登记

第三方资产统一登记到 `registry/`，方便换机器时查阅和重装。对于第三方 skills，正式内容直接放在仓库 `skills/` 下，再由安装器暴露到已选宿主的 skills 目录。

当前按资产类型拆分：

- `registry/third-party-skills.md`：第三方 skills 的人工清单，记录名称、来源、获取方式和备注
- `registry/plugins.md`：第三方 plugins / MCP 的人工清单

记录原则：

- 只登记第三方资产，不登记本仓库自建 skill
- 以”安装单位”记录，不展开插件内每个附带文件
- skills 清单不记录宿主路径和安装状态；plugins 清单可记录启用状态

### 刷新插件状态

当你切换机器、执行过插件更新、或怀疑插件环境漂移时，运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/verify-registry-state/scripts/verify-registry-state.ps1
```

它会检查 `registry/plugins.md` 里登记的 plugins 是否在当前机器存在，并把状态刷新为 `✅ 已装` 或 `⬜ 未装`。第三方 skills 以 `skills/<name>/` 中的正式内容为准，不维护状态列。

---

## 验证安装是否正常

```bash
ls -la ~/.claude/skills/
ls -la ~/.claude/agents/
cat ~/.claude/skills/audit-agent-setup/SKILL.md   # 确认内容可读

ls -la ~/.codex/skills/
ls -la ~/.codex/agents/

ls -la ~/.gemini/skills/
ls -la ~/.gemini/agents/
```

如果某个宿主识别不到 skill，优先用上面命令确认目录链接是否指向正确路径，以及 `commands/` 文件是否已复制。

## 冲突策略

- 目录目标不存在：创建 junction 或链接
- 目录目标已是指向当前 workbench 的 junction/链接：跳过并提示 `already linked, skipped`
- 文件目标不存在：复制
- 文件目标内容相同：跳过并提示 `already copied, skipped`
- 目标已存在但不匹配：跳过并提示 `conflict, skipped`
- 安装器不会删除已有同名目录、文件或其他链接

## 扩展新宿主

- 在 `install.sh` 和 `install.ps1` 的宿主映射表里增加新宿主名和根目录
- 同步更新 `tests/install.ps1`、`README.md` 和相关 `docs/workbench-design/` 规范
- 其余安装流程复用现有 `skills/agents/commands` 逻辑，无需重写主流程

安装器变更后运行：

```powershell
powershell -ExecutionPolicy Bypass -File tests/install.ps1
```

第三方 registry 逻辑变更后额外运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1
```


