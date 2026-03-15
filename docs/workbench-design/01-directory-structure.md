# 目标目录结构

```
my-workbench/
│
├── install.sh                          ← 一键安装到目标项目
├── README.md
│
├── scripts/                            ← 跨 skill 共用的脚本
│   ├── utils.sh
│   └── parse-frontmatter.py
│
├── skills/                             ← 自定义 skills，安装到 ~/.claude/skills/
│   ├── agentic-audit/                  ← Agentic 环境质量审查
│   │   ├── SKILL.md
│   │   ├── scripts/                    ← 该 skill 专属脚本
│   │   │   └── scan-repo.sh
│   │   ├── rules/
│   │   │   ├── official.md             ← 官方链接 + 离线快照
│   │   │   └── custom.md               ← 个人经验积累（长期维护）
│   │   └── examples/
│   │       ├── claude-md-good.md
│   │       └── claude-md-bad.md
│   └── .../                            ← 其他自定义 skills
│
├── agents/                             ← 安装到目标项目 .claude/agents/
│   └── agentic-audit/
│       └── agent.md                    ← subagent 身份 + 工作流定义
│
├── commands/                           ← 安装到目标项目 .claude/commands/
│   └── audit.md                        ← /audit 触发入口
│
├── templates/                          ← 新项目初始化模板
│   └── CLAUDE.md.tpl                   ← 带变量的 CLAUDE.md 模板
│   
│
└── registry/                           ← 第三方工具清单，仅备忘，不参与安装
    ├── skills.md                        ← 第三方 skills 及安装命令
    └── plugins.md                       ← MCP/plugin 及安装命令
```

## 说明

- `skills/` 下的每个目录是一个独立 skill，结构详见 `specs/02-skills-spec.md`
- `agents/` 下的内容会被 `install.sh` 复制到目标项目的 `.claude/agents/`
- `templates/` 内容只在目标项目**不存在对应文件时**才生成，不覆盖已有内容
- `registry/` 纯粹是人类可读的备忘清单，install.sh 不读取它
