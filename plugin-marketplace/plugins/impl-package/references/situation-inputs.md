
# Situation 输入字段合同

本文件是 `dev-with-track` situation table 的输入合同。它描述的是
`plugin-marketplace/plugins/impl-package/scripts/situation.py` 当前真正读取和判定的
package 形状，目的是让不阅读推导器实现的人也能构造 fixture、per-package 覆盖和审计输入。

截至 2026-08-17，正式表有 59 个 situation row、68 个唯一的非 `manual` `when` key。
本文逐一覆盖这 68 个 key。`manual` row 不需要输入字段；它们始终出现在 `manual` 输出中，
由主控做语义判断。

> 重要边界：本文的“能被推导器识别”首先指 `situation.py render` 的输入合同。完整的
> 3.5 runtime 还会检查 `plan.md`、`spec.md`、Ticket 的 Publication Status、artifact
> 是否存在、Git revision 是否可解析和 projections；这些额外要求仍以
> `references/impl-package-current-state.md`、`impl-package-composition-contract.md`
> 和 runtime validate 为准。本文不会把 situation parser 偶然接受的宽松形状写成完整
> runtime 的推荐写法。

## 1. 先记住三件事

### 1.1 输入文件和 subject

推导器只从下列 package-relative 位置取事实：

| 代号 | 实际路径 | 读取方式 |
| --- | --- | --- |
| S | `.impl-package/state.json` | 严格 JSON object；先做 state schema，再做 Ticket/evidence/checkpoint 交叉校验 |
| T | `tickets/*.md` 的直接子文件 | 按正文里的 Ticket ID 建索引；文件名本身不参与 ID 解析 |
| R | `execution/<attempt-id>/trail.jsonl` | `<attempt-id>` 来自 `S.attempt.id`；renderer 只读取当前未编号文件，每个非空行必须能解析成 JSON object；同目录的 `trail.NNN.jsonl` 是按序归档，仅由 `dispatch_audit.py` 做历史审计/回放 |
| G | `gate.md` | 按固定 Markdown 行解析 Verdict 和可选 Comparison commit |
| F | `execution-findings.md` | 按二级至六级 heading 分块，再解析 finding block |
| I | intake 候选路径 | 见下文 `intake.has_backlog` 行的顺序 |
| P | 调用 `render` 时传入的只读结构化 validation result；见 3.1 | 只有 `package.validate.projection_drift` 使用；不执行另一个 CLI，也不解析错误文本；缺失时可退回 R 中同 key 的 fact |
| CP | 调用 `render` 时传入的只读结构化 compaction pressure；由宿主脚本计算，不由 renderer 读取 sessions root | 只有 `attempt.compaction_pressure_high` 使用；只消费 `high`，缺失时返回 U |
| Git | 当前 package 所在 Git 仓库的 HEAD、commit resolve 和 diff | `trail` 中的 `head` 是比较基线；不会从普通 prose 推断 commit |

subject 不是自由标签。`attempt` scope 默认只看 trail 行的 `subject` 为 `attempt`、空值或
缺失的行；`ticket` scope 看 `ticket:<Ticket ID>` 或裸 Ticket ID；`finding` scope 看
`finding:<finding ID>` 或裸 finding ID。少数 attempt-level trail signal 会显式扫描全部 trail
行，本文在对应 key 中标出。

### 1.2 unknown、false 和硬失败不是一回事

本文表格使用以下词：

- **未知（U）**：parser 返回 `Fact(known=False)`。该 key 不满足 row；row 会进入
  `undetermined`，而不是当成 false。
- **已知 false（F）**：parser 返回已知值 `False`。row 可以确定不命中。
- **硬失败（HF）**：不是某个 key 的正常结果，而是 CLI/package/table 层直接报错并退出。
  例如 package 目录不存在、`--at` commit 无法解析、YAML/table 非法。缺失的 state、trail、
  findings 或 intake 本身通常不会 HF；它们按下表返回 true、false 或 U。

对一个含多个 `when` 的 row，**任意一个 U 都使整行成为 unknown**，即使另一个 key 已知
false；只有没有 U 且所有比较都相等时才是 true。

### 1.3 `when` 比较表达式语法

`_compare` 的行为是固定的：

| YAML 中的 expected | 语义 | 例子 |
| --- | --- | --- |
| JSON/YAML boolean | Python 值精确相等；表中应使用布尔而不是字符串 | `true`、`false` |
| 普通字符串 | 字符串/枚举精确相等，大小写不自动归一化 | `PENDING`、`DONE`、`implement` |
| 形如 `op number` 的字符串 | 数值比较；`op` 只能是 `> >= < <= == !=` | `">1"`、`">0"`、`"<=2"`、`"==1.5"` |
| YAML number | 直接做值相等比较；正式表没有用它替代数值比较字符串 | `1`、`0` |

数值正则允许负数和小数，允许操作符与数字之间有空格，外侧空格会被去掉。`">1"` 比较
的是 parser 的实际数值；它不会自动取 list 长度。`"1"` 是字符串相等，不是数值 1。
`=>1`、`<>1`、`=1`、`between 1 and 2`、`truthy`、`not false` 和带单位的字符串都不支持；
不匹配数值语法时会退回普通相等比较，通常得到已知 false，而不是 U。

## 2. 68 个 `when` key 合同

表中的“缺失/错误”列同时说明文件不存在、字段不存在、字段形状不对和没有匹配 marker
时的行为；`HF：无`表示该 key 本身不会因该输入缺失直接让 CLI 失败。

### 2.1 package、attempt、state 和 Git admission

| key 名 | 数据来源与实际计算 | 合法取值 | 缺失/错误行为 | 被哪些行使用 |
| --- | --- | --- | --- | --- |
| `package.state_invalid` | S：整个 `.impl-package/state.json` 的解析/校验结果；缺文件、JSON 非 object、顶层 key 不对、formatVersion 不对、Ticket/evidence/checkpoint 交叉校验失败都算 invalid | `true` = state 缺失或非法；`false` = situation parser 认为 state 合法 | 缺失/非法是**已知 true**，并保留 reason；合法是 F；HF：无 | `package.record.state-missing` |
| `package.validate.projection_drift` | P：`--validation-result` 传入的 JSON object；没有 P 时才读 R 中 attempt scope 同 key 的最新 fact | 布尔；P 的规范形状是 `{"projection_drift":true/false}`；R 规范形状见 3.1 | 没有 P 且没有 fact = U；P 顶层、字段或类型错误 = HF；`--at` 不改变判定；HF：仅 validation result 结构错误或外围 CLI/package 错误 | `package.record.projection-drift` |
| `attempt.active_checkpoint_present` | S：`activeCheckpoints` 中是否存在 key `attempt`；只在 attempt subject 计算 | 布尔；`activeCheckpoints.attempt` 存在 = true，不存在 = false | state 无效/缺失 = U；合法空 mapping = F；HF：无 | `attempt.record.session-resumed`、`attempt.record.checkpoint-missing`、`attempt.record.checkpoint-refresh` |
| `attempt.all_tickets_terminal` | S：`tickets` 是否非空且每个 row 的 `state` 都是 `SATISFIED` 或 `RETIRED` | 布尔 | state 无效 = U；合法但 tickets 为空 = F；有任一 `PENDING/BLOCKED/NEEDS-REVALIDATION` = F；HF：无 | `attempt.accept.all-tickets-terminal` |
| `attempt.completion_claim_pending` | R：attempt scope 的最新 fact；兼容读取旧 `facts/when/derived` 容器 | 布尔；只推荐规范 JSON boolean | 没有 fact = U；显式非布尔 = U；未知 fact key = HF | `attempt.accept.completion-claim-unaudited` |
| `attempt.handoff_or_long_task` | R：attempt scope 的最新 `kind=fact` 同 key；兼容读取旧 `facts` 容器；没有从 checkpoint 的 `next/blocker` 或 trail prose 自动推导 | 布尔 | 没有 fact = U；显式非布尔 = U；未知 fact key = HF | `attempt.record.checkpoint-missing` |
| `attempt.compaction_pressure_high` | CP：`--compaction-pressure` 传入的 JSON object 的 `high`；宿主脚本以第一段间隔为 baseline，最近三段间隔的中位数至少缩短 20% 且至少有三段间隔时才给 `high=true`；renderer 不重算 | 布尔 | 缺少参数 = U（不是 false）；合法 `high=false` = F；JSON 非 object、缺 `high`、类型/未知字段错误 = HF | `attempt.record.handoff-due` |
| `attempt.has_pending_ticket` | S：`tickets[*].state` 是否至少有一个 `PENDING` | 布尔 | state 无效 = U；合法无 Ticket 或全非 PENDING = F；HF：无 | `attempt.readiness.all-edges-held` |
| `attempt.implementation_edges_held` | S + T：先计算 `ready_ticket_ids`，再判断“存在 PENDING Ticket 且 ready 数量为 0”；implementation dependency 的释放规则见 `ticket.acceptance_edge_released` | 布尔 | state、Ticket 文件或 dependency 不可判定 = U；无 pending = F；有 pending 且至少一个 ready = F；HF：无 | `attempt.readiness.all-edges-held` |
| `attempt.in_flight` | R：先找 fact；否则同时识别旧 `kind=decision` + `chosen` dispatch/sdd 未配 result，以及 `kind=dispatch` + `outcome=RUNNING` + `returned=false` | 布尔；dispatch 可无 id；有 id 时 result-like 的 `of/dispatch_id/decision...` 可关闭 | 无 trail = U；trail 存在但没有 open dispatch = F；显式非布尔 = U；HF：无 | `attempt.readiness.multiple-ready-tickets` |
| `attempt.integration_carrier_available` | R：attempt scope 的最新 fact `attempt.integration_carrier_available`；不再扫描 unavailable 文本 marker | 布尔 | 无 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.readiness.integration-carrier-unavailable` |
| `attempt.integration_evidence_available` | R：attempt scope 的最新 fact `attempt.integration_evidence_available`；不再扫描 unavailable 文本 marker | 布尔 | 无 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.verify.integration-evidence-unavailable` |
| `attempt.manual_verification_owner` | R：attempt scope 的最新 fact `attempt.manual_verification_owner` | 布尔 | 没有值或非布尔 = U；未知 fact key = HF | `attempt.verify.manual-result-missing` |
| `attempt.manual_verification_result_present` | R：attempt scope 的最新 fact `attempt.manual_verification_result_present` | 布尔 | 没有值或非布尔 = U；未知 fact key = HF | `attempt.verify.manual-result-missing` |
| `attempt.near_terminal_gate` | S + G：`all_tickets_terminal` 为 true，或 `gate.md` 存在且 Verdict 可解析 | 布尔 | state 无效 = U；state 合法且无 terminal Ticket、无可解析 Gate = F；malformed Gate 不满足该辅助条件；HF：无 | `attempt.disposition.findings-triage-pending` |
| `attempt.ready_ticket_count` | S + T：收集所有 `PENDING` Ticket，只有 implementation dependencies 全部由 `SATISFIED`、`RETIRED/waived` 或已释放 successor 释放时才进入 ready list；返回 list 长度 | 非负整数；用于表的比较是 `">1"` 或 `0` | state/Ticket/dependency 不可判定 = U；合法空图返回 0；HF：无 | `attempt.readiness.multiple-ready-tickets`、`attempt.readiness.all-edges-held` |
| `attempt.session_resumed` | S + R：不读取声明；`activeCheckpoints.attempt` 存在，且 checkpoint 后没有动作行时为 true | 布尔 | trail error 或 state/checkpoint 不可判定 = U；无 active checkpoint = F；有显式 checkpoint marker 时只计 marker 后的行；没有 marker 时忽略兼容性的 `attempt.session_resumed` 声明，但其它 typed fact/action 会使结果为 false；HF：无 | `attempt.record.session-resumed`（兼容 parser key） |
| `attempt.terminal_coverage_complete` | S + 最新 `review.terminal_summary` fact + package-relative report | 布尔；核对 comparisonHead、A/B/C 与按需 Safety 的 PASS，同 ReviewRun 的 B/C/Safety 可凭 reuseEvidence 复用 | 尚未终审为 U；缺结果或来源不匹配为 false；旧 false 仍可表示 gap，旧 true/dispatch 不能证明完成；Gate 终态不能替代结果 | `attempt.review.terminal-coverage-incomplete` |
| `attempt.terminal_gate_pending` | S + G：先要求所有 Ticket terminal；再取 `gate.terminal`，返回其否定 | 布尔 | state 或 gate verdict 不可判定 = U；尚有非 terminal Ticket = F；全 terminal 且 gate 缺失/非 terminal = true；pass/fail/defer = F；HF：无 | `attempt.gate.durable-delta-missing` |
| `git.acceptance_revision_diverged` | S + Git（ticket subject）：Ticket row 必须是 `SATISFIED`，读取 `acceptance.revision`，确认该 revision 可 resolve，再与当前 Git HEAD 比较 | 布尔；可 resolve 且不等于当前 HEAD = true，等于 = false | 非 ticket subject = U；state 无效时当前实现把无 row 当作“非 SATISFIED”，返回 F；缺 acceptance、HEAD、或 revision 无法 resolve = U；HF：无 | `ticket.rework.revision-diverged` |
| `git.comparison_head_fixed` | R：attempt scope 的最新 fact `git.comparison_head_fixed`；不再从自由文本 marker 推导 | 布尔 | 无 trail/无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.review.comparison-head-unfixed` |
| `git.comparison_revision_matches_acceptance` | G + S：已有 `pass` Gate 时比较 Gate comparison commit；准备判 pass 且尚无 Gate 时，以当前 HEAD 作为将传给 CLI 的 comparison commit；逐个检查 SATISFIED Ticket 的 `acceptance.revision` 是否相等 | 布尔 | 非 pass Gate 且未声明 `attempt.completion_claim_pending` = F；准备判 pass 时 HEAD/state 不可读 = U；state 无效 = U；任一 SATISFIED acceptance revision 不等 = F；没有 SATISFIED Ticket 时为 true；HF：无 | `attempt.gate.comparison-mismatch` |
| `git.contract_changed_since_last_trail` | R + Git：读取最后一个适用 trail 行的顶层 `head`；若它与当前右端不同，检查 `head..HEAD` diff 中是否有 `plan.md`、`spec.md`、`contract-design.md`、`decision.md` 或 `tickets/` 文件 | 布尔 | 无 trail head = U；head 等于当前 HEAD = F；Git diff 不可读 = U；diff 命中上述路径 = true，否则 F；HF：无 | `attempt.rework.contract-changed` |
| `git.head_advanced_since_last_trail` | R + Git：最后一个适用 trail 行的顶层 `head` 与当前 HEAD 比较 | 布尔 | 无 trail head 或当前 HEAD 不可读 = U；相同 = F；不同 = true；HF：无 | `ticket.rework.revision-diverged` |

### 2.2 ticket、evidence 和 dependency

| key 名 | 数据来源与实际计算 | 合法取值 | 缺失/错误行为 | 被哪些行使用 |
| --- | --- | --- | --- | --- |
| `ticket.acceptance_conditions_satisfied` | S + T：等价于 `evidence.all_required_claims_supported=true` 且 `evidence.contradictory_unresolved=false`；required claims 来自 Ticket 的 Stable claim ID | 布尔 | 任一子事实 U 就 U；无 claims 时 supporting 子事实为 F；有完整 supporting 且无 active contradictory/inconclusive 才 true；HF：无 | `ticket.accept.release-edge-unchecked` |
| `ticket.acceptance_edge_released` | S + T：Ticket 的 `## 阻塞依赖` 中 kind=`acceptance` 的目标全部已释放；`SATISFIED`、`RETIRED/waived` 释放，`RETIRED/superseded` 递归看 successor，其余状态不释放 | 布尔 | state/Ticket/dependency 不可判定 = U；没有 acceptance 边时 `all([])` 为 true；任一边未释放 = F；HF：无 | `ticket.accept.acceptance-edge-held`、`ticket.accept.satisfiable` |
| `ticket.acceptance_revision_parseable` | S + Git：先取 Ticket 的 `acceptance.revision/environment`；若 Ticket 是 PENDING 且没有 acceptance，再从 evidence group 找第一组可解析 revision | 布尔 | 非 ticket subject = U；没有 pair 且 evidence 可读 = F；Git 不可用 = U；pair 的 revision 可 resolve = true，否则 F；HF：无 | `ticket.accept.satisfiable` |
| `ticket.blocker_maybe_resolved` | R：当前 Ticket scope 的最新 fact；旧 Ticket 正文 alias 仅作兼容 fallback | 布尔 | 没有值 = U；显式值不是布尔 = U；不会因为 Ticket 为 BLOCKED 自动变 true；未知 fact key = HF | `ticket.readiness.blocker-maybe-resolved` |
| `ticket.no_longer_needed` | R：当前 Ticket scope 的最新 fact；旧 Ticket 正文 `no longer needed: true` 仅作兼容 fallback | 布尔 | 没有正向声明 = U，不是 F；显式值不是布尔 = U；未知 fact key = HF | `ticket.disposition.retire-undecided` |
| `ticket.investigation_carrier_present` | R + S：当前 Ticket 有结构化 investigate 派发/结果，或 evidenceIndex 至少有一条 `timing=early-falsification` 记录 | 布尔 | 无/坏 trail 且无法判断派发，或 state/evidence 不可读 = U；两类载体都没有 = F；HF：无 | `ticket.investigate.no-carrier` |
| `ticket.investigation_context_clear` | R：当前 Ticket 与 attempt scope 没有其它 typed fact；纯 checkpoint marker 不算其它处境 | 布尔 | 无/坏 trail = U；任一相关 typed fact（无论 true/false）存在 = F；没有 typed fact = true；HF：无 | `ticket.investigate.no-carrier` |
| `ticket.release_edge_rechecked` | R：当前 Ticket scope 的最新 fact `ticket.release_edge_rechecked`；不再从 `chosen` 前缀、situation 或 dependency 状态推导 | 布尔 | 无 trail/无 fact = U；fact 非布尔 = U；未知 fact key = HF | `ticket.accept.release-edge-unchecked` |
| `ticket.release_edge_present` | T：当前 Ticket 的 typed dependency 中是否至少有一个 kind=`release` | 布尔 | Ticket 文件缺失/解析失败 = U；无 release dependency = F；至少一条 release dependency = true；HF：无 | `ticket.accept.release-edge-unchecked` |
| `ticket.review_required` | R/T：显式 `ticket.review_required` 优先；否则 trail 行 `review_state`（大小写不敏感）为 `PENDING_REVIEW`，或 Ticket 正文有 `review: required` | 布尔 | 无 trail 时在进入 Ticket prose fallback 前就返回 U；有 trail 无 signal 且 Ticket 无该行 = F；HF：无 | `ticket.review.awaiting-reviewer` |
| `ticket.review_trigger` | R：当前 Ticket scope 的最新 fact；没有由 outcome 或 `review_state` 自动推导 | 布尔 | 没有值或非布尔 = U；未知 fact key = HF | `ticket.review.required-trigger` |
| `ticket.safety_invariant_unfalsified` | S + T：Ticket claims 中 ID 以 `INV-`（不区分大小写）开头的项是安全不变量；比较 active evidence 的 claim 集合，若至少一个 INV claim 没有 active record 就 true | 布尔 | 非 ticket、Ticket 无法解析、state/evidence 无效 = U；没有安全 claim = F；所有 INV claim 都有未 invalidated record = F；至少一个缺 record = true；HF：无 | `ticket.verify.safety-invariant-unfalsified`（描述为尚未验证） |
| `ticket.state` | S：当前 ticket subject 的 `tickets[identifier].state` | 枚举 `PENDING`、`BLOCKED`、`NEEDS-REVALIDATION`、`SATISFIED`、`RETIRED` | 非 ticket subject、state 无效、Ticket ID 不存在 = U；合法时返回枚举原值；HF：无 | `ticket.readiness.blocker-maybe-resolved`、`ticket.investigate.no-carrier`、`ticket.rework.evidence-conflict`、`ticket.rework.revalidation-pending` |
| `evidence.all_required_claims_supported` | S + T：required claims 是 Ticket 解析到的全部 Stable claim ID；先取 acceptance pair（SATISFIED 的 acceptance 或 PENDING evidence group），只在同 revision/environment 中检查每个 claim 有 `conclusion=supporting` 且未 invalidated | 布尔 | 非 ticket/Ticket 无 claims = U 或 F（Ticket 无法解析为 U、无 claims 为 F）；state/evidence 不可读 = U；没有 acceptance pair = F；全部 claim 支持才 true；HF：无 | `ticket.accept.satisfiable` |
| `evidence.contradictory_unresolved` | S + T：先取当前 acceptance pair，再只检查该 pair 中 required claim 的 active record；任一 `conclusion` 是 `contradictory` 或 `inconclusive` 就 true | 布尔 | state/evidence/Ticket 不可读 = U；没有 acceptance pair 或该 pair 无 required-claim conflict = F；其它 revision/非 required claim 的冲突不计入；HF：无 | `ticket.verify.contradictory-unresolved`、`ticket.accept.satisfiable`、`ticket.acceptance_conditions_satisfied` |
| `evidence.count` | S：当前 ticket 的 `evidenceIndex[Ticket ID]` 下所有 claim mapping 中 list item 的总数；包含已 invalidated record | 非负整数；表里比较 `">0"` 或与 0 相等 | state 无效、非 ticket subject 或 evidenceIndex 不可读 = U；合法空 mapping = 0；HF：无 | `ticket.investigate.no-carrier`、`ticket.accept.acceptance-edge-held` |
| `evidence.indexed` | R + S：把 `kind=result` 或 `kind=worker-return` 行中的 `ref/evidence/artifact/evidence_ref/direct_evidence` payload 当 direct evidence；每个 payload 必须可得 artifact、claim、revision、environment，再检查同 tuple 是否存在未 invalidated S record | 布尔 | 无/坏 trail = U；无 direct payload = F；payload 缺任一 link 字段 = U；state 无效 = U；所有 tuple 已登记 = true，否则 F；HF：无 | `ticket.record.evidence-unfiled` |
| `evidence.new_claim_conflict` | S：先要求 state 可读；只有当前 Ticket state 是 `SATISFIED` 才调用 `evidence.contradictory_unresolved`，否则 false | 布尔 | state 无效 = U；Ticket 不存在或不是 SATISFIED = F；SATISFIED 但 evidence 不可读 = U；有 active contradictory/inconclusive = true；HF：无 | `ticket.rework.evidence-conflict` |
| `evidence.sources_uniquely_decide` | R：当前 Ticket scope 的最新 fact；没有根据 evidence 数量自动判断“唯一来源” | 布尔 | 没有值或非布尔 = U；未知 fact key = HF | `ticket.route.sources-uniquely-decide` |
| `finding.closure_review_pending` | R 显式值优先；否则 F 中当前 finding block 的 status 和文本：closed/resolved/retired/complete = false；`closure ... pending/awaiting` 或反向 30 字符窗口命中 = true | 布尔 | F 缺失/读取错误或 finding ID 不存在 = U；closed status = F；存在 finding 但无 closure marker = F；HF：无 | `finding.review.closure-awaiting` |
| `finding.grading_pending` | F：finding 非 closed 且 block 含 `grading_pending`、`待定级`，或没有可识别的 `P1/P2/P3/editorial` grade | 布尔 | F 缺失或 finding 不存在 = U；open 且无 Grade = true；open 且有 P1/P2/P3/editorial = F；closed = F；HF：无 | `finding.disposition.grading-undecided` |
| `finding.review_track` | F：当前 finding block 中 `Track A/B/C/D` 或 `轨道 A/B/C/D` 的捕获值 | 枚举 `A`、`B`、`C`、`D`，没有 track 时是已知 `None` | F 缺失/错误或 finding 不存在 = U；finding 存在但没有 track = 已知值 None（与期望 `C` 不相等）；HF：无 | `finding.review.source-recheck-pending` |
| `finding.source_recheck_pending` | F：block 中的 `source_recheck: pending`、`source recheck ... pending` 或中文待复核/待重查 marker | 布尔 | F 缺失/错误或 finding 不存在 = U；无 marker = F；HF：无 | `finding.review.source-recheck-pending` |
| `findings.triage_pending` | F：对所有 parsed findings，`triage_pending` 为非 closed 且（有 `triage: pending`/未分流/待分流，或没有 Decision/Spec/Execution Record/Durable Delta route marker） | 布尔 | F 缺失/解析错误 = U；F 存在但没有 parsed finding = false；任一 finding pending = true；HF：无 | `attempt.disposition.findings-triage-pending` |
| `gate.stage7_complete` | G：精确找到 `## Durable Deltas` section；其中至少一行 `- ...`，且不是 `- none` 或 `- Reason: none` | 布尔 | G 缺失或读取/解析错误 = U；没有 Durable Deltas section = F；有 meaningful bullet = true；HF：无 | `attempt.gate.durable-delta-missing` |
| `gate.present` | G：`gate.md` 文件是否存在；不把文件内容是否 malformed 混入 presence | 布尔 | 缺 Gate = F；文件存在（即使 malformed）= true；HF：无 | `attempt.gate.missing`、`attempt.gate.verdict-undecided`、`attempt.gate.comparison-mismatch` |
| `gate.terminal` | G 的 `Verdict`；`pass/fail/defer` 属于 terminal | 布尔 | G 缺失 = 已知 F；有文件但 Verdict 缺失/格式错 = U；`blocked/undecided` = F；`pass/fail/defer` = true；HF：无 | `attempt.gate.terminal-frozen` |
| `gate.verdict` | G：`- Verdict: pass / fail / blocked / defer / undecided` 或中文 `判定` 行；只读取已存在 Gate 的显式 verdict | 枚举 `pass`、`fail`、`blocked`、`defer`、`undecided`，解析后转小写 | 缺 G = U（由 `gate.present=false` 单独表达）；有 G 但 Verdict 缺失/格式错 = U；HF：无 | `attempt.gate.verdict-undecided` |
| `intake.has_backlog` | I：按顺序找第一个存在的文件：`.impl-package/intake.jsonl`、`.impl-package/intake-queue.jsonl`、`.impl-package/intake.json`、`execution/intake.jsonl`、`execution/intake-queue.jsonl`、`execution/intake.json`、`intake.jsonl`、`intake.json`；其次找目录 `.impl-package/intake`、`.impl-package/intake-queue`、`execution/intake`、`execution/intake-queue`、`intake`、`intake-queue` | 布尔；JSON list 非空、dict 的 `items/queue` list 非空、非 JSON 但有非空行、目录有 entry = true | 所有候选不存在 = U；存在但空文本/空 list/空目录 = F；读取错误或 dict 无 list 时按非空文本 fallback；HF：无 | `package.record.intake-backlog` |
| `trail.actions_since_checkpoint` | R（当前活动 `trail.jsonl`）：在适用 subject rows 中找最后一个 `kind=checkpoint`、`chosen/situation` 含 checkpoint 或 `checkpoint=true` 的 marker，返回 marker 后的行数；无 marker 时忽略兼容性的 `attempt.session_resumed` 声明并计其它 rows；轮换后不读取 `trail.NNN.jsonl` | 非负整数；表只比较 `0` | 无/坏 trail = U；state 无效导致 checkpoint 不可判定 = U；无 active checkpoint = 0；有 marker 且 marker 后无行 = 0；无 marker 且没有其它 typed fact/action = 0；HF：无 | `attempt.record.session-resumed` |
| `trail.last_ticket_terminal_transition` | R（当前活动 `trail.jsonl`）：attempt scope 扫描全部 rows，Ticket scope 只扫描当前 Ticket；取最后一个 `kind=result`、`transition=ticket-state` 且 `subject` 为 `ticket:<id>` 的状态转换行，检查其 `to`（兼容 `outcome`）是否为 `SATISFIED` 或 `RETIRED`；轮换后不读取归档 | 布尔；最后一个 Ticket 状态转换进入 `SATISFIED/RETIRED` = true | trail 缺失或可读但为空 = F；坏 trail = U；没有状态转换 = F；最后状态转换不是终态 = F；普通 worker result 没有 `transition=ticket-state`，不参与；HF：无 | `attempt.record.ticket-boundary-handoff`、`attempt.record.trail-rotation-due` |
| `trail.anchor_mismatch` | R：attempt scope 的最新 fact；不再扫描 JSON 文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.anchor-mismatch` |
| `trail.checkpoint_refresh_needed` | R：attempt scope 的最新 fact；不再扫描 JSON 文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.checkpoint-refresh` |
| `trail.decision_without_result` | R（当前活动 `trail.jsonl`）：旧 decision/result 配对差集非空，或存在 `kind=dispatch`、`outcome=RUNNING`、`returned=false` 且未被 result-like `of/dispatch_id/...` 关闭；轮换后不读取归档 open dispatch | 布尔；dispatch 不要求 identifier；decision 旧写法要求 `seq/id/decision_id/decisionId` | 无/坏 trail = U；没有未配对 decision/dispatch = F；HF：无 | `attempt.readiness.worker-still-running` |
| `trail.direct_evidence_returned` | R：扫描 `kind=result` 与 `kind=worker-return`；其 payload key 是 `ref/evidence/artifact/evidence_ref/direct_evidence`，非空 scalar/list item 即算 direct payload | 布尔；payload 可以 object、string 或其他 truthy 值，但要继续判 `evidence.indexed` 时必须有 artifact/claim/revision/environment | 无/坏 trail = U；trail 有但没有 result-like payload = F；HF：无 | `ticket.record.evidence-unfiled` |
| `trail.envelope_valid` | R：显式 fact `trail.envelope_valid` 优先；否则读取 result-like row 或 `envelope/result` 容器中的结构化 `envelope_valid/envelopeValid` | 布尔；建议 JSON bool `true/false` | 无/坏 trail = U；有 trail 但没有结构化字段/fact = U；显式非布尔 = U；不再识别 envelope 文本 marker；HF：未知 fact key | `finding.fix.worker-envelope-invalid` |
| `trail.finding_source` | R：当前 subject rows 的顶层 `finding_source` 或 `findingSource` 字符串，取最后一个 | 字符串；表使用 `reviewer`、`main-session` | 无/坏 trail = U；trail 正常但没有字段 = 已知值 None（与任何字符串不等）；HF：无 | `finding.fix.reviewer-returned`、`finding.fix.main-session-discovered` |
| `trail.handoff_in_flight` | R：attempt scope 的最新 fact；不再扫描 handoff/relay/continuation 文本 marker | 布尔 | 无/坏 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.handoff-in-flight` |
| `trail.handoff_recovery_needed` | R：attempt scope 的最新 fact；不再扫描 bootstrap/retry/rename/create-thread 文本 marker | 布尔 | 无/坏 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.handoff-recovery-needed` |
| `trail.handoff_target_corrected` | R：attempt scope 的最新 fact；不再扫描 corrected target/order 文本 marker | 布尔 | 无/坏 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.handoff-target-corrected` |
| `trail.has_investigate` | R：attempt context 扫全部 rows；ticket/finding context 扫各自 subject rows；`situation` 以 `ticket.investigate.` 开头，或 chosen 含 `investigate`，或 outcome 为 `EVIDENCE_GAP/EVIDENCE_SUFFICIENT` 即 true | 布尔 | 无/坏 trail = U；有 trail 无 signal = F；HF：无 | 兼容 parser key；正式 `ticket.investigate.no-carrier` 使用 `ticket.investigation_carrier_present` |
| `trail.incomplete_count` | R（当前活动 `trail.jsonl`）：从适用 rows 末尾往前扫描 `kind=result` 或 `kind=worker-return`；连续 `outcome=INCOMPLETE` 计数，遇到另一个 result-like event 即停止；轮换是连续计数边界 | 非负整数；表精确比较 1 或 2 | 无/坏 trail = U；没有 result-like event 或最后一个不是 INCOMPLETE = 0；HF：无 | `ticket.implement.worker-incomplete-first`、`ticket.implement.worker-incomplete-second` |
| `trail.judgment_unfiled` | R：当前 subject 的最新 fact；兼容旧 alias `ticket.judgment_unfiled`，不再扫描自由文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `ticket.record.judgment-unfiled` |
| `trail.last_outcome` | R（当前活动 `trail.jsonl`）：适用 rows 末尾优先找 result-like（`kind=result` 或 `kind=worker-return`）且 outcome 为字符串；找不到时退回任何 row 的字符串 outcome；轮换后不读取归档 outcome | 字符串枚举由表约定：`EVIDENCE_GAP`、`DONE`、`INCOMPLETE`、`BLOCKED`、`FINDING` 等；比较大小写敏感 | 无/坏 trail = U；正常空 trail/无 outcome = 已知 None；HF：无 | `ticket.investigate.evidence-gap`、`ticket.review.awaiting-reviewer`、`ticket.implement.worker-incomplete-first`、`ticket.implement.worker-incomplete-second`、`ticket.implement.worker-blocked`、`finding.fix.reviewer-returned` |
| `trail.last_worker_mode` | R（当前活动 `trail.jsonl`）：显式 `trail.last_worker_mode` 优先；否则从 row、`facts/when/derived/worker/envelope/result` 读取 `worker_mode/workerMode/mode`，或从 chosen 匹配 `worker-mode` 或 `mode: <value>`；轮换后不读取归档 mode | 枚举 `investigate`、`implement`、`fix`、`verify`、`review`；解析后小写 | 无/坏 trail = U；正常 trail 无 mode = 已知 None；显式非允许值返回已知原值，因而与合法枚举不等；HF：无 | `ticket.implement.worker-incomplete-first`、`ticket.implement.worker-incomplete-second`、`ticket.implement.worker-blocked`、`finding.fix.worker-envelope-invalid` |
| `trail.reviewer_unavailable` | R：attempt scope 的最新 fact；不再扫描 timeout/unavailable 文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.review.reviewer-unavailable` |

## 3. 比较、subject 和 per-package override 的实用规则

### 3.1 trail event schema、fact 通道和 validation result

renderer 的当前输入是 `execution/<attempt-id>/trail.jsonl`，其每个非空行必须是 JSON object；轮换归档 `trail.NNN.jsonl` 不进入 renderer，只由 `dispatch_audit.py` 按序读作历史审计/回放输入。正式事件使用同一组公共字段：

| 字段 | 作用 | 要求 |
| --- | --- | --- |
| `v` | 轨迹 schema 版本 | 可选；现有 reader 不因缺失而拒绝旧行 |
| `seq` | attempt 内顺序 | 可选；同一 `ts` 下用于 fact 的后写覆盖 |
| `ts` | ISO 8601 事件时间 | `kind=fact` 必填；普通旧事件可缺失 |
| `subject` | 事实作用域 | 推荐必填；`attempt`、`ticket:<id>`、`finding:<id>` |
| `kind` | 事件语义 | 见下方事件类型 |
| `head` | 事件发生时的 Git SHA | Git rework 判断使用；不是普通 prose |

事件类型统一按语义归一，旧的 `kind=result` 继续有效：

| `kind` | 正式形状 | renderer 消费 |
| --- | --- | --- |
| `decision` | `subject`、`seq/id/decision_id/decisionId` 至少一个、`chosen` | 与 result 的 `of/decision/...` 配对；未配对 dispatch 属于 in-flight |
| `dispatch` | `subject`、`outcome:"RUNNING"`、`returned:false/true`、`worker`；建议带 `seq` 或 `id`；常规字段为 `situation_digest`；review dispatch 可带成对的 `review_phase`、`review_track`，以及可选布尔 `review_recheck` | `returned:false` 直接表示 worker 尚未返回；review dispatch 的 `review_phase` ∈ `initial | finding-closure | terminal-final`，`review_track` ∈ `Track A | Track B | Track C | Track D`，两者要么都没有、要么同时出现且合法；`review_recheck=true` 标记 source recheck；有匹配 `of` 的 return 才关闭带 id 的 dispatch；`situation_digest` 是本次派发所依据的 renderer 12 位 digest；老轨迹和手写轨迹缺失时由审计识别，不使 renderer 失败 |
| `escape` | `subject`、`deviation`、`reason`；可带 `of` 关联 dispatch/decision | 记录偏离 renderer 建议或处境表未覆盖的决定；作为事件读取，不进入 fact 通道 |
| `result` | `subject`、`outcome`；返回 decision 时带 `of`；direct evidence 放在 `ref/evidence/artifact/evidence_ref/direct_evidence`；CLI Ticket 终态转换可带 `transition=ticket-state`、`from`、`to` | outcome、incomplete、旧 direct-evidence 写法和 decision 关闭；`transition=ticket-state` 供 Ticket 边界 when-key 读取 |
| `worker-return` | `subject`、`outcome`、可选 `of`、worker 返回的 direct-evidence payload | 与 `result` 归一；`EVIDENCE_SUFFICIENT` + `evidence` 是规范 direct-evidence 返回 |
| `fact` | `subject`、`kind:"fact"`、`key`、`value`、`ts`，可选 `seq` | renderer 在当前活动 `trail.jsonl` 内读取同一 key 的最新事实；`trail.NNN.jsonl` 只供 `dispatch_audit.py` 历史审计/回放；`ts` 会在 JSON `when_values` 中暴露，不添加过期规则 |

`checkpoint`、`handoff`、`judgment`、`integration`、`review` 等旧 kind 仍可作为普通事件，
但它们不再通过自由文本 marker 产生本节列出的业务事实。迁移期允许任意旧 kind 携带旧
`facts` object；新写入必须使用单条 `kind=fact`：

```json
{"v":1,"seq":12,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"attempt.handoff_or_long_task","value":true}
```

同一活动 trail 中同一 subject、同一 key 有多条 fact 时，按 `ts` 新者优先，`ts` 相同按 `seq`
新者优先，再以当前文件顺序作稳定兜底。轮换后归档 fact 不进入 renderer；陈旧 fact 在当前
文件内不会自动失效，最新 fact 的 `ts` 始终可见。
`value` 的类型由消费 key 校验；需要布尔的 key 只接受布尔/既有布尔兼容表示。

#### 封闭的 fact key 集合与缺省语义

新 `kind=fact` 和兼容读取的旧 `facts` object 只能使用下表的 canonical key；未知 key 是
trail schema 硬失败。显式 fact 优先；trail 可读取但 key 未声明时按下表取值，`unknown`
表示不猜测并让依赖该 key 的 situation 保持 undetermined。trail 缺失或读取失败仍是输入
不可用，不套用缺省值。

| fact key | 缺省语义 | 理由 |
| --- | --- | --- |
| `package.validate.projection_drift` | `unknown` | 没有 validation 结果或 fact 不能证明发生漂移，默认 false 会少提醒刷新。 |
| `attempt.session_resumed` | `unknown` | 没有恢复声明不能证明会话未恢复，默认 false 会少提醒检查 checkpoint。 |
| `attempt.in_flight` | `unknown` | 没有 in-flight 信号不能证明 worker 已返回，默认 false 还可能错误放行 ready Ticket。 |
| `attempt.handoff_or_long_task` | `unknown` | 没有声明不能区分短动作与长任务，默认 false 会少提醒写 checkpoint。 |
| `attempt.integration_carrier_available` | `unknown` | 没有可用性声明不等于 carrier 不可用，默认 false 会凭空触发 blocker。 |
| `attempt.integration_evidence_available` | `unknown` | 没有可用性声明不等于 integration evidence 不可用，默认 false 会凭空触发 blocker。 |
| `attempt.manual_verification_owner` | `unknown` | 没有 owner 声明不能证明不需要人工复核，默认 false 会少提醒人工验证。 |
| `attempt.manual_verification_result_present` | `unknown` | 没有结果声明不能证明结果不存在，默认 false 会把未登记结果误报为缺失。 |
| `attempt.completion_claim_pending` | `unknown` | 没有 pending 声明不能证明完成声明已审计，默认 false 会少提醒完成前检查。 |
| `attempt.terminal_coverage_complete` | 按 required 结果和 report 判定；终审阶段缺证据是 `false` | 没有 summary 时旧 false 可保留 gap；新 summary 必须覆盖 A/B/C 与按需 Safety，并满足 head / 同 ReviewRun 复用约束。 |
| `ticket.blocker_maybe_resolved` | `unknown` | 没有变化声明不能判断 blocker 是否已解除，默认 false 会少提醒重新评估。 |
| `ticket.no_longer_needed` | `unknown` | 没有处置声明不能授权退休 Ticket，默认 false 会少提醒需要的处置判断。 |
| `ticket.release_edge_rechecked` | `false` | 未声明时默认就是“尚未复核”，保留 release-edge 提醒属于 fail-closed。 |
| `ticket.review_required` | `unknown` | 没有要求声明不能证明不需要 reviewer，默认 false 会少提醒派发复核。 |
| `ticket.review_trigger` | `unknown` | 没有触发声明不能证明没有 review trigger，默认 false 会少提醒必要复核。 |
| `ticket.post_fix_regression_pending` | `unknown` | 没有 pending 声明不能证明回归检查已完成，默认 false 会少提醒复验。 |
| `evidence.sources_uniquely_decide` | `unknown` | 没有唯一性裁决不能证明单一来源足以决定路径，默认 false 会少提醒路由判断。 |
| `git.comparison_head_fixed` | `unknown` | 没有 fixed 声明不能区分未固定与未记录，默认 false 会误触发重开复核。 |
| `trail.anchor_mismatch` | `unknown` | 没有 mismatch 声明不能证明锚点一致，默认 false 会少提醒锚点恢复。 |
| `trail.bookkeeper_partial_write` | `unknown` | 没有 partial-write 声明不能证明写入完整，默认 false 会少提醒轨迹完整性检查。 |
| `trail.checkpoint_projection_race` | `unknown` | 没有 race 声明不能证明不存在竞态，默认 false 会少提醒 checkpoint 对账。 |
| `trail.checkpoint_refresh_needed` | `unknown` | 没有 refresh 声明不能证明不需要刷新，默认 false 会少提醒更新 checkpoint。 |
| `trail.envelope_valid` | `unknown` | 没有结构化 validity 声明不能证明 envelope 无效，默认 false 会把无 envelope 误报为 invalid。 |
| `trail.handoff_in_flight` | `unknown` | 没有 in-flight 声明不能证明 handoff 已结束，默认 false 会少提醒继续处理。 |
| `trail.handoff_recovery_needed` | `unknown` | 没有 recovery 声明不能证明 bootstrap 正常，默认 false 会少提醒恢复动作。 |
| `trail.handoff_target_corrected` | `unknown` | 没有 corrected 声明不能证明目标未修正，默认 false 会少提醒重发或取消。 |
| `trail.judgment_unfiled` | `unknown` | 没有 unfiled 声明不能证明判断已归档，默认 false 会少提醒补录判断。 |
| `trail.reviewer_unavailable` | `unknown` | 没有 unavailable 声明不能证明 reviewer 可用，默认 false 会少提醒重新派发。 |
| `finding.closure_review_pending` | `unknown` | 没有 pending 声明不能证明 closure review 已完成，默认 false 会少提醒收口复核。 |

历史行中的 `ticket.judgment_unfiled` 是唯一保留的 canonical alias，reader 会把它归一为
`trail.judgment_unfiled`；新行不得再写 alias。自由文本如 `carrier unavailable`、
`comparison-head-unfixed`、`recheck-release-edge` 或 `reviewer timeout` 不再改变事实值。

#### Projection validation result

`package.validate.projection_drift` 可以从一个只读、结构化的 validation result 得到。调用
形式为：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py render \
  --package <package> --validation-result '{"projection_drift":true}' --json
```

也可以把同样的 JSON object 放入 `--validation-result <file>` 指定的文件。object 只允许
`projection_drift` 布尔字段和可选的非空 `source` 字符串；未知字段或错误类型是 HF。传入
result 优先于 trail fact；没有传入时才读取 trail fact。该输入不启动
`impl_package_state.py`，也不解析 stdout/stderr，因此 `--at <commit>` 可以用同一个结构化
result 回放快照。

### 3.2 比较 row 的优先级

P0 是有序 list；P1-P5 是无序 set。只要合法 P0 candidate 存在，所有低层 candidate 都
进入 `suppressed_matches`。同一层没有 `selected` 时，输出 `parallel_matches`；因此“secondary”
不是事实不成立，而是排序后的可见性结果。

特别注意：`attempt.gate.comparison-mismatch` 现在只在 pass Gate 写入前检查；它要求
`attempt.completion_claim_pending=true`、`gate.present=false`，并把当前 HEAD 当作将传给
CLI 的 comparison commit。已有 `Verdict: pass` 的 Gate 不再满足该 row，也不会再被
`attempt.gate.terminal-frozen` 以“已太晚”的顺序压住。

### 3.3 package-level `situations.yaml` override

如果 package 根目录有 `situations.yaml`，只允许：

```yaml
extends: dev-with-track
skip: []
add: []
```

`skip` 只能引用已有 slug；`add` 必须是完整 situation mapping，且合并后仍要通过正式表的
version/stage/object/phase/priority/when parser 校验。未知字段、错误 extends、重复 slug 或
未覆盖 priority 都是 HF；这不属于某个输入 key 的 U/F 语义。

## 4. 从零构造一个最小合法 package

下面的“合法”以 `situation.py render` 能读取并产生确定事实为准；文件中的字段同时尽量
遵守 3.5 runtime 规定。示例使用 `initial`，且所有引用的 Ticket ID、Attempt ID 必须一致。

### 4.1 state.json：必须精确控制外层和每种 row 形状

#### 最小完整 state 示例

这是一个 state 合法、当前没有 evidence、没有 active checkpoint 的 package：

```text
<package>/
├─ .impl-package/state.json
└─ tickets/TKT-01.md
```

`.impl-package/state.json`：

```json
{
  "formatVersion": "3.5",
  "attempt": {
    "id": "initial",
    "plan": "plan.md"
  },
  "attemptHistory": [
    {
      "id": "initial",
      "plan": "plan.md",
      "lifecycle": "active",
      "gate": null,
      "executionRecord": "execution/initial/execution-record.md"
    }
  ],
  "predecessors": null,
  "tickets": {
    "TKT-01": {
      "state": "PENDING"
    }
  },
  "evidenceIndex": {},
  "activeCheckpoints": {}
}
```

`situation.py` 的硬 schema 要求是：顶层 key **恰好**为
`formatVersion`、`attempt`、`attemptHistory`、`predecessors`、`tickets`、`evidenceIndex`、
`activeCheckpoints`；`formatVersion` 必须是字符串 `"3.5"`；`attempt` 必须恰好只有
`id`、`plan`，两者都是非空字符串。生命周期只能放在 `attemptHistory[*].lifecycle`（完整
runtime 还要求该 row 的其他字段和 history 末项与 current attempt 对齐）。

顶层字段逐项对照：

| 字段 | 合法形状 | 非法形状 | 结果 |
| --- | --- | --- | --- |
| `formatVersion` | `"3.5"` | `3.5`、`"3.4"` | state invalid |
| `attempt` | `{ "id": "initial", "plan": "plan.md" }` | 额外增加 `lifecycle` 或缺 `id/plan` | state invalid；lifecycle 应在 history |
| `attemptHistory` | list；完整 runtime 的 row 为 `id/plan/lifecycle/gate/executionRecord` | `{}`、`null`；runtime 中缺字段或 history 不以 current attempt 结尾 | situation/parser 或 runtime invalid |
| `predecessors` | `null` 或非空 repository-relative package path list | 缺字段、空 list、非 path string、`None` 与路径混用 | state invalid |
| `tickets` | object，key 为 Ticket ID，value 使用下表状态形状 | `[]`、任意 value 缺 `state` 或含额外字段 | state invalid |
| `evidenceIndex` | object，按 `Ticket ID → claim ID → evidence list` 嵌套 | `[]`、未知 Ticket/claim、record 缺必需 evidence 字段 | state invalid |
| `activeCheckpoints` | object，key 为 `attempt` 或合法 `ticket:<id>`，value 使用下方三字段 | `[]`、未知 subject、value 缺 `next/blocker/evidence` 或含额外字段 | state invalid |

`tickets` 每个 value 的合法形状如下：

| state | value 必须的 key | 合法示例 | 非法示例 |
| --- | --- | --- | --- |
| `PENDING` | 只有 `state` | `{"state":"PENDING"}` | `{"state":"PENDING","lifecycle":"active"}` |
| `BLOCKED` | `state`、`evidence` | `{"state":"BLOCKED","evidence":"evidence/blocker.md"}` | 缺 `evidence`，或 `evidence: null` |
| `NEEDS-REVALIDATION` | `state`，可选 `evidence` | `{"state":"NEEDS-REVALIDATION"}` | 增加任意第三个字段 |
| `SATISFIED` | 只有 `state`、`acceptance`；acceptance 只有 `revision`、`environment` | `{"state":"SATISFIED","acceptance":{"revision":"5f299f3","environment":"fixture"}}` | `{"state":"SATISFIED","acceptance":{"commit":"..."}}` |
| `RETIRED` | `state`、`disposition`、`evidence`；若 superseded 再加 `successor` | `{"state":"RETIRED","disposition":"waived","evidence":"evidence/waive.md"}` | `waived` 带 successor；`superseded` 缺 successor |

`revision` 必须匹配 7–64 位十六进制 commit ID。situation parser 只检查形状；完整 runtime
还会调用 Git resolve。`BLOCKED`、`RETIRED` 和 revalidation 的 evidence 也必须是非空字符串；
完整 runtime 的 active 生命周期还会检查 repository-relative path 是否存在。

`evidenceIndex` 的合法最小 record 是：

```json
{
  "evidenceIndex": {
    "TKT-01": {
      "AC-1": [
        {
          "timing": "remaining-completion",
          "artifact": "evidence/tkt-01.md#claim",
          "revision": "5f299f3",
          "environment": "fixture",
          "conclusion": "supporting",
          "invalidatedBy": null
        }
      ]
    }
  }
}
```

`timing` 只能是 `early-falsification` 或 `remaining-completion`；`conclusion` 只能是
`supporting`、`contradictory`、`inconclusive`；artifact/revision/environment 都必须是非空
字符串；claim 必须已被同 Ticket 的 Stable claim ID 解析出来。`invalidatedBy` 可以省略，或
是字符串/null。`completion`、`early`、`remaining`、`pass` 都不是合法 timing。

active checkpoint 的合法最小形状是：

```json
{
  "activeCheckpoints": {
    "attempt": {
      "next": "continue TKT-01",
      "blocker": null,
      "evidence": ["evidence/context.md#anchor"]
    },
    "ticket:TKT-01": {
      "next": "verify AC-1",
      "blocker": "awaiting read-back",
      "evidence": ["evidence/context.md#ticket"]
    }
  }
}
```

subject 只能是 `attempt` 或存在于 `tickets` 的 `ticket:<id>`；value key 必须恰好是
`next`、`blocker`、`evidence`；`next` 必须非空字符串，`blocker` 是 null 或字符串，
`evidence` 是字符串 list。不要写 `next: null`，也不要把 anchor、target、order、lifecycle
塞进 checkpoint value；当前 parser 不消费这些字段，额外字段还会使 state invalid。

state 缺失或非法不是“没有处境”：`package.state_invalid` 会返回已知 true，通常抢到 P0；
state 合法但某个依赖它的 key 无法计算，则那些 key 返回 U。

### 4.2 tickets/*.md：ID、claim 和 typed dependency 是正文正则，不是标题语义

#### 最小完整 Ticket 示例

```markdown
# TKT-01 — 最小 Ticket

Ticket ID：TKT-01
Publication Status：Approved
Attempt ID：initial

## 验收标准

- AC-1：返回可观察的结果
  - Stable claim ID：`AC-1`
  - 证据时机：`remaining-completion`

## 安全不变量

- 租户边界保持不变
  - Stable claim ID：`INV-tenant-isolation`
  - 证据时机：`early-falsification`

## 阻塞依赖

- 无
```

推导器实际解析的部分是：

1. `Ticket ID：TKT-01` 或 ASCII 冒号版本；它必须等于 state 的 key。缺失、与文件
   state 不一致或同 Attempt 下找不到对应文件，会使 Ticket 无法参与 state 合法性。
2. `Attempt ID：initial`（也接受英文/中文长字段名的 regex 变体）；它必须等于
   `S.attempt.id`。有 active attempt 而 Ticket 不写该行，Ticket 会被标成 invalid。
3. claim 只认形如 `Stable claim ID：` 加反引号包裹 ID，或 ASCII 冒号版本。反例是只写
   `- **AC-1：** ...`：人能看懂，但 situation parser 的 `claims` 仍为空。claim 内容可以
   是任意不含反引号的非空字符串；以 `INV-` 开头的 claim（大小写不敏感）会进入安全不变量
   集合。
4. typed dependency 只在 heading **`## 阻塞依赖`** 或 **`## Blocking Dependencies`**
   到下一个 `##` 的 section 中解析。合法行是：
   `- implementation: TKT-01`、`- acceptance: TKT-01`、`- release: TKT-01`；kind
   大小写不敏感，target 是下一个空白前的字符串。无依赖用 `- 无` 或 `- none`。未知 target
   或 cycle 会使 state invalid；完整 runtime 还会拒绝 section 中格式错误的非空 dependency 行。

`situation.py` 不读取 Ticket 的 Publication Status，也不读取“证据时机”来校验 claim timing；
但完整 3.5 runtime 要求 Publication Status 为 `Draft` 或 `Approved`，每个 claim 有合法 timing
（安全不变量默认 `early-falsification`），且 evidence record 的 timing 与 claim timing 一致。
因此上面的完整写法是规范写法，不要利用 situation parser 的宽松之处省略这些行。

### 4.3 trail.jsonl：按统一 event schema 写入

新增 `dispatch`、`escape`、`fact` 和 `worker-return` 的主入口是 `trail append`：将事件 JSON 从 stdin 交给 `python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> trail append`；CLI 自动补全 `v`、`seq`、`ts`、`head`，调用方不要传入这些字段，并校验 `kind` 与 fact key。`kind=dispatch` 必须先运行 `python <impl-package-plugin-root>/scripts/situation.py render --package <package> --json`，将返回的 12 位 `digest` 填入 `situation_digest`；render 写入 `execution/<attempt>/situation-digest.json`，`trail append` 要求该凭据对应当前 `.impl-package/state.json`。checkpoint、handoff、judgment 和 Ticket 状态转换仍由各自 CLI 追加；老 package 或异常补写仍可按本节 schema 手写轨迹。

#### 最小完整 trail 示例

以下三行分别建立规范 fact、可消费的 result outcome 和一个仍在运行的 dispatch：

```jsonl
{"v":1,"seq":1,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"attempt.handoff_or_long_task","value":true}
{"timestamp":"2026-08-15T12:01:00Z","subject":"ticket:TKT-01","kind":"result","outcome":"EVIDENCE_GAP"}
{"timestamp":"2026-08-15T12:02:00Z","subject":"attempt","kind":"dispatch","outcome":"RUNNING","worker":"worker-01","returned":false}
```

`trail.jsonl` 每个非空行必须是 JSON object；空行忽略。坏 JSON 或非 object 不会让 CLI HF，
但会把整个 TrailView 置为 error，所有依赖该 trail 的 key 通常变为 U。未知 fact key 是
HF。规范 kind 的字段如下：

| kind/写法 | 为被当前 parser 消费所需的字段 | 说明 |
| --- | --- | --- |
| `fact` | `subject`、`key`、`value`、`ts`；key 必须属于 3.1 的闭合集合 | 同 key 按 `ts/seq/文件顺序` 取最新；旧 `facts` object 只作为兼容输入 |
| `decision` | `subject`、`seq/id/decision_id/decisionId` 至少一个；`chosen` 在 `attempt.in_flight` 中应含 `dispatch` 或 `sdd` | 旧 decision/result 配对继续识别 |
| `dispatch` | `subject`、`outcome=RUNNING`、`returned=false`、`worker`；建议带 id/seq；常规字段为 `situation_digest` | `returned=false` 直接建立 `trail.decision_without_result=true`；`situation_digest` 是本次派发所依据的 renderer 12 位 digest；老轨迹和手写轨迹缺失时由审计识别，不使 renderer 失败 |
| `escape` | `subject`、`deviation`、`reason`；可带 `of` 关联 dispatch/decision | 偏离或表外处境的结构化事件；缺少这些字段不使 renderer 失败 |
| `result` | `subject`、`outcome`；关闭 decision 可带 `of`/decision ID | 与 `worker-return` 统一为 result-like event |
| `worker-return` | `subject`、`outcome=EVIDENCE_SUFFICIENT`、`evidence` payload；payload 需有 artifact/claim/revision/environment 才能判 indexed | 建立 direct evidence；旧 `kind=result` 写法保持有效 |
| direct evidence | 在 result-like row 或 `ref/evidence/artifact/evidence_ref/direct_evidence` payload 中提供 artifact、claim、revision、environment | tuple 完整才能继续判 `evidence.indexed` |
| `handoff`、`checkpoint`、`judgment`、`integration`、`review` | 无新的业务 fact 语义；需要声明事实时使用 `kind=fact` | `checkpoint` 仍可用 `checkpoint:true` 或 chosen/situation 含 checkpoint 来计算 actions |

subject 必须和 key 的 scope 一致。比如 direct evidence 行应写
`"subject":"ticket:TKT-01"`；把它写成 `subject:"attempt"` 不会成为该 Ticket 的 evidence。

### 4.4 execution-findings.md：finding ID 是正式正则合同

#### 最小完整 finding 示例

```markdown
# Execution Findings

## FND-001 — evidence review

- Status: open
- Track C
- finding-source: reviewer
- Source recheck: pending
- Grade: P1
- Triage: pending
- Closure: awaiting reviewer
- Route: Decision D-001
```

正式 finding ID 合同是：在二级至六级 heading 中出现
`F-<token>`、`FND-<token>`、`FIND-<token>` 或 `FINDING-<token>`；前缀大小写不敏感，
结果转大写；`<token>` 以字母或数字开头，后续可含字母、数字、`.`、`_`、`-`。因此
`F-001`、`FND-001`、`FIND-001` 和 `FINDING-001` 都会建立对应的 finding subject。
仅写 `# F-001` 仍不会创建 finding block，因为一级 heading 不在扫描范围。heading 中出现
`finding`/`发现` 但没有 ID 时，实现可能按 block 顺序合成 `FINDING-1`，这是 fallback，
不是可依赖的 ID 合同。

可识别字段是：

- `Status: open`、`Status: closed`、`Status: resolved`、`Status: retired` 或
  `Status: complete`；closed/resolved/retired/complete 会使 grading、triage、closure
  三类 pending 变成 false。没有 Status 的 open block 仍可被解析，但不会因此自动关闭。
- `Track A`、`Track B`、`Track C`、`Track D`；没有 Track 时
  `finding.review_track` 是已知 `None`，不是未知。
- `finding-source: reviewer`、`finding-source: main-session` 或中文 `来源：...`；
  这是 finding block 内的来源字段。trail 的 `finding_source` 是另一套输入。
- `Source recheck: pending`（也可用 `source_recheck: pending` 或中文待复核/待重查）
  才会使 `finding.source_recheck_pending=true`。
- `Grade: P1/P2/P3/editorial` 使 open finding 不再因缺 Grade 被判
  `finding.grading_pending=true`；写 `grading_pending` 或 `待定级` 会保持 pending。
- `Triage: pending`、`未分流`、`待分流` 会使 triage pending；如果 open block 没有
  `Decision`、`Spec`、`Execution Record` 或 `Durable Delta` route marker，也会 pending。
- `Closure: awaiting reviewer` 或 `closure: pending` 会使 closure pending；closed status
  优先使其为 false。

文件缺失、读取错误或目标 finding ID 不存在时，finding-specific key 返回 U；文件存在但
没有可识别 heading 时，`findings.triage_pending` 对“所有 parsed findings”返回已知 false，
而具体 finding key 仍因找不到目标返回 U。finding heading 中的 ID 与 trail 的
`finding:<finding-id>` subject 必须使用同一 canonical 大写 ID。

### 4.5 gate.md：Verdict 行是固定格式

#### 最小完整 Gate 示例

```markdown
# Gate

- Verdict: blocked
- Attempt: initial
- Comparison commit: 5f299f345d14389d1520d68e84eec52342d16564

## Durable Deltas

- No durable delta: this fixture intentionally remains blocked.
```

`situation.py` 识别的 Verdict 行必须独占一行，格式为
`- Verdict: pass|fail|blocked|defer|undecided`，也接受 `- 判定：...`；解析结果转小写。
可选的 comparison 行必须是 `- Comparison commit: <7-64 位十六进制>` 或中文变体。
`## Durable Deltas` 下至少有一行 `- ...`，且不能是 `- none` 或 `- Reason: none`，
才会使 `gate.stage7_complete=true`。上例因此同时提供了可识别的 blocked verdict 和
meaningful durable-delta bullet。

没有 `gate.md` 时，`gate.present=false`、`gate.terminal=false`，`gate.verdict=U`；文件存在但
Verdict 缺失、拼写错误或值不在五个枚举内时，`gate.verdict` 是 U。`blocked` 和 `undecided`
不是 terminal；`pass`、`fail`、`defer` 才是 terminal。完整 runtime 还会检查 Attempt、
comparison commit、Durable Deltas 以及其它 Gate 内容，并不把 renderer-only 的
`undecided` 当作可发布 Gate 状态。

## 5. 三个端到端最小 package

下面三套都只包含 situation renderer 的输入文件，目录内容是完整的；`plan.md`、`spec.md`、
`progress.md` 和 Execution Record 若要通过完整 runtime validate，仍须按 3.5 runbook 补齐。
三个示例中的 `5f299f345d14389d1520d68e84eec52342d16564` 是本仓库 2026-08-15 的 HEAD；复制到
别的 Git repository 时，把它替换为该 repository 中实际存在的 `git rev-parse HEAD`。

### 5.1 P0 record：anchor mismatch

应命中：`attempt.record.anchor-mismatch`（P0）。

目录：

```text
p0-anchor-mismatch/
├─ .impl-package/state.json
├─ tickets/TKT-01.md
└─ execution/initial/trail.jsonl
```

`.impl-package/state.json`：

```json
{
  "formatVersion": "3.5",
  "attempt": {"id": "initial", "plan": "plan.md"},
  "attemptHistory": [{"id": "initial", "plan": "plan.md", "lifecycle": "active", "gate": null, "executionRecord": "execution/initial/execution-record.md"}],
  "predecessors": null,
  "tickets": {"TKT-01": {"state": "PENDING"}},
  "evidenceIndex": {},
  "activeCheckpoints": {}
}
```

`tickets/TKT-01.md`：

```markdown
# TKT-01 — Anchor fixture

**Ticket ID：** TKT-01
**Publication Status：** Approved
**Attempt ID：** initial

## 验收标准
- AC-1：anchor validation is observable
  - Stable claim ID：`AC-1`
  - 证据时机：`remaining-completion`

## 阻塞依赖
- 无
```

`execution/initial/trail.jsonl`：

```json
{"v":1,"seq":1,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"trail.anchor_mismatch","value":true}
```

该 package state 合法；显式 fact 让 `trail.anchor_mismatch=true`。没有 Gate，不会触发
`gate.terminal`；没有 active checkpoint，不会触发 `attempt.record.session-resumed` 或
`checkpoint-refresh`。低层可能出现在 diagnostics/suppressed 中，但 P0 primary 是 anchor mismatch。

### 5.2 P2 worker return：invalid fixer envelope

应命中：`finding.fix.worker-envelope-invalid`（P2）。

目录：

```text
p2-worker-envelope-invalid/
├─ .impl-package/state.json
├─ execution-findings.md
└─ execution/initial/trail.jsonl
```

`.impl-package/state.json`：

```json
{
  "formatVersion": "3.5",
  "attempt": {"id": "initial", "plan": "plan.md"},
  "attemptHistory": [{"id": "initial", "plan": "plan.md", "lifecycle": "active", "gate": null, "executionRecord": "execution/initial/execution-record.md"}],
  "predecessors": null,
  "tickets": {},
  "evidenceIndex": {},
  "activeCheckpoints": {}
}
```

`execution-findings.md`：

```markdown
# Execution Findings

## FND-001 — fixer envelope

- Status: open
- Grade: P1
```

`execution/initial/trail.jsonl`：

```json
{"timestamp":"2026-08-15T12:10:00Z","subject":"finding:FND-001","kind":"fix-return","worker_mode":"fix","envelope_valid":false}
```

`finding:FND-001` context 中 `trail.last_worker_mode=fix` 且 `trail.envelope_valid=false`，
所以命中目标行。用 `F-001` 会没有 finding context；用只有
`{"envelope":{"status":"invalid"}}` 也不等于 `envelope_valid=false`，应直接写布尔字段，
或写 `kind=fact` 的 `trail.envelope_valid`。

### 5.3 P4 accept：satisfiable

应命中：`ticket.accept.satisfiable`（P4）。

目录：

```text
p4-satisfiable/
├─ .impl-package/state.json
├─ tickets/TKT-01.md
├─ evidence/tkt-01.md
└─ gate.md
```

`.impl-package/state.json`：

```json
{
  "formatVersion": "3.5",
  "attempt": {"id": "initial", "plan": "plan.md"},
  "attemptHistory": [{"id": "initial", "plan": "plan.md", "lifecycle": "active", "gate": {"verdict": "blocked", "commit": "5f299f345d14389d1520d68e84eec52342d16564"}, "executionRecord": "execution/initial/execution-record.md"}],
  "predecessors": null,
  "tickets": {
    "TKT-01": {
      "state": "PENDING"
    }
  },
  "evidenceIndex": {
    "TKT-01": {
      "AC-1": [{
        "timing": "remaining-completion",
        "artifact": "evidence/tkt-01.md#claim",
        "revision": "5f299f345d14389d1520d68e84eec52342d16564",
        "environment": "fixture",
        "conclusion": "supporting",
        "invalidatedBy": null
      }]
    }
  },
  "activeCheckpoints": {}
}
```

`tickets/TKT-01.md`：

```markdown
# TKT-01 — Acceptance fixture

**Ticket ID：** TKT-01
**Publication Status：** Approved
**Attempt ID：** initial

## 验收标准
- AC-1：claim is supported
  - Stable claim ID：`AC-1`
  - 证据时机：`remaining-completion`

## 阻塞依赖
- 无
```

`evidence/tkt-01.md`：

```markdown
# Evidence

<a id="claim"></a>
Supporting evidence for AC-1.
```

`gate.md`：

```markdown
# Gate
- Verdict: blocked
- Attempt: initial
- Comparison commit: 5f299f345d14389d1520d68e84eec52342d16564
- Reason: acceptance is ready but Gate remains blocked for this fixture.
```

这里 `evidence.all_required_claims_supported=true`，因为 PENDING Ticket 的 evidence group
提供了一个可解析的当前 HEAD revision；没有 acceptance dependency，所以
`ticket.acceptance_edge_released=true`；Git 可 resolve，所以
`ticket.acceptance_revision_parseable=true`。`gate.md` 使用 blocked 以避免无 Gate 时额外命中
`attempt.gate.verdict-undecided`。该 package 的 primary 是 `ticket.accept.satisfiable`。

## 6. 形状缺陷清单和修复取舍

下面按“独立的输入形状/边界问题”计数，不按受影响 fixture 数量重复计数，共 **10 条**。
“建议改实现”只计需要改变 parser 的事实解释；其余先通过本合同固定文档/fixture 形状。

| # | 形状缺陷 | 证据与影响 | 建议 |
| ---: | --- | --- | --- |
| 1 | `attempt.lifecycle` 放错层 | 3.5 state 的 `attempt` 只允许 `id/plan`；lifecycle 属于 `attemptHistory`。独立复验的 24 个带 state fixture 都因此 invalid，8 条被标为“期望造错”的 fixture 直接受影响 | 改文档/fixture，不改实现；state parser 与 current-state/runtime 已一致 |
| 2 | active checkpoint 没有 anchor/target/order 的结构化槽位 | checkpoint value 只能是 `next/blocker/evidence`；anchor mismatch、handoff target/order 不进入 checkpoint value | 文档固定这类事实必须写入 R 的 typed fact；不扩展 checkpoint schema |
| 3 | Ticket 的隐式正则前置条件没有在 situation 合同中公开 | `Attempt ID`、`Stable claim ID`、heading 名称和 typed dependency 才会建立 TicketInfo；独立 fixture 的 `AC-1` bullet、缺 Attempt ID 会让 Ticket 不可消费 | 改文档；可选地让实现兼容普通 `AC-1` heading，但不能继续让正则成为唯一未公开合同 |
| 4 | evidence timing 的同一语义出现两套词 | state/runtime 只认 `early-falsification`、`remaining-completion`；复验 fixture 使用 `completion`，导致 contradictory、acceptance-edge、satisfiable 的 evidence 不能构成合法 state | 改文档和 fixture；不要把 `completion` 默认为合法别名，除非另行修改 runtime 合同 |
| 5 | finding ID 前缀是偶然白名单 | parser 原来不认 `F-001`，导致 closure/envelope 两条 finding 无法建立 subject | **已改实现**：正式接受 `F-*`，并在 4.4 固定完整 finding ID 正则合同 |
| 6 | worker direct evidence 的 kind 与自然返回形状不一致 | 人写 `worker-return + EVIDENCE_SUFFICIENT + evidence`，旧 parser 只扫描 `kind=result` | **已改实现**：`worker-return` 与 `result` 统一为 result-like；旧 `result` 继续兼容 |
| 7 | worker liveness 的 kind 与自然 dispatch 形状不一致 | `dispatch/RUNNING/returned=false` 已充分表达未返回，旧 parser却只收 `decision` 与 result 配对 | **已改实现**：直接消费 dispatch liveness，并保留旧 decision/result 配对 |
| 8 | 多个业务 flag 只有未公开的显式 boolean 入口 | `handoff_or_long_task`、manual verification、review trigger、sources uniquely decide 等 key 不能从产物可靠推导 | 本轮用文档和封闭 fact 通道固定 owner 声明形状；不改 state schema |
| 9 | projection drift 不是 package 输入字段 | 旧实现执行当前 worktree 的另一个 CLI 并解析错误文本，`--at` 快照被迫 U | **已改实现**：renderer 接受结构化 read-only validation result；不执行外部 CLI、不解析错误文本，`--at` 可回放 |
| 10 | availability/recheck 事实依赖自由文本 marker，语义边界不封闭 | carrier/evidence/comparison/recheck 可能被相邻 prose、chosen 或 blocker 文案误导 | **已改实现**：相关事实全部走封闭 typed fact；删除负向 substring 和 release-edge chosen fallback |

第 2 条仍由文档约束 checkpoint 不得扩展字段；第 8 条已由本轮 fact 合同落地；第 5、6、7、9、10 条
是本轮按 Owner 决定改实现的 5 条。所有新 fact key 还必须通过第 3.1 的封闭集合。

### 复验中 11 条“期望造错”的再归因

按 fixture 计，有 **10/11 条**包含真实输入形状问题：

- `p0-session-resumed`、`p0-terminal-frozen`、`p1-all-edges-held`、`p2-reviewer-unavailable`、
  `p3-comparison-head-unfixed`、`p3-contradictory-unresolved`、`p4-acceptance-edge-held`、
  `p4-satisfiable` 的 state 都把 `lifecycle` 放进了非法的 `attempt`；其中后三条还把
  evidence timing 写成非法的 `completion`。
- `p2-closure-awaiting`、`p2-worker-envelope-invalid` 原先用不被识别的 `F-001`；本轮 regex
  已建立对应 finding subject，后续 envelope 语义仍按 4.3 的 event 字段合同判断。
- `p0-terminal-frozen` 的 expected primary 本身是对的，但非法 state 还制造了不应有的
  `package.record.state-missing` secondary，因此它同时属于形状误报。

剩下的 **1/11** 是 `p4-comparison-mismatch`：`Gate Verdict: pass` 按当前优先级必然命中
P0 `attempt.gate.terminal-frozen`，expected 却把它列入 `must_not_hit`；这是 priority/语义
边界错误，不是输入 shape 错误。上述 10/11 不是说所有 expected primary 都正确，而是说
“造不出所依赖的合法事实形状”是主要失败原因。

## 7. 两个已知失效 key：修复后的规范形状

### 7.1 `ticket.record.evidence-unfiled`

**应有行为**：下列自然返回应该建立 `trail.direct_evidence_returned=true`：

```json
{"subject":"ticket:TKT-01","kind":"worker-return","outcome":"EVIDENCE_SUFFICIENT","evidence":{"artifact":"evidence/returned.md#result","claim":"AC-1","revision":"5f299f3","environment":"fixture"}}
```

**当前行为（修复后）**：renderer 将 `kind=worker-return` 与 `kind=result` 归一为
result-like event，因此该行建立 `trail.direct_evidence_returned=true`。payload 未登记时，
`evidence.indexed=false`，可以进入 `ticket.record.evidence-unfiled`。

旧写法仍然合法并保持同样语义：

```json
{"subject":"ticket:TKT-01","kind":"result","outcome":"EVIDENCE_SUFFICIENT","evidence":{"artifact":"evidence/returned.md#result","claim":"AC-1","revision":"5f299f3","environment":"fixture"}}
```

两种 kind 都是正式兼容形状；新 worker 返回优先使用 `worker-return`，不要为了适配旧
parser 把它改写成 `result`。

### 7.2 `attempt.readiness.worker-still-running`

**应有行为**：下列 dispatch liveness 应建立 `trail.decision_without_result=true`：

```json
{"subject":"attempt","kind":"dispatch","outcome":"RUNNING","worker":"worker-01","returned":false}
```

**当前行为（修复后）**：`dispatch` 的 `outcome=RUNNING` 且 `returned=false` 直接建立
`trail.decision_without_result=true`；如果 dispatch 带 id，后续 result-like 行可以通过
`of/dispatch_id/decision...` 关闭它。旧的 decision/result 配对仍继续识别。

旧写法仍然合法并保持同样语义：

```json
{"subject":"attempt","kind":"decision","seq":1,"chosen":"dispatch-worker"}
```

且不要给它配匹配的 result 行；新写法应优先使用带 `returned=false` 的结构化 dispatch，
因为它明确记录了 liveness，而不依赖“缺少 result”这一负向推断。

## 8. 验收自问与剩余缺口

一个不读 `situation.py` 的人现在可以：

1. 用第 4.1 的 state 外层、Ticket row、evidence record 和 checkpoint 形状构造一个不触发
   `package.state_invalid` 的 package；
2. 用第 4.2 的正则字段和第 4.3 的 subject/kind 规则让 Ticket、evidence、worker、handoff
   和 checkpoint facts 进入正确 context；
3. 用第 4.4/4.5 的 heading/line 形式构造 finding 和 Gate；
4. 用第 2 节的 66 行逐项反查 source、expected value、缺失语义和 slug，并按第 5 节照抄
   三个端到端目录。

仍不能仅靠本文把 `manual` situation（`ticket.route.multiple-business-outcomes`、
`ticket.route.sources-conflicting`）构造为自动 primary；它们本来就没有机械 when key，只能
进入 `manual` 由主控做语义判断。

projection drift 已改为结构化 validation result；owner 声明型业务事实的 ownership 统一落在
trail 的 fact 通道，陈旧性只通过 `ts` 暴露，不由 renderer 自行过期。本文剩余的边界是
`manual` row 的语义判断，以及完整 runtime 对 plan/spec、Publication Status、artifact、Git
revision 和 projection 的额外校验。

## 9. 56 行 `slug → when` 完整映射

前面的第 2 节解释每一个 `when` key 如何产生值；本节把正式
`situations.yaml` 的 56 行逐行展开。这里的“命中”严格指：在相应 subject context
中，表格第二列的所有条件都比较为真。条件之间是 AND，不是“满足其中一个”。

表中 `U key` 列列出该行的全部判据 key：其中任意一个变成 unknown，整行就是
`undetermined`，不会成为 active match；即使另一个 key 已知 false，也不会把该行当作
false。key 何时为 U 仍以第 2 节为准。`HF` 是 package/table/CLI 层硬失败，不是这张表
里的普通 U。

scope 也必须同时满足：`package.*` 行在 package context 评估一次，`attempt.*`、
`gate.*`、`git.*`、`findings.*`、`intake.*` 行在 attempt context 评估，`ticket.*` 和
`evidence.*` 行对每一个已解析 Ticket 分别评估，`finding.*` 行对每一个已解析 finding
分别评估。`trail.*` 使用当前 row 的 subject scope；attempt-level 的少数 parser 会
明确扫描全部 attempt trail，见第 2 节。没有对应的合法 Ticket/finding context 时，
不要把“文件里有一行文字”当成该 row 已经具备 subject。

### 9.1 P0：有序的 fail-closed 层

P0 内部顺序就是 YAML 的顺序。P0 有多个 active match 时，renderer 取最前面的一个作为
`selected`，其余 P0 match 放入同层 `other_matches`；所有 P1-P5 match 都被压到
`suppressed_matches`。因此下表的序号也属于最终呈现规则的一部分。

| 顺序 | slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| ---: | --- | --- | --- | --- |
| 1 | `attempt.gate.terminal-frozen` | `gate.terminal = true` | `gate.terminal` | `gate.md` 必须存在且 Verdict 可解析为 `pass`、`fail` 或 `defer`；缺 Gate 是已知 false，坏 Verdict 是 U。它会先于所有低层 row 抢占。 |
| 2 | `package.record.state-missing` | `package.state_invalid = true` | 无（该 parser 总能给出已知 true/false；外围 package 不存在仍可 HF） | 缺失或不合法 state 都是已知 true，包括 schema、Ticket、evidence、checkpoint 交叉校验失败；不要把它当作“没有 state 才命中”。 |
| 3 | `package.record.projection-drift` | `package.validate.projection_drift = true` | `package.validate.projection_drift` | 必须有结构化 `--validation-result` 或 attempt-scoped typed fact，且值为 true；错误的 validation result 是 HF，不是该 key 的 U。 |
| 4 | `attempt.record.anchor-mismatch` | `trail.anchor_mismatch = true` | `trail.anchor_mismatch` | 当前正式入口是 attempt scope 的 typed fact；普通 prose 或相邻 marker 不建立该事实。 |
| 5 | `attempt.record.handoff-recovery-needed` | `trail.handoff_recovery_needed = true` | `trail.handoff_recovery_needed` | 必须有 attempt scope 的 typed fact；缺声明是 U，不是“恢复正常”的 false。 |
| 6 | `attempt.record.handoff-target-corrected` | `trail.handoff_target_corrected = true` | `trail.handoff_target_corrected` | 必须有 attempt scope 的 typed fact；`chosen` 或 prose 中写 corrected 不再自动命中。 |
| 7 | `attempt.record.session-resumed` | `attempt.active_checkpoint_present = true` AND `trail.actions_since_checkpoint = 0` | `attempt.active_checkpoint_present`、`trail.actions_since_checkpoint` | 只需要合法 state 中的 `activeCheckpoints.attempt`，以及 checkpoint 后没有动作。显式 `attempt.session_resumed` 不再是判据；有 marker 时检查 marker 后的行数，没有 marker 时忽略兼容性的 session declaration、但其它 typed fact/action 会使计数大于 0。 |
| 8 | `attempt.record.checkpoint-missing` | `attempt.handoff_or_long_task = true` AND `attempt.active_checkpoint_present = false` | `attempt.handoff_or_long_task`、`attempt.active_checkpoint_present` | 需要 attempt fact 明确声明 handoff/long task；合法 state 中不得有 `activeCheckpoints.attempt`。缺 handoff fact 是 U，不会自动当作 false。 |
| 9 | `attempt.record.checkpoint-refresh` | `attempt.active_checkpoint_present = true` AND `trail.checkpoint_refresh_needed = true` | `attempt.active_checkpoint_present`、`trail.checkpoint_refresh_needed` | checkpoint 必须先在合法 state 中存在，refresh 必须由 typed fact 声明；旧 checkpoint prose 不再补出 refresh fact。 |
| 10 | `attempt.record.handoff-in-flight` | `trail.handoff_in_flight = true` | `trail.handoff_in_flight` | 必须有 attempt scope 的 typed fact；handoff/relay/continuation 字样本身不够。 |
| 11 | `ticket.record.evidence-unfiled` | `trail.direct_evidence_returned = true` AND `evidence.indexed = false` | `trail.direct_evidence_returned`、`evidence.indexed` | 必须在当前 Ticket subject 下有 `result` 或 `worker-return` 的 direct-evidence payload；要让 `evidence.indexed` 确定为 false，payload 还必须能解析出完整的 artifact、claim、revision、environment tuple，但该 tuple 不得出现在未 invalidated 的 `evidenceIndex` 中。payload 缺 link 字段会使第二个 key U。 |
| 12 | `ticket.record.judgment-unfiled` | `trail.judgment_unfiled = true` | `trail.judgment_unfiled` | 必须在当前 Ticket subject 下声明 typed fact；旧 alias 只作兼容读取，未知 fact key 仍会 HF。 |

### 9.2 P1：准入与 worker liveness

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `attempt.record.handoff-due` | `attempt.compaction_pressure_high = true` | `attempt.compaction_pressure_high` | 需要调用方传入 `--compaction-pressure` 的合法 JSON 且 `high=true`；缺参数是 U，不命中该行；它位于 P1，因此 P0 完整性行仍先显示。默认动作是在主控选定的下一个 recovery checkpoint 后交接，不中断当前单元。 |
| `attempt.record.ticket-boundary-handoff` | `trail.last_ticket_terminal_transition = true` AND `attempt.has_pending_ticket = true` | `trail.last_ticket_terminal_transition`、`attempt.has_pending_ticket` | 当前活动 trail 的最后一个 CLI Ticket 状态转换必须进入 `SATISFIED` 或 `RETIRED`，且 state 中仍有 `PENDING` Ticket；这是交接机会，不阻断当前单元。它与 pressure-driven `attempt.record.handoff-due` 独立，不要求 compaction pressure。 |
| `attempt.record.trail-rotation-due` | `trail.last_ticket_terminal_transition = true` AND `attempt.has_pending_ticket = true` | `trail.last_ticket_terminal_transition`、`attempt.has_pending_ticket` | 与 Ticket 边界交接同一机械窗口；动作入口是显式 `recovery checkpoint --handoff`，不把普通 checkpoint 当作轮换触发，也不读取 pressure key。state 先提交，CLI 随后写 `kind=handoff` 并轮换活动 trail；轮换失败只 warning。轮换后 renderer 只看新的 `trail.jsonl`，归档由 audit 读取。 |
| `attempt.readiness.worker-still-running` | `trail.decision_without_result = true` | `trail.decision_without_result` | trail 必须可读，并且存在未配 result 的 decision，或 `kind=dispatch`、`outcome=RUNNING`、`returned=false` 的 open dispatch。带 id 的 dispatch 只有匹配 result 才关闭；无 id 的 running dispatch 始终保持 open。 |
| `attempt.readiness.all-edges-held` | `attempt.ready_ticket_count = 0` AND `attempt.has_pending_ticket = true` AND `attempt.implementation_edges_held = true` | `attempt.ready_ticket_count`、`attempt.has_pending_ticket`、`attempt.implementation_edges_held` | 需要合法 state、每个 Ticket 文件都能解析、implementation dependency 的目标状态都能判定，并且至少有一个 `PENDING` Ticket；不能只在“看起来没有 ready Ticket”时手写期望。后两个条件在当前实现中有推导重叠，但 row 仍会逐项比较。 |
| `attempt.readiness.multiple-ready-tickets` | `attempt.ready_ticket_count > 1` AND `attempt.in_flight = false` | `attempt.ready_ticket_count`、`attempt.in_flight` | 需要完整 Ticket/dependency 图，且 open dispatch 已被明确排除。没有 trail 或无法证明没有 in-flight 时第二个 key 是 U，不是 false；“有两个 pending Ticket”也不等于有两个 ready Ticket。 |
| `ticket.readiness.blocker-maybe-resolved` | `ticket.state = "BLOCKED"` AND `ticket.blocker_maybe_resolved = true` | `ticket.state`、`ticket.blocker_maybe_resolved` | 当前 Ticket 必须可由 state 和 Ticket 文件建立 context；resolved 需要 typed fact 或兼容的 Ticket 正文声明。`BLOCKED` 本身不会把 blocker 自动变成 resolved。 |
| `attempt.readiness.integration-carrier-unavailable` | `attempt.integration_carrier_available = false` | `attempt.integration_carrier_available` | 必须有 attempt scope 的布尔 fact `false`；没有 fact 是 U，不能用“没找到 carrier”这件事反推 false。 |

### 9.3 P2：未完成动作、调查和 review 返回

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `finding.fix.worker-envelope-invalid` | `trail.last_worker_mode = "fix"` AND `trail.envelope_valid = false` | `trail.last_worker_mode`、`trail.envelope_valid` | 必须有合法 finding context，且当前 finding subject 的最后 worker mode 是 `fix`；envelope 的 false 必须来自 typed fact 或结构化字段。缺 envelope 不是 false，而是 U。 |
| `ticket.implement.worker-incomplete-first` | `trail.last_outcome = "INCOMPLETE"` AND `trail.incomplete_count = 1` AND `trail.last_worker_mode = "implement"` | `trail.last_outcome`、`trail.incomplete_count`、`trail.last_worker_mode` | 三者都从当前 Ticket scope 读取；`incomplete_count=1` 是从末尾连续 result/worker-return 事件精确计数，不是“历史上曾经有一次 incomplete”。 |
| `ticket.implement.worker-incomplete-second` | `trail.last_outcome = "INCOMPLETE"` AND `trail.incomplete_count = 2` AND `trail.last_worker_mode = "implement"` | `trail.last_outcome`、`trail.incomplete_count`、`trail.last_worker_mode` | 必须是末尾连续两个 result-like `INCOMPLETE`，中间不能有另一个 result-like outcome；它不会与 first row 因“至少一次 incomplete”同时命中。 |
| `ticket.implement.worker-blocked` | `trail.last_outcome = "BLOCKED"` AND `trail.last_worker_mode = "implement"` | `trail.last_outcome`、`trail.last_worker_mode` | 当前 Ticket 的最后有效 outcome 必须精确为大写 `BLOCKED`，worker mode 必须能解析为 `implement`；缺 trail 是 U。 |
| `ticket.investigate.no-carrier` | `ticket.state = "PENDING"` AND `ticket.investigation_carrier_present = false` AND `ticket.investigation_context_clear = true` AND `evidence.count = 0` | `ticket.state`、`ticket.investigation_carrier_present`、`ticket.investigation_context_clear`、`evidence.count` | carrier 只由当前 Ticket 的 investigate 派发/结果或 `timing=early-falsification` evidence 建立；其它 typed fact 表示已有明确处境，不让该 P2 row 越权抢占；仍要求 evidenceIndex 完全为空以避开已进入 acceptance/补证窗口的 Ticket。 |
| `ticket.investigate.evidence-gap` | `trail.last_outcome = "EVIDENCE_GAP"` | `trail.last_outcome` | 当前 Ticket scope 的最后 result-like outcome 必须精确为 `EVIDENCE_GAP`；只写普通 prose 或另一个 subject 的 outcome 不能保证该 row 命中。 |
| `finding.fix.reviewer-returned` | `trail.last_outcome = "FINDING"` AND `trail.finding_source = "reviewer"` | `trail.last_outcome`、`trail.finding_source` | 需要解析出的 finding ID 与 trail subject 一致；`finding-source: reviewer` 写在 finding block 里不等同于 trail 的 `finding_source=reviewer`，本 row 看的是 trail。 |
| `finding.review.closure-awaiting` | `finding.closure_review_pending = true` | `finding.closure_review_pending` | finding block 必须存在且不是 closed/resolved/retired/complete，或有显式 closure-pending fact/marker；缺 findings 文件或 finding ID 不存在为 U。 |
| `attempt.review.reviewer-unavailable` | `trail.reviewer_unavailable = true` | `trail.reviewer_unavailable` | 必须有 attempt scope typed fact；`timeout`、`unavailable` 等自由文本不再触发。 |
| `ticket.review.awaiting-reviewer` | `trail.last_outcome = "DONE"` AND `ticket.review_required = true` | `trail.last_outcome`、`ticket.review_required` | 必须同时有精确的 `DONE` 和 reviewer requirement。requirement 可来自 typed fact、当前 Ticket trail 的 `review_state=PENDING_REVIEW` 或 Ticket 正文 marker；但 trail 缺失时 parser 会先返回 U，不会仅凭 Ticket prose 让该 row 命中。 |
| `ticket.review.required-trigger` | `ticket.review_trigger = true` | `ticket.review_trigger` | 需要当前 Ticket scope 的显式布尔 trigger；不会从 outcome 或 `review_state` 自动推导。 |
| `finding.fix.main-session-discovered` | `trail.finding_source = "main-session"` | `trail.finding_source` | 需要合法 finding context 和当前 finding trail 的 source 字段；finding 文档里的来源字段不替代 trail source。 |
| `finding.review.source-recheck-pending` | `finding.review_track = "C"` AND `finding.source_recheck_pending = true` | `finding.review_track`、`finding.source_recheck_pending` | 必须有可解析 finding block，且 block 中是 Track C 与 source-recheck pending；没有 Track 会得到已知 None，不会命中 C。 |

### 9.4 P3：验证、返工和路由

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `ticket.verify.contradictory-unresolved` | `evidence.contradictory_unresolved = true` | `evidence.contradictory_unresolved` | 当前 Ticket、state/evidenceIndex 和 acceptance pair 必须可读；只在该 pair 的 required claim 中存在 active `contradictory`/`inconclusive` 记录时命中。其它 revision 或非当前 required claim 的冲突不再触发。 |
| `ticket.verify.safety-invariant-unfalsified` | `ticket.safety_invariant_unfalsified = true` | `ticket.safety_invariant_unfalsified` | Ticket 必须解析出一个以 `INV-` 开头的 Stable claim ID，且至少一个此类 claim 没有 active evidence record；没有安全 claim 是已知 false，不是 U。 |
| `attempt.review.comparison-head-unfixed` | `git.comparison_head_fixed = false` | `git.comparison_head_fixed` | 必须有 attempt scope typed fact `false`；缺 fact 是 U。即使该 row 命中，仍要检查 P2 `ticket.investigate.no-carrier` 是否抢先。 |
| `attempt.verify.integration-evidence-unavailable` | `attempt.integration_evidence_available = false` | `attempt.integration_evidence_available` | 必须有 attempt scope typed fact `false`；它只描述 evidence carrier，不会因为 carrier fact 缺失而自动命中。 |
| `ticket.rework.evidence-conflict` | `ticket.state = "SATISFIED"` AND `evidence.new_claim_conflict = true` | `ticket.state`、`evidence.new_claim_conflict` | 当前实现把 `new_claim_conflict` 建立在 SATISFIED Ticket 的 active contradictory/inconclusive evidence 上；需要合法 state/evidence。非 SATISFIED 会使第二个事实已知 false。 |
| `ticket.rework.revision-diverged` | `git.acceptance_revision_diverged = true` AND `git.head_advanced_since_last_trail = true` AND `git.accepted_seam_changed = true` | `git.acceptance_revision_diverged`、`git.head_advanced_since_last_trail`、`git.accepted_seam_changed` | `git.accepted_seam_changed` 先消费显式布尔覆盖；缺省时机械比较 acceptance revision 到当前 HEAD 的 diff。只有全部改动都在 `docs/` 下或后缀为 `.md` 才为 false；存在其它路径才为 true。拿不到或无法解析 acceptance revision、无法读取/得到空 diff 时为 U。 |
| `ticket.rework.revalidation-pending` | `ticket.state = "NEEDS-REVALIDATION"` | `ticket.state` | 必须在 state 中为当前 Ticket 建立合法 row；仅在正文写“待重验”不会改变 state。 |
| `ticket.disposition.retire-undecided` | `ticket.no_longer_needed = true` | `ticket.no_longer_needed` | 需要显式 true 或精确的 Ticket 正文正向声明；缺声明是 U，不是 false，因为“不再需要”本身是业务判断。 |
| `ticket.route.multiple-business-outcomes` | `when: manual`，无机械条件 | 无 | 不会被 parser 依据字段自动命中；主控只有在发现多个合理业务结果且机械输入无法裁决时，才主动进入该 manual row。 |
| `ticket.route.sources-conflicting` | `when: manual`，无机械条件 | 无 | 不会因 evidence 数量、文本里的 conflict 字样自动命中；主控需判断来源是否缺失、含糊或冲突后主动进入。 |
| `ticket.route.sources-uniquely-decide` | `evidence.sources_uniquely_decide = true` | `evidence.sources_uniquely_decide` | 需要当前 Ticket scope 的显式布尔 fact；不会从“只有一条 evidence”自动推导来源足以决定实现路径。 |
| `attempt.rework.contract-changed` | `git.contract_changed_since_last_trail = true` | `git.contract_changed_since_last_trail` | trail 中必须有可比较的旧 `head`，且 `head..HEAD` 可读并命中 `plan.md`、`spec.md`、`contract-design.md`、`decision.md` 或 `tickets/` 路径；没有旧 head 是 U。 |

### 9.5 P4：acceptance 与全局收口

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `ticket.accept.acceptance-edge-held` | `evidence.count > 0` AND `ticket.acceptance_edge_released = false` | `evidence.count`、`ticket.acceptance_edge_released` | 必须有至少一条 evidenceIndex 记录（包含已 invalidated 记录的计数也算），并且当前 Ticket 的 typed `acceptance` dependency 至少有一条尚未释放。没有 acceptance edge 时 `all([])` 是 true，不能用“没有依赖”构造 held。 |
| `ticket.accept.release-edge-unchecked` | `ticket.acceptance_conditions_satisfied = true` AND `ticket.release_edge_present = true` AND `ticket.release_edge_rechecked = false` | `ticket.acceptance_conditions_satisfied`、`ticket.release_edge_present`、`ticket.release_edge_rechecked` | 只对真实存在 release dependency 的 Ticket 提醒；acceptance conditions 需要同一 revision/environment 下所有 required claims supporting 且没有 active contradictory/inconclusive；本 row 是流程提示，CLI 不检查 `release_edge_rechecked` fact。 |
| `ticket.accept.satisfiable` | `evidence.all_required_claims_supported = true` AND `evidence.contradictory_unresolved = false` AND `ticket.acceptance_edge_released = true` AND `ticket.acceptance_revision_parseable = true` | `evidence.all_required_claims_supported`、`evidence.contradictory_unresolved`、`ticket.acceptance_edge_released`、`ticket.acceptance_revision_parseable` | 需要 Ticket 的 Stable claims 可解析、同一 acceptance pair 覆盖全部 claims、该 pair 无 active contradictory/inconclusive、所有 acceptance edges 已释放，且 revision 能被当前 Git resolve；与 CLI `ticket satisfy` 的 `_evidence_coverage` 同一 pair 语义。 |
| `attempt.verify.manual-result-missing` | `attempt.manual_verification_owner = true` AND `attempt.manual_verification_result_present = false` | `attempt.manual_verification_owner`、`attempt.manual_verification_result_present` | 两个布尔都要由 owner/主控显式声明；缺 result 声明是 U，不会自动变成 false。 |
| `attempt.accept.completion-claim-unaudited` | `attempt.completion_claim_pending = true` | `attempt.completion_claim_pending` | 需要 attempt scope 的显式 pending fact；没有声明不能证明 completion claim 已 pending，也不能证明已审计。 |
| `attempt.review.terminal-coverage-incomplete` | `attempt.terminal_coverage_complete = false` | `attempt.terminal_coverage_complete` | 最新 structured summary 缺少 required 结果或有效 report / 复用证据时命中；旧 false 可继续表示 gap，旧 true 不替代结果。 |
| `finding.disposition.grading-undecided` | `finding.grading_pending = true` | `finding.grading_pending` | 必须有可解析的 open finding，且没有合法 Grade 或有 `grading_pending`/待定级 marker；closed finding 会得到 false。 |
| `attempt.disposition.findings-triage-pending` | `findings.triage_pending = true` AND `attempt.near_terminal_gate = true` | `findings.triage_pending`、`attempt.near_terminal_gate` | execution-findings.md 必须存在且至少有一个 parsed finding 未分流；near-terminal 条件是“所有 Ticket terminal”或“Gate 文件存在且 Verdict 可解析”，malformed Gate 不再满足辅助条件。 |
| `attempt.accept.all-tickets-terminal` | `attempt.all_tickets_terminal = true` | `attempt.all_tickets_terminal` | state 必须合法、Ticket 集合非空，且每个 Ticket state 都是 `SATISFIED` 或 `RETIRED`；空 tickets 是已知 false。 |
| `attempt.gate.durable-delta-missing` | `gate.stage7_complete = false` AND `attempt.terminal_gate_pending = true` | `gate.stage7_complete`、`attempt.terminal_gate_pending` | 要让这行真正可命中，Gate 文件必须存在且 Verdict 可解析为非 terminal（如 blocked/undecided），所有 Ticket 必须 terminal，同时 Durable Deltas section 没有 meaningful bullet。缺 Gate 会让 `stage7_complete` U，不能命中。 |
| `attempt.gate.missing` | `gate.present = false` AND `attempt.terminal_gate_pending = true` | `gate.present`、`attempt.terminal_gate_pending` | 只在所有 Ticket 已 terminal 且 Gate 尚未写入时命中；非 terminal 工作窗口不会因为缺 Gate 产生该 row。 |
| `attempt.gate.verdict-undecided` | `gate.present = true` AND `gate.verdict = "undecided"` | `gate.present`、`gate.verdict` | 只表示已写入 Gate 且 Verdict 显式为 `undecided`；缺 Gate 由 `attempt.gate.missing` 单独表达，malformed Verdict 是 U。 |
| `attempt.gate.comparison-mismatch` | `attempt.completion_claim_pending = true` AND `gate.present = false` AND `git.comparison_revision_matches_acceptance = false` | `attempt.completion_claim_pending`、`gate.present`、`git.comparison_revision_matches_acceptance` | 这是写 pass Gate 之前的检查：准备判 pass 且尚无 Gate 时，以当前 HEAD 作为将传给 CLI 的 comparison commit；若任一 SATISFIED acceptance revision 不等，则先对齐再写 Gate。不会再读取 pass 后的 Gate，因此不被 `terminal-frozen` 永久压制。 |

### 9.6 P5：intake 卫生

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `package.record.intake-backlog` | `intake.has_backlog = true` | `intake.has_backlog` | parser 按固定顺序取第一个存在的 intake 文件或目录；只要前面的候选已存在，后面的 backlog 就不会被看。要命中，实际被选中的第一个候选必须是非空 JSON/list、非空行文件或含 entry 的目录。全部候选不存在是 U。 |

### 9.7 系统性补入的隐式前置条件清单

下面按“一个独立的、会改变可命中性或最终可见性、且容易被只读表读者漏掉的实现要求”计数；同一要求覆盖多个 slug 时只计一次，共 **21 条**。这些条目已经逐条落在上面的映射行中：

1. **subject context 必须先建立。** Ticket/evidence row 只对 state 中存在且 Ticket 正文可解析的 Ticket 评估；finding row 只对二至六级 heading 中可解析且 canonical ID 一致的 finding 评估。
2. **`session-resumed` 不依赖声明。** active checkpoint 加上 checkpoint 后没有动作即可命中；有 marker 时读 marker 后的行数，没有 marker 时忽略兼容性的 `attempt.session_resumed` 声明、但其它 typed fact/action 会使它不再是“刚接手”。
3. **evidence-unfiled 需要完整 direct-evidence tuple。** payload 缺 artifact、claim、revision 或 environment 时，`evidence.indexed` 是 U，不会稳定得到 false。
4. **ready/edge 行需要完整 Ticket dependency 图。** 缺 Ticket、坏 Ticket 或无法解析 dependency 时，ready count/edges 不能被“看起来为 0”替代。
5. **multiple-ready 需要已知的 `in_flight=false`。** 没有 trail 或没有办法证明 open dispatch 已关闭，不足以进入多 ready 行。
6. **`no-carrier` 的“无 carrier”是组合推导。** 必须同时是 PENDING、没有结构化 investigate 派发/结果、没有 early-falsification evidence、没有其它 typed 处境，且 `evidenceIndex` 计数恰为 0；它不是单独的 carrier 字段。
7. **`no-carrier` 的排除边界是显式 typed fact。** P3/P4 输入一旦已有其它 typed fact，no-carrier 不再越权抢占；纯 checkpoint marker 不算该排除条件。
8. **worker incomplete 的次数是末尾连续次数。** 历史上出现过一次或两次 INCOMPLETE 不够，中间的 result-like outcome 会重置计数。
9. **finding 的文档来源和 trail 来源不是同一字段。** reviewer-returned/main-session-discovered 看 trail 的 `finding_source`；finding block 的 `finding-source` 不能替代它。
10. **safety-invariant 行依赖 Stable claim ID 正则。** 只有 `INV-` 前缀 claim 会进入安全不变量集合；没有该 claim 时是已知 false。
11. **awaiting-reviewer 的 Ticket prose fallback 仍依赖可读 trail。** 无 trail 时 parser 在 fallback 前返回 U，不能只凭 Ticket 正文的 `review: required` 预测命中。
12. **satisfiable 需要同一 acceptance pair。** 所有 claims 必须在同一 revision/environment 下 supporting；evidence 数量大于 0 不足以命中。
13. **acceptance-edge-held 需要真实 acceptance edge。** 没有 acceptance dependency 时 `all([])=true`，不能把“无依赖”当作 held。
14. **revision-diverged 需要两套比较都成立。** acceptance revision 必须可 resolve 且相对 HEAD 已分叉，同时 trail 旧 head 也必须存在且已前进。
15. **findings triage 的 near-terminal 条件不接受 malformed Gate。** 所有 Ticket terminal，或 Gate 文件存在且 Verdict 可解析，才算接近 terminal。
16. **terminal coverage 使用结果证据。** 从最新 `review.terminal_summary` 与各 track 的独占 report 判定：A/B/C required，按需 Safety；A 最终 HEAD 重审，B/C/Safety 在同 ReviewRun 内凭 PASS 与 reuseEvidence 复用。dispatch 或 Gate 终态不替代结果。
17. **release-edge-unchecked 需要显式 `release_edge_rechecked=false`。** 缺声明不会自动变成 false。
18. **durable-delta-missing 需要一个存在且可解析的非 terminal Gate。** 缺 Gate 会让 `gate.stage7_complete` 为 U，而不是 false。
19. **comparison-mismatch 在 pass 前检查。** 只有 completion claim pending、尚无 Gate 且当前 HEAD 与 SATISFIED acceptance revision 不一致时命中；pass 后不再产生该 row。
20. **缺 Gate 不再合成 `gate.verdict=undecided`。** terminal Gate pending 时由 `attempt.gate.missing` 表达；已有 Gate 且显式写 `undecided` 才进入 `attempt.gate.verdict-undecided`。
21. **intake 是 first-existing-wins。** 前序候选即使为空，也会阻止后序候选被读取；不能只看目录里“某处”有 backlog。

## 10. 如何预测一个包最终呈现什么

只读推导器输入并预测输出时，按下面顺序走查；不要只挑一个“看起来最像”的 slug：

1. **先确认没有 HF。** package 路径、`--at` commit、正式/override table 需要可读取且合法；否则先得到 CLI/table failure，后面的 U/F 预测不适用。
2. **确定 contexts。** 读取 state 的 attempt ID、Ticket map 和 parsed findings，分别建立 package、attempt、每个 Ticket、每个 finding context。先记录 subject；同一个 slug 可能对多个 Ticket 或 finding 各产生一条 match。
3. **逐行枚举候选。** 按第 9 节从 P0 到 P5 检查属于该 context 的全部 56 行。对每一行逐项读取完整 `when` 组合：所有 key 都 true 才是 match；任一 key 已知 false 就不是 match；任一 key U 就记到 `undetermined`，不能把缺失当 false。
4. **把 manual 单独记账。** `ticket.route.multiple-business-outcomes` 和 `ticket.route.sources-conflicting` 永远进入 `manual` 列表，但不会因为“感觉像”而成为机械 candidate；只有主控做出对应语义判断时才主动进入。
5. **汇总所有 active matches，再算层。** 先看有没有 P0。只要有一个 P0，P0 抢占一切低层 match；P1-P5 全部是 `suppressed_matches`，不是当前可见 secondary。
6. **P0 的特殊呈现。** 若命中多个 P0，按 YAML 的 P0 顺序取第一个 `selected`；同组其余 P0 放 `other_matches`。P0 不是 P1-P5 那种无序并列层。
7. **没有 P0 时取最高命中层。** 取数值最小的 P1-P5 层。该层命中一条时，它出现在 `parallel_matches`，人读输出也把它作为当前处境；命中多条时全部并列，**没有主 slug**，主控要先在并列处境中选择。更低层的 active matches 进入 `other_matches`，也就是 secondary。
8. **最后再看 undetermined。** undetermined 行不参加抢占，但必须保留在预测里，因为它表示“当前输入不足以证明不命中”，不是“确定不命中”。

### 10.1 常见的意外抢占

- `ticket.investigate.no-carrier` 仍是 P2，但只覆盖 PENDING、无两类调查 carrier、无其它 typed 处境且 evidenceIndex 为空的 Ticket；P3 comparison/integration 的 typed fact 会让它变为 false。
- `attempt.gate.missing` 只在所有 Ticket terminal 且缺 Gate 时命中；普通 PENDING 窗口不会因为尚未写 Gate 而和 acceptance row 并列。已有 Gate 且显式 `undecided` 才进入 `attempt.gate.verdict-undecided`。
- `attempt.gate.comparison-mismatch` 在写 pass Gate 前检查当前 HEAD 与 acceptance revision；pass Gate 已存在时不再产生该 row，因此不会被 P0 `attempt.gate.terminal-frozen` 永久压制。
- `attempt.accept.all-tickets-terminal` 只要所有 Ticket 都是 SATISFIED/RETIRED 就会出现；它常和 P3 revision/rework 同时命中而成为 secondary；没有更高层 match 时，它也可能和其它 P4 row 并列。

### 10.2 完整走查示例：`p3-comparison-head-unfixed`

以 B2 的 `tests/fixtures/situations-a2/p3-comparison-head-unfixed` 为例。只读输入给出：

- state 合法；只有 `TKT-01`，状态为 `PENDING`；`evidenceIndex` 为空；Ticket 的 claim 和 dependency 形状合法。
- attempt trail 有 `git.comparison_head_fixed=false`。
- 没有 `gate.md`，也没有该 Ticket 的 investigate signal、evidence record 或 running dispatch。

按第 9 节逐层走查：

1. **P0**：没有 terminal Gate，所以 `gate.terminal=false`；state 也合法，所以
   `package.state_invalid=false`。projection drift 因没有 validation result/fact 是 U，但 U
   不等于 active match。其它 P0 fact 也没有为真，因此没有 P0 candidate。
2. **P1**：没有 open dispatch，worker-still-running 不命中；只有一个 ready Ticket，
   multiple-ready 不命中；all-edges-held 不命中。carrier availability 没声明是 U，仍没有
   P1 active match。
3. **P2**：虽然 `ticket.state=PENDING`、没有 investigate carrier、`evidence.count=0`，
   但 attempt scope 已有 `git.comparison_head_fixed=false` typed fact，
   `ticket.investigation_context_clear=false`，所以 no-carrier 不命中。
4. **P3**：`git.comparison_head_fixed=false`，所以目标
   `attempt.review.comparison-head-unfixed` 也命中。
5. **P4**：无 Gate 现在是 `gate.present=false`、`gate.verdict=U`；Ticket 仍为 PENDING，
   `attempt.terminal_gate_pending=false`，所以 missing/undecided 两行都不命中。
6. **结算**：最高 active layer 是 P3，目标 row 成为可见并列 match；
   `package.record.projection-drift` 等 U 行留在
   `undetermined`，不参加抢占。

这里的 `git.comparison_head_fixed=false` typed fact 同时是明确的其它处境，足以让
`ticket.investigation_context_clear=false`；不需要虚构 investigate signal 或 evidence
来迁就 P3 目标。

### 10.3 B2 四条差异的文档预测

- `p0-session-resumed`：active checkpoint 存在，trail 只有兼容性的
  `attempt.session_resumed` 声明；新定义忽略该声明但没有其它动作，所以目标 row
  成为 P0 primary，不依赖“用完记得清”的纪律。
- `p3-comparison-head-unfixed`：typed comparison-head fact 让 investigation context
  不再 clear；目标 row 成为 P3 primary，不被 no-carrier 抢先。
- `p3-integration-evidence-unavailable`：`attempt.integration_evidence_available=false`
  使目标 row 命中，也让 investigation context 不再 clear；P2 no-carrier 不命中，
  P1 carrier row 不会因 carrier fact 缺失而命中。可预测。
- `p4-acceptance-edge-held`：evidence count 大于 0 且 acceptance edge 未释放使目标命中；
  Ticket 尚未 terminal，所以缺 Gate 不产生 `attempt.gate.missing`，只有目标 row 可见。可预测。

### 10.4 缺失或零行 trail 的降级补充

`execution/<attempt-id>/trail.jsonl` 缺失，或文件可读但没有非空 JSON 行，统一视为
“没有事件”；坏 JSON、读取错误仍按 U 处理。对直接查询“轨迹中是否记录过某类事件”的
key，空集有确定值，不把整行推入 `undetermined`：`evidence.indexed=false`、
`trail.decision_without_result=false`、`trail.direct_evidence_returned=false`、
`trail.finding_source=None`、`trail.incomplete_count=0`、`trail.last_outcome=None`、
`trail.last_worker_mode=None`。

其余依赖轨迹缺席来判断 worker、调查、复核、handoff、checkpoint、envelope、可用性、
业务声明或 Git trail head 的 key，缺失或零行仍返回 U；特别是不能把老 package 未写入
新版 trail 的动作当成“没有做过”。`ticket.release_edge_rechecked` 的既有缺省值只在
trail 可读且含事件时适用，缺失或零行仍为 U。

### 终审结果事实

`review.terminal_summary` 是 attempt-scoped structured fact，形状与写入时机见 `../skills/do-review/references/output-templates.md` 的 Terminal coverage record。renderer 读取 package 内 report 的 verdict、reviewed-head、review-run、review-track，核对当前 comparisonHead 与条件 Safety；B/C/Safety 旧 PASS 还需同 ReviewRun 的 reuseEvidence。旧 `attempt.terminal_coverage_complete` 布尔键只兼容读取历史行，不替代结果证据。
