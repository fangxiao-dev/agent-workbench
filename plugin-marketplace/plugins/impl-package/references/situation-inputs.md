
# Situation 输入字段合同

本文件是 `dev-with-track` situation table 的输入合同。它描述的是
`plugin-marketplace/plugins/impl-package/scripts/situation.py` 当前真正读取和判定的
package 形状，目的是让不阅读推导器实现的人也能构造 fixture、per-package 覆盖和审计输入。

截至 2026-09-08，正式表有 42 个 situation row、51 个唯一的非 `manual` `when` key。
本文逐一覆盖这些 key。`manual` row 不需要输入字段；它们始终出现在 `manual` 输出中，
由主控做语义判断。

> 重要边界：本文的“能被推导器识别”首先指 `situation.py render` 的输入合同。完整的
> 3.5 runtime 还会检查 `plan.md`、`spec.md`、Ticket 的 Publication Status、artifact
> 是否存在、Git revision 是否可解析和 projections；这些额外要求仍以
> `references/impl-package-current-state.md`、`impl-package-composition-contract.md`
> 和 runtime validate 为准。本文不会把 situation parser 偶然接受的宽松形状写成完整
> runtime 的推荐写法。

`skills/dev-with-track/references/runtime-protocol.md` 在候选清单、dispatch、worker-return 或恢复的
热路径只需读取 1.2、3.1 和 4.3 的 trail 合同；其它 `when` 事实表、fixture 与历史缺陷说明仅在
排查、构造 fixture 或审计时读取。主控按第 10 节的新分区执行。

## 1. 先记住三件事

### 1.1 输入文件和 subject

推导器只从下列 package-relative 位置取事实：

| 代号 | 实际路径 | 读取方式 |
| --- | --- | --- |
| S | `.impl-package/state.json` | 严格 JSON object；先做 state schema，再做 Ticket/evidence/checkpoint 交叉校验 |
| T | `tickets/*.md` 的直接子文件 | 按正文里的 Ticket ID 建索引；文件名本身不参与 ID 解析 |
| R | `execution/<attempt-id>/trail.NNN.jsonl` 与 `trail.jsonl` | `<attempt-id>` 来自 `S.attempt.id`；renderer 按编号归档后接活动文件读取，每个非空行必须能解析成 JSON object；dispatch/return 关联可跨轮换恢复 |
| G | `gate.md` | 按固定 Markdown 行解析 Verdict 和可选 Comparison commit |
| F | `execution-findings.md` | 按二级至六级 heading 分块，再解析 finding block |
| I | intake 候选路径 | 见下文 `intake.has_backlog` 行的顺序 |
| P | 调用 `render` 时传入的只读结构化 validation result；见 3.1 | 只有 `package.validate.projection_drift` 使用；不执行另一个 CLI，也不解析错误文本；缺失时为 U |
| CP | 调用 `render` 时传入的只读结构化 compaction pressure；由宿主脚本计算，不由 renderer 读取 sessions root | 只有 `attempt.compaction_pressure_high` 使用；只消费 `high`，缺失时返回 U |
| Git | 当前 package 所在 Git 仓库的 HEAD、commit resolve 和 diff | `trail` 中的 `head` 是比较基线；不会从普通 prose 推断 commit |

subject 不是自由标签。`attempt` scope 默认只看 trail 行的 `subject` 为 `attempt`、空值或
缺失的行；`ticket` scope 看 `ticket:<Ticket ID>` 或裸 Ticket ID；`finding` scope 看
`finding:<finding ID>` 或裸 finding ID。少数 attempt-level trail signal 会显式扫描全部 trail
行，本文在对应 key 中标出。

### 1.2 候选清单、dispatch 与新投影

主控可用 `kind=fact,key=dispatch.candidates,subject=attempt` 写入辅助候选清单。
`value.candidates` 是数组；每项带 `candidate_id/subject/mode/action_id/resource_keys`，可带逐候选
`blockers`。CLI 自动补 `value.attempt/head/state_sha256`。指纹只说明清单新鲜度，不是语义 hash，
也不拥有业务准入。投影为候选附加 `declaration_status=current|missing|stale` 与
`declaration_reason`；该状态
本身不是 blocker。关联声明按唯一 candidate_id、唯一 subject/action/resource footprint、唯一
subject/action 的顺序判断；有歧义时不把某候选的局部限制套给其他工作。显式 resource_key
仍按实际受影响资源检查。

同一 Attempt 的旧清单即使 stale，renderer 仍按当前 state、typed dependency、授权、资源与
in-flight 重新判断，并保留清单中显式 blocker。最新 `candidates=[]` 清除补充候选。没有清单时，
合法的 situation action、主控机械动作和待派 review 仍可进入 `runnable`，状态为 `missing`。

候选 subject 与 mode 有硬边界：`implement/fix` 必须使用 `ticket:<存在的 Ticket ID>`；
`attempt` 和 `finding:<id>` 只允许 `investigate/verify`，且 finding ID 必须存在于已解析的
`execution-findings.md`。Ticket/finding subject 都不能用自由标签代替。finding 候选进入 brief 时，
同时保留已确认意见、定位和裁决，避免 worker 丢失线索后重新猜测。

`resource_keys` 只记录主控声明的 effect footprint。相同 key 不自动构成冲突：稳定只读可以共享；
只有主控确认存在不兼容副作用时，才在相关候选的 `blockers` 中写
`type=resource` 与受影响的 `resource_key`。renderer 不推断资源、不求交集、不加自动锁。

新 dispatch 自身必须带 `dispatch_id/candidate_id/subject/resource_keys/receipt/mode/chosen`；
`candidates_of` 可选，仅用于关联辅助清单。派发前重新 render 当前状态并使用 credential；
subject、mode、resource、实际 dependency、已知 authorization/resource blocker 和同一工作
in-flight 都按当前事实校验。CLI 自动把 `state_sha256` 与 `runnable_candidate_ids` 复制进
dispatch 行作为审计证据，不把 ID 列表成员资格当作派发 gate。候选清单缺失或 stale 不放宽
这些实时检查，也不额外阻止合法 dispatch。

审计有完整清单时可以核对 dispatch 当时的候选全集；清单缺失或不完整时记为 uncheckable，
不记违规，也不算通过。

worker 返回使用 `kind=worker-return`，以 `of` 指向 dispatch_id，并带唯一 `return_id`。含代码
增量时同时带完整 SHA 的 `code_delta={base,head}` 与 `consumption_id`。真实 delta review dispatch
用 `reviews=<return_id>`、相同 code_delta/consumption_id 关联；容量不足用
`review.dispatch_pending` fact 保留该增量。同一 dispatch_id 只接受一个 worker-return；原样
return_id 重试幂等，迟到的第二个 return_id 被拒绝。该检查读取编号归档与活动 trail，因此轮换后
仍按同一规则原样重试。renderer 对每个 dispatch 只采纳同 subject 的首个有效 return；迟到、
重复、错 subject 和普通 Ticket 状态转换不会覆盖它。可信 worker 续接同一 candidate 时使用新的
dispatch_id；当前恢复动作只看该 candidate 的最新 dispatch，旧 code_delta 仍独立保留待审。

render 新增 `blocking/runnable/withheld/in_flight`。`blocking` 只含 terminal-frozen、
state-missing、projection-drift、anchor-mismatch 四个全局 P0；局部 foundation/acceptance/
resource/authorization 原因逐候选进入 `withheld`。`source=situation` 的 dispatch 建议与主控机械
动作都按当前事实分区；缺少匹配清单时仅标记 `declaration_status=missing`。`runnable` 全量呈现
合法机械动作、补充候选与待派 delta review；`in_flight` 按 dispatch_id 展示真实在途工作。
主控从这四个分区决策，不从旧 cursor 选单一动作。旧四键仅按旧优先级算法保留在 JSON 中供
兼容消费者读取；`digest` 覆盖新四分区，`legacy_digest` 保留旧算法。

### 1.3 unknown、false 和硬失败不是一回事

本文表格使用以下词：

- **未知（U）**：parser 返回 `Fact(known=False)`。该 key 不满足 row；row 会进入
  `undetermined`，而不是当成 false。
- **已知 false（F）**：parser 返回已知值 `False`。row 可以确定不命中。
- **硬失败（HF）**：不是某个 key 的正常结果，而是 CLI/package/table 层直接报错并退出。
  例如 package 目录不存在、`--at` commit 无法解析、YAML/table 非法。缺失的 state、trail、
  findings 或 intake 本身通常不会 HF；它们按下表返回 true、false 或 U。

对一个含多个 `when` 的 row，**任意一个 U 都使整行成为 unknown**，即使另一个 key 已知
false；只有没有 U 且所有比较都相等时才是 true。

### 1.4 `when` 比较表达式语法

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

## 2. 51 个 `when` key 合同

表中的“缺失/错误”列同时说明文件不存在、字段不存在、字段形状不对和没有匹配 marker
时的行为；`HF：无`表示该 key 本身不会因该输入缺失直接让 CLI 失败。

### 2.1 package、attempt、state 和 Git admission

| key 名 | 数据来源与实际计算 | 合法取值 | 缺失/错误行为 | 被哪些行使用 |
| --- | --- | --- | --- | --- |
| `package.state_invalid` | S：整个 `.impl-package/state.json` 的解析/校验结果；缺文件、JSON 非 object、顶层 key 不对、formatVersion 不对、Ticket/evidence/checkpoint 交叉校验失败都算 invalid | `true` = state 缺失或非法；`false` = situation parser 认为 state 合法 | 缺失/非法是**已知 true**，并保留 reason；合法是 F；HF：无 | `package.record.state-missing` |
| `package.validate.projection_drift` | P：`--validation-result` 传入的 JSON object | 布尔；规范形状是 `{"projection_drift":true/false}` | 没有 P = U；顶层、字段或类型错误 = HF；`--at` 不改变判定；HF：仅 validation result 结构错误或外围 CLI/package 错误 | `package.record.projection-drift` |
| `attempt.active_checkpoint_present` | S：`activeCheckpoints` 中是否存在 key `attempt`；只在 attempt subject 计算 | 布尔；`activeCheckpoints.attempt` 存在 = true，不存在 = false | state 无效/缺失 = U；合法空 mapping = F；HF：无 | `attempt.record.session-resumed` |
| `attempt.all_tickets_terminal` | S：`tickets` 是否非空且每个 row 的 `state` 都是 `SATISFIED` 或 `RETIRED` | 布尔 | state 无效 = U；合法但 tickets 为空 = F；有任一 `PENDING/BLOCKED/NEEDS-REVALIDATION` = F；HF：无 | `attempt.accept.all-tickets-terminal` |
| `attempt.compaction_pressure_high` | CP：`--compaction-pressure` 传入的 JSON object 的 `high`；宿主脚本以第一段间隔为 baseline，最近三段间隔的中位数至少缩短 20% 且至少有三段间隔时才给 `high=true`；renderer 不重算 | 布尔 | 缺少参数 = U（不是 false）；合法 `high=false` = F；JSON 非 object、缺 `high`、类型/未知字段错误 = HF | `attempt.record.handoff-due` |
| `attempt.has_pending_ticket` | S：`tickets[*].state` 是否至少有一个 `PENDING` | 布尔 | state 无效 = U；合法无 Ticket 或全非 PENDING = F；HF：无 | `attempt.readiness.all-edges-held` |
| `attempt.implementation_edges_held` | S + T：先计算 `ready_ticket_ids`，再判断“存在 PENDING Ticket 且 ready 数量为 0”；implementation dependency 的释放规则见 `ticket.acceptance_edge_released` | 布尔 | state、Ticket 文件或 dependency 不可判定 = U；无 pending = F；有 pending 且至少一个 ready = F；HF：无 | `attempt.readiness.all-edges-held` |
| `attempt.in_flight` | R：旧 dispatch/decision 与 result 配对的兼容诊断；不接受 fact 覆盖 | 布尔；旧行可无 id；有关联 ID 时 result-like 可关闭 | 无 trail或无法归属 = U；可读且没有 open 旧事件 = F；HF：无 | 兼容 parser key；新运行读取 `in_flight[]`，不以此布尔压制候选 |
| `attempt.near_terminal_gate` | S + G：`all_tickets_terminal` 为 true，或 `gate.md` 存在、属于当前 Attempt 且 Verdict 可解析 | 布尔 | state 无效 = U；state 合法且无 terminal Ticket、无可解析 Gate = F；malformed Gate 或只有上一个 Attempt 的 Gate 不满足该辅助条件；Attempt 归属不可判定 = U；HF：无 | `attempt.disposition.findings-triage-pending` |
| `attempt.ready_ticket_count` | S + T：收集所有 `PENDING` Ticket，只有 implementation dependencies 全部由 `SATISFIED`、`RETIRED/waived` 或已释放 successor 释放时才进入 ready list；返回 list 长度 | 非负整数；用于表的比较是 `">1"` 或 `0` | state/Ticket/dependency 不可判定 = U；合法空图返回 0；HF：无 | `attempt.readiness.multiple-ready-tickets`、`attempt.readiness.all-edges-held` |
| `attempt.session_resumed` | S + R：不读取声明；`activeCheckpoints.attempt` 存在，且 checkpoint 后没有动作行时为 true | 布尔 | trail error 或 state/checkpoint 不可判定 = U；无 active checkpoint = F；有显式 checkpoint marker 时只计 marker 后的行；没有 marker 时忽略兼容性的 `attempt.session_resumed` 声明，但其它 typed fact/action 会使结果为 false；HF：无 | `attempt.record.session-resumed`（兼容 parser key） |
| `attempt.terminal_coverage_complete` | S + 最新 `review.terminal_summary` fact + package-relative report | 布尔；核对 comparisonHead、A/B/C 与按需 Safety 的 PASS，同 ReviewRun 的 B/C/Safety 可凭 reuseEvidence 复用 | 尚未终审为 U；缺结果或来源不匹配为 false；Gate 终态不能替代结果 | `attempt.review.terminal-coverage-incomplete` |
| `attempt.terminal_gate_pending` | S + G：先要求所有 Ticket terminal；再取 `gate.terminal`，返回其否定 | 布尔 | state 或 gate verdict 不可判定 = U；尚有非 terminal Ticket = F；全 terminal 且 gate 缺失/非 terminal = true；pass/fail/defer = F；HF：无 | `attempt.gate.durable-delta-missing` |
| `git.acceptance_revision_diverged` | S + Git（ticket subject）：Ticket row 必须是 `SATISFIED`，读取 `acceptance.revision`，确认该 revision 可 resolve，再与当前 Git HEAD 比较 | 布尔；可 resolve 且不等于当前 HEAD = true，等于 = false | 非 ticket subject = U；state 无效时当前实现把无 row 当作“非 SATISFIED”，返回 F；缺 acceptance、HEAD、或 revision 无法 resolve = U；HF：无 | `ticket.rework.revision-diverged` |
| `git.accepted_seam_changed` | S + Git（ticket subject）：从 acceptance revision 到当前 HEAD 的 diff 自动判断是否包含非文档源码变化；不接受 fact 覆盖 | 布尔；存在源码变化 = true，仅文档变化 = false | 缺 acceptance revision、HEAD、diff 或无法 resolve = U；HF：无 | `ticket.rework.revision-diverged` |
| `git.contract_changed_since_last_trail` | R + Git：读取最后一个适用 trail 行的顶层 `head`；若它与当前右端不同，检查 `head..HEAD` diff 中是否有 `plan.md`、`spec.md`、`contract-design.md`、`decision.md` 或 `tickets/` 文件 | 布尔 | 无 trail head = U；head 等于当前 HEAD = F；Git diff 不可读 = U；diff 命中上述路径 = true，否则 F；HF：无 | `attempt.rework.contract-changed` |
| `git.head_advanced_since_last_trail` | R + Git：最后一个适用 trail 行的顶层 `head` 与当前 HEAD 比较 | 布尔 | 无 trail head 或当前 HEAD 不可读 = U；相同 = F；不同 = true；HF：无 | `ticket.rework.revision-diverged` |

### 2.2 ticket、evidence 和 dependency

| key 名 | 数据来源与实际计算 | 合法取值 | 缺失/错误行为 | 被哪些行使用 |
| --- | --- | --- | --- | --- |
| `ticket.acceptance_conditions_satisfied` | S + T：等价于 `evidence.all_required_claims_supported=true` 且 `evidence.contradictory_unresolved=false`；required claims 来自 Ticket 的 Stable claim ID | 布尔 | 任一子事实 U 就 U；无 claims 时 supporting 子事实为 F；有完整 supporting 且无 active contradictory/inconclusive 才 true；HF：无 | `ticket.accept.release-edge-unchecked` |
| `ticket.acceptance_edge_released` | S + T：Ticket 的 `## 阻塞依赖` 中 kind=`acceptance` 的目标全部已释放；`SATISFIED`、`RETIRED/waived` 释放，`RETIRED/superseded` 递归看 successor，其余状态不释放 | 布尔 | state/Ticket/dependency 不可判定 = U；没有 acceptance 边时 `all([])` 为 true；任一边未释放 = F；HF：无 | `ticket.accept.acceptance-edge-held`、`ticket.accept.satisfiable` |
| `ticket.acceptance_revision_parseable` | S + Git：先取 Ticket 的 `acceptance.revision/environment`；若 Ticket 是 PENDING 且没有 acceptance，再从 evidence group 找第一组可解析 revision | 布尔 | 非 ticket subject = U；没有 pair 且 evidence 可读 = F；Git 不可用 = U；pair 的 revision 可 resolve = true，否则 F；HF：无 | `ticket.accept.satisfiable` |
| `ticket.blocker_maybe_resolved` | R：当前 Ticket scope 的最新 fact；旧 Ticket 正文 alias 仅作兼容 fallback | 布尔 | 没有值 = U；显式值不是布尔 = U；不会因为 Ticket 为 BLOCKED 自动变 true；未知 fact key = HF | `ticket.readiness.blocker-maybe-resolved` |
| `ticket.investigation_carrier_present` | R + S：当前 Ticket 有结构化 investigate 派发/结果，或 evidenceIndex 至少有一条 `timing=early-falsification` 记录 | 布尔 | 无/坏 trail 且无法判断派发，或 state/evidence 不可读 = U；两类载体都没有 = F；HF：无 | `ticket.investigate.no-carrier` |
| `ticket.investigation_context_clear` | R：当前 Ticket 与 attempt scope 没有其它 typed fact；纯 checkpoint marker 不算其它处境 | 布尔 | 无/坏 trail = U；任一相关 typed fact（无论 true/false）存在 = F；没有 typed fact = true；HF：无 | `ticket.investigate.no-carrier` |
| `ticket.release_edge_rechecked` | R：当前 Ticket scope 的最新 fact `ticket.release_edge_rechecked`；不再从 `chosen` 前缀、situation 或 dependency 状态推导 | 布尔 | 无 trail/无 fact = U；fact 非布尔 = U；未知 fact key = HF | `ticket.accept.release-edge-unchecked` |
| `ticket.release_edge_present` | T：当前 Ticket 的 typed dependency 中是否至少有一个 kind=`release` | 布尔 | Ticket 文件缺失/解析失败 = U；无 release dependency = F；至少一条 release dependency = true；HF：无 | `ticket.accept.release-edge-unchecked` |
| `ticket.safety_invariant_unfalsified` | S + T：Ticket claims 中 ID 以 `INV-`（不区分大小写）开头的项是安全不变量；比较 active evidence 的 claim 集合，若至少一个 INV claim 没有 active record 就 true | 布尔 | 非 ticket、Ticket 无法解析、state/evidence 无效 = U；没有安全 claim = F；所有 INV claim 都有未 invalidated record = F；至少一个缺 record = true；HF：无 | `ticket.verify.safety-invariant-unfalsified`（描述为尚未验证） |
| `ticket.state` | S：当前 ticket subject 的 `tickets[identifier].state` | 枚举 `PENDING`、`BLOCKED`、`NEEDS-REVALIDATION`、`SATISFIED`、`RETIRED` | 非 ticket subject、state 无效、Ticket ID 不存在 = U；合法时返回枚举原值；HF：无 | `ticket.readiness.blocker-maybe-resolved`、`ticket.investigate.no-carrier`、`ticket.rework.evidence-conflict`、`ticket.rework.revalidation-pending` |
| `evidence.all_required_claims_supported` | S + T：required claims 是 Ticket 解析到的全部 Stable claim ID；先取 acceptance pair（SATISFIED 的 acceptance 或 PENDING evidence group），只在同 revision/environment 中检查每个 claim 有 `conclusion=supporting` 且未 invalidated | 布尔 | 非 ticket/Ticket 无 claims = U 或 F（Ticket 无法解析为 U、无 claims 为 F）；state/evidence 不可读 = U；没有 acceptance pair = F；全部 claim 支持才 true；HF：无 | `ticket.accept.satisfiable` |
| `evidence.contradictory_unresolved` | S + T：先取当前 acceptance pair，再只检查该 pair 中 required claim 的 active record；任一 `conclusion` 是 `contradictory` 或 `inconclusive` 就 true | 布尔 | state/evidence/Ticket 不可读 = U；没有 acceptance pair 或该 pair 无 required-claim conflict = F；其它 revision/非 required claim 的冲突不计入；HF：无 | `ticket.verify.contradictory-unresolved`、`ticket.accept.satisfiable`、`ticket.acceptance_conditions_satisfied` |
| `evidence.count` | S：当前 ticket 的 `evidenceIndex[Ticket ID]` 下所有 claim mapping 中 list item 的总数；包含已 invalidated record | 非负整数；表里比较 `">0"` 或与 0 相等 | state 无效、非 ticket subject 或 evidenceIndex 不可读 = U；合法空 mapping = 0；HF：无 | `ticket.investigate.no-carrier`、`ticket.accept.acceptance-edge-held` |
| `evidence.indexed` | R + S：把 `kind=result` 或 `kind=worker-return` 行中的 `ref/evidence/artifact/evidence_ref/direct_evidence` payload 当 direct evidence；每个 payload 必须可得 artifact、claim、revision、environment，再检查同 tuple 是否存在未 invalidated S record | 布尔 | 无/坏 trail = U；无 direct payload = F；payload 缺任一 link 字段 = U；state 无效 = U；所有 tuple 已登记 = true，否则 F；HF：无 | `ticket.record.evidence-unfiled` |
| `evidence.new_claim_conflict` | S：先要求 state 可读；只有当前 Ticket state 是 `SATISFIED` 才调用 `evidence.contradictory_unresolved`，否则 false | 布尔 | state 无效 = U；Ticket 不存在或不是 SATISFIED = F；SATISFIED 但 evidence 不可读 = U；有 active contradictory/inconclusive = true；HF：无 | `ticket.rework.evidence-conflict` |
| `finding.grading_pending` | F：finding 非 closed 且 block 含 `grading_pending`、`待定级`，或没有可识别的 `P1/P2/P3/editorial` grade | 布尔 | F 缺失或 finding 不存在 = U；open 且无 Grade = true；open 且有 P1/P2/P3/editorial = F；closed = F；HF：无 | `finding.disposition.grading-undecided` |
| `finding.review_track` | F：当前 finding block 中 `Track A/B/C/D` 或 `轨道 A/B/C/D` 的捕获值 | 枚举 `A`、`B`、`C`、`D`，没有 track 时是已知 `None` | F 缺失/错误或 finding 不存在 = U；finding 存在但没有 track = 已知值 None（与期望 `C` 不相等）；HF：无 | `finding.review.source-recheck-pending` |
| `finding.source_recheck_pending` | F：block 中的 `source_recheck: pending`、`source recheck ... pending` 或中文待复核/待重查 marker | 布尔 | F 缺失/错误或 finding 不存在 = U；无 marker = F；HF：无 | `finding.review.source-recheck-pending` |
| `findings.triage_pending` | F：对所有 parsed findings，`triage_pending` 为非 closed 且（有 `triage: pending`/未分流/待分流，或没有 Decision/Spec/Execution Record/Durable Delta route marker） | 布尔 | F 缺失/解析错误 = U；F 存在但没有 parsed finding = false；任一 finding pending = true；HF：无 | `attempt.disposition.findings-triage-pending` |
| `gate.stage7_complete` | G：先核对 `- Attempt:` 是否属于当前 Attempt（见 `gate.terminal` 的 Attempt 判据），再精确找到 `## Durable Deltas` section；其中至少一行 `- ...`，且不是 `- none` 或 `- Reason: none` | 布尔 | G 缺失或读取/解析错误 = U；没有 Durable Deltas section = F；只有上一个 Attempt 的 Gate = F（当前 Attempt 未完成 Stage 7）；Attempt 归属不可判定 = U；有 meaningful bullet 且属于当前 Attempt = true；HF：无 | `attempt.gate.durable-delta-missing` |
| `gate.present` | G：`gate.md` 文件是否存在且其 `- Attempt:`属于当前 Attempt；不把文件内容是否 malformed 混入 presence | 布尔 | 缺 Gate = F；文件存在但只属于上一个 Attempt = F；文件存在（即使 malformed）且明确属于当前 Attempt = true；缺少 Attempt = U；Attempt 归属不可判定 = U；HF：无 | `attempt.gate.missing`、`attempt.gate.verdict-undecided` |
| `gate.terminal` | G 的 `Verdict`；`pass/fail/defer` 属于 terminal；terminal 结论只对写下该 Verdict 的 Attempt 生效——`- Attempt:` 必须存在并与 state.json 的当前 attempt id 相等；缺少 Attempt 时为 U，等价于 `engine.py` 的 `_lifecycle` 判据 | 布尔 | G 缺失 = 已知 F；有文件但 Verdict 缺失/格式错 = U；`blocked/undecided` = F；Verdict 是 terminal 但 Attempt 不匹配 = F；Attempt 归属不可判定 = U；`pass/fail/defer` 且 Attempt 匹配 = true；HF：无 | `attempt.gate.terminal-frozen` |
| `gate.verdict` | G：`- Verdict: pass / fail / blocked / defer / undecided` 或中文 `判定` 行；只读取属于当前 Attempt 的已存在 Gate 的显式 verdict | 枚举 `pass`、`fail`、`blocked`、`defer`、`undecided`，解析后转小写 | 缺 G = U（由 `gate.present=false` 单独表达）；有 G 但 Verdict 缺失/格式错 = U；只有上一个 Attempt 的 Gate = U（当前 Attempt 尚未写 Gate）；Attempt 归属不可判定 = U；HF：无 | `attempt.gate.verdict-undecided` |
| `intake.has_backlog` | I：按顺序找第一个存在的文件：`.impl-package/intake.jsonl`、`.impl-package/intake-queue.jsonl`、`.impl-package/intake.json`、`execution/intake.jsonl`、`execution/intake-queue.jsonl`、`execution/intake.json`、`intake.jsonl`、`intake.json`；其次找目录 `.impl-package/intake`、`.impl-package/intake-queue`、`execution/intake`、`execution/intake-queue`、`intake`、`intake-queue` | 布尔；JSON list 非空、dict 的 `items/queue` list 非空、非 JSON 但有非空行、目录有 entry = true | 所有候选不存在 = U；存在但空文本/空 list/空目录 = F；读取错误或 dict 无 list 时按非空文本 fallback；HF：无 | `package.record.intake-backlog` |
| `trail.actions_since_checkpoint` | R（归档后接活动 trail）：在适用 subject rows 中找最后一个 checkpoint marker，返回 marker 后的行数；无 marker 时忽略兼容性的 `attempt.session_resumed` 声明并计其它 rows | 非负整数；表只比较 `0` | 无/坏 trail = U；state 无效导致 checkpoint 不可判定 = U；无 active checkpoint = 0；HF：无 | `attempt.record.session-resumed` |
| `trail.last_ticket_terminal_transition` | R（编号归档后接活动 trail）：attempt scope 扫描全部 rows，Ticket scope 只扫描当前 Ticket；取最后一个 `kind=result`、`transition=ticket-state` 且 `subject` 为 `ticket:<id>` 的状态转换行，检查其 `to`（兼容 `outcome`）是否为 `SATISFIED` 或 `RETIRED` | 布尔；最后一个 Ticket 状态转换进入 `SATISFIED/RETIRED` = true | trail 缺失或可读但为空 = F；坏 trail = U；没有状态转换 = F；最后状态转换不是终态 = F；普通 worker result 没有 `transition=ticket-state`，不参与；HF：无 | `attempt.record.trail-rotation-due` |
| `trail.anchor_mismatch` | R：attempt scope 的最新 fact；不再扫描 JSON 文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.anchor-mismatch` |
| `trail.decision_without_result` | R（归档后接活动 trail）：按 dispatch_id/of 轴判断 dispatch 是否仍未返回；旧行缺关联 ID 时为 U，不做 Ticket/Attempt 聚合 | 布尔；新 dispatch 必须有 dispatch_id | 无/坏 trail或旧行缺关联 = U；已关联关闭 = F；HF：无 | 诊断输出；在途工作由 `in_flight[]` 呈现 |
| `trail.direct_evidence_returned` | R：扫描 `kind=result` 与 `kind=worker-return`；其 payload key 是 `ref/evidence/artifact/evidence_ref/direct_evidence`，非空 scalar/list item 即算 direct payload | 布尔；payload 可以 object、string 或其他 truthy 值，但要继续判 `evidence.indexed` 时必须有 artifact/claim/revision/environment | 无/坏 trail = U；trail 有但没有 result-like payload = F；HF：无 | `ticket.record.evidence-unfiled` |
| `trail.envelope_valid` | R：显式 fact `trail.envelope_valid` 优先；否则读取 result-like row 或 `envelope/result` 容器中的结构化 `envelope_valid/envelopeValid` | 布尔；建议 JSON bool `true/false` | 无/坏 trail = U；有 trail 但没有结构化字段/fact = U；显式非布尔 = U；不再识别 envelope 文本 marker；HF：未知 fact key | `finding.fix.worker-envelope-invalid` |
| `trail.finding_source` | R：当前 subject rows 的顶层 `finding_source` 或 `findingSource` 字符串，取最后一个 | 字符串；表使用 `reviewer`、`main-session` | 无/坏 trail = U；trail 正常但没有字段 = 已知值 None（与任何字符串不等）；HF：无 | `finding.fix.reviewer-returned`、`finding.fix.main-session-discovered` |
| `trail.handoff_recovery_needed` | R：attempt scope 的最新 fact；不再扫描 bootstrap/retry/rename/create-thread 文本 marker | 布尔 | 无/坏 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.handoff-recovery-needed` |
| `trail.handoff_target_corrected` | R：attempt scope 的最新 fact；不再扫描 corrected target/order 文本 marker | 布尔 | 无/坏 trail 或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.record.handoff-target-corrected` |
| `trail.has_investigate` | R：attempt context 扫全部 rows；ticket/finding context 扫各自 subject rows；`situation` 以 `ticket.investigate.` 开头，或 chosen 含 `investigate`，或 outcome 为 `EVIDENCE_GAP/EVIDENCE_SUFFICIENT` 即 true | 布尔 | 无/坏 trail = U；有 trail 无 signal = F；HF：无 | 兼容 parser key；正式 `ticket.investigate.no-carrier` 使用 `ticket.investigation_carrier_present` |
| `trail.incomplete_count` | R（归档后接活动 trail）：按 dispatch_id/of 轴统计该派发末尾连续 INCOMPLETE；次数只作诊断观察，后续动作依据边界与上下文可信度 | 非负整数 | 无/坏 trail或旧 result 缺 of = U；没有 INCOMPLETE = 0；HF：无 | 诊断输出 |
| `trail.last_outcome` | R（归档后接活动 trail）：按 dispatch_id/of 轴读取该派发最后一个 result-like outcome；旧 result 缺 of 时不聚合 | 字符串枚举由表约定；比较大小写敏感 | 无/坏 trail或旧行缺 of = U；该派发无 outcome = 已知 None；HF：无 | worker-return 消费处境 |
| `trail.last_worker_mode` | R（编号归档后接活动 trail）：在当前 dispatch 轴上读取 dispatch/result 的结构化 `mode/worker_mode/workerMode`，并兼容旧 `facts` 与 `chosen` | 枚举 `investigate`、`implement`、`fix`、`verify`、`review`；解析后小写 | 无/坏 trail = U；没有对应 dispatch context 时不形成可执行 worker 结论；非允许值与合法枚举不等；HF：无 | `ticket.implement.worker-incomplete-first`、`ticket.implement.worker-blocked`、`finding.fix.worker-envelope-invalid` |
| `trail.reviewer_unavailable` | R：attempt scope 的最新 fact；不再扫描 timeout/unavailable 文本 marker | 布尔 | 无/坏 trail或无 fact = U；fact 非布尔 = U；未知 fact key = HF | `attempt.review.reviewer-unavailable` |

## 3. 比较、subject 和 per-package override 的实用规则

### 3.1 trail event schema、fact 通道和 validation result

renderer 的 trail 输入是按编号排序的 `execution/<attempt-id>/trail.NNN.jsonl`，随后接活动
`trail.jsonl`；每个非空行必须是 JSON object。dispatch/return、fact 最新值和恢复判断都跨轮换
读取这条连续事件流。正式事件使用同一组公共字段：

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
| `decision` | 历史形状：`subject`、`seq/id/decision_id/decisionId` 至少一个、`chosen` | 仅只读兼容旧 decision/result 配对；新运行不从该游标派发 |
| `dispatch` | `subject`、`dispatch_id`、`candidate_id`、`resource_keys`、`receipt`、`mode`、`chosen`、`outcome:"RUNNING"`、`returned:false`、`worker`、`situation_digest`；可选 `candidates_of` | 使用当前 credential，并通过实时 dependency、授权、资源与 in-flight 校验；`runnable_candidate_ids` 只供审计。有 `candidates_of` 时核对辅助清单。匹配 `worker-return.of` 后关闭；review dispatch 还要用 `reviews/code_delta/consumption_id` 绑定原 return |
| `escape` | `subject`、`deviation`、`reason`；可带 `of` 关联 dispatch/decision | 记录偏离 renderer 建议或处境表未覆盖的决定；作为事件读取，不进入 fact 通道 |
| `result` | `subject`、`outcome`；返回 decision 时带 `of`；direct evidence 放在 `ref/evidence/artifact/evidence_ref/direct_evidence`；CLI Ticket 终态转换可带 `transition=ticket-state`、`from`、`to` | outcome、incomplete、旧 direct-evidence 写法和 decision 关闭；`transition=ticket-state` 供 Ticket 边界 when-key 读取 |
| `worker-return` | `subject`、`outcome`、`of`、`return_id`；代码增量同时带 `code_delta/consumption_id`；可带 direct-evidence payload | `subject` 必须匹配 dispatch；同一 `of` 只接受一个 return_id，完全相同事件跨归档重试幂等 |
| `fact` | `subject`、`kind:"fact"`、`key`、`value`、`ts`，可选 `seq` | renderer 在归档与活动 trail 的连续流中读取同一 key 的最新事实；`ts` 会在 JSON `when_values` 中暴露，不添加过期规则 |

`checkpoint`、`handoff`、`judgment`、`integration`、`review` 等旧 kind 仍可作为普通事件，
但它们不再通过自由文本 marker 产生本节列出的业务事实。迁移期允许任意旧 kind 携带旧
`facts` object；新写入必须使用单条 `kind=fact`：

```json
{"v":1,"seq":12,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"trail.anchor_mismatch","value":true}
```

同一连续 trail 中同一 subject、同一 key 有多条 fact 时，按 `ts` 新者优先，`ts` 相同按 `seq`
新者优先，再以归档到活动文件的读取顺序作稳定兜底。陈旧 fact 不会自动失效，最新 fact 的
`ts` 始终可见。
`value` 的类型由消费 key 校验；需要布尔的 key 只接受布尔/既有布尔兼容表示。

#### 封闭的 fact key 集合与缺省语义

新 `kind=fact` 和兼容读取的旧 `facts` object 只能使用下表的 canonical key；语义 CLI
拒绝未知 key，renderer 读取历史未知行时忽略并给出 warning。表外的自动计算 key 不接受
fact 覆盖；`unknown` 表示不猜测并让依赖该 key 的 situation 保持 undetermined。
trail 缺失或读取失败仍是输入不可用，不套用缺省值。

| fact key | 缺省语义 | 理由 |
| --- | --- | --- |
| `ticket.blocker_maybe_resolved` | `unknown` | 没有变化声明不能判断 blocker 是否已解除，默认 false 会少提醒重新评估。 |
| `ticket.release_edge_rechecked` | `false` | 未声明时默认就是“尚未复核”，保留 release-edge 提醒属于 fail-closed。 |
| `trail.anchor_mismatch` | `unknown` | 没有 mismatch 声明不能证明锚点一致，默认 false 会少提醒锚点恢复。 |
| `trail.checkpoint_projection_race` | `unknown` | 没有 race 声明不能证明不存在竞态，默认 false 会少提醒 checkpoint 对账。 |
| `trail.envelope_valid` | `unknown` | 没有结构化 validity 声明不能证明 envelope 无效，默认 false 会把无 envelope 误报为 invalid。 |
| `trail.handoff_recovery_needed` | `unknown` | 没有 recovery 声明不能证明 bootstrap 正常，默认 false 会少提醒恢复动作。 |
| `trail.handoff_target_corrected` | `unknown` | 没有 corrected 声明不能证明目标未修正，默认 false 会少提醒重发或取消。 |
| `trail.reviewer_unavailable` | `unknown` | 没有 unavailable 声明不能证明 reviewer 可用，默认 false 会少提醒重新派发。 |
| `review.canonical_summary` | `review` 的结构化 summary | 无默认值；由 review 流程写入并供追踪/统计消费 | `do-review` 的 ReviewRun 记录 |
| `review.terminal_summary` | `review` 的结构化 terminal coverage summary | 无默认值；由 `attempt.terminal_coverage_complete` 按结果证据判定 | `attempt.review.terminal-coverage-incomplete` |

自由文本如 `carrier unavailable`、`comparison-head-unfixed`、`recheck-release-edge` 或
`reviewer timeout` 不再改变事实值。

#### Projection validation result

`package.validate.projection_drift` 可以从一个只读、结构化的 validation result 得到。调用
形式为：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py render \
  --package <package> --validation-result '{"projection_drift":true}' --json
```

也可以把同样的 JSON object 放入 `--validation-result <file>` 指定的文件。object 只允许
`projection_drift` 布尔字段和可选的非空 `source` 字符串；未知字段或错误类型是 HF。传入
result 是唯一来源；没有传入时该 key 为 U。该输入不启动 `impl_package_state.py`，也不解析
stdout/stderr，因此 `--at <commit>` 可以用同一个结构化 result 回放快照。

### 3.2 旧四键 JSON 兼容

`selected/parallel_matches/other_matches/suppressed_matches` 继续按旧优先级算法输出：P0 是有序
list，P1-P5 是无序 set；P0 存在时低层进入 `suppressed_matches`，否则最高命中层进入
`parallel_matches`。这四键只供旧 JSON 消费者和历史审计兼容。主控运行时读取
`blocking/runnable/withheld/in_flight`，不把 legacy `selected` 当成唯一下一动作，也不从
`suppressed_matches` 推断工作不可推进。

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

state 缺失或非法不是“没有处境”：`package.state_invalid` 返回已知 true，并进入新投影
`blocking`；state 合法但某个依赖它的 key 无法计算，则那些 key 返回 U。

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

#### 最小 dispatch 事件链

下面是 `trail append` 的两次独立输入。先 render 当前状态取得 candidate_id 与 credential，再由
dispatch 自身声明 subject、mode 和 resources；第二行用 `of` 唯一归还该 dispatch。辅助清单和
`candidates_of` 都可省略：

```jsonl
{"subject":"ticket:TKT-01","kind":"dispatch","dispatch_id":"dispatch-01","candidate_id":"candidate-01","resource_keys":["worktree:a"],"receipt":"thread-01","mode":"implement","chosen":"implement","outcome":"RUNNING","worker":"worker-01","returned":false,"situation_digest":"0123456789ab"}
{"subject":"ticket:TKT-01","kind":"worker-return","of":"dispatch-01","return_id":"return-01","outcome":"DONE"}
```

若要补充清单，另写 `dispatch.candidates` fact；有 `candidates_of` 的 dispatch 必须引用对应清单。
清单的 `head/state_sha256` 过期只把 declaration 标为 stale，当前业务与资源检查仍重新执行。

`trail.jsonl` 每个非空行必须是 JSON object；空行忽略。坏 JSON 或非 object 不会让 renderer
HF，但会把整个 TrailView 置为 error，所有依赖该 trail 的 key 通常变为 U。未知 fact key
由写入 CLI 拒绝，renderer 读取历史行时忽略并给出 warning。规范 kind 的字段如下：

| kind/写法 | 为被当前 parser 消费所需的字段 | 说明 |
| --- | --- | --- |
| `fact` | `subject`、`key`、`value`；key 必须属于 3.1 的闭合集合 | CLI 补 `ts/seq`；同 key 跨归档按 `ts/seq/读取顺序` 取最新；旧 `facts` object 只读兼容 |
| `decision` | 历史 `subject`、关联 ID、`chosen` | 只读兼容旧 decision/result 配对；新派发使用当前投影与 dispatch |
| `dispatch` | 1.2 和 3.1 列出的完整字段；`candidates_of` 可选 | 必须匹配当前 credential；有清单关联时额外核对该声明；`in_flight[]` 按 dispatch_id 标注 |
| `escape` | `subject`、`deviation`、`reason`；可带 `of` 关联 dispatch/decision | 偏离或表外处境的结构化事件；缺少这些字段不使 renderer 失败 |
| `result` | `subject`、`outcome`；关闭 decision 可带 `of`/decision ID | 与 `worker-return` 统一为 result-like event |
| `worker-return` | `subject`、`outcome`、`of`、`return_id`；代码增量成对带 `code_delta/consumption_id` | 同一 `of` 只接受一个 return_id；完全相同事件跨归档重试幂等；可携带 direct evidence |
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
不是 terminal；`pass`、`fail`、`defer` 才是 terminal。renderer 会核对 `gate.md` 的
`- Attempt:` 与当前 attempt id，只有上一个 Attempt 遗留的 Gate 时 `gate.present`、
`gate.verdict`、`gate.terminal`、`gate.stage7_complete` 均按“当前 Attempt 未写 Gate”
处理，不会读到旧 Attempt 的 verdict；完整 runtime 还会检查 comparison commit、Durable
Deltas 以及其它 Gate 内容，并不把 renderer-only 的 `undecided` 当作可发布 Gate 状态。

## 5. 三个端到端最小 package

下面三套都只包含 situation renderer 的输入文件，目录内容是完整的；`plan.md`、`spec.md`、
`progress.md` 和 Execution Record 若要通过完整 runtime validate，仍须按 3.5 runbook 补齐。
三个示例中的 `5f299f345d14389d1520d68e84eec52342d16564` 是本仓库 2026-08-15 的 HEAD；复制到
别的 Git repository 时，把它替换为该 repository 中实际存在的 `git rev-parse HEAD`。

### 5.1 全局 blocking：anchor mismatch

应命中 `attempt.record.anchor-mismatch`，并进入 `blocking`。

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
`checkpoint-refresh`。其它匹配仍保留在 diagnostics；`anchor-mismatch` 作为全局 blocker 清空
本轮 `runnable`。

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
`ticket.acceptance_revision_parseable=true`。`gate.md` 的 blocked 是显式非 terminal verdict；
无 Gate 也不会合成 `attempt.gate.verdict-undecided`。`ticket.accept.satisfiable` 进入 `matches`，
其主控机械 action 进入 `runnable`。

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
- `p0-terminal-frozen` 的 legacy expected primary 本身是对的，但非法 state 还制造了不应有的
  legacy `package.record.state-missing` secondary，因此它同时属于形状误报；新投影把两者都
  作为 `blocking` 事实呈现。

剩下的 **1/11** 是 `p4-comparison-mismatch`：`Gate Verdict: pass` 按当前优先级必然命中
P0 `attempt.gate.terminal-frozen`，expected 却把它列入 `must_not_hit`；这是 priority/语义
边界错误，不是输入 shape 错误。上述 10/11 不是说所有 legacy expected primary 都正确，而是说
“造不出所依赖的合法事实形状”是主要失败原因。

## 7. 两个已知失效 key：修复后的规范形状

### 7.1 `ticket.record.evidence-unfiled`

**应有行为**：下列自然返回应该建立 `trail.direct_evidence_returned=true`：

```json
{"subject":"ticket:TKT-01","kind":"worker-return","of":"dispatch-01","return_id":"return-01","outcome":"EVIDENCE_SUFFICIENT","evidence":{"artifact":"evidence/returned.md#result","claim":"AC-1","revision":"5f299f3","environment":"fixture"}}
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

### 7.2 `in_flight[]`

**应有行为**：下列 dispatch liveness 应建立一条按 dispatch 归属的 `in_flight[]` 标注：

```json
{"subject":"ticket:TKT-01","kind":"dispatch","dispatch_id":"dispatch-01","candidate_id":"candidate-01","candidates_of":1,"mode":"implement","chosen":"implement","resource_keys":["worktree:a"],"receipt":"thread-01","outcome":"RUNNING","worker":"worker-01","returned":false,"situation_digest":"0123456789ab"}
```

这里的 `candidates_of=1` 只演示可选清单关联；没有该字段的合法 dispatch 同样进入
`in_flight[]`。

`worker-return.of=dispatch-01` 关闭该项。在途 worker 是事实标注，不再命中一个默认 wait 的
situation row；其它独立 runnable 候选仍同时呈现。

旧写法仍然合法并保持同样语义：

```json
{"subject":"attempt","kind":"decision","seq":1,"chosen":"dispatch-worker"}
```

旧 decision/result 仍只读兼容；缺少 dispatch_id/of 时关联结论为 unknown，不参与新的按
dispatch 判定。

## 8. 验收自问与剩余缺口

一个不读 `situation.py` 的人现在可以：

1. 用第 4.1 的 state 外层、Ticket row、evidence record 和 checkpoint 形状构造一个不触发
   `package.state_invalid` 的 package；
2. 用第 4.2 的正则字段和第 4.3 的 subject/kind 规则让 Ticket、evidence、worker、handoff
   和 checkpoint facts 进入正确 context；
3. 用第 4.4/4.5 的 heading/line 形式构造 finding 和 Gate；
4. 用第 2 节逐项反查 source、expected value、缺失语义和 slug，并按第 5 节照抄
   三个端到端目录。

`manual` situation（`ticket.route.multiple-business-outcomes`、
`ticket.route.sources-conflicting`）没有机械 when key，只进入 `manual`，由主控做语义判断。

projection drift 已改为结构化 validation result；owner 声明型业务事实的 ownership 统一落在
trail 的 fact 通道，陈旧性只通过 `ts` 暴露，不由 renderer 自行过期。本文剩余的边界是
`manual` row 的语义判断，以及完整 runtime 对 plan/spec、Publication Status、artifact、Git
revision 和 projection 的额外校验。

## 9. 42 行 `slug → when` 完整映射

前面的第 2 节解释每一个 `when` key 如何产生值；本节把正式
`situations.yaml` 的 42 行逐行展开。这里的“命中”严格指：在相应 subject context
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

### 9.1 P0：legacy 有序层与全局 blocking

P0 内部顺序只决定旧四键的 `selected/other_matches/suppressed_matches` 兼容输出。新投影只把
`attempt.gate.terminal-frozen`、`package.record.state-missing`、
`package.record.projection-drift` 和 `attempt.record.anchor-mismatch` 放入 `blocking`；其余 P0
命中仍作为普通动作参与新分区，不会凭 legacy 顺序暂停全部 runnable 工作。

| 顺序 | slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| ---: | --- | --- | --- | --- |
| 1 | `attempt.gate.terminal-frozen` | `gate.terminal = true` | `gate.terminal` | `gate.md` 必须存在且 Verdict 可解析为 `pass`、`fail` 或 `defer`；缺 Gate 是已知 false，坏 Verdict 是 U。命中时进入新投影 `blocking`。 |
| 2 | `package.record.state-missing` | `package.state_invalid = true` | 无（该 parser 总能给出已知 true/false；外围 package 不存在仍可 HF） | 缺失或不合法 state 都是已知 true，包括 schema、Ticket、evidence、checkpoint 交叉校验失败；不要把它当作“没有 state 才命中”。 |
| 3 | `package.record.projection-drift` | `package.validate.projection_drift = true` | `package.validate.projection_drift` | 必须有结构化 `--validation-result` 且值为 true；错误的 validation result 是 HF，不是该 key 的 U。 |
| 4 | `attempt.record.anchor-mismatch` | `trail.anchor_mismatch = true` | `trail.anchor_mismatch` | 当前正式入口是 attempt scope 的 typed fact；普通 prose 或相邻 marker 不建立该事实。 |
| 5 | `attempt.record.handoff-recovery-needed` | `trail.handoff_recovery_needed = true` | `trail.handoff_recovery_needed` | 必须有 attempt scope 的 typed fact；缺声明是 U，不是“恢复正常”的 false。 |
| 6 | `attempt.record.handoff-target-corrected` | `trail.handoff_target_corrected = true` | `trail.handoff_target_corrected` | 必须有 attempt scope 的 typed fact；`chosen` 或 prose 中写 corrected 不再自动命中。 |
| 7 | `attempt.record.session-resumed` | `attempt.active_checkpoint_present = true` AND `trail.actions_since_checkpoint = 0` | `attempt.active_checkpoint_present`、`trail.actions_since_checkpoint` | 只需要合法 state 中的 `activeCheckpoints.attempt`，以及 checkpoint 后没有动作。显式 `attempt.session_resumed` 不再是判据；有 marker 时检查 marker 后的行数，没有 marker 时忽略兼容性的 session declaration、但其它 typed fact/action 会使计数大于 0。 |
| 8 | `ticket.record.evidence-unfiled` | `trail.direct_evidence_returned = true` AND `evidence.indexed = false` | `trail.direct_evidence_returned`、`evidence.indexed` | 必须在当前 Ticket subject 下有 `result` 或 `worker-return` 的 direct-evidence payload；要让 `evidence.indexed` 确定为 false，payload 还必须能解析出完整的 artifact、claim、revision、environment tuple，但该 tuple 不得出现在未 invalidated 的 `evidenceIndex` 中。payload 缺 link 字段会使第二个 key U。 |

### 9.2 P1：准入与 worker liveness

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `attempt.record.handoff-due` | `attempt.compaction_pressure_high = true` | `attempt.compaction_pressure_high` | 需要调用方传入 `--compaction-pressure` 的合法 JSON 且 `high=true`；缺参数是 U，不命中该行；它位于 P1，因此 P0 完整性行仍先显示。默认动作是在主控选定的下一个 recovery checkpoint 后交接，不中断当前单元。 |
| `attempt.record.trail-rotation-due` | `trail.last_ticket_terminal_transition = true` AND `attempt.has_pending_ticket = true` | `trail.last_ticket_terminal_transition`、`attempt.has_pending_ticket` | 与 Ticket 边界交接同一机械窗口；动作入口是显式 `recovery checkpoint --handoff`，不把普通 checkpoint 当作轮换触发，也不读取 pressure key。state 先提交，CLI 随后写 `kind=handoff` 并轮换活动 trail；轮换失败只 warning。轮换后 renderer 按编号归档后接新 `trail.jsonl` 恢复连续事实。 |
| `attempt.readiness.all-edges-held` | `attempt.ready_ticket_count = 0` AND `attempt.has_pending_ticket = true` AND `attempt.implementation_edges_held = true` | `attempt.ready_ticket_count`、`attempt.has_pending_ticket`、`attempt.implementation_edges_held` | 需要合法 state、每个 Ticket 文件都能解析、implementation dependency 的目标状态都能判定，并且至少有一个 `PENDING` Ticket；不能只在“看起来没有 ready Ticket”时手写期望。后两个条件在当前实现中有推导重叠，但 row 仍会逐项比较。 |
| `attempt.readiness.multiple-ready-tickets` | `attempt.ready_ticket_count > 1` | `attempt.ready_ticket_count` | 需要完整 Ticket/dependency 图；在途 dispatch 不再压掉其它 ready 候选，它们另列于 `in_flight[]`。 |
| `ticket.readiness.blocker-maybe-resolved` | `ticket.state = "BLOCKED"` AND `ticket.blocker_maybe_resolved = true` | `ticket.state`、`ticket.blocker_maybe_resolved` | 当前 Ticket 必须可由 state 和 Ticket 文件建立 context；resolved 需要 typed fact 或兼容的 Ticket 正文声明。`BLOCKED` 本身不会把 blocker 自动变成 resolved。 |

### 9.3 P2：未完成动作、调查和 review 返回

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `finding.fix.worker-envelope-invalid` | `trail.last_worker_mode = "fix"` AND `trail.envelope_valid = false` | `trail.last_worker_mode`、`trail.envelope_valid` | 必须有合法 finding context 和可归属 dispatch；envelope 的 false 来自 typed fact 或结构化字段，缺 envelope 是 U。该 `source=situation` fix 先进入 withheld；真正 fix 候选改用 owning `ticket:<id>`，brief 保留 finding 线索。 |
| `ticket.implement.worker-incomplete-first` | dispatch 轴的 `trail.last_outcome = "INCOMPLETE"` AND `trail.last_worker_mode = "implement"` | `trail.last_outcome`、`trail.last_worker_mode` | 按实际边界与上下文可信度选择恢复、调查或换人；次数不驱动不同分支，也不自动 BLOCKED。 |
| `ticket.implement.worker-blocked` | `trail.last_outcome = "BLOCKED"` AND `trail.last_worker_mode = "implement"` | `trail.last_outcome`、`trail.last_worker_mode` | 当前 dispatch 的 outcome 必须精确为大写 `BLOCKED`，worker mode 必须能解析为 `implement`；缺 trail 或无法归属是 U。 |
| `ticket.investigate.no-carrier` | `ticket.state = "PENDING"` AND `ticket.investigation_carrier_present = false` AND `ticket.investigation_context_clear = true` AND `evidence.count = 0` | `ticket.state`、`ticket.investigation_carrier_present`、`ticket.investigation_context_clear`、`evidence.count` | carrier 只由当前 Ticket 的 investigate 派发/结果或 `timing=early-falsification` evidence 建立；其它 typed fact 表示已有明确处境，不让该 P2 row 越权抢占；仍要求 evidenceIndex 完全为空以避开已进入 acceptance/补证窗口的 Ticket。 |
| `ticket.investigate.evidence-gap` | `trail.last_outcome = "EVIDENCE_GAP"` | `trail.last_outcome` | 当前 dispatch 的 result-like outcome 必须精确为 `EVIDENCE_GAP`；只写普通 prose、缺少 `of` 或另一个 dispatch 的 outcome 不能保证该 row 命中。 |
| `finding.fix.reviewer-returned` | `trail.last_outcome = "FINDING"` AND `trail.finding_source = "reviewer"` | `trail.last_outcome`、`trail.finding_source` | finding ID 必须存在并与 trail subject 一致；文档来源字段不替代 trail source。该 fix 建议未声明时 withheld；主控以 owning Ticket 声明 fix，并把 reviewer 原始意见、定位和裁决带入 brief。 |
| `attempt.review.reviewer-unavailable` | `trail.reviewer_unavailable = true` | `trail.reviewer_unavailable` | 必须有 attempt scope typed fact；`timeout`、`unavailable` 等自由文本不再触发。 |
| `finding.fix.main-session-discovered` | `trail.finding_source = "main-session"` | `trail.finding_source` | 需要存在的 finding context 和当前 finding trail source。若选择修复，主控以 owning Ticket 声明 fix 候选，并把 finding 线索带入 brief。 |
| `finding.review.source-recheck-pending` | `finding.review_track = "C"` AND `finding.source_recheck_pending = true` | `finding.review_track`、`finding.source_recheck_pending` | 必须有可解析 finding block，且 block 中是 Track C 与 source-recheck pending；没有 Track 会得到已知 None，不会命中 C。 |

### 9.4 P3：验证、返工和路由

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `ticket.verify.contradictory-unresolved` | `evidence.contradictory_unresolved = true` | `evidence.contradictory_unresolved` | 当前 Ticket、state/evidenceIndex 和 acceptance pair 必须可读；只在该 pair 的 required claim 中存在 active `contradictory`/`inconclusive` 记录时命中。其它 revision 或非当前 required claim 的冲突不再触发。 |
| `ticket.verify.safety-invariant-unfalsified` | `ticket.safety_invariant_unfalsified = true` | `ticket.safety_invariant_unfalsified` | Ticket 必须解析出一个以 `INV-` 开头的 Stable claim ID，且至少一个此类 claim 没有 active evidence record；没有安全 claim 是已知 false，不是 U。 |
| `ticket.rework.evidence-conflict` | `ticket.state = "SATISFIED"` AND `evidence.new_claim_conflict = true` | `ticket.state`、`evidence.new_claim_conflict` | 当前实现把 `new_claim_conflict` 建立在 SATISFIED Ticket 的 active contradictory/inconclusive evidence 上；需要合法 state/evidence。非 SATISFIED 会使第二个事实已知 false。 |
| `ticket.rework.revision-diverged` | `git.acceptance_revision_diverged = true` AND `git.head_advanced_since_last_trail = true` AND `git.accepted_seam_changed = true` | `git.acceptance_revision_diverged`、`git.head_advanced_since_last_trail`、`git.accepted_seam_changed` | `git.accepted_seam_changed` 机械比较 acceptance revision 到当前 HEAD 的 diff。只有全部改动都在 `docs/` 下或后缀为 `.md` 才为 false；存在其它路径才为 true。拿不到或无法解析 acceptance revision、无法读取/得到空 diff 时为 U。 |
| `ticket.rework.revalidation-pending` | `ticket.state = "NEEDS-REVALIDATION"` | `ticket.state` | 必须在 state 中为当前 Ticket 建立合法 row；仅在正文写“待重验”不会改变 state。 |
| `ticket.route.multiple-business-outcomes` | `when: manual`，无机械条件 | 无 | 不会被 parser 依据字段自动命中；主控只有在发现多个合理业务结果且机械输入无法裁决时，才主动进入该 manual row。 |
| `ticket.route.sources-conflicting` | `when: manual`，无机械条件 | 无 | 不会因 evidence 数量、文本里的 conflict 字样自动命中；主控需判断来源是否缺失、含糊或冲突后主动进入。 |
| `attempt.rework.contract-changed` | `git.contract_changed_since_last_trail = true` | `git.contract_changed_since_last_trail` | trail 中必须有可比较的旧 `head`，且 `head..HEAD` 可读并命中 `plan.md`、`spec.md`、`contract-design.md`、`decision.md` 或 `tickets/` 路径；没有旧 head 是 U。 |

### 9.5 P4：acceptance 与全局收口

| slug | 完整命中条件（全部 AND） | U key | 命中所需的实现前置条件与常见漏项 |
| --- | --- | --- | --- |
| `ticket.accept.acceptance-edge-held` | `evidence.count > 0` AND `ticket.acceptance_edge_released = false` | `evidence.count`、`ticket.acceptance_edge_released` | 必须有至少一条 evidenceIndex 记录（包含已 invalidated 记录的计数也算），并且当前 Ticket 的 typed `acceptance` dependency 至少有一条尚未释放。没有 acceptance edge 时 `all([])` 是 true，不能用“没有依赖”构造 held。 |
| `ticket.accept.release-edge-unchecked` | `ticket.acceptance_conditions_satisfied = true` AND `ticket.release_edge_present = true` AND `ticket.release_edge_rechecked = false` | `ticket.acceptance_conditions_satisfied`、`ticket.release_edge_present`、`ticket.release_edge_rechecked` | 只对真实存在 release dependency 的 Ticket 提醒；acceptance conditions 需要同一 revision/environment 下所有 required claims supporting 且没有 active contradictory/inconclusive；本 row 是流程提示，CLI 不检查 `release_edge_rechecked` fact。 |
| `ticket.accept.satisfiable` | `evidence.all_required_claims_supported = true` AND `evidence.contradictory_unresolved = false` AND `ticket.acceptance_edge_released = true` AND `ticket.acceptance_revision_parseable = true` | `evidence.all_required_claims_supported`、`evidence.contradictory_unresolved`、`ticket.acceptance_edge_released`、`ticket.acceptance_revision_parseable` | 需要 Ticket 的 Stable claims 可解析、同一 acceptance pair 覆盖全部 claims、该 pair 无 active contradictory/inconclusive、所有 acceptance edges 已释放，且 revision 能被当前 Git resolve；与 CLI `ticket satisfy` 的 `_evidence_coverage` 同一 pair 语义。 |
| `attempt.review.terminal-coverage-incomplete` | `attempt.terminal_coverage_complete = false` | `attempt.terminal_coverage_complete` | 最新 structured summary 缺少 required 结果或有效 report / 复用证据时命中；手工 fact 不替代结果证据。 |
| `finding.disposition.grading-undecided` | `finding.grading_pending = true` | `finding.grading_pending` | 必须有可解析的 open finding，且没有合法 Grade 或有 `grading_pending`/待定级 marker；closed finding 会得到 false。 |
| `attempt.disposition.findings-triage-pending` | `findings.triage_pending = true` AND `attempt.near_terminal_gate = true` | `findings.triage_pending`、`attempt.near_terminal_gate` | execution-findings.md 必须存在且至少有一个 parsed finding 未分流；near-terminal 条件是“所有 Ticket terminal”或“属于当前 Attempt 的 Gate 文件存在且 Verdict 可解析”，malformed Gate 或只有上一个 Attempt 的 Gate 都不满足该辅助条件。 |
| `attempt.accept.all-tickets-terminal` | `attempt.all_tickets_terminal = true` | `attempt.all_tickets_terminal` | state 必须合法、Ticket 集合非空，且每个 Ticket state 都是 `SATISFIED` 或 `RETIRED`；空 tickets 是已知 false。 |
| `attempt.gate.durable-delta-missing` | `gate.stage7_complete = false` AND `attempt.terminal_gate_pending = true` | `gate.stage7_complete`、`attempt.terminal_gate_pending` | 要让这行真正可命中，所有 Ticket 必须 terminal，且当前 Attempt 的 Gate 没有 meaningful Durable Delta bullet——包括“Gate 文件存在、属于当前 Attempt 且 Verdict 可解析为非 terminal（如 blocked/undecided）但缺 bullet”，以及“Gate 文件只属于上一个 Attempt（当前 Attempt 尚未写 Gate）”两种情形，后者 `stage7_complete` 直接为 false 而非 U。物理上完全缺 Gate 会让 `stage7_complete` U，不能命中。 |
| `attempt.gate.missing` | `gate.present = false` AND `attempt.terminal_gate_pending = true` | `gate.present`、`attempt.terminal_gate_pending` | 只在所有 Ticket 已 terminal 且当前 Attempt 尚未写 Gate 时命中；物理上存在但只属于上一个 Attempt 的 Gate 按“当前 Attempt 缺 Gate”处理，同样能命中；非 terminal 工作窗口不会因为缺 Gate 产生该 row。 |
| `attempt.gate.verdict-undecided` | `gate.present = true` AND `gate.verdict = "undecided"` | `gate.present`、`gate.verdict` | 只表示已写入 Gate 且 Verdict 显式为 `undecided`；缺 Gate 由 `attempt.gate.missing` 单独表达，malformed Verdict 是 U。 |

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
5. **multiple-ready 不受无关 in-flight 压制。** ready 仍由 canonical implementation dependencies 判定；在途工作单独呈现。
6. **`no-carrier` 的“无 carrier”是组合推导。** 必须同时是 PENDING、没有结构化 investigate 派发/结果、没有 early-falsification evidence、没有其它 typed 处境，且 `evidenceIndex` 计数恰为 0；它不是单独的 carrier 字段。
7. **`no-carrier` 的排除边界是显式 typed fact。** P3/P4 输入一旦已有其它 typed fact，no-carrier 不再越权抢占；纯 checkpoint marker 不算该排除条件。
8. **worker incomplete 按 dispatch 归属。** 次数只作观察；续接、调查或换人依据边界与上下文可信度。
9. **finding 的文档来源和 trail 来源不是同一字段。** reviewer-returned/main-session-discovered 看 trail 的 `finding_source`；finding block 的 `finding-source` 不能替代它。
10. **safety-invariant 行依赖 Stable claim ID 正则。** 只有 `INV-` 前缀 claim 会进入安全不变量集合；没有该 claim 时是已知 false。
11. **awaiting-reviewer 的 Ticket prose fallback 仍依赖可读 trail。** 无 trail 时 parser 在 fallback 前返回 U，不能只凭 Ticket 正文的 `review: required` 预测命中。
12. **satisfiable 需要同一 acceptance pair。** 所有 claims 必须在同一 revision/environment 下 supporting；evidence 数量大于 0 不足以命中。
13. **acceptance-edge-held 需要真实 acceptance edge。** 没有 acceptance dependency 时 `all([])=true`，不能把“无依赖”当作 held。
14. **revision-diverged 需要两套比较都成立。** acceptance revision 必须可 resolve 且相对 HEAD 已分叉，同时 trail 旧 head 也必须存在且已前进。
15. **findings triage 的 near-terminal 条件不接受 malformed 或跨 Attempt 的 Gate。** 所有 Ticket terminal，或 Gate 文件存在、属于当前 Attempt 且 Verdict 可解析，才算接近 terminal；只有上一个 Attempt 的 Gate 不算数。
16. **terminal coverage 使用结果证据。** 从最新 `review.terminal_summary` 与各 track 的独占 report 判定：A/B/C required，按需 Safety；A 最终 HEAD 重审，B/C/Safety 在同 ReviewRun 内凭 PASS 与 reuseEvidence 复用。dispatch 或 Gate 终态不替代结果。
17. **release-edge-unchecked 需要显式 `release_edge_rechecked=false`。** 缺声明不会自动变成 false。
18. **durable-delta-missing 也覆盖跨 Attempt 的 Gate。** 一个存在且可解析的非 terminal Gate 缺 bullet，或物理上只存在上一个 Attempt 的 Gate，都会让 `gate.stage7_complete` 为 false；物理上完全缺 Gate 才是 U。
19. **comparison-mismatch 在 pass 前检查。** 只有 completion claim pending、尚无 Gate 且当前 HEAD 与 SATISFIED acceptance revision 不一致时命中；pass 后不再产生该 row。
20. **缺 Gate 不再合成 `gate.verdict=undecided`。** terminal Gate pending 时由 `attempt.gate.missing` 表达；已有 Gate 且显式写 `undecided` 才进入 `attempt.gate.verdict-undecided`。
21. **intake 是 first-existing-wins。** 前序候选即使为空，也会阻止后序候选被读取；不能只看目录里“某处”有 backlog。

## 10. 如何预测一个包最终呈现什么

只读推导器输入并预测主控可执行集合时，按下面顺序走查：

1. **确认硬失败。** package 路径、`--at` commit、正式/override table 和结构化外部输入必须可读且合法；HF 时停止，U/F 预测不适用。
2. **建立 contexts 并枚举。** 从 state、Ticket 与 findings 建立合法 subject，对第 9 节全部 42 行求值。真值进入 `matches`，缺输入进入 `undetermined`，manual 保持单独列出；这些是诊断全集，不是单选 cursor。
3. **先看 `blocking`。** 只有 terminal-frozen、state-missing、projection-drift、anchor-mismatch 四类全局事实阻止本轮全部 dispatch。其它命中继续参与候选分区。
4. **核对 `in_flight`。** 按 dispatch_id 列出已派发且没有匹配 worker-return 的工作。它是并行安排与恢复事实，不会自动压掉无关 runnable。
5. **核对候选清单状态。** 每项的 `declaration_status=current|missing|stale` 与 `declaration_reason` 只说明辅助记录新鲜度。stale 清单按当前事实重算并保留显式 blocker；最新空清单清除补充候选。`implement/fix` 绑定存在且 ready 的 Ticket；attempt/finding 只承载 investigate/verify，finding 必须存在。
6. **读取 `runnable/withheld` 全集。** 当前 dependency、授权、实际资源冲突或同一工作 in-flight 形成 blocker 的候选进入 `withheld`；其余合法 situation action、主控机械动作、补充候选与待派 review 进入 `runnable`。missing/stale declaration 不改变分区结论。
7. **按实际冲突安排。** `resource_keys` 相同只说明观察到同一资源，不自动表示互斥。主控把不兼容 effect footprint 写成 resource blocker；稳定读取可以并行，renderer 不建立资源锁。
8. **派发或恢复。** dispatch 自身携带目标 subject、mode、resource_keys、identity 与 receipt；`candidates_of` 可选。任一状态输入变化后重新 render，并用实时 dependency、授权、资源与 in-flight 校验准入；credential 中的 `runnable_candidate_ids` 只供审计。在途返回按 `of` 跨归档恢复；无 worthwhile runnable 时可以等待，但 idle/in-flight 不代表 Ticket 或 package closed。
9. **保留 legacy 输出。** `selected/parallel_matches/other_matches/suppressed_matches` 和 `legacy_digest` 继续按旧优先级生成，供旧消费者读取；主控不依据它们裁掉新分区中的候选。

### 10.1 关键分区边界

- `ticket.investigate.no-carrier` 只覆盖 PENDING、无调查 carrier、无其它 typed 处境且 evidenceIndex 为空的 Ticket；命中只是一个待声明的 dispatch 建议。
- `attempt.gate.missing` 只在所有 Ticket terminal 且缺当前 Attempt Gate 时命中。普通 PENDING 窗口不会因缺 Gate 阻塞其它候选。
- `attempt.accept.all-tickets-terminal` 是普通处境动作；只有四个 `GLOBAL_BLOCKING_SLUGS` 会清空新投影的 `runnable`。
- worker 的 `INCOMPLETE/BLOCKED` 结论按 dispatch 归属。主控依据边界和上下文可信度决定续接、调查或换人，次数不产生自动升级。

### 10.2 关键输入的预测

- `p0-session-resumed`：active checkpoint 存在且 checkpoint 后没有动作，直接由 state/trail
  结构命中；不依赖声明事实。
- `package.record.projection-drift`：只有 `--validation-result` 的结构化输入能让该行命中；
  trail fact 不再作为 fallback。
- `ticket.rework.revision-diverged`：`git.accepted_seam_changed` 由 acceptance revision
  到当前 HEAD 的 diff 自动判定，不接受手工覆盖。
- `attempt.review.terminal-coverage-incomplete`：只按最新 `review.terminal_summary`、当前
  HEAD、required review tracks 与 report 判定，不接受旧布尔覆盖。
- `p4-acceptance-edge-held`：evidence count 大于 0 且 acceptance edge 未释放使目标命中；
  Ticket 尚未 terminal，所以缺 Gate 不产生 `attempt.gate.missing`。该命中与其它候选一起进入
  新分区，不生成唯一可见 row。

### 10.4 缺失或零行 trail 的降级补充

缺失全部 `trail.NNN.jsonl` 与活动 `trail.jsonl`，或连续流没有事件时，候选 declaration 为
missing，但这不阻止 situation 根据当前 package 事实产生合法 runnable。此时不存在已有
dispatch identity 或可恢复的 worker-return 轴，不能把 `last_outcome=None` 或
`incomplete_count=0` 当成“worker 已成功/从未失败”的运行事实，也不能据此派发、换人或关闭
工作；dispatch-scoped action 没有归属输入。旧 result/dispatch 存在但缺 `of/dispatch_id` 时，
跨工作聚合结果为 U。

其它 key 是否能从空事件集得到已知 false，逐项以第 2 节为准；坏 JSON、读取错误仍为 U。
依赖调查 carrier、复核、handoff recovery、handoff target、envelope、release recheck 或 Git
trail head 的判断不能用“没有事件”替代证据。恢复时读取编号归档加活动文件的完整连续流；
旧 package 缺少新关联字段时保留兼容事实，并把无法归属的结论留为 unknown。

### 终审结果事实

`review.terminal_summary` 是 attempt-scoped structured fact，形状与写入时机见 `../skills/do-review/references/output-templates.md` 的 Terminal coverage record。renderer 读取 package 内 report 的 verdict、reviewed-head、review-run、review-track，核对当前 comparisonHead 与条件 Safety；B/C/Safety 旧 PASS 还需同 ReviewRun 的 reuseEvidence。`attempt.terminal_coverage_complete` 只由这些结果证据计算。
