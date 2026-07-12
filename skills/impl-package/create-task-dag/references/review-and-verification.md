# Review 与验证

worker 返回后或请求 implementation-level review 时读本文件。共享 acceptance、seam 和 Stage 7 规则以 `skills/impl-package/references/impl-package-composition-contract.md` 为准。

## Review 层次

- **任务 spec review**：确认 worker 满足其有界任务契约。
- **任务质量 review**：确认 worker 的 patch 可维护且经过本地测试。
- **Implementation-level review**：调用 `module-review` 的 **Spec 轴**，对固定 comparison point 的完整 implementation 做 contract-fidelity review。

任务级通过不能代替 implementation-level review。create-task-dag 不另行定义 whole-slice / contract-drift 检查项，也不代替 module-review 的 Standards 轴或 Spec 轴。

## Main Session 集成与验证

main session 在请求 module-review 前完成：

- 处理已点名的 ownership seam；
- 汇集 worker 的聚焦测试、集成测试和所需浏览器/外部验证证据；
- 对账任务的 `contributes-to` / `enables` 目标与已有 evidence producer；
- 将未完成工作、外部 gate 或人工验证 owner 如实记录。

UI 改动、外部系统 mutation 的具体验证约束继续由 package plan、repo 指令与 task verification gates 决定；本 reference 不把它们重定义成独立 review contract。

## 调用 module-review 的 Spec 轴

调用者必须提供：

- 固定 comparison point：明确的 commit、commit range、固定 diff 或等价不可变基线；
- package `spec.md` 与 `plan.md`；
- 所有相关 Approved ticket、`dag.md` 和可用的 progress/handoff；
- 已运行验证和未运行 gate 的证据。

请求以 `module-review` 的 Spec 轴为 implementation-level review 的唯一来源；其 finding、结论和需要重开的工作按该 skill 的契约记录。若还满足 Standards 轴的触发条件，遵从 module-review 自身的双轴流程，而不是在此复制审查规则。

## 最终报告形状

implementation 准备交接或关闭时报告：

- worker cohort 和 main session 处理的 seam；
- 已运行验证及其证据，未运行 gate 及原因；
- 固定 comparison point；
- `module-review` Spec 轴结论；
- 残余风险和被阻塞的 gate。

## 持久化

Impl-Package review/验证必须按 `SKILL.md` 的持久化映射落盘：任务局部 review finding 写入 earned `tasks/Tn-progress.md`，implementation-level review 与实际验证结果 append 到当前 plan Execution Record，gate entry 只引用其 ER anchor 并保存 verdict 摘要。只留在对话或 handoff 的内容不构成可恢复、可判决的 evidence。
