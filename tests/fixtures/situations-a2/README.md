# Situation 字段合同 A2 复验

本目录是 2026-08-15 的独立复验输入。目标不是重放上一轮 fixture，而是只读判据字段合同、55 行人读表和真实 legacy package 后，重新构造能命中指定行的最小 package。

## 数量与覆盖

共 25 个 fixture，覆盖 55 行中的以下 25 个 distinct row。P0 的 12 行与“上一轮新增 13 行”存在 6 行交集（handoff 四条、checkpoint-refresh、judgment-unfiled），因此优先集合的并集是 19 行；余下 6 个是额外的 basis=cli 行。

| fixture | layer | expected primary | confidence |
| --- | --- | --- | --- |
| p0-terminal-frozen | P0 | attempt.gate.terminal-frozen | high |
| p0-state-invalid | P0 | package.record.state-missing | high |
| p0-projection-drift | P0 | package.record.projection-drift | high |
| p0-anchor-mismatch | P0 | attempt.record.anchor-mismatch | high |
| p0-handoff-recovery-needed | P0 | attempt.record.handoff-recovery-needed | high |
| p0-handoff-target-corrected | P0 | attempt.record.handoff-target-corrected | high |
| p0-session-resumed | P0 | attempt.record.session-resumed | high |
| p0-checkpoint-missing | P0 | attempt.record.checkpoint-missing | medium |
| p0-checkpoint-refresh | P0 | attempt.record.checkpoint-refresh | medium |
| p0-handoff-in-flight | P0 | attempt.record.handoff-in-flight | high |
| p0-evidence-unfiled | P0 | ticket.record.evidence-unfiled | medium |
| p0-judgment-unfiled | P0 | ticket.record.judgment-unfiled | high |
| p2-closure-awaiting | P2 | finding.review.closure-awaiting | medium |
| p2-worker-envelope-invalid | P2 | finding.fix.worker-envelope-invalid | medium |
| p2-reviewer-unavailable | P2 | attempt.review.reviewer-unavailable | high |
| p3-integration-evidence-unavailable | P3 | attempt.verify.integration-evidence-unavailable | high |
| p1-integration-carrier-unavailable | P1 | attempt.readiness.integration-carrier-unavailable | high |
| p3-comparison-head-unfixed | P3 | attempt.review.comparison-head-unfixed | high |
| p1-worker-still-running | P1 | attempt.readiness.worker-still-running | high |
| p4-acceptance-edge-held | P4 | ticket.accept.acceptance-edge-held | high |
| p4-satisfiable | P4 | ticket.accept.satisfiable | high |
| p4-release-edge-unchecked | P4 | ticket.accept.release-edge-unchecked；ticket.accept.satisfiable | medium |
| p3-revision-diverged | P3 | ticket.rework.revision-diverged | medium |
| p3-revalidation-pending | P3 | ticket.rework.revalidation-pending | high |
| p4-durable-delta-missing | P4 | attempt.gate.durable-delta-missing；attempt.accept.all-tickets-terminal | medium |

所有 source 都指向两个指定仓库下的真实 legacy package 目录；fixture 文本没有复制客户名、账号、金额、域名或密钥。

## 合同缺口

1. situation-inputs.md 按 key 说明来源、类型和缺失语义，但没有逐行公开 slug 到 when 比较式的完整映射。尤其是 checkpoint-missing 的 long-task 与 checkpoint presence 组合、evidence-unfiled 的 returned/indexed 组合、以及 release-edge-unchecked 与 satisfiable 的并列条件，需要从处境描述反推。
2. situation-inputs.md §2.2 的 trail.last_worker_mode 说明支持显式值，但 §3.1 的封闭 fact key 集合没有 trail.last_worker_mode。worker-envelope-invalid 只能把 fix mode 放在 worker-return 的 worker_mode 字段，同时把 envelope validity 放在合法的 trail.envelope_valid fact；这不是一个单一、封闭的 fact 构造路径。
3. 合同声明完整 3.5 runtime 还会检查 plan.md、spec.md、Publication Status、artifact、Git revision 和 projections，但没有明确 A2 fixture 的“合法”是 renderer 合法还是完整 runtime 合法。这里按 situation renderer 的输入边界构造；只在 evidence 被引用的 fixture 中补了最小 artifact。
4. attemptHistory[*].gate 的合法 object 形状没有像 gate.md 的 Verdict 行那样单独定义。fixture 沿用最小示例的 gate:null；要构造“历史中已有 Gate 且 current state 对齐”的完整 package，读合同的人仍需猜字段。
5. finding fact、finding block marker 和 result-like worker-return 都能表达 closure/envelope 事实，但合同没有给出这些通道在一个 finding 同时存在时的最小推荐组合。closure-awaiting 使用 fact 加 block marker；这是按“显式事实优先”的方向构造，而不是由逐行合同直接得到。

## medium / low

medium：

- p0-checkpoint-missing：row 的 AND 组合未逐字公开。
- p0-checkpoint-refresh：是否还需要 action-count/checkpoint marker 条件未逐字公开。
- p0-evidence-unfiled：direct evidence tuple、artifact 存在和 evidenceIndex 缺行的组合依赖推断。
- p2-closure-awaiting：fact 与 finding prose 两个入口同时存在。
- p2-worker-envelope-invalid：last_worker_mode 没有 canonical fact key，只能用 event 字段。
- p3-revision-diverged：需要依赖当前 Git HEAD 与 trail.head 的真实比较。
- p4-release-edge-unchecked：与 satisfiable 同层并列的精确条件没有逐行公开。
- p4-durable-delta-missing：与 all-tickets-terminal 同层并列，且 terminal gate pending 依赖 Gate 缺失/非 terminal 的组合。

没有标为 low 的 fixture；low 将意味着连目标 key 的来源或取值类型都无法由允许材料确定，本轮没有把这种猜测伪装成输入。

## 独立性与验证边界

- 允许材料：situation-inputs.md、references 下直接相关契约、55 行人读表、README、trail-schema，以及两个指定仓库的 legacy package。
- 未读取 situation.py、situations.yaml、既有 situations/situations-independent fixture 内容、tests/test_situation_render.py、reverify-report.md 或 replay 报告。
- 未以任何方式运行 situation.py。验证只做了本目录的 JSON、JSONL、Ticket 字段、state 顶层键和 canonical fact key 闭集合检查。
- p0-state-invalid 是目标行定义要求的故意 invalid state；其余 state 均按 3.5 输入合同的最小外形书写。
