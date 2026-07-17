---
name: subagent-driven-development
description: 当已批准的 plan、ticket 或 DAG 含有边界明确、可委派且需要即时独立 review 的 implementation unit 时使用；主 agent 保留 integration 与最终判断责任。
---

# Subagent-Driven Development

主 agent 负责授权、调度、seam、集成和最终判断；subagent 负责边界清楚的执行单元。委派不能转移最终责任。本 skill 是 task 级的执行与即时 review 载体，不拥有 ticket 验收状态、plan Execution Record、findings 分流或 gate；它们仍由 `dev-with-track` 维护。

## 适用条件

使用前确认：

- 已有批准的 plan、ticket 或 DAG；
- 每个执行单元有稳定输入、scope 和验收条件；
- ownership 不重叠，或已有明确的 seam owner；
- subagent 不需要自行决定产品、架构或外部副作用边界。

紧密耦合、仍在设计或需要共享写入的工作由主 agent 直接处理，或先重新分解。委派是按收益 earn 的，不是进入 Implementation Package 后的默认步骤：单 owner、机械、局部可逆、上下文切换成本高于独立 review 收益的变化由主 agent 直接完成，并在既有 evidence 中用一句话记录未委派理由，不创建额外 task artifact。

## 调度

1. 主 agent 先读取完整计划，解析依赖、权限和集成点。
2. 给每个 subagent 提供任务正文、必要上下文、工作目录、允许的读写范围、验证要求和返回格式。派发实现任务时使用 [`references/prompts.md`](references/prompts.md) 中的 implementer 模板，确保授权边界和证据要求不会因临场提示而漂移。
3. subagent 遇到未决 contract、越权动作或无法可靠完成的部分时应停止并返回，不自行扩大范围。
4. 独立单元可以并行；共享 seam 或相同运行资源必须串行或隔离。

### 审查基线与风险覆盖

对改变行为、契约或关键数据状态的 task，主 agent 在派发前准备一份简短的 **review basis**，并随实现和审查任务传递。它不是第二份 spec，也不罗列所有输入组合；它只把最容易被局部修复漏掉的判断显式化：

- 验收条件或 contract 中需要保持为真的断言；
- 相关实现位置或权威事实来源；
- 支撑该断言的正常路径证据；
- 仅在存在风险信号时需要检查的反向、边界或“看似成功”的路径；
- 哪个 reviewer 负责确认该行。

风险信号包括公共接口或数据映射、验证与状态迁移、身份/权限/隔离、金额或其他高影响决策、不可逆外部副作用及其失败处理，以及结论依赖外部证据、历史记录或派生元数据的情形。对这些信号，反向检查应验证系统不会因缺失、过期、不匹配、被拒绝、部分失败或跨状态漂移而错误地接受、发布或宣称成功。具体反例由实际 contract 决定，不预设技术形态。

纯机械、低风险 task 可以省略 review basis，但主 agent 要在 evidence 中说明省略理由。没有风险信号时不要为了形式创造反例或额外测试。一个 review basis 可以合并同一实现和同一证据支撑的普通验收条件；风险不同或 failure mode 不同的断言必须分行，避免“测试通过”掩盖另一项断言未被检查。

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
2. 使用 [`references/prompts.md`](references/prompts.md) 的 **Spec-compliance reviewer** 模板，按 review basis 对 task 契约、AC contribution、越界和遗漏做一次完整覆盖；没有 review basis 时按验收条件覆盖，并说明为何无需风险行。
3. Spec-compliance 通过后，使用同一 reference 的 **Code-quality reviewer** 模板，检查该 task 的工程风险、失败路径、测试和 seam；两者必须是独立于实现者的 subagent。
4. reviewer 发现问题后必须修正并做 closure review，不能只记录意见就继续集成。closure review 要复查所有受该修复影响的 review-basis 行，以及最接近的相关边界；不必重跑已证明与改动无关的行。如果 closure review 发现新的、原本不在 review basis 内的实质问题，先把它记录为 coverage gap，补全相关基线后再做一次完整的 spec-compliance 覆盖，不能把多轮零散发现误报为闭环。多个高度相关、共享同一 contract 和 comparison point 的小单元优先组成一个 integration batch review；只保留能定位到 task 的 findings/结论，不复制一套完整 review 正文到每个 task。
5. 所有单元完成后，主 agent 检查 diff 冲突、接口衔接和整体验证，并把 task review evidence 交给 `dev-with-track`。

review basis 是 task-level review 的共同事实来源：实现者提供逐行证据，spec reviewer 判断断言是否被满足，code-quality reviewer 判断该证据在失败、重试、并发、兼容和 seam 情形下是否仍可信。若代码镜像另一个权威 contract，相关风险行要覆盖字段、required、类型/枚举、私有字段排除和兼容格式；若没有该信号，不增加这类检查。

Task review 不替代 ticket acceptance：当一个 ticket 达到验收候选，`dev-with-track` 必须按项目 review 路由运行正式 review——`code-review` 恒必做；当前 diff 或 S/P delta 触及 interface、状态机、模块边界、跨模块行为或 seam 时 `module-review` 必做，tickets/DAG 本身不构成触发；出现安全或外部副作用信号时 `safety-review` 必做。正式 reviewer 的 findings 必须在 ticket acceptance 前闭环。

本 skill 不拥有 worktree、plan revision、runtime ledger、Git 或发布流程；这些由项目规则及对应 owner 管理。
