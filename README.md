# agent-workbench

个人 Agentic Coding 基础设施工具库。这个仓库是 `claude`、`codex`、`grok` 多宿主共享的 skills、agents、commands、安装器和治理文档的 source of truth。

**安装后能做什么？** → [docs/capabilities.md](docs/capabilities.md)

---

## 设计总览

`agent-workbench` 的目标是把可复用的 agent 能力集中维护，然后以非破坏方式暴露给不同宿主：

- `skills/` 保存所有正式 skill，包括自建 skill、审查过的第三方 skill、以及本地工作流知识库
- `skills/` 也包含可显式 `$` 调用的共享委派入口：`investigate-before-implement`、`reviewer`
- `agents/` 保存可安装到宿主的 subagent 定义，目前正式 subagent 是 `audit-agent-setup`
- `commands/` 保存宿主 command 提示文件；是否能用 `/...` 唤出取决于具体宿主
- `scripts/link_skill.py` 把单个（或全部顶层）skill **link** 到 `~/.claude` / `~/.codex` / `~/.grok` 的 `skills/`（Windows junction，Unix/macOS symlink）
- `registry/` 只记录第三方资产来源和重装方式，不记录宿主本机状态
- `docs/workbench-design/` 保存当前实现规范，README 只做入口说明
- `tests/` 保存安装器和核心脚本测试

仓库根目录下的 `.agents/`、`.claude/`、`.pytest_cache/`、`skills-lock.json` 等属于本机运行态、工具状态或缓存，不作为规范源。

---

## 安装（skill link）

薄安装器：`scripts/link_skill.py`。Agent 日常只需 **skill 名 + host**。

```bash
# 单个 skill
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude

# 多个宿主
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude codex grok

# 全部顶层 skills/*
python3 /path/to/agent-workbench/scripts/link_skill.py --all --host claude

# 卸载宿主 link（不删 workbench 源头）
python3 /path/to/agent-workbench/scripts/link_skill.py verify-registry-state --unlink --host claude codex grok
```

| 平台 | 机制 |
|------|------|
| Windows | 每个 skill 目录 **junction**（通常无需开发者模式） |
| Linux / macOS / Unix | 每个 skill 目录 **symlink** |

默认行为：

- 非破坏：冲突则跳过并报告，不覆盖
- 若宿主 `skills` 仍是「整树指向本 workbench `skills/`」的旧 junction/symlink，会先拆掉并建成真实目录，再写 per-skill link
- 支持宿主：`claude`、`codex`、`grok`
- 不安装 `agents/` / `commands/`；不改项目 `.gitignore`

`skills/` 支持 bundle（如 `skills/lark-skills/`）：按**顶层目录**链一次，内部子 skill 随目录暴露。

> **约定**：workbench 路径尽量固定——link 使用绝对路径。

### Discuss Ledger MCP 注册

`discuss-ledger` MCP **不**由 `link_skill.py` 注册，需单独运行：

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

Codex 写入项目内 `.codex/config.toml`；Claude 优先 `claude mcp add --scope project`。无 `claude` CLI 时只打印 `.mcp.json` 片段。

---

## 日常使用

### Codex Session Prune

`codex_session_prune.py` 通过 Codex App Server 枚举 session，并按 project、archive state 和更新时间生成安全的删除计划。默认只做 inventory；候选计划也是 dry-run，不会读取或直接删除 rollout JSONL。需要磁盘占用时加 `--disk-size`，工具只枚举 `sessions/` 和 `archived_sessions/` 下的 rollout 文件并读取文件大小元数据，不解析文件内容。

```powershell
python scripts/codex_session_prune.py

python scripts/codex_session_prune.py `
  --project D:\CodeSpace\agent-workbench `
  --archive-state archived `
  --take 20 `
  --max-affected 100 `
  --disk-size
```

审阅输出中的 `plan_id` 后，只有显式同时传入 `--apply --expect-plan <plan_id>` 才会调用 App Server 的 `thread/delete`。apply 会重新枚举并校验计划；Owner 未单独批准具体 plan ID 时不要执行 apply。

### 修改和同步

宿主 `skills/<name>` 是指向 workbench 的 **per-skill** junction（Win）或 symlink（Unix）。新增顶层 `skills/<name>/` 后执行：

```bash
python3 scripts/link_skill.py <name> --host claude
# 或
python3 scripts/link_skill.py --all --host claude
```

仅新增 bundle **内部**子目录时，若顶层 bundle 已 link，通常立即可见。

### 核对宿主最终可见 skills

```bash
bash scripts/list-visible-skills.sh
```

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
/audit [path ...]
/audit --full
/audit --full --include-global [host ...]
```

默认只审指定文件；未指定时只审根 `AGENTS.md`、`CLAUDE.md`。`--full` 才扩展到项目级 agent setup，`--include-global [host ...]` 才读取指定的用户级宿主状态，并同步收窄项目级专属宿主目录。审计只输出带证据的改进建议，不修改文件。

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

### 回刷常青文档

`$backfill-stable-docs` 是 Impl-Package 内维护阶段的公共入口，不需要 Plugin。它按仓库内配置的显式相对路径收集 package、pending 和 stable docs。audit 只读生成带可读 item ID 的报告；apply 只处理 owner 对某报告明确批准的 item ID；verify 独立检查路径、目标 Git commit、链接、audit 结构和 inventory，且不补写内容。三个阶段必须分别汇报，audit 完成不表示 apply 或 verify 完成。

### Implementation Package 规划发布

当 plan、earned Ticket/DAG bundle 已 review 且 owner 批准后，直接写入批准内容并初始化最小 current state：

```powershell
python skills/impl-package/scripts/impl_package_state.py --package <package> init --attempt <attempt-id> --plan <repo-relative-plan>
python skills/impl-package/scripts/impl_package_state.py --package <package> validate
```

D/S/P 只作为可读别名；跨 session 比较使用批准内容所在的 Git commit。所有持久化文件和 evidence 引用使用仓库相对路径。Git commit/push 与远程更新保持独立。

不同仓库通过项目根 `.stable-docs-backfill.json` 或显式的仓库内配置文件声明 canonical docs、pending 和 Implementation Package 根目录。配置只接受显式仓库相对路径；目标基准使用本地可解析的 Git commit。

### 多任务 / worktree 工作流

WT-PM 工作流拆成三个 skill：

| Skill | 场景 | 职责 |
|-------|------|------|
| `wt-pm` | 不确定当前阶段时 | 识别阶段并路由到 planning 或 dev |
| `wt-plan` | trunk 规划侧 | 任务定义、plan 三文件、branch/worktree handoff |
| `wt-dev` | task worktree 执行侧 | 加载 plan、实现、验证、回收和状态更新 |

不需要 worktree 隔离时，用 `planning-with-files` 维护 `plans/todo_current.md` 和每个 task 的 plan 文件。

### 用 Grill Me Smartly 审设计

当你想审一个方案，但希望 agent 一边追问、一边代你调研代码事实，并把自动判断过程整理成中文记录时，使用 `grill-me-smartly`。

推荐说法：

```text
用 grill-me-smartly 审 docs/plans/user-auth-migration.md。
```

实际流程：

- 主 session 是书记、裁判和用户意图网关，只通过脚本写入 ledger
- 常驻 Questioner subagent 负责沿设计树提出下一个关键问题
- Answerer subagent 只回答可通过本地文件、代码库、git 历史或工具确认的问题
- ledger 写在 `docs/exchange/grill/grill-<slug>.md`，顶部用中文汇总已收敛决策、待用户裁决、问题与回答总览、停止证明
- review 阶段只输出完整意见对齐文档，不直接改被审计划
- 你检查 ledger 后明确要求应用时，才把已收敛意见更新回原文档

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
├── scripts/link_skill.py       ← 多宿主 per-skill 安装入口
├── skills/                     ← 正式 skills：自建、第三方、工作流知识库
│   ├── audit-agent-setup/      ← agent setup 审查知识库（rules + examples）
│   ├── grill-me-smartly/       ← 中文 Grill Ledger + Questioner/Answerer 设计审查
│   ├── handoff-new-session/    ← 会话上下文落盘和新会话接续提示词
│   ├── feishu-skills/          ← 国内飞书 skills bundle（feishu-*）
│   ├── lark-skills/            ← Lark International bundle（using-lark 入口 + 内部 sub-skills）
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

1. 在 `skills/` 下创建目录并添加 `SKILL.md`；成组能力可放在 `skills/<bundle>/<name>/SKILL.md`（frontmatter 格式见 [docs/workbench-design/02-skills-spec.md](docs/workbench-design/02-skills-spec.md)）
2. skill 专属脚本放进该 skill 自己的 `scripts/` 目录，不要默认提取到仓库顶层

新增顶层 skill 后需要再跑 `link_skill.py`（或 `--all`）才会出现在宿主 `skills/`。

第三方 skill 通过 `npx skills add <pkg> -g -y` 安装，默认落入本仓库 `skills/<name>/`；同一上游的成组能力可归入 `skills/<bundle>/<name>/`。是否需要重跑安装器取决于上面的平台安装态，安装后在 `registry/third-party-skills.md` 补登记实际路径。

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

ls -la ~/.grok/skills/
```

如果某个宿主识别不到 skill，优先用上面命令确认目录链接是否指向正确路径，以及 `commands/` 文件是否已复制。

## 冲突策略

- skill 目标不存在：创建 per-skill junction（Win）或 symlink（Unix）
- 目标已是指向同一 skill 源的 link：跳过（`skipped`）
- 文件目标不存在：复制
- 文件目标内容相同：跳过并提示 `already copied, skipped`
- 目标已存在但不匹配：跳过并提示 `conflict, skipped`
- 安装器不会删除已有同名目录、文件或其他链接

## 扩展新宿主

- 在 `scripts/link_skill.py` 的宿主映射里增加新宿主名和根目录
- 同步更新 `tests/test_link_skill.py`、`README.md` 和 `docs/workbench-design/04-install-spec.md`
- 其余安装流程复用现有 `skills/agents/commands` 逻辑，无需重写主流程

安装器变更后运行：

```powershell
python -m pytest tests/test_link_skill.py -q
```

第三方 registry 逻辑变更后额外运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1
```
