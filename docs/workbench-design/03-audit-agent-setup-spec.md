# Audit Agent Setup 规范

`audit-agent-setup` 是低频、只读的 agent setup 审计能力。它由 skill 和 subagent 两部分组成：

| 位置 | 类型 | 职责 |
|------|------|------|
| `skills/audit-agent-setup/` | Skill | 选择审计范围并提供审查规则、示例和判断基线 |
| `agents/audit-agent-setup/` | Subagent | 按已选范围执行只读审计并输出报告 |

## 设计目标

- 覆盖 Codex、Claude、Gemini 等多宿主环境，但不在普通开发任务中默认调用。
- 默认只审用户指定文件或根 instruction files；`--full` 才审项目级 setup，`--include-global [host ...]` 才审指定的用户级宿主状态。
- 输出可执行的改进建议，而不是只检查文件是否存在或直接修改配置。

## Skill 部分

推荐结构：

```text
skills/audit-agent-setup/
├── SKILL.md
├── rules/
│   ├── official.md
│   └── custom.md
└── examples/
    ├── good-agent-instructions.md
    └── bad-agent-instructions.md
```

要求：

- `SKILL.md` 的 `name` 为 `audit-agent-setup`。
- description 明确说明它只审查已有 agent setup，并说明默认、`--full` 与 `--include-global` 的范围。
- `rules/official.md` 记录官方或厂商规则；宿主特定规则必须显式标注适用宿主。
- `rules/custom.md` 沉淀个人经验规则，不和官方规则混写。
- `examples/` 使用宿主中立命名，示例聚焦结构、可执行性、验证、边界与安全。

## Subagent 部分

`agents/audit-agent-setup/agent.md` 是执行者定义。它只执行已选范围的审计，审查结束后只输出报告，不自动修改文件；通过相对路径加载共享规则与示例，避免绑定到某个用户目录或单一宿主。

## 审查范围

默认（targeted）：

- 用户指定的文件；未指定时仅根目录已有的 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`

`--full` 项目级扩展：

- 嵌套 instruction files
- `.claude/agents|skills|commands`
- `.codex/agents|skills|commands`
- `.gemini/agents|skills|commands`
- 其他明显的项目级 agent 宿主目录或 instruction 入口

当 `--include-global` 指定 host 时，只审相同 host 的项目级专属目录和指令文件，同时保留共享 `AGENTS.md`。

`--include-global [host ...]` 用户级扩展：

- 指定宿主下的 instruction files、`skills/`、`agents/`、`commands/` 清单
- 未指定宿主时才盘点已安装宿主

不存在的指定目标必须在报告中列出，不能为了凑范围而扫描无关目录。

## 报告要求

- 报告先写 Scope，再按严重度给出 evidence、impact 与具体 change direction。
- 只表扬能降低歧义或风险的实践；没有问题时也要保留范围与假设。
- 只有涉及当前宿主行为的发现才读取或引用 `official.md`；其余审计以本地规则和已读文件为证据。

## Command 入口

`commands/audit.md` 保持命令名 `audit`，并显式说明 `/audit [path...]`、`/audit --full` 和 `/audit --full --include-global [host...]`。这样用户入口稳定，审计成本和隐私范围也保持清晰。
