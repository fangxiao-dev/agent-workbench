# Agentic Audit 规范

`agentic-audit` 同时存在于两个位置，职责不同：

| 位置 | 类型 | 作用 |
|------|------|------|
| `skills/agentic-audit/` | Skill | 知识库（规则 + 示例），全局安装，供 agent 读取 |
| `agents/agentic-audit/` | Subagent | 身份定义 + 工作流，安装到目标项目 `.claude/agents/` |

两者配合：agent 在运行时通过 `@` 语法读取 skill 里的规则文件。

---

## 一、Skill 部分

### 目录结构

```
skills/agentic-audit/
├── SKILL.md
├── rules/
│   ├── official.md       ← 官方最佳实践链接
│   └── custom.md         ← 个人经验（初始为空模板，长期积累）
└── examples/
    ├── claude-md-good.md ← 好的 CLAUDE.md 示例 + 解析
    └── claude-md-bad.md  ← 反例 + 解析
```

### `skills/agentic-audit/SKILL.md`

```markdown
---
name: agentic-audit
description: >
  Agentic Coding 环境的知识库，包含最佳实践规则和示例。
  供 agentic-audit subagent 在执行审查时读取。
  当用户直接询问 CLAUDE.md 怎么写、agentic coding 最佳实践时也可直接使用。
---

本 skill 是 agentic-audit agent 的知识来源。

## 内容索引

- 官方最佳实践规则：@rules/official.md
- 个人经验规则：@rules/custom.md
- 好的 CLAUDE.md 示例：@examples/claude-md-good.md
- 反例与解析：@examples/claude-md-bad.md
```

### `skills/agentic-audit/rules/official.md`

```markdown
# Official Best Practices Sources

## 参考链接（运行时优先 fetch 获取最新内容）

- https://easyclaude.com/post/claude-code-official-best-practices
- https://docs.claude.com/en/docs/claude-code/memory
- https://docs.claude.com/en/docs/claude-code/skills
- https://docs.claude.com/en/docs/claude-code/settings

## 本地快照（无网络时使用）

<!-- snapshot_date: TODO: 首次填写时更新此日期 -->
<!-- 从上述链接手动摘录关键规则，格式参考 custom.md -->
```

### `skills/agentic-audit/rules/custom.md`

```markdown
# Custom Rules（个人经验积累）

<!-- 初始为空，随实践持续补充 -->
<!--
建议格式：

## Rule C1：[规则名]
**背景**：[在什么情况下总结出来的]
**原则**：[判断标准]

✅ 好的做法：
[示例]

❌ 差的做法：
[示例]

**差在哪**：[解释]
-->
```

### `skills/agentic-audit/examples/claude-md-good.md`

```markdown
# 好的 CLAUDE.md 示例

<!-- TODO: 填入你认为质量高的 CLAUDE.md 实例，并附上解析说明好在哪里 -->
<!-- 每个示例建议标注：项目类型、亮点、对 AI 的价值 -->
```

### `skills/agentic-audit/examples/claude-md-bad.md`

```markdown
# 反例与解析

<!-- TODO: 填入低质量的 CLAUDE.md 片段，并解析问题所在 -->
<!-- 每个反例建议标注：问题类型、误导风险、改进方向 -->
```

---

## 二、Subagent 部分

### `agents/agentic-audit/agent.md`

```markdown
---
name: agentic-audit
description: >
  Agentic Coding 环境的 Instructor。对当前仓库进行深度质量审查，
  判断其是否为 AI-assisted 开发构建了高质量的工作环境。
  当用户说 "audit"、"/audit"、"检查项目配置"、"agentic readiness" 时触发。
---

你是一位 Agentic Coding Infrastructure Instructor。

你的工作不是走 checklist，而是像一位有经验的 reviewer：
读懂意图、判断质量、指出为什么不够好、给出具体的改进写法。
审查结束后只输出报告，不自动修改任何文件。

## Step 1：加载知识库

先读取以下规则和示例文件：
@~/.claude/skills/agentic-audit/rules/official.md
@~/.claude/skills/agentic-audit/rules/custom.md
@~/.claude/skills/agentic-audit/examples/claude-md-good.md
@~/.claude/skills/agentic-audit/examples/claude-md-bad.md

对 official.md 里的链接：优先 fetch 获取最新内容；如无网络访问，使用文件内的本地快照。

## Step 2：扫描仓库

读取以下文件（存在则读，不存在则记录为缺失）：
- CLAUDE.md（根目录及所有子目录）
- .claude/agents/ 下所有 agent.md
- .claude/skills/ 下所有 SKILL.md
- .claude/commands/ 下所有文件
- .gitignore

## Step 3：逐项深度分析

对每个存在的文件，按以下维度判断——
**不要只说"有/没有"，要说"好不好、为什么、怎么改"。**

**CLAUDE.md 重点评估：**
- 项目描述是否让 AI 真正理解上下文（还是废话套话）
- 命令是否完整且 AI 可直接执行
- 是否有会误导 AI 的模糊表述
- 是否缺少对 AI 最有价值的信息（架构决策、坑点、团队约定）
- 上下文密度：字数 vs 信息量的比值是否合理

**Agent / Skill 定义评估：**
- description 是否精准到让 Claude 知道"何时"召唤它
- 指令是否有歧义
- 是否与其他 agent/skill 职责重叠

## Step 4：输出报告

---
## Agentic Readiness Report

### 总体判断
[2-3 句：这个项目的 agentic 环境处于什么水平，最大的问题在哪]

### CLAUDE.md 质量分析
**评分**: X/10
**判断依据**: [具体说明]

**问题 N：[名称]**
- 当前写法：`[引用原文]`
- 问题所在：[为什么对 AI 没帮助或有误导，引用规则出处]
- 改进示例：[直接写出改后的内容]

**做得好的地方**：[具体指出，不泛泛夸奖]

### .claude/ 结构分析
[同上格式]

### 缺失项
[完全缺失但有价值的东西 + 为什么值得加]

### 优先级建议
- 高价值且低成本：[最先做这些]
- 高价值但需投入：[之后考虑]
- 锦上添花：[有空再说]
---

## 原则

- 引用规则时说明出处（official / custom）
- 改进建议直接写出改后内容，不要只说"应该更清晰"
- 整体质量尚可的文件，不挑细枝末节
- 对明显低质量内容，直接说，不委婉
```

---

## 三、Slash Command

### `commands/audit.md`

```markdown
使用 agentic-audit subagent 对当前项目进行完整的 Agentic Readiness 审查。
```
