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
│   ├── skills.md               ← 第三方 skills 备忘清单（手动安装，不参与 install.sh）
│   └── plugins.md              ← MCP/plugin 备忘清单
└── docs/design/                ← workbench 自身的设计规范
```

---

## 添加新 Skill

1. 在 `skills/` 下创建目录，加 `SKILL.md`（frontmatter 格式见 [design/02-skills-spec.md](docs/design/02-skills-spec.md)）
2. 重跑 `install.sh` 创建新软链接

---

## 第三方 Skills

不通过 install.sh 安装，需手动安装后记录在 [registry/skills.md](registry/skills.md)，方便换机器时查阅。

---

## 验证软链接是否正常

```bash
ls -la ~/.claude/skills/
ls -la ~/.claude/agents/
cat ~/.claude/skills/agentic-audit/SKILL.md   # 确认内容可读
```

如果 Claude Code 识别不到某个 skill，优先用上面命令确认链接是否指向正确路径。
