# [实施名称] 规格

状态（Status）：Draft | Spec Gate Passed | Spec Gate Blocked
创建时间（Created）：
Decision Revision：D<n>
Spec Revision：S<n>
需求来源（Requirement source）：
主题 slug（Topic slug）：
任务包 ID（Package ID）：
规范任务包路径（Canonical package）：`docs/implementations/<package-id>/`
决策（Decision）：[decision.md](decision.md) | 无独立 decision 文件

## Decision 门记录（Decision Gate Record）

<!-- 仅在 Decision PASSED 后填写。没有 decision.md 时，本节是必经 lightweight Decision 步骤的规范最小证据。Decision BLOCKED 路径使用 decision.md，不生成本 spec。因此，已存在 spec 中的 Decision Gate Result 只能是 PASSED。`Status: Spec Gate Passed` 要求 Spec Gate Result 为 PASSED；`Status: Spec Gate Blocked` 要求 Spec Gate Result 为 BLOCKED。若引用 investigations/<topic>.md，本 spec 仍必须自足表达当前行为合同。 -->

- 结果（Result）：PASSED
- 目标落点与预期结果：
- 权威来源 / 当前状态证据：
- 选定方向与理由：
- Blocking-uncertainty triage / 开放问题处理结果：
- Owner 决策（已解决 / 未解决）：
- 证据位置：decision.md | 本记录
- 评估人 / 日期：

## Spec 设计范围

<!-- 每次创建或更新本 Spec 时首先整体重建本节。这里只保存当前完整合同对象与唯一承载位置，不记录本轮 delta 或历史判断。对象必须写具体名称，不能只写 api=true / persistence=true。没有某类 surface 时写“无”。只冻结会改变可观察行为或正确性的维度，不为不适用项补空合同。 -->

- API operations：
- Persistence models：
- Cross-module seams：
- Public read models：
- 详细合同承载：本文件 §<n> | [contract-design.md](contract-design.md)（写明 earned 原因） | 未 earned

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED | BLOCKED
- 当前设计范围已完整兑现：
- 详细合同 authority 无重复或冲突：
- 八个行为合同章节完整：
- 验收证据已映射：
- 阻塞决策 / 歧义：
- 批准人 / 日期：

## 1. 范围 / 权威来源 / 非目标

- 范围：
- 权威来源与优先级：
- 非目标：
- 需要确认的假设：

## 2. 术语 / 数据合同

- 领域术语：
- 输入、输出、身份与不变量：
- 数据结构、归一化、精度与 ownership 语义：
- 精确合同引用：本节 | [contract-design.md](contract-design.md) 的稳定章节 | 不适用
- 条件化 evidence-integrity 合同（仅当验收结论依赖权威证据、发布/消费状态、兼容投影、外部副作用或随状态变化的公共输出时填写）：主要断言与比较单元；来源权威与私有字段排除；实际范围与声明范围；完整 frozen-format admission；发布不完整后 reader 可相信的权威状态；预期 operational failure 表面与稳定公共 shape。

## 3. 行为 / 状态机 / 工作流

| Actor / 系统 | 条件 / 状态 | 动作 / 事件 | 结果 / 下一状态 |
| --- | --- | --- | --- |

## 4. 模块边界 / 依赖

- Owning 模块及其职责：
- Core 不变量与 Capability 暴露边界：
- 接口与 seam：
- 上游 / 下游依赖：
- 兼容或迁移窗口：

## 5. 错误边界 / 失败恢复

| 失败模式 | 可观察影响 | 隔离方式 | 重试 / 补偿 / 恢复 | Owner |
| --- | --- | --- | --- | --- |

## 6. 约束合同

- 禁止行为：
- Trust 与 permission 边界：
- 精度 / 归一化义务：
- 外部 provider 义务：
- 负向依赖（不得依赖）：

## 7. 验收语义 / 验证证据

| AC ID | 承诺结果 / 约束 | 证据 producer 或 manual owner | 通过证据 |
| --- | --- | --- | --- |

<!-- 当条件化 evidence-integrity 合同适用时，只加入相关的 false-PASS 反例，例如：归一化掩盖比较 drift、副作用后失败、rollback/invalidation 失败、不兼容投影输入或状态 shape 漂移。这些只是示例，不是必选场景。 -->

## 8. 合同一致性

- 跨章节一致性：
- 接口 / seam ownership：
- 验收覆盖：
- 剩余非阻塞假设：

## 修订记录

<!-- 每次写入新行后仅保留最近 3 条。 -->

| 前一修订 | 新修订 | 合同变化 | 原因 / 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
