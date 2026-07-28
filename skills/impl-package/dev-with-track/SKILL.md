---
name: dev-with-track
description: >
  当已批准 implementation attempt 需要恢复执行、选择下一 actionable unit、记录 verification
  evidence、处理返工失效、分流 execution findings 或评估 append-only gate ledger 时使用；不拥有
  decision/spec/plan/ticket/DAG 定义。
---

# Dev With Track

执行 approved implementation package 的 current attempt。共享 lifecycle、Composition、readiness 和 gate 语义只引用 `../references/impl-package-composition-contract.md`；结构化字段与 CLI 只引用 `../references/impl-package-state-schema.md`。

## Ownership

- `req-align` owns current Decision/Spec and D/S gate；`impl-planning` owns plan, P revision, Composition, planned verification and Execution Record；`to-tickets` / `create-task-dag` own published ticket/DAG contracts.
- 本 skill 维护 earned runtime state、artifact hash chain、ER、execution findings 和 gate ledger；不重写长期 contract、不能从历史 Composition 推断 current attempt，也不修改旧 gate entry。
- 主 session owns 调度、授权记录、decision、cross-task seaming、shared verification、Ticket acceptance 和最终集成；它不自行代替 task worker 或 leaf reviewer。worker 可做调研、实现、局部验证和记录，但不替代跨层判断或选择方案。

## 主 session 控制循环

仅当存在跨模块业务链、`material seam`、昂贵验证或已发生系统性 failure 时，对 E2E、integration 或共享 seam 的失败按此顺序；低风险局部改动保留轻量路径：

1. **Investigate**：确认失败点、真实输入、持久化状态、权威来源和已通过边界；不能只根据错误码或单个 worker 结论修改。
2. **Decide & seam**：主 session 对照 Decision、Spec 和 plan 判断共享能力漏接、adapter/mapper 断层、runner/fixture 问题或 owner decision。现有 contract 能唯一裁决时按 implementation defect 修复；存在多个合理业务结果才路由 owner。优先复用正式 shared contract；不得用 fixture 或 domain 特判绕过通用规则。
3. **Implement**：修复已证实 seam 的实现任务才派发。为收集 checkpoint、补足可观测性或进行受控探索而做的调研/验证可在 seam 尚未确认时派发，但必须说明候选假设、非变更边界与决定性观察；worker 不重新选择方案。实现 prompt 必须给出调用链、可复用 contract、禁改范围、成功条件、关键反例和局部验证。
4. **Evaluate**：按渐进式系统证据先选择忠实边界。已知确定性内部前置缺证据时默认先补便宜证据；真实环境独有、探索诊断或边界未知时可带明确目的运行 runtime/E2E。重复昂贵运行必须有新假设、环境/修复 delta 或决定性观察目标。失败回到 Investigate；不连续补丁、猜测后续问题或无证据重跑。

每次实现动作只修复已证实、当前可归责的首个违约边界；failure 分类可随新 evidence 修订并可多因。共享复用不等于把当前 domain 常量、fixture 或 oracle 写成通用业务规则。只有存在多个会改变业务结果的合理方案时才请求 owner 决定。

## Restore and dispatch

1. 先按 delta-first restore 读取 current package、sidecar、最新 gate、可靠 ER/comparison point 与后续 diff；运行 committed binding validation。
2. 确认唯一 Active attempt、approved Composition、ticket/DAG bindings 和第一个 actionable unit。高风险 unit 必须已有 spec/AC、可执行入口、oracle 和 ER owner；缺口按 authority 回流。
3. evidence 胜过 stale state；P revision 变化只重验受影响 subset。状态只能通过 `impl_package_state.py set-state --expect --evidence` 变更。
4. 默认等待上游 Ticket `SATISFIED` 或 Task `DONE`；若主 session 判断上游已形成可复用实现检查点，可按 runtime protocol 提前派发仅依赖该检查点的下游 Ticket/Task implementation。该例外只影响 implementation readiness，不释放 acceptance 或 release dependency。
5. 派发 worker 时给出 primary ownership、禁改范围、已知依赖、贡献 Ticket、局部验证和 `BLOCKED` 返回格式。Task `DONE` 不等于 Ticket acceptance。

需要详细 restore/readiness、渐进式系统证据、runtime state、ER、review、finding 分流、claim audit、gate 或 Stage 7 时，读取 [`references/runtime-protocol.md`](references/runtime-protocol.md) 的相应章节；跨阶段判断同时引用 [`../references/progressive-system-evidence.md`](../references/progressive-system-evidence.md)，不在本入口复制方法论正文。

## Review and gate entry

基于实际 diff、contract impact 和已有定向证据选择 review：局部可逆且无共享 contract/状态/外部副作用的改动可简化；普通实现的正式 review 默认 `code-review`；interface/state/seam 倾向 standards/spec review；data integrity、evidence authority、auth、external mutation 或 concurrency 必须 safety review。需要正式 review 时，主 session 将明确的 reviewer selection 交给 `do-review`；它是范围固定、leaf 调度、ledger 与 finding 分类的唯一编排器。P1/P2 必须修复并 closure verify。

GO 后自动完成适用验证、ER、review、finding 分流、claim audit 和 gate verdict；不得将 gate 或验证变成二次 owner approval。Push、merge、生产/共享可变操作和会改变业务结果的方案仍须明确授权。

## Output

向 owner 使用 `talk-to-boss`：首段说明范围、实施/验证/gate 状态、剩余 blocker 数量、是否 closed 与所需 decision。随后给 canonical handoff：package/attempt、D/S/P、binding/lifecycle、Composition、evidence、manual readiness（如适用）、findings、最新 gate/Supersedes、Stage 7 和 claim audit。不要要求 owner 打开 JSON。
