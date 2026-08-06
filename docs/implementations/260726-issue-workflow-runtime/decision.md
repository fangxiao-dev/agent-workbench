# Issue Workflow Runtime 需求与决策

状态（Status）：Decision Gate Passed
创建时间（Created）：2026-07-26
决策修订（Decision Revision）：D2
需求来源（Requirement source）：2026-07-23 至 2026-07-26 owner 确认的 issue-driven development 设计与 [运行时设计](../../../skills/issue-workflow/assets/design/issue-workflow-implementation-design.md)
主题 slug（Topic slug）：issue-workflow-runtime
任务包 ID（Package ID）：260726-issue-workflow-runtime
规范任务包路径（Canonical package）：`docs/implementations/260726-issue-workflow-runtime/`

## 1. 需求定义（Focused PRD）

### 1.1 目标受益者与使用 / 调用情境

KaiSpan 的两人开发团队在讨论、调研、实现、review 与交接时使用 GitHub Issue 作为人与 agent 的共同协作语言。团队成员通过自然语言调用 `$issue-triage` 或 `$issue-reporter`，不应手工维护第二套工单系统。

### 1.2 当前问题或机会，以及改变原因

旧 `$triage` 是未被主动采用的 Matt 流程，错误地把外部 PR 当需求入口、依赖 `needs-triage` 与自动 Agent Brief，无法表达当前团队的 parent/sub-issue、readiness handoff 与 PR 证据边界。团队缺少可审计、可复用的 Issue 读取入口。

### 1.3 期望结果与产品 / 业务价值

团队能够用少量稳定 label 和 GitHub 原生关系表达当前工作；agent 能给出简短路由建议或可靠简报；任何远程修改都由用户确认后执行。这样交接与 review 不依赖聊天记忆，也不让流程本身成为负担。

### 1.4 核心产品行为或体验

用户描述新工作、已有 Issue、PR 或 backlog 时，`$issue-triage` 读取上下文并提出 parent/leaf/investigation、label、依赖、PR 关联和下一位行动者的建议。用户确认后才写入。用户只问当前状态时，`$issue-reporter` 读取同一合同并返回 portfolio、Issue brief、audit 或显式 PR hygiene，且不写入。

### 1.5 范围与边界

本包实现共享 issue-workflow bundle、YAML 合同、软模板、Python 只读读模型/计划计算，并以 `$issue-triage` 替换旧 `$triage`。GitHub CLI `gh` 是唯一远程适配器；Python 不保存 token、不直接写 GitHub。KaiSpan 的 repo-local 人员映射、tracker 文档、labels 与开放 Issue 迁移属于协调的 KaiSpan package。

### 1.6 成功信号

两位团队成员可在同一仓库中调用 `$issue-triage` 与 `$issue-reporter`，并获得符合共同合同的 proposal/report；在确认前运行不会改变 GitHub，确认后的操作可明确列出其 Issue、PR、label 和人员影响。

## 2. 目标落点与合同交接

- 受影响的系统边界：agent-workbench `skills/` bundle 与宿主 skill discovery。
- Core / Capability 边界与 owner：共享合同、读模型和 skill runtime 由 agent-workbench 拥有；KaiSpan 是该合同的首个 repo-specific consumer。
- 当前 Capability、调用者与延后暴露：Codex、Claude、Gemini 可发现 leaf skill；GitHub Project、webhook、bot 和自动修复延后且不暴露。
- 交给 `spec.md` 定义的行为合同范围：CLI 输入输出、readiness handoff、hard/soft rule、`gh` 边界、确认与 failure 行为。
- 交给 `plan.md` 解决的实施范围：本任务不创建独立 plan；实现按 spec 的小型变更直接执行。

## 3. 知识来源 / 当前状态

- 已检查的权威来源：`AGENTS.md`、`docs/workbench-design/02-skills-spec.md`、现有 `$triage`/`$write-issue`、三份 issue workflow 设计稿。
- 聚焦代码 / 测试事实：现有 `$triage` 仅有 Markdown 规则；skill bundle 可递归发现；`discuss-ledger` 证明专属 Python scripts 模式可用。
- 预期但缺失的知识：无；私库访问由运行时 `gh auth` 决定。
- 冲突或 drift：旧 triage 词汇与新合同不兼容，实施时统一替换。

## 4. 约束 / Authority 边界

- 约束：YAML 是机器 canonical；Markdown 和模板不复制可枚举规则；Python 仅做确定性处理。
- 安全或外部 mutation 边界：未确认前不调用任何 `gh` 写命令；确认后的写入由 `$issue-triage` 而非 Python 执行。

## 5. 选项 / 权衡

| 选项 | 收益 | 成本 / 风险 | 与仓库的契合度 |
| --- | --- | --- | --- |
| 纯 Markdown skill | 初始最快 | 规则分散、审计重复推理 | 不足 |
| YAML + Python 读模型 + 薄 skill | 规则稳定、保留 agent 判断 | 需维护小型 fixture | 选中 |
| Python 工作流引擎 | 自动化最多 | 将 agent 限制为填表 | 过重 |

## 6. 决策 / 理由

| 决策 | 理由 | Owner | 日期 |
| --- | --- | --- | --- |
| 采用共享 bundle、YAML 合同、Python 读模型与 `gh` 适配器 | 将机械校验与业务判断分离，满足两人团队轻量协作 | fangxiao-dev | 2026-07-26 |

## 7. 开放问题 / Owner 决策 / 就绪度

### 开放问题

无 blocking 问题。GitHub labels 与迁移需要 KaiSpan package 的后续 owner 确认，不阻塞本包的本地实现。

### Decision 门

- 结果（Result）：PASSED
- 目标落点可回答：共享 workbench bundle 与 Python scripts。
- 仓库契合度已有证据：bundle、references、templates 与 scripts 均为现有规范能力。
- 实质选择已决定：采用 YAML + Python 读模型，不建自动写入引擎。
- blocking decision uncertainty 已关闭：是。
- 开放问题不阻塞 Spec：是。
- Owner 决策已记录：2026-07-26 批准运行时实现设计。
- 证据 / 剩余 blocker：无。
- 评估人 / 日期：Codex / 2026-07-26。

## 修订历史

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| 无 | D1 | 初始运行时决策 | owner 批准设计 | 2026-07-26 | 无 |
| D1 | D2 | 将 router 调用名更改为 `$issue-triage` | owner 批准 rename | 2026-07-26 | D1 |
