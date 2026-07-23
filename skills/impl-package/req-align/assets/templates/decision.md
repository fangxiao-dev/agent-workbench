# [实施名称] 需求与决策

状态（Status）：Draft | Decision Gate Passed | Decision Gate Blocked
创建时间（Created）：
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D<n>
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：
主题 slug（Topic slug）：
任务包 ID（Package ID）：
规范任务包路径（Canonical package）：`docs/implementations/<package-id>/`

本文是任务包活动期间“聚焦需求定义 + 当前方案决策与理由”的事实源：回答为什么做、要达到什么结果、为什么选择该方向。系统必须如何表现、字段与状态合同、错误处理和 Acceptance Semantics 只属于 `spec.md`；如何拆解、实现和验证只属于 `plan.md`。当前正文只保留最新需求与选择，被取代内容写入修订历史，完整旧正文由 Git 保存。Decision 被阻塞时使用本文件，不创建 `spec.md`。`Status: Decision Gate Passed` 必须对应 `Result: PASSED`；`Status: Decision Gate Blocked` 必须对应 `Result: BLOCKED`。若引用 `investigations/<topic>.md`，本文件仍必须自足说明当前需求与决定；investigation 默认无 authority，且不维护 backlink 或采用状态。

## 1. 需求定义（Focused PRD）

<!-- 聚焦表达本次变化的产品需求，不复制 spec 的字段级合同、状态机、错误处理或逐条 Acceptance Criteria。 -->

- 目标用户 / 使用场景：
- 当前问题与触发条件：
- 期望结果与用户价值：
- 范围：
- 非目标：
- 核心体验或业务流程：
- 成功判断信号：

## 2. 目标落点与合同交接

- 受影响的系统边界：
- 交给 `spec.md` 定义的行为合同范围：
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

<!-- 当前和历史 D 修订的内容绑定保存在内部 `.impl-package/revision-bindings.json` sidecar 中；不要在本文写入自身 hash，也不得要求 owner 阅读 sidecar。 -->

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
