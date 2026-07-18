# Review 与验证

Task 局部验证用于让 Working Branch owner 判断其产出是否可集成；它不是 Task-level formal acceptance，也不能替代 Ticket review。共享 acceptance、状态和最终 package gate 以 `skills/impl-package/references/impl-package-composition-contract.md` 与 `dev-with-track` 为准。

## 集成与 Ticket 验收

Working Branch owner 在并行 Task 返回、发现 BLOCKED、以及 Ticket 最终验收前执行 integration step：合并 Task 产出，处理已出现的 seam/冲突，运行共享验证和正式 review，将实际 evidence 映射回 Ticket AC，并决定 Ticket 是否可验收。

进入某 Ticket 的最终验收前，只扫描 contributes-to 该 Ticket 的 BLOCKED Task：

- blocker 会影响该 Ticket 的 AC、声明行为或风险边界时，Ticket 不可通过，必须先完成 seaming 或解除阻塞；
- blocker 不贡献且不影响该 Ticket 时，不阻塞该 Ticket；
- 真实影响扩大时，先更新 Task 的 contribution mapping，再重新判断，不能静默绕过。

`DONE` 不是 acceptance verdict。Ticket 的 AC、evidence、正式 review 和 acceptance status 是唯一权威；no-ticket DAG 仍由 Spec AC/plan gate 判定，不借 Task 状态伪造 Ticket。

## 质量要求与最终收口

普通 Task 不自动触发独立正式 review。tenant isolation、auth/permission、migration、真实外部写入、金额、不可逆数据等高风险工作，可按实际 diff 提前要求更严格的验证/review；优先不拆，或拆为可独立验收的 Ticket，而不是创建严格 Task 流程。

最终 package review 前，Working Branch owner 全局扫描所有 Task：每个 Task 必须 DONE，或有明确、已批准且带理由的 WAIVED/SUPERSEDED；不得遗留 BLOCKED。之后按既有 `dev-with-track` 路由运行正式 Ticket/Spec review，并确认所有 Ticket AC 都有实际 evidence、active Spec 全覆盖。最终 review 以 Ticket/Spec 为中心，不以 Task 状态或数量为中心。

验证和 review evidence 进入既有 Execution Record/gate；Task progress 只在其条件满足时补充局部 blocker、evidence 和下一动作。不要建立默认 Ticket progress，或让 Task review 产物成为 Ticket acceptance status。
