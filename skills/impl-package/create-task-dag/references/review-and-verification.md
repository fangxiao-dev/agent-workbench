# Review 与验证

worker 返回后或请求 implementation-level review 时读本文件。共享 acceptance、seam 和 Stage 7 规则以 `skills/impl-package/references/impl-package-composition-contract.md` 为准。

## Review 层次

- **任务级 review**：由 `subagent-driven-development` 以非实现者 reviewer subagent 完成 task spec-compliance 后再做 task code-quality review；确认 worker 满足有界任务契约，且 patch 可维护并经过本地测试。
- **Ticket acceptance review**：由 `dev-with-track` 在 ticket（无 tickets 时为 attempt）达到验收候选后固定 comparison point，并自动路由正式 reviewer。

任务级通过不能代替 ticket acceptance review。create-task-dag 不另行定义 whole-slice / contract-drift 检查项，也不代替 `code-review`、module-review 的 Standards/Spec 双轴或 safety-review。

## Main Session 集成与验证

main session 在请求 module-review 前完成：

- 处理已点名的 ownership seam；
- 汇集 worker 的聚焦测试、集成测试和所需浏览器/外部验证证据；
- 对账任务的 `contributes-to` / `enables` 目标与已有 evidence producer；
- 将未完成工作、外部 gate 或人工验证 owner 如实记录。

UI 改动、外部系统 mutation 的具体验证约束继续由 package plan、repo 指令与 task verification gates 决定；本 reference 不把它们重定义成独立 review contract。

## Ticket acceptance review 路由

`dev-with-track` 必须提供：

- 固定 comparison point：明确的 commit、commit range、固定 diff 或等价不可变基线；
- package `spec.md` 与 `plan.md`；
- 所有相关 Approved ticket、`dag.md` 和可用的 progress/handoff；
- 已运行验证和未运行 gate 的证据。

`code-review` 是每个 implementation 的必经 review。当前 attempt 存在 tickets/DAG，或 contract 涉及 interface、状态机、模块边界或 seam 时，必须额外运行 `module-review` 的 Standards 与 Spec 双轴。出现安全或外部副作用信号时，必须运行 `safety-review`。finding、closure verification 和 ticket acceptance 状态按各 skill 与 `dev-with-track` 的契约记录。

## 最终报告形状

implementation 准备交接或关闭时报告：

- worker cohort 和 main session 处理的 seam；
- 已运行验证及其证据，未运行 gate 及原因；
- 固定 comparison point；
- `code-review`、适用的 module-review 双轴与 safety-review 结论；
- 残余风险和被阻塞的 gate。

## 持久化

Impl-Package review/验证必须按 `SKILL.md` 的持久化映射落盘：任务局部 review finding 写入 earned `tasks/Tn-progress.md`，implementation-level review 与实际验证结果 append 到当前 plan Execution Record，gate entry 只引用其 ER anchor 并保存 verdict 摘要。只留在对话或 handoff 的内容不构成可恢复、可判决的 evidence。
