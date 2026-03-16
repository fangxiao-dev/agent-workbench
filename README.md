# agent-workbench

个人 Agentic Coding 基础设施工具库。一次安装，在所有项目里共享同一套 skills、agents 和 commands，并可同时安装到多个 agent 宿主。

**安装后能做什么？** → [docs/capabilities.md](docs/capabilities.md)

---

## 安装

```bash
# 在任意目标项目目录下执行（Windows 用 install.ps1）
bash /path/to/agent-workbench/install.sh

# 显式只安装到指定宿主
bash /path/to/agent-workbench/install.sh /path/to/project claude codex
```

Windows 使用 `junction` 安装目录内容，通常不需要开发者模式；Bash/Unix 侧仍使用符号链接。

默认行为：

- 自动发现已知宿主目录并安装到这些宿主
- 当前内置宿主：`claude`、`codex`
- 也可以在命令后显式追加宿主名，只安装到指定宿主
- 遇到同名目标时不会删除或覆盖，而是跳过并报告冲突

安装后的位置：

| 来源 | 安装到 | 机制 |
|------|--------|------|
| `skills/*/` | `~/.claude/skills/`、`~/.codex/skills/` | Windows: junction；Bash/Unix: 软链接 |
| `agents/*/` | `~/.claude/agents/`、`~/.codex/agents/` | Windows: junction；Bash/Unix: 软链接 |
| `commands/*` | `~/.claude/commands/`、`~/.codex/commands/` | 复制 |

> **约定**：把 agent-workbench 放在固定路径（如 `~/dev/agent-workbench`），不要随意移动——软链接依赖绝对路径。

---

## 日常使用

### 修改立即生效

`skills/` 和 `agents/` 会直接指向本仓库；`commands/` 使用复制，如有变更需要重跑安装器同步。

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

触发 `agentic-audit` subagent，对当前项目的 CLAUDE.md、agents、skills、commands 做深度质量审查，输出带改进建议的报告。

### 生成项目上下文文件

`CLAUDE.md` 迁移到 `init-project-context` 流程里，按需主动触发，不再由安装器自动生成。

---

## 目录结构

```
agent-workbench/
├── install.sh / install.ps1    ← 多宿主安装入口
├── skills/                     ← 自定义 skills，安装到已选宿主的 skills/
│   ├── agentic-audit/          ← audit 知识库（rules + examples）
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
│   └── agentic-audit/
│       └── agent.md
├── commands/                   ← slash commands，安装到已选宿主的 commands/
│   └── audit.md
├── templates/
│   └── CLAUDE.md.tpl           ← 供 init-project-context 使用的模板
├── registry/
│   ├── third-party-skills.md   ← 第三方 skills 可复现清单
│   ├── plugins.md              ← 第三方 plugins / MCP 可复现清单
│   └── ...                     ← 只记录“安装单位”，不展开插件内每个文件
└── docs/workbench-design/                ← workbench 自身的设计规范
```

---

## 添加新 Skill

1. 在 `skills/` 下创建目录，加 `SKILL.md`（frontmatter 格式见 [docs/workbench-design/02-skills-spec.md](docs/workbench-design/02-skills-spec.md)）
2. skill 专属脚本放进该 skill 自己的 `scripts/` 目录，不要默认提取到仓库顶层
3. 重跑 `install.sh` 创建新软链接

---

## 第三方资产登记

第三方资产统一登记到 `registry/`，方便换机器时查阅、校验和重装。对于第三方 skills，当前优先把实际内容 vendoring 到仓库 `skills/` 下，再由 `install.sh` 暴露到已选宿主的全局 skills 目录。

当前按资产类型拆分：

- `registry/third-party-skills.md`：第三方 skills 的人工清单
- `registry/skills.lock.json`：skills 的机器可读元数据
- `registry/plugins.md`：第三方 plugins / MCP 的人工清单

记录原则：

- 只登记第三方资产，不登记本仓库自建内容
- 以“安装单位”记录，不展开插件内每个附带文件
- 优先写清来源、安装方式、配置入口和当前状态
- 第三方 skills 的上游元数据统一保存在 `registry/skills.lock.json`，不把 `.agents/` 之类的本机状态目录提交到仓库

### 刷新第三方状态

当你切换机器、执行过更新、或怀疑环境漂移时，运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/verify-registry-state/scripts/verify-registry-state.ps1
```

它会检查 `registry/` 里登记的第三方 skills / plugins 是否在当前机器存在，并把状态统一刷新为 `✅ 已装` 或 `⬜ 未装`。如果某个 plugin 同时附带 agents 或 commands，也仍按 plugin 这个安装单位登记。

---

## 验证安装是否正常

```bash
ls -la ~/.claude/skills/
ls -la ~/.claude/agents/
cat ~/.claude/skills/agentic-audit/SKILL.md   # 确认内容可读

ls -la ~/.codex/skills/
ls -la ~/.codex/agents/
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
- 其余安装流程复用现有 `skills/agents/commands` 逻辑，无需重写主流程


