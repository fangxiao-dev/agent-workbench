# [实施名称] 需求与决策

状态（Status）：Draft | Decision Gate Passed | Decision Gate Blocked
创建时间（Created）：
Decision Revision：D<n>
需求来源（Requirement source）：
主题 slug（Topic slug）：
任务包 ID（Package ID）：
规范任务包路径（Canonical package）：`docs/implementations/<package-id>/`

本文是任务包活动期间“聚焦需求定义 + 当前方案决策与理由”的事实源：回答为什么做、要达到什么结果、为什么选择该方向。系统必须如何表现、字段与状态合同、错误处理和 Acceptance Semantics 属于 Spec 阶段，由 `spec.md` 与其按需使用的 `contract-design.md` 共同承载；如何拆解、实现和验证只属于 `plan.md`。当前正文只保留最新需求与选择，修订历史只记录最近变更。Decision 被阻塞时使用本文件，不创建 `spec.md`。`Status: Decision Gate Passed` 必须对应 `Result: PASSED`；`Status: Decision Gate Blocked` 必须对应 `Result: BLOCKED`。若引用 `investigations/<topic>.md`，本文件仍必须自足说明当前需求与决定；investigation 默认无 authority，且不维护 backlink 或采用状态。

## 1. 需求定义（Focused PRD）

<!-- 聚焦表达本次变化的产品需求，不复制 spec 的字段级合同、状态机、错误处理或逐条 Acceptance Criteria。写作和 Gate 判断须遵循 `req-align/references/requirement-inputs.md` 与 `req-align/references/focused-prd.md`：第一版承接已确认的口头/文档输入；后续版本先读取当前 D/S，再合并本次 delta。存在条件式产品信号时，在相关小节内补充回答；不要为未出现的信号制造空章节。 -->

### 1.1 目标受益者与使用 / 调用情境

### 1.2 当前问题或机会，以及改变原因

### 1.3 期望结果与产品 / 业务价值

### 1.4 核心产品行为或体验

### 1.5 范围与边界

### 1.6 成功信号

## 2. 目标落点与合同交接

- 受影响的系统边界：
- Core / Capability 边界与 owner：
- 当前 Capability、调用者与延后暴露：
- 交给 Spec 阶段定义的行为与 canonical contract 范围：
- 交给 `plan.md` 解决的实施范围：

## 3. 知识来源 / 当前状态

- 已检查的权威来源：
- 聚焦代码 / 测试事实：
- 预期但缺失的知识：
- 冲突或 drift：

## 4. 约束 / Authority 边界

- 约束：
- 安全或外部 mutation 边界：

## 5. 选项 / 权衡

| 选项 | 收益 | 成本 / 风险 | 与仓库的契合度 |
| --- | --- | --- | --- |

## 6. 决策 / 理由

<!-- 只记录选中的方向及其理由；不要重复第 1 节的需求背景，也不要复制 spec 中的行为合同。 -->

| 决策 | 理由 | Owner | 日期 |
| --- | --- | --- | --- |

## 7. 开放问题 / Owner 决策 / 就绪度

### 开放问题

| 问题 | 分类 | 若未证实 / 不成立的合同影响 | 所需证据 | 可直接只读调查 | Owner / 授权或延后边界 |
| --- | --- | --- | --- | --- |

<!-- 分类只能是 blocking 或 non-blocking。blocking 默认阻塞 Decision Gate；non-blocking 延后必须在最后一列写明 Owner、后果与 defer boundary，并已证明不阻塞 Spec。 -->

### Decision 门

- 结果（Result）：PASSED | BLOCKED
- 目标落点可回答：
- 仓库契合度已有证据：
- 实质选择已决定：
- blocking decision uncertainty 已关闭：
- 开放问题不阻塞 Spec：
- Owner 决策已记录：
- 证据 / 剩余 blocker：
- 评估人 / 日期：

## 8. Backfill 候选

<!-- 这里只记录非约束性的研究提示，不是 durable-delta capture，也不授权修改稳定文档。规范捕获发生在 gate Durable Deltas -> `_pending.md`。 -->

| 可能的目标位置 | 候选洞见 | 可能长期有效的原因 |
| --- | --- | --- |

## 修订历史

<!-- 每次写入新行后仅保留最近 3 条。 -->

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
