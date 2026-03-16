# agent-workbench

个人 Agentic Coding 基础设施工具库。一次安装，在所有项目里共享同一套 skills、agents 和 commands。

**安装后能做什么？** → [docs/capabilities.md](docs/capabilities.md)

---

## 安装

```bash
# 在任意目标项目目录下执行（Windows 用 install.ps1）
bash /path/to/agent-workbench/install.sh
```

Windows 需要开启开发者模式（设置 → 系统 → 开发者选项），因为目录软链接需要该权限。

安装后的位置：

| 来源 | 安装到 | 机制 |
|------|--------|------|
| `skills/*/` | `~/.claude/skills/` | 软链接 |
| `agents/*/` | `~/.claude/agents/` | 软链接 |
| `commands/*` | `~/.claude/commands/` | 软链接 |
| `templates/CLAUDE.md.tpl` | `<目标项目>/CLAUDE.md` | 复制（仅在不存在时） |

> **约定**：把 agent-workbench 放在固定路径（如 `~/dev/agent-workbench`），不要随意移动——软链接依赖绝对路径。

---

## 日常使用

### 修改立即生效

所有文件通过软链接指向本仓库。在 workbench 里改完保存，无需重跑 install.sh。

### 在任意项目里运行审查

```
/audit
```

触发 `agentic-audit` subagent，对当前项目的 CLAUDE.md、agents、skills、commands 做深度质量审查，输出带改进建议的报告。

### 生成新项目的 CLAUDE.md

```bash
bash /path/to/agent-workbench/install.sh /path/to/new-project
```

如果目标项目没有 CLAUDE.md，会从 `templates/CLAUDE.md.tpl` 生成一份带 TODO 标注的草稿。

---

## 目录结构

```
agent-workbench/
├── install.sh / install.ps1    ← 安装入口
├── skills/                     ← 自定义 skills，安装到 ~/.claude/skills/
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
├── agents/                     ← subagents，安装到 ~/.claude/agents/
│   └── agentic-audit/
│       └── agent.md
├── commands/                   ← slash commands，安装到 ~/.claude/commands/
│   └── audit.md
├── templates/
│   └── CLAUDE.md.tpl           ← 新项目初始化模板
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

第三方资产统一登记到 `registry/`，方便换机器时查阅、校验和重装。对于第三方 skills，当前优先把实际内容 vendoring 到仓库 `skills/` 下，再由 `install.sh` 暴露到 `~/.claude/skills/`。

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

## 验证软链接是否正常

```bash
ls -la ~/.claude/skills/
ls -la ~/.claude/agents/
cat ~/.claude/skills/agentic-audit/SKILL.md   # 确认内容可读
```

如果 Claude Code 识别不到某个 skill，优先用上面命令确认链接是否指向正确路径。


