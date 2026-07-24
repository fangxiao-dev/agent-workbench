# 讨论路由与通用模型执行器需求与决策

状态（Status）：Decision Gate Passed
创建时间（Created）：2026-07-24
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D1
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：用户确认的 Blind Opening、Discuss Ledger 与通用 executor 设计
主题 slug（Topic slug）：discussion-router-executors
任务包 ID（Package ID）：260724-discussion-router-executors
规范任务包路径（Canonical package）：`docs/implementations/260724-discussion-router-executors/`

本文是任务包活动期间“聚焦需求定义 + 当前方案决策与理由”的事实源。

## 1. 需求定义（Focused PRD）

- 目标用户 / 使用场景：需要多个模型协助发散、讨论和收敛方案的工作台使用者及其上游 skill。
- 当前问题与触发条件：现有 Discuss Ledger 只能从首位参与者开始顺序讨论，后续参与者会先看到前序观点；Codex 与 Claude 的 CLI 适配又内嵌在讨论脚本中，不能被其他 skill 复用。
- 期望结果与用户价值：用户可以明确选择独立 Blind Opening、现有 Ledger 讨论或二者组合；其他 skill 可稳定调用 Codex/Claude，而不重复实现 CLI 适配。
- 范围：新增 Blind Opening、薄 Router、`call-codex`、`call-claude`，并将现有 orchestrator 的内嵌适配下沉。
- 非目标：不改变正常 Ledger 的讨论语义；不改变或扩展 MCP；不添加预制 role；不改变 loop mode。
- 核心体验或业务流程：先独立收集多方方案，再按需将归并出的争点交给原有 Ledger 收敛；或只做独立发散后结束。
- 成功判断信号：默认 Ledger 调用的行为与 fake smoke path 保持可用；Blind Opening 的每个参与者不接收其他参与者结果；两个 executor 可由不同上游传入 prompt 与模型配置。

## 2. 目标落点与合同交接

- 受影响的系统边界：`skills/discuss-ledger/` 及新增 `skills/call-codex/`、`skills/call-claude/`。
- Core / Capability 边界与 owner：Core 是两个 executor 对各自 CLI 的运行、超时、错误和结果适配；Capability 是 Discuss Ledger Router 与 Blind Opening 工作流。各自 skill 拥有对应实现。
- 当前 Capability、调用者与延后暴露：Discuss Ledger 是首个调用方；任何未来 skill 都可调用 executor。MCP 交互式账本接口维持原状并不参与新流程。
- 交给 `spec.md` 定义的行为合同范围：模式路由、上下文隔离、组合 hand-off、executor 输入输出、兼容性和验收语义。
- 交给 `plan.md` 解决的实施范围：目录/脚本迁移顺序、测试、文档迁移和回归验证。

## 3. 知识来源 / 当前状态

- 已检查的权威来源：根 `AGENTS.md`、`skills/discuss-ledger/SKILL.md`、其 orchestrator/loop references、`scripts/discuss_orchestrator.py`、`mcp_server.py`、`skills/call-grok/` 及项目级设计文档。
- 聚焦代码 / 测试事实：现有 orchestrator 直接运行 `codex exec` 和 `claude -p`，并拥有 Ledger prompt、schema 验证、轮询和 fake adapter；MCP server 只暴露 ledger 读写工具和资源。
- 预期但缺失的知识：没有现成的 `call-codex` 或 `call-claude` skill，也没有 Blind Opening 脚本或 schema。
- 冲突或 drift：无；现有设计文档的 MCP 描述保留为现状说明，本任务不将 MCP 作为新机制依赖。

## 4. 约束 / Authority 边界

- 约束：现有 normal Ledger 的 prompt、状态机、CLI 语义和 fake smoke path 是兼容性底线；默认路由保持 Ledger；模式歧义时由 Router 询问用户。
- 安全或外部 mutation 边界：executor 不定义权限、role 或任务语义；调用者显式传入模型配置与 prompt。Discuss Ledger 继续由上游请求只读模型行为。

## 5. 选项 / 权衡

| 选项 | 收益 | 成本 / 风险 | 与仓库的契合度 |
| --- | --- | --- | --- |
| 在现有 orchestrator 内添加 blind flag | 改动表面小 | Blind Opening 不能独立使用，耦合正常 Ledger | 低 |
| 独立 Blind Opening + 原样 Ledger + Router | 复用清晰，隔离上下文，可单独结束 | 新增薄编排层和归并契约 | 高 |
| 通过 MCP 编排所有模型调用 | 统一工具表面 | 增加服务生命周期，不能简化并发/超时/结构化输出 | 低 |

## 6. 决策 / 理由

| 决策 | 理由 | Owner | 日期 |
| --- | --- | --- | --- |
| 采用独立 Blind Opening、原样 Discuss Ledger 和薄 Router 的三模式设计 | 避免首位观点锚定，同时不侵入成熟的 Ledger 状态机 | 用户 | 2026-07-24 |
| 新建无预制 role 的 `call-codex` 与 `call-claude` 基础 skill | 将 CLI 易变细节集中复用，保留上游对 prompt 与权限的控制 | 用户 | 2026-07-24 |
| 新机制不使用 MCP，既有 MCP 不动 | 自动编排直接管理进程和结果更简单；MCP 仍可服务交互式 ledger 操作 | 用户 | 2026-07-24 |

## 7. 开放问题 / Owner 决策 / 就绪度

### 开放问题

| 问题 | 分类 | 若未证实 / 不成立的合同影响 | 所需证据 | 可直接只读调查 | Owner / 授权或延后边界 |
| --- | --- | --- | --- | --- |
| executor 的统一 envelope 是否可同时承载 Codex JSONL 与 Claude JSON wrapper | non-blocking | 仅影响适配实现，不改变模式合同 | 现有 CLI 输出与 fake tests | 是 | 实施者；以 `text`、status、error、exit_code 为最小共同字段 |

### Decision 门

- 结果（Result）：PASSED
- 目标落点可回答：三模式 Router 与通用 executor 的边界已确定。
- 仓库契合度已有证据：复用现有 skill 目录、脚本和 `call-grok` 的 executor 形态。
- 实质选择已决定：独立 Blind Opening，正常 Ledger 原样保留，不使用 MCP 或 role presets。
- blocking decision uncertainty 已关闭：是。
- 开放问题不阻塞 Spec：是，只有适配内部实现细节。
- Owner 决策已记录：是。
- 证据 / 剩余 blocker：无。
- 评估人 / 日期：Codex / 2026-07-24。

## 8. Backfill 候选

| 可能的目标位置 | 候选洞见 | 可能长期有效的原因 |
| --- | --- | --- |
| `docs/workbench-design/02-skills-spec.md` | 通用 executor 的目录/调用契约 | 其他 skill 将依赖该约定 |

## 修订历史

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| 无 | D1 | 初始方向：三模式讨论 Router 与通用 executor | 用户确认的设计 | 2026-07-24 | 无 |
