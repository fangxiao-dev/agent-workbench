---
name: subagent-driven-development
description: Use when approved plan, ticket, or DAG work contains bounded implementation units that can be delegated with immediate independent review; the main agent retains integration and final judgment responsibility.
---

# Subagent-Driven Development

主 agent 负责授权、调度、seam、集成和最终判断；subagent 负责边界清楚的执行单元。委派不能转移最终责任。本 skill 是 task 级的执行与即时 review 载体，不拥有 ticket 验收状态、plan Execution Record、findings 分流或 gate；它们仍由 `dev-with-track` 维护。

## 适用条件

使用前确认：

- 已有批准的 plan、ticket 或 DAG；
- 每个执行单元有稳定输入、scope 和验收条件；
- ownership 不重叠，或已有明确的 seam owner；
- subagent 不需要自行决定产品、架构或外部副作用边界。

紧密耦合、仍在设计或需要共享写入的工作由主 agent 直接处理，或先重新分解。

## 调度

1. 主 agent 先读取完整计划，解析依赖、权限和集成点。
2. 给每个 subagent 提供任务正文、必要上下文、工作目录、允许的读写范围、验证要求和返回格式。派发实现任务时使用 [`references/prompts.md`](references/prompts.md) 中的 implementer 模板，确保授权边界和证据要求不会因临场提示而漂移。
3. subagent 遇到未决 contract、越权动作或无法可靠完成的部分时应停止并返回，不自行扩大范围。
4. 独立单元可以并行；共享 seam 或相同运行资源必须串行或隔离。

## 返回状态

subagent 使用以下状态之一：

- `DONE`：实现和约定验证均已完成；
- `DONE_WITH_CONCERNS`：完成但存在需要主 agent 判断的风险；
- `NEEDS_CONTEXT`：缺少继续所需的信息；
- `BLOCKED`：当前授权或方案下无法完成。

返回内容至少包括变更摘要、验证证据、涉及文件和未决问题。主 agent 不只读取状态标签，还要检查实际产物。

主 agent 按状态推进：

- `DONE`：进入 task-level review 与集成；
- `DONE_WITH_CONCERNS`：先判断 concern 是否影响 correctness、scope 或后续集成，再决定修正或继续；
- `NEEDS_CONTEXT`：补齐缺失上下文后重派；
- `BLOCKED`：先改变前提，例如补上下文、调整任务粒度或能力、修订 plan，不能原样重试。

只有在现有授权内无法消解时才交给 owner。除需要新上下文、不可消解的 blocker 或新的 owner decision 外，继续执行后续可运行单元，不逐项请求继续许可。

## Task-level review 与集成

每个改变代码、契约或行为的 task 都必须由**非实现者的 reviewer subagent**完成 task review；主 agent 只负责给 reviewer 完整上下文、处理结果和集成，不能以自己的复读替代独立 review。明确的纯机械、低风险改动可以跳过，但必须在 ticket evidence 中记录理由。

1. 主 agent 先做基本验收：检查实际产物、验证证据和集成状态。
2. 使用 [`references/prompts.md`](references/prompts.md) 的 **Spec-compliance reviewer** 模板，检查 task 契约、AC contribution、越界和遗漏。
3. Spec-compliance 通过后，使用同一 reference 的 **Code-quality reviewer** 模板，检查该 task 的工程风险、失败路径、测试和 seam；两者必须是独立于实现者的 subagent。
4. reviewer 发现问题后必须修正并复核；不能只记录意见就继续集成。多个高度相关的小单元可以组成一个明确的 integration batch review，但仍必须保留逐 task 的结论与证据。
5. 所有单元完成后，主 agent 检查 diff 冲突、接口衔接和整体验证，并把 task review evidence 交给 `dev-with-track`。

Task review 不替代 ticket acceptance：当一个 ticket 达到验收候选，`dev-with-track` 必须按项目 review 路由运行正式 review——`code-review` 恒必做；存在 tickets、DAG、interface、状态机、模块边界或 seam 变化时 `module-review` 必做；出现安全或外部副作用信号时 `safety-review` 必做。正式 reviewer 的 findings 必须在 ticket acceptance 前闭环。

本 skill 不拥有 worktree、plan revision、runtime ledger、Git 或发布流程；这些由项目规则及对应 owner 管理。
