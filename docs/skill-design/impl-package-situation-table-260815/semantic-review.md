# dev-with-track 处境表逐行语义审查

审查日期：2026-08-15。

结论先行：55 行中，42 行忠实、6 行过宽、2 行过窄、4 行名不副实、1 行死行。当前不能接线。最先要处理的是 `ticket.investigate.no-carrier` 的语义边界、`ticket.accept`/`ticket.verify` 的 CLI 一致性、`attempt.disposition.findings-triage-pending` 的 near-terminal 过宽，以及永远不能成为可见 primary 的 `attempt.gate.comparison-mismatch`。本文件只记录审查，不修改表、实现、fixture 或复验报告。

## 审查口径

“实际判据”按 `situation-inputs.md` 第 9 节的完整 `slug → when` 组合，并用 `situation.py` 中对应 parser 的实际推导复核。非 manual 行的条件全部是 AND；任一 key 为 unknown 时不是命中，而是 `undetermined`。优先级按 YAML 的 P0 严格顺序及 P1–P5 层级结算。

“名不副实”用于名称或处境标签已经暗示了另一件事，但当前组合本身可能是一个合理的不同判据；它不等同于单纯的文字风格问题。`manual` 行不作为机械 primary 评估：它们会进入 `manual` 列，故不把这种有意的类别设计计作意外死行。

## 逐行结果

| # | slug | 人读描述（逐字） | 实际判据（完整组合） | 判定 | 依据 | 修法建议 |
| ---: | --- | --- | --- | --- | --- | --- |
| A1 | `package.record.state-missing` | state 缺失或 `package validate` 失败 | `package.state_invalid = true` | 名不副实 | `state_invalid` 不只表示缺文件，还包括 schema、Ticket、evidence、checkpoint 交叉校验失败。按描述中“validate 失败”的宽表述它并不算误命中，但 `state-missing` 这个名称把整类 invalid 错叫成 missing。 | 改描述 |
| A2 | `package.record.projection-drift` | `package validate` 报告 projection drift | `package.validate.projection_drift = true` | 忠实 | 判据就是结构化 validation result 或同名 fact 报告的 projection drift；不会把普通 state invalid 当成 drift。 | 无需改动 |
| A3 | `attempt.record.session-resumed` | 跨 session 刚接手，本 session 尚无动作 | `attempt.session_resumed = true` AND `attempt.active_checkpoint_present = true` AND `trail.actions_since_checkpoint = 0` | 过窄 | active checkpoint 存在但 trail 没有可定位 marker 时，真实的“刚接手且尚无动作”只能得到 unknown；marker 是证据形状，不是该处境本身。显式 session fact 也不能接住这类情况。 | 改描述 |
| A4 | `attempt.gate.terminal-frozen` | terminal Gate 已写，仍有推进请求 | `gate.terminal = true` | 忠实 | 在 renderer 被调用即表示主控正在处理当前 Attempt 的前提下，terminal Gate 正是 CLI 的 fail-closed admission 条件；`pass/fail/defer` 都会进入该行。 | 无需改动 |
| N05 | `attempt.record.handoff-in-flight` | handoff/relay 正在发送或等待 continuation | `trail.handoff_in_flight = true` | 忠实 | typed handoff-in-flight fact 与描述是同一状态；自由文本不会伪造命中。 | 无需改动 |
| N06 | `attempt.record.anchor-mismatch` | anchor 存在但表示不一致导致校验失败 | `trail.anchor_mismatch = true` | 忠实 | 判据直接读取 attempt scope 的 anchor mismatch fact，表达的就是校验失败而非一般 handoff。 | 无需改动 |
| N07 | `attempt.record.handoff-recovery-needed` | handoff bootstrap、重命名或创建失败 | `trail.handoff_recovery_needed = true` | 忠实 | recovery-needed fact 只在该恢复语义被声明时成立，和描述一致。 | 无需改动 |
| N08 | `attempt.record.handoff-target-corrected` | handoff target/order 已被纠正 | `trail.handoff_target_corrected = true` | 忠实 | 判据只接受 corrected target/order 的 typed fact，不把普通文字当作纠正事件。 | 无需改动 |
| N09 | `attempt.record.checkpoint-refresh` | active checkpoint 已有但下一动作发生变化 | `attempt.active_checkpoint_present = true` AND `trail.checkpoint_refresh_needed = true` | 忠实 | 既要求 checkpoint 真实存在，又要求 refresh fact；没有 checkpoint 不会把一般下一动作变化误报为刷新。 | 无需改动 |
| N10 | `ticket.record.judgment-unfiled` | judgment/conclusion 已形成但未进入记录 | `trail.judgment_unfiled = true` | 忠实 | 当前 Ticket subject 的 unfiled fact 正是“判断已形成但未落账”的唯一机械入口。 | 无需改动 |
| B1 | `attempt.readiness.multiple-ready-tickets` | 有多个 readyTicket，无 in-flight 工作 | `attempt.ready_ticket_count > 1` AND `attempt.in_flight = false` | 忠实 | ready count 来自完整 dependency 图，且显式排除了 open dispatch；多个 PENDING 不会被误当成多个 ready。 | 无需改动 |
| B2 | `attempt.readiness.all-edges-held` | 无 readyTicket，但有 PENDING | `attempt.ready_ticket_count = 0` AND `attempt.has_pending_ticket = true` AND `attempt.implementation_edges_held = true` | 忠实 | 三个条件共同表达“仍有 PENDING，但所有 implementation 入边都挡住”；依赖无法解析时不会伪造全挡住。 | 无需改动 |
| B3 | `attempt.accept.all-tickets-terminal` | 全部 Ticket 为 SATISFIED 或 RETIRED | `attempt.all_tickets_terminal = true` | 忠实 | 非空 Ticket 集合中的每一项都必须是 SATISFIED/RETIRED，空集合不会命中。 | 无需改动 |
| B4 | `ticket.readiness.blocker-maybe-resolved` | 有 BLOCKED，且其 blocker 可能已解 | `ticket.state = BLOCKED` AND `ticket.blocker_maybe_resolved = true` | 忠实 | BLOCKED 不会自行推导为已解除，只有当前 Ticket 的显式业务判断才命中。 | 无需改动 |
| Owner | `attempt.readiness.worker-still-running` | 已派出的 worker 尚未返回，主控准备另起动作或打断 | `trail.decision_without_result = true` | 忠实 | 未配对 decision 或未返回的 RUNNING dispatch 都表达“仍在运行”；调用 renderer 的主控意图是上下文，不需另造机械 key。 | 无需改动 |
| N20 | `attempt.readiness.integration-carrier-unavailable` | integration carrier 不可用 | `attempt.integration_carrier_available = false` | 忠实 | 明确的 false fact 才命中；缺失 fact 是 unknown，不会把“没找到”偷换成不可用。 | 无需改动 |
| C1 | `ticket.investigate.no-carrier` | PENDING，无 investigate 载体也无 evidence | `ticket.state = PENDING` AND `trail.has_investigate = false` AND `evidence.count = 0` | 过宽 | `has_investigate=false` 只是没有可识别调查信号，`evidence.count=0` 只是没有 indexed evidence；可用但尚未记录的调查载体、未索引的直接证据都可能落入该组合。它至少会成为背景 match；在没有更高层抢占时会把本来要处理 P3 的输入抬成 P2 primary，正是 B2 两次抢占的根因。 | 改判据 |
| C2 | `ticket.investigate.evidence-gap` | investigate 返回 `EVIDENCE_GAP` | `trail.last_outcome = EVIDENCE_GAP` | 忠实 | 在 mode contract 中 `EVIDENCE_GAP` 是 investigate 的专用返回；当前 Ticket 最后 result-like outcome 足以表达调查缺口。 | 无需改动 |
| C3 | `ticket.route.multiple-business-outcomes` | 存在多个合理业务结果 | `manual`，无机械条件；只有主控显式作出该语义判断才进入 manual 列表 | 忠实 | 这是不能由列出的机械输入裁决的业务选择，manual 是正确的判据形态。 | 无需改动 |
| C4 | `ticket.route.sources-uniquely-decide` | 来源唯一裁决 | `evidence.sources_uniquely_decide = true` | 忠实 | 唯一裁决是业务/证据判断，显式 fact 与描述一致；不会从 evidence 数量自动推导。 | 无需改动 |
| C5 | `ticket.route.sources-conflicting` | 来源缺失、含糊或冲突 | `manual`，无机械条件；主控判断后才进入 manual 列表 | 忠实 | 来源是否足以裁决是语义判断，manual 行没有假装存在一个机械冲突检测器。 | 无需改动 |
| C6 | `ticket.review.awaiting-reviewer` | implement DONE 且 `review=required` | `trail.last_outcome = DONE` AND `ticket.review_required = true` | 忠实 | `DONE` 在 implement contract 中是局部实现完成，和 review requirement 合取后正好表达等待 reviewer；缺 trail 时不会仅凭 prose 伪命中。 | 无需改动 |
| C7 | `ticket.review.required-trigger` | 命中 shared seam、安全、数据完整性、并发、migration 或不可逆外部副作用 | `ticket.review_trigger = true` | 忠实 | trigger 是上游风险判断的显式结果；它不应由 renderer 从普通 outcome 或 review state 猜测，缺失时保持 unknown。 | 无需改动 |
| C8 | `ticket.record.evidence-unfiled` | worker 已返回直接证据，但 `evidenceIndex` 无行 | `trail.direct_evidence_returned = true` AND `evidence.indexed = false` | 过宽 | 实现检查的是每个 direct-evidence artifact/claim/revision/environment tuple 是否有未失效索引，不是 evidenceIndex 是否完全没有行；已有其它行或已有但已失效的对应行仍会命中。 | 改描述 |
| C9 | `ticket.verify.safety-invariant-unfalsified` | 安全不变量 claim 从未取证 | `ticket.safety_invariant_unfalsified = true`，即至少一个 `INV-` claim 没有 active evidence record | 名不副实 | 判据表达的是“未验证/缺 active evidence”，与人读描述相符；但 `unfalsified` 通常表示没有被证伪，不能表示没有任何取证。 | 改描述 |
| C10 | `ticket.implement.worker-incomplete-first` | worker 第一次返回 `INCOMPLETE` | `trail.last_outcome = INCOMPLETE` AND `trail.incomplete_count = 1` AND `trail.last_worker_mode = implement` | 忠实 | last outcome、末尾连续计数和 implement mode 三项共同排除了历史上曾经 incomplete 或其它 mode 的情况。 | 无需改动 |
| C11 | `ticket.implement.worker-incomplete-second` | worker 第二次返回 `INCOMPLETE` | `trail.last_outcome = INCOMPLETE` AND `trail.incomplete_count = 2` AND `trail.last_worker_mode = implement` | 忠实 | 只计算末尾连续两个 result-like incomplete，不会把两次历史返回误判成第二次 fallback。 | 无需改动 |
| C12 | `ticket.implement.worker-blocked` | worker 返回业务 `BLOCKED` | `trail.last_outcome = BLOCKED` AND `trail.last_worker_mode = implement` | 忠实 | 精确要求 implement mode 的最后业务结果是大写 `BLOCKED`，与“不 fallback”的动作边界一致。 | 无需改动 |
| C13 | `ticket.accept.acceptance-edge-held` | 有 evidence 但 acceptance 边未释放 | `evidence.count > 0` AND `ticket.acceptance_edge_released = false` | 忠实 | 人读描述只说有 evidence，不承诺 supporting；当前实现也明确把已 invalidated evidence 计数，条件没有额外偷换。 | 无需改动 |
| C14 | `ticket.verify.contradictory-unresolved` | required claim 带矛盾或不确定证据 | `evidence.contradictory_unresolved = true`，当前 Ticket 任意 evidence record 有未失效 `contradictory`/`inconclusive` | 过宽 | 实际不要求 required claim、当前 acceptance revision、当前 environment，旧 revision 或其它 claim 的冲突也会命中；而 CLI 的 SATISFIED 校验只阻断当前 acceptance pair。 | 改判据 |
| C15 | `ticket.accept.satisfiable` | 全 claim 有支撑、入边已释放、revision 可解析 | `evidence.all_required_claims_supported = true` AND `ticket.acceptance_edge_released = true` AND `ticket.acceptance_revision_parseable = true` | 名不副实 | 该组合可以在同一 pair 仍有 active contradictory/inconclusive evidence 时成立；renderer 会说 satisfiable，但 `ticket satisfy` CLI 会拒绝。名称和动作承诺比当前 predicate 更强。 | 改判据 |
| D1 | `ticket.rework.evidence-conflict` | 已 SATISFIED，新证据触及其 claim | `ticket.state = SATISFIED` AND `evidence.new_claim_conflict = true`；后者实际等于任意未失效 contradictory/inconclusive evidence | 过宽 | 没有比较 evidence 是否在 SATISFIED 之后产生；一个旧的未处置冲突也会触发，判据不能证明“新证据”。 | 改判据 |
| D2 | `ticket.rework.revision-diverged` | acceptance revision 与当前 HEAD 已分叉 | `git.acceptance_revision_diverged = true` AND `git.head_advanced_since_last_trail = true` | 过窄 | 描述所指的 revision/HEAD 分叉只需第一项；当前还要求 trail 记录了旧 head 且该 head 已推进，没有该记录的真实分叉会被漏掉。 | 改描述 |
| D3 | `ticket.rework.revalidation-pending` | Ticket 处于 NEEDS-REVALIDATION | `ticket.state = NEEDS-REVALIDATION` | 忠实 | state 枚举和人读描述完全相同；是否执行 verify 是后续动作，不影响该行识别当前状态。 | 无需改动 |
| D4 | `attempt.rework.contract-changed` | plan 或 contract 实际变化 | `git.contract_changed_since_last_trail = true`，即旧 trail head 到当前 HEAD 的 diff 命中约定 contract 路径 | 忠实 | 判据确实检查 plan/spec/contract-design/decision/tickets 的实际 Git 变化，而不是 prose 中写了 changed。 | 无需改动 |
| D5 | `ticket.disposition.retire-undecided` | 不再需要完成 | `ticket.no_longer_needed = true` | 忠实 | “不再需要”本身是 owner 业务判断；CLI 负责约束后续 waived/superseded 形状，不能替代这个判断。 | 无需改动 |
| E1 | `finding.fix.reviewer-returned` | reviewer 返回 finding | `trail.last_outcome = FINDING` AND `trail.finding_source = reviewer` | 忠实 | reviewer source 与 FINDING outcome 的合取表达了 review 返回 actionable finding，而不是主控自行发现。 | 无需改动 |
| E2 | `finding.review.source-recheck-pending` | accepted Track C 或 Spec fidelity finding | `finding.review_track = C` AND `finding.source_recheck_pending = true` | 忠实 | pending marker 是 parent 接受后的一次性 source recheck 载体；Track C 只是轨道，不能单独触发，当前组合没有把普通 finding 混入。 | 无需改动 |
| E3 | `finding.fix.main-session-discovered` | 主控自己发现 finding | `trail.finding_source = main-session` | 忠实 | source fact 直接区分主控发现与 reviewer 返回，动作差异有明确依据。 | 无需改动 |
| N13 | `finding.review.closure-awaiting` | fix 已完成但等待同 scope finding-closure reviewer | `finding.closure_review_pending = true` | 忠实 | closure-pending marker 是当前 finding 进入 closure review 阶段的事实；closed/resolved finding 会排除。 | 无需改动 |
| N15 | `finding.fix.worker-envelope-invalid` | finding fixer 的 envelope 不完整或不可采信 | `trail.last_worker_mode = fix` AND `trail.envelope_valid = false` | 忠实 | envelope validity 只从结构化 fact/result 字段读取，并且绑定最后一次 fix mode；不会把缺少 envelope 当作 false。 | 无需改动 |
| E4 | `finding.disposition.grading-undecided` | finding 待定级 | `finding.grading_pending = true` | 忠实 | open finding 没有可识别 grade 或显式 pending 就是待定级；closed finding 不会命中。 | 无需改动 |
| E5 | `attempt.disposition.findings-triage-pending` | `execution-findings.md` 未分流且接近 terminal Gate | `findings.triage_pending = true` AND `attempt.near_terminal_gate = true`，后者为“所有 Ticket terminal OR `gate.md` 文件存在” | 过宽 | 一个很早创建的或 malformed 的 `gate.md` 就满足 near-terminal；文件存在不等于接近可解析的 terminal Gate，会把 findings triage 提前投递。 | 改判据 |
| F1 | `attempt.verify.manual-result-missing` | Planned Verification 有 manual owner 且无结果 | `attempt.manual_verification_owner = true` AND `attempt.manual_verification_result_present = false` | 忠实 | 两个显式 boolean 正好表达 owner 存在与结果缺失；缺失声明保持 unknown，不把未登记误报为无结果。 | 无需改动 |
| F2 | `attempt.accept.completion-claim-unaudited` | 准备声明完成 | `attempt.completion_claim_pending = true` | 忠实 | completion claim pending 是“准备声明完成”的明确入口，不能从普通 Gate 或 Ticket 状态推导。 | 无需改动 |
| F3 | `attempt.review.terminal-coverage-incomplete` | terminal-final coverage 不完整 | `attempt.terminal_coverage_complete = false` | 忠实 | 缺 coverage fact 是 unknown，不是 incomplete；只有显式 false 才表达描述中的“不完整”。 | 无需改动 |
| N18 | `attempt.review.reviewer-unavailable` | reviewer timeout、无效 envelope 或旧 ReviewRun 不可采信 | `trail.reviewer_unavailable = true` | 忠实 | unavailable fact 是该类 review 载体失效的统一语义，普通 timeout 文本不会误触发。 | 无需改动 |
| N19 | `attempt.verify.integration-evidence-unavailable` | 所需 integration evidence 载体不可取得 | `attempt.integration_evidence_available = false` | 忠实 | 只在 attempt scope 明确声明 evidence carrier 不可用时命中，和“carrier unavailable”不是同一层的 P1 行。 | 无需改动 |
| N21 | `attempt.review.comparison-head-unfixed` | review 没有可信 immutable comparison head | `git.comparison_head_fixed = false` | 忠实 | explicit false 直接表达尚未固定；缺 fact 是 unknown，不会把未记录当成未固定。 | 无需改动 |
| F4 | `ticket.accept.release-edge-unchecked` | 其余条件满足，release 边未复核 | `ticket.acceptance_conditions_satisfied = true` AND `ticket.release_edge_rechecked = false` | 过宽 | 判据没有要求当前 Ticket 存在 release edge；无 release edge 时该 fact 仍因 fail-closed 缺省为 false，仍会命中。CLI 也只检查 release edge 是否已释放，不检查这个 rechecked fact。 | 改判据 |
| F5 | `attempt.gate.durable-delta-missing` | terminal Gate 前 Stage 7 未完成 | `gate.stage7_complete = false` AND `attempt.terminal_gate_pending = true` | 忠实 | 只在所有 Ticket terminal 且 Gate 仍非 terminal 时检查 Durable Deltas；缺 Gate 本身因 stage7 unknown 不会伪造该行。 | 无需改动 |
| F6 | `attempt.gate.verdict-undecided` | 判 Gate | `gate.verdict = undecided`；缺 `gate.md` 也被合成该值，显式 `undecided` 亦命中 | 名不副实 | “没有 Gate”与“已有 Gate 且 verdict=undecided”不是同一处境，当前 parser 为了 fail-closed 把两者合并，导致 row 名称和 Gate 状态不精确。 | 拆行 |
| F7 | `attempt.gate.comparison-mismatch` | 判了 pass | `gate.verdict = pass` AND `git.comparison_revision_matches_acceptance = false` | 死行 | `pass` 必然使 `gate.terminal=true`，P0 `attempt.gate.terminal-frozen` 永远先成为 visible primary；本行最多进入 suppressed/matches，不能成为可见 primary。 | 删行 |
| G1 | `attempt.record.checkpoint-missing` | 需要跨 session 交接或长任务收口 | `attempt.handoff_or_long_task = true` AND `attempt.active_checkpoint_present = false` | 忠实 | 只有显式 handoff/long-task fact 且当前没有 active attempt checkpoint 才命中，符合“先写 checkpoint”的动作。 | 无需改动 |
| G2 | `package.record.intake-backlog` | 待落账队列积压 | `intake.has_backlog = true`，按固定 first-existing-wins 候选读取 | 忠实 | 该行表达的是被合同选中的 intake carrier 有 backlog；first-existing-wins 是输入解析规则，不会把后序非权威候选偷算进来。 | 无需改动 |

## 判定分布与死行

| 判定 | 数量 |
| --- | ---: |
| 忠实 | 42 |
| 过宽 | 6 |
| 过窄 | 2 |
| 名不副实 | 4 |
| 死行 | 1 |
| 合计 | 55 |

唯一的意外死行是：

- `attempt.gate.comparison-mismatch`：`pass` Gate 与 P0 `terminal-frozen` 的逻辑蕴含使它不可能成为可见 primary。

`ticket.route.multiple-business-outcomes` 与 `ticket.route.sources-conflicting` 不计入死行：它们是显式 `manual` 行，按设计进入 `manual` 列而不是机械 candidate。若把 renderer 的 `primary` 字段机械地当成唯一可见位置，则两个 manual 行也不会进入该字段，但那是类别契约，不是优先级或前置条件造成的意外失效。

## 覆盖偏斜

这里是基于条件宽度和生命周期位置的定性估计，不把 25 个 fixture 当作生产频率样本。

频繁或偏频繁的行：

- `ticket.investigate.no-carrier`：每个 PENDING Ticket 只要没有可识别 investigate signal 且 index 为空就命中；它是按 Ticket 复制的宽 P2 行，最容易成为全表的背景命中和抢占源。
- `attempt.gate.verdict-undecided`：缺 Gate 被合成 `undecided`，因此几乎所有 pre-Gate 的可读 Attempt 都有该 match；当前还与多个 P4 行并列。
- `attempt.readiness.multiple-ready-tickets`：多 Ticket 计划的入口阶段常有两个以上 ready Ticket，且没有 open dispatch 时直接命中。
- `attempt.accept.all-tickets-terminal`：所有 Ticket 收口后必命中，是每个正常完成 Attempt 的固定尾部行。
- `ticket.accept.satisfiable` 与 `ticket.accept.release-edge-unchecked`：在 evidence 已齐的收口窗口经常同时出现；后者的 `false` 缺省和“无 release edge 也可命中”使它偏宽。
- `finding.disposition.grading-undecided`：新建且未写 grade 的 open finding 默认就是 grading pending；如果 findings 较多，它会比显式异常类 row 更常见。

近乎不可能或低频的行：

- `attempt.gate.comparison-mismatch` 的可见 primary 频率是 0；它只能在一个已经被 P0 冻结的 pass 输入中作为 suppressed 事实出现。
- 两个 manual route 行不会自动命中，只有主控明确作出对应判断才出现。
- `package.record.projection-drift`、`attempt.record.anchor-mismatch`、`handoff-recovery-needed`、`handoff-target-corrected`、`handoff-in-flight`、`checkpoint-refresh`、`judgment-unfiled` 都依赖少见的 typed operational fact；正常 CLI 维护下属于异常/交接窗口。
- `attempt.verify.integration-evidence-unavailable`、`attempt.readiness.integration-carrier-unavailable`、`attempt.verify.manual-result-missing`、`attempt.review.comparison-head-unfixed`、`attempt.gate.durable-delta-missing`、`attempt.review.terminal-coverage-incomplete` 依赖特定任务类型或 Gate 收口窗口，通常低频。
- `ticket.rework.revision-diverged` 还要求 SATISFIED acceptance、当前 HEAD 已变、并且 trail 留有可比较旧 head，条件明显窄于普通 PENDING/accept 行。

## `basis` 标注真实性

`cli` 的定义是“CLI 本来就会拒绝违反者”，不是“修法最后会调用 CLI”。按当前 `impl_package_runtime/engine.py` 的实际拒绝路径，13 条 `cli` 的结论如下：

| slug | basis 结论 | 依据 |
| --- | --- | --- |
| `package.record.state-missing` | 属实 | `package validate` 对 state schema、Ticket/evidence/checkpoint 等 admission 错误失败。 |
| `package.record.projection-drift` | 属实 | projection validation 失败会被 `package validate` 拒绝；renderer 接收的结构化 validation result 只是只读输入。 |
| `attempt.gate.terminal-frozen` | 属实 | terminal Attempt 的状态写入经过 `_assert_mutable`，CLI 拒绝继续变更。 |
| `attempt.readiness.all-edges-held` | 部分属实 | CLI 会在 `ticket satisfy` 时拒绝未释放 implementation dependency，但没有 CLI 直接禁止“派发 implementation”；“不得硬上”仍是 prose admission。 |
| `ticket.accept.acceptance-edge-held` | 属实 | `ticket satisfy` 检查 implementation/acceptance dependencies，acceptance edge 未释放会拒绝。 |
| `ticket.verify.contradictory-unresolved` | 当前不属实 | 当前 row 检查任意 revision/claim 的冲突，而 CLI 只对待 satisfy 的 acceptance revision/environment 检查；需先收窄判据。 |
| `ticket.accept.satisfiable` | 当前不属实 | active contradiction 与 supporting evidence 并存时该 row 仍可命中，但 `ticket satisfy` 会拒绝；需先把无冲突条件纳入判据。 |
| `ticket.rework.revision-diverged` | 仅间接属实 | `gate pass` 会拒绝旧 acceptance revision，但“发现分叉就进入 rework”不是 CLI 强制的状态转移。 |
| `ticket.rework.revalidation-pending` | 不属实 | 当前 engine 没有禁止从 `NEEDS-REVALIDATION` 直接以正确 `--expect` 做 satisfy；它是流程要求，不是现有 CLI admission。 |
| `ticket.disposition.retire-undecided` | 仅部分属实 | CLI 强制 retire 必须带 disposition/successor/evidence，但不能从 CLI 推导 `no_longer_needed` 这个业务判断。 |
| `ticket.accept.release-edge-unchecked` | 不属实 | CLI 检查 release edge 是否 released，不检查 `release_edge_rechecked` fact；无 release edge 时也可能通过 CLI。 |
| `attempt.gate.durable-delta-missing` | 属实 | terminal Gate 必须带 Durable Delta 或明确 no-durable reason。 |
| `attempt.gate.comparison-mismatch` | 属实但为死行 | terminal Gate 要求 comparison commit 等于当前 HEAD，`pass` 还要求等于每个 SATISFIED Ticket 的 acceptance revision；CLI 会拒绝，但 P0 已先抢占展示。 |

因此，13 个 `cli` 标注中只有 6 个当前无条件属实，3 个只有间接强制，4 个与当前判据/CLI 实际行为不符。42 个 `prose` 标注整体属实：它们的触发条件没有被 CLI 自动强制；即使修复动作会调用 CLI，也不等于 CLI 会拒绝“不先做该动作”的输入。

## 接线判断与必须先改项

当前不能接线；本轮逐行 audit 可以交付，但整个任务未 closed。接线前至少要完成下面这些语义/合同修正，并重新跑全部 fixture 与可见性核验：

### P0：先消除错误处境和不可见规则

1. `改判据`：`ticket.investigate.no-carrier`。必须把“没有调查载体”与“没有调查 signal、没有 indexed evidence”区分开，明确 carrier 的权威事实及 evidence 是否按 indexed 计数；同时决定它在 P3/P4 目标存在时是否仍应抢占。该项直接决定“先调查后实现”核心价值，最高优先级。
2. `删行`：`attempt.gate.comparison-mismatch`。如果仍需要提醒 comparison mismatch，应把它并入一个可见的 P0 Gate admission 规则并重新设计 priority；原行不能原样接线。
3. `改判据`：`ticket.verify.contradictory-unresolved` 与 `ticket.accept.satisfiable`。两者必须共享 acceptance pair、required claim 和“无 active contradictory/inconclusive evidence”的同一 acceptance 语义，不能出现 renderer 建议 satisfy 而 CLI 拒绝的窗口。

### P1：修复会改变主控下一动作的过宽命中

4. `改判据`：`attempt.disposition.findings-triage-pending` 的 `near_terminal_gate`。`gate.md` 文件存在不能单独证明接近 terminal Gate；至少要要求可解析的 Gate/明确收口阶段，或把“所有 Ticket terminal”和“Gate 已开始”拆成可解释条件。
5. `改判据`：`ticket.accept.release-edge-unchecked`。要求真实存在 release dependency，并明确 CLI 是否要记录/强制 recheck；否则无 release edge 的 Ticket 会收到错误的 recheck 动作。
6. `过窄`对应的合同修正：`attempt.record.session-resumed`。若保留 marker 的 fail-closed 实现，就用 `改描述` 明确“必须有可定位 checkpoint marker”；若人读处境才是权威，则改判据让显式恢复事实能表达“本 session 尚无动作”。二者必须选定一个 owner 语义。
7. `拆行`：`attempt.gate.verdict-undecided`。分别表达“Gate 缺失”和“Gate 存在但 verdict=undecided”，避免把 absence 当作 verdict。

### P2：清理名称、证据声明与 CLI 标注

8. `改描述`：`package.record.state-missing` 明确写成 `state_invalid`（含 schema/交叉校验失败），不要让 slug 的 missing 误导主控。
9. `改描述`：`ticket.record.evidence-unfiled` 改为“direct-evidence tuple 尚无未失效 index record”，不要写成 evidenceIndex 完全无行。
10. `改描述`：`ticket.verify.safety-invariant-unfalsified` 改成“安全不变量缺 active evidence/尚未验证”，或由 owner 决定真正实现 unfalsified 语义；当前名字与判据不能同时保留。
11. `改判据`：`ticket.rework.evidence-conflict` 如果必须保留“新证据”描述，就补 post-SATISFIED 的新证据事实/顺序；否则改描述为“SATISFIED 后存在未失效 contradictory/inconclusive evidence”。
12. `改描述`：`ticket.rework.revision-diverged` 补上“且 trail 有旧 head 并已推进”的实现前置条件，或删掉该前置条件让判据覆盖描述的全部分叉情况。
13. `改判据`：`ticket.accept.release-edge-unchecked` 的 CLI basis 同步修正；若不增加 CLI 强制，basis 应改为 prose，而不是继续标 cli。

上述第 8、9、10、12 项主要是描述/名称合同，第 1–7、11–13 项会改变命中或动作路由。完成这些决定后，再以 55 行完整映射和“primary/parallel/secondary/suppressed/undetermined”边界重跑 25 个复验；在复验与语义修正共同通过前，不应接线。

## 证据定位

- 人读处境与动作：`docs/skill-design/impl-package-situation-table-260815/situation-table-dev-with-track.md`。
- 完整逐行组合、21 条隐式前置条件和命中结算：`plugin-marketplace/plugins/impl-package/references/situation-inputs.md` 第 9–10 节。
- YAML 行、priority 和 basis：`plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`。
- key parser、AND/unknown、priority 可见性：`plugin-marketplace/plugins/impl-package/scripts/situation.py`。
- 最近 25 fixture 的实测背景：`docs/skill-design/impl-package-situation-table-260815/reverify-b2-report.md`。
