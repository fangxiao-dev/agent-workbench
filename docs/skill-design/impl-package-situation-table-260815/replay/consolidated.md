# dev-with-track 处境表回放合并：可执行修表提案

日期：2026-08-15  
输入：`map-case1.md`、`map-case2a.md`、`map-case2b.md`、`map-case2c.md`、`map-case2d.md`、`map-case3.md`  
明确忽略：同目录较早的 `case-3.md`

## 总结

本报告只完成 replay 的合并、去重和修表提案；没有修改 `situations.yaml`、README、人读枚举或任何其它仓库文件，因此“提案阶段完成”不等于修表已 apply，也不等于整个工作 closed。六份报告合计 240 个决策点、167 个主命中、68 个明确 `unmatched`，命中率为 69.6%，多重命中 61 个。跨报告去重后有 23 个候选新增行：22 个可以使用现有 12 个环节，1 个是必须新增环节取值的重大变更备选；其中 13 个原始 unmatched 不建议进表。Owner 需要决定的是：是否先 apply 优先级与证据 intake 契约，以及是否把规划生命周期继续留在 dev-with-track 表外；本报告不替 Owner 做这两个决定。

准确口径如下：

- 22 条“现有环节”候选覆盖 44 个 unmatched 决策点。
- 1 条“新增环节”重大备选覆盖 11 个规划边界决策点；它不建议本轮加入 dev-with-track，只作为需要另开设计决策的方案保留。
- 13 个 unmatched 明确不建议进表。`44 + 11 + 13 = 68`，与六份报告的明确 unmatched 总数对账。
- `insufficient-evidence` 不并入 68。它们只进入跳步和 evidence 章节的证据边界统计。

### 六份报告的合并读数

| 报告 | 决策点 | 主命中 | 明确 unmatched | 报告内多重命中 |
| --- | ---: | ---: | ---: | ---: |
| case1 | 22 | 11 | 10 | 5 |
| case2a | 39 | 27 | 12 | 8 |
| case2b | 34 | 25 | 7 | 11 |
| case2c | 35 | 26 | 9 | 12 |
| case2d | 65 | 40 | 25 | 13 |
| case3 | 45 | 38 | 5 | 12 |
| **合计** | **240** | **167** | **68** | **61** |

所有 slug 均按 `对象.环节.状况` 三段式检查；新增建议遵守现有对象×环节矩阵，并按六条判定线区分 `record`、`verify`、`readiness`、`review`、`rework` 和 `fix`。新增行的 basis 默认建议为 `prose`：回放显示它们是流程规则或主控判断，尚没有 CLI 强制。只有在 CLI 已经拒绝该情况时才应改成 `cli`。

## 1. 新增行提案

### 1.1 可用现有 12 个环节表达的 22 条

下表的“出现”是原始 unmatched 决策点的归并计数，不是建议 slug 的字符串出现次数。`case2d #63` 的 external HEAD advance 归入比较点未固定这一结构性缺口，不再另造 planning 行。

| 编号 | 建议 slug | 出现报告与次数 | 现表为什么接不住 | basis | 可选动作与默认动作 |
| --- | --- | --- | --- | --- | --- |
| N01 | `attempt.readiness.single-ready-ticket` | case2a ×1（D15） | 现表只有多个 ready、所有边被挡和 blocker 重评；唯一 ready Ticket 的正常前沿没有正向行。 | prose | 默认：选择并派发唯一 ready Ticket；可选：暂缓并记录依赖/集成顺序理由。 |
| N02 | `attempt.readiness.patch-attempt-not-initialized` | case3 ×1（seq 382–415） | `attempt.gate.terminal-frozen` 不能区分“继续旧 attempt”与“Owner 已授权的新 patch 但尚未 init”。 | prose | 默认：校验授权后初始化并绑定新 patch attempt；可选：授权或绑定缺失时 fail closed 回规划。 |
| N03 | `attempt.verify.baseline-freshness-missing` | case2a ×1（D03） | 历史 anchor 缺失但当前 main 足以给出继续结论，不是普通 evidence gap，也不是 Ticket safety claim 未验证。 | prose | 默认：核验当前 baseline 的 freshness 并记录边界；可选：明确以当前 main 继续并写 reason。 |
| N04 | `ticket.rework.rebase-conflicts-present` | case2a ×1（D23） | `ticket.rework.revision-diverged` 只给重新取证或确认原结论，没有 shared seam 冲突的解决/重验动作。 | prose | 默认：按已验证 resolution 手工解决冲突并重验；可选：中止 rebase，重新 investigate。 |
| N05 | `attempt.record.handoff-in-flight` | case2a ×5（D04、D16、D29、D34、D37）；case2b ×1（seq 2456）；case2c ×1（#33） | A3 只覆盖恢复成功，G1 只覆盖 checkpoint 缺失；持续 relay、已存在 checkpoint 的 handoff pending 和 continuation 发送没有载体。 | prose | 默认：写入/校验 checkpoint 与 relay 上下文，验证 anchor 后发送 continuation；可选：保持 pending 并等待 Owner 重选顺序。 |
| N06 | `attempt.record.anchor-mismatch` | case2a ×1（D07）；case2c ×1（#34） | anchor 事实存在但因 branch/path/分隔符表示不一致而 FAIL，不能误套 `state-missing` 或成功的 `session-resumed`。 | prose | 默认：规范化 anchor 后重试；可选：停止 continuation，重建 handoff。 |
| N07 | `attempt.record.handoff-recovery-needed` | case2c ×1（#31）；case2d ×1（#23） | 新 thread 重命名/创建失败是 handoff bootstrap 故障，不是 checkpoint 内容缺失。 | prose | 默认：停止重复创建，记录失败并执行一次受控 bootstrap retry；可选：上交 Owner。 |
| N08 | `attempt.record.handoff-target-corrected` | case2a ×1（D25）；case2c ×1（#29） | handoff 目标或顺序选错后被纠正，现有 A3/G1 没有目标校正动作。 | prose | 默认：记录 corrected target/order 后重新发送；可选：取消本次 handoff，等待新目标。 |
| N09 | `attempt.record.checkpoint-refresh` | case1 ×2（D10、D20） | G1 的判据是 checkpoint 缺失；已有 active checkpoint 的推进、刷新和下一动作改变没有记录行。 | prose | 默认：刷新 active checkpoint；可选：发现并发冲突时转 N11。 |
| N10 | `ticket.record.judgment-unfiled` | case1 ×2（D09、D19） | C8 只覆盖 evidence index；主控已经形成 recovery/finding-closure judgment，但没有“结论存在、尚未入账”的 record 行。 | prose | 默认：把 judgment、subject、claim 边界和结果写入记录；可选：判断尚未完整时记录 pending reason。 |
| N11 | `attempt.record.checkpoint-projection-race` | case2c ×1（#32） | G1 只表达需要写 checkpoint，不表达旧 session 异步改写 projection 时的并发冲突和 canonical record 选择。 | prose | 默认：只读核对正式 ER/anchor，采用 CAS 或重试刷新；可选：冲突未消除时 fail closed。 |
| N12 | `attempt.record.bookkeeper-partial-write` | case3 ×1（seq 1006–1025） | bookkeeper 0/3 或部分写入不是 Ticket implement，也不是 intake backlog；现表不能表达部分落账后的恢复。 | prose | 默认：按写入清单核对缺项并由 owner 机械补写；可选：停止后续派发并上交 Owner。 |
| N13 | `finding.review.closure-awaiting` | case1 ×2（D05、D17） | E1 描述 reviewer finding → fixer，E2 只覆盖 source recheck；fix 已完成后等待同 scope finding-closure reviewer 的窗口没有行，C6 的 `last_outcome=DONE` 也不适配。 | prose | 默认：派同 scope closure reviewer；可选：reviewer unavailable 时保持 finding 未闭合并记录。 |
| N14 | `ticket.verify.worker-incomplete` | case1 ×1（D13） | C10/C11 把 INCOMPLETE 绑定在 `implement`，verify worker 的 INCOMPLETE 会被错误导向 implement/fallback，不能表达实际的独立 review/诊断动作。 | prose | 默认：转独立 review/诊断验证 blocker；可选：允许一次有 reason 的 verify retry。判据必须含 `worker_mode=verify`。 |
| N15 | `finding.fix.worker-envelope-invalid` | case2b ×2（seq 1995、2747） | C10–C12 只合法作用于 `ticket.implement`；ack-only、commit 后无完整 envelope 的 finding fixer 不能套业务 `BLOCKED`。 | prose | 默认：不采信 envelope，停止残余进程，检查 diff 后 fresh invocation；可选：由主控做 bounded direct verification 并强制复审。 |
| N16 | `finding.review.candidate-unverified` | case2b ×1（seq 2278） | E4 假定 finding 已进入定级；reviewer candidate 还需 parent 核实事实，不能直接 P1/P2/editorial。 | prose | 默认：核实 candidate 的事实和 scope 后再定级；可选：标为 UNCERTAIN 并请求 Owner。 |
| N17 | `finding.fix.parallel-fan-in-pending` | case2b ×1（seq 2649–2721） | B1 只描述多个 ready Ticket，不描述同一 Ticket 多个 disjoint finding/seam 的部分返回、等待剩余 worker 和一次性 fan-in。 | prose | 默认：等待全部 admitted seam 返回后统一集成/复核；可选：将剩余 seam 改串行并记录理由。 |
| N18 | `attempt.review.reviewer-unavailable` | case2b ×1（seq 3126）；case2c ×1（#7） | F3 只能表达 coverage incomplete，不能区分正常等待、超时、无效 envelope、压缩返回、取消旧 ReviewRun 和重开 fresh reviewer。 | prose | 默认：一次 bounded escalation 后关闭不可采信的 ReviewRun 并重开 fresh review；可选：标 UNCERTAIN，保持 Gate/acceptance 不动。 |
| N19 | `attempt.verify.integration-evidence-unavailable` | case2b ×1（seq 2776–2799）；case2c ×1（#25） | C13 只能说不能收，F1 又要求既有 manual owner；这里是所需外部/integration evidence 根本不可取得，不是普通 record gap。 | prose | 默认：保留 lower-layer evidence，明确 acceptance held，并请求/选择已批准的验证载体；可选：defer 并记录缺失环境。 |
| N20 | `attempt.readiness.integration-carrier-unavailable` | case2d ×3（#28、#32、#37） | 5433、dotenv 顺序、DIRECT_URL 等使 integration carrier 不可用；B2 太宽，F1 太窄，现表没有选择等价 process-scoped carrier 的 readiness 行。 | prose | 默认：切换已批准的等价本地 profile，不改配置文件或远程库；可选：无法提供等价载体时保持 blocked/defer。 |
| N21 | `attempt.review.comparison-head-unfixed` | case2c ×1（#19）；case2d ×4（#6、#41、#42、#63）；case3 ×1（seq 1151–1206） | dirty worktree、staged scope、外部 HEAD advance 和临时 snapshot 使 review 没有可信 immutable comparison head；D2 只处理 acceptance revision divergence，F7 只处理 pass 后 mismatch。 | prose | 默认：固定 exact immutable head，隔离 protected docs，再以新 head 重开 review；可选：停止该 ReviewRun 并请求 Owner 授权 commit。 |
| N22 | `ticket.verify.post-fix-regression-pending` | case2d ×1（#5） | 现有 verify 行只描述 safety/manual claim，不描述 fix 返回后由 owner 统一跑 focused/typecheck/lint、完成后才重进 review 的顺序。 | prose | 默认：先跑授权范围内 post-fix regression，再进入 review；可选：以明确 waiver 进入 review，不能直接 satisfy。 |

这些 22 条的共同点是：它们都能在现有矩阵中找到合法对象和环节。尤其 worker/tool 异常不需要新增 `worker` 或 `envelope` 环节；它们分别落在 `implement`、`fix`、`review` 或 `record`，执行者和协议结果写在 `when`/action 中即可。集成 readiness、baseline freshness、dirty comparison head、parallel fan-in 和记录层 race 也都不需要新增 phase。

### 1.2 必须新增环节取值的重大变更备选：1 条，当前不建议加入

| 编号 | 备选 slug | 出现报告与次数 | 为什么不能用现有 12 个环节 | basis | 如果 Owner 坚持，必须先做什么 |
| --- | --- | --- | --- | --- | --- |
| M01 | `ticket.plan.lifecycle-boundary` | case2d ×11（#52、#54、#55、#56、#58、#59、#60、#61、#62、#64、#65） | 这些动作属于 req-align/impl-planning 的规划 bundle、设计预览、artifact write/review、scope freeze 和“runtime state 尚未初始化”，不是 dev-with-track 的 investigate/route/readiness。硬塞成 `investigate` 或 `readiness` 会把阶段边界伪装成实现前沿。 | prose | 新增 `plan` 或 `align` phase，修改 README §9.2 的 phase 域、§9.3 对象×环节矩阵、YAML `phases/allowed`、人读枚举、renderer 和 trail 取值域，并另做 owner 决策。当前建议继续按 README §11 留在表外。 |

`case2d #63` 的 external HEAD advance 已归入 N21，因为它改变了 comparison head；因此 M01 是 11 条，不是 12 条。规划 lifecycle 若未来需要建模，应该新建/扩展规划阶段的表，不应为 dev-with-track 偷加一个 catch-all phase。

### 1.3 13 个不建议进表的 unmatched

这些点仍然保留在合并账中，但不把一次性事件写成永久规则。理由不是“没发生”，而是它们目前没有足够重复度，或者是版本/表外 artifact/偶发环境故障；应由现有行的 reason、evidence scope 或外部工具记录承接。

| 原始建议 | 出现 | 不建议进表的理由与替代处理 |
| --- | --- | --- |
| `package.record.projection-stale` | case1 ×1（D06） | 是旧 Runtime Acceptance projection 遗留，且与现有 `package.record.projection-drift` 不是同一判据；按 §4.1 改 projection drift 的输入来源，不新增 stale 子类型。 |
| `attempt.verify.environment-authorized` | case1 ×1（D14） | 一次 Owner 授权导致验证 profile 切换，不是稳定处境；把授权变化作为 verify evidence/context 记录。 |
| `attempt.record.change-committed` | case1 ×1（D22） | 一次用户请求的 landing boundary，不应把每次 commit 都变成处境行；需要 immutable review head 时由 N21 承接，普通 commit 留在 execution record。 |
| `attempt.review.external-contract-impact` | case2a ×1（D18） | 单次外部 comment 影响审阅，可由 C7/C5 的 review/来源判断和 reason 承接；重复出现后再看是否需 attempt-level review 行。 |
| `attempt.record.impact-guidance-written` | case2a ×1（D21） | artifact 写在 package 外部 Temp，不是 package evidence/checkpoint；由外部 artifact pointer/Execution Record 记录。 |
| `attempt.rework.finding-deferred` | case2c ×1（#30） | 这是一次 Owner 选择把 finding 留给下一 session 的调度决定，可在现有 rework/checkpoint 行上写 reason，不另造 finding 状态。 |
| `attempt.record.review-ledger-stale` | case2d ×1（#19） | 一次 ledger provenance header 漂移；先由 validator/ledger schema 校验修复，避免把每一种 metadata stale 都拆成 record 行。 |
| `attempt.verify.runner-timeout` | case2d ×1（#38） | 一次并行负载下的 runner timeout，按 N18/N19 的证据边界记录，不足以成为通用 verify situation。 |
| `attempt.verify.quality-bundle-pending` | case2d ×1（#39） | 一次质量 bundle 收口顺序，属于验收计划/证据编排，不是独立处境；由 F1/F2/F3 和 evidence bundle 记录。 |
| `attempt.verify.flaky-run-recheck` | case2d ×1（#46） | 一次污染敏感的重跑，属于测试工具策略；不把 flaky runner 作为流程规则。 |
| `ticket.verify.out-of-scope-wrapper-failure` | case2d ×1（#47） | 一次与 DMI Ticket 无关的 root wrapper 失败；必须保留 caveat 并隔离 Ticket-scoped evidence，但不应让 wrapper 噪声进入主表。 |
| `attempt.verify.component-harness-missing` | case3 ×1（seq 845） | 一次组件 harness/授权缺失，属于环境能力缺口；按 N19 的 evidence unavailable 语义或 manual reason 记录。 |
| `finding.fix.worker-blocked` | case3 ×1（seq 1468–1474） | 一次因测试依赖缺失造成的 finding fixer BLOCKED，属于偶发环境故障；若同一对象的 blocked 反复出现，再评估是否补 finding.fix 专属行。 |

因此，“不建议进表”不等于删除证据：这些事件仍应出现在 replay、Execution Record 或 evidence scope 中，避免把一次性 wrapper/环境噪声误改成永久规则。

## 2. 优先级规则怎么修

### 2.1 61 条多重命中的问题诊断

61/240 = 25.4%，所以当前首要风险不是“再多覆盖几条”，而是同一回合渲染出两个互相冲突的默认动作。现有五组有四类具体缺陷：

1. **第 1 组不是完整的记录/安全组。** 它列了 A1、A2、A4，却漏了 A3；也没有 C8、G1 以及新的 judgment/checkpoint/projection-race。A4 不是记录动作，而是 fail-closed 安全边；应把它单独作为最高安全优先项，但不应因此漏掉 A3。
2. **第 2 组和第 3 组重复。** `ticket.review.awaiting-reviewer`、`ticket.implement.worker-incomplete-first/second/blocked` 在两组同时出现。重复使“组优先”失去意义，也没有定义 worker mode。第 2 组应只负责消费返回/协议结果；第 3 组不再复制它们。
3. **第 3 组漏了实际的 admission、finding 和 record 行。** B1/B2/B4、E2/E3/E4/E5、G1、A3 等没有完整排序。case3 已实际撞出 A3/A4、E1/E5、F3/E5；`E5` 漏列是最明显的全局裁决缺口。
4. **第 4 组只排了 global closure，没有写清 local review、acceptance edge 和 finding triage 的先后。** C6/C7、C13、F3、E5 反复重叠；如果没有“证据先入账、具体 review 先于宽泛 triage、completion claim 先于 terminal coverage”的顺序，主 slug 只是事后解释。
5. **第 5 组的 G2 应永远不抢占，但不能把所有 record 问题都放到 G2。** intake backlog 是卫生项；state invalid、checkpoint、evidence 和 judgment 是完整性项，必须在它之前。

需要的修正类型不是单一的：漏列 A3/E5 等是“补组”；同组里 C6/C7、C8/E1、F2/F3 等是“补组内顺序”；C14/C5、C4/D4、C13/F3、E4/E5 需要新增“更具体的裁决规则”。

### 2.2 修正后的完整优先级规范

渲染器按下列顺序取第一个命中；其余命中保留为 secondary，不丢弃。每个 slug 只出现一次，组内从上到下有序。下面包含现有行和 22 条建议进入表的行；M01 不进入本顺序。

**P0：fail-closed 与记录完整性**

1. `attempt.gate.terminal-frozen`
2. `package.record.state-missing`
3. `package.record.projection-drift`
4. `attempt.record.checkpoint-projection-race`（N11）
5. `attempt.record.handoff-recovery-needed`（N07）
6. `attempt.record.anchor-mismatch`（N06）
7. `attempt.record.handoff-target-corrected`（N08）
8. `attempt.record.session-resumed`
9. `attempt.record.checkpoint-missing`
10. `attempt.record.checkpoint-refresh`（N09）
11. `attempt.record.handoff-in-flight`（N05）
12. `ticket.record.evidence-unfiled`
13. `ticket.record.judgment-unfiled`（N10）
14. `attempt.record.bookkeeper-partial-write`（N12）

**P1：attempt admission 与验证载体准入**

15. `attempt.readiness.all-edges-held`
16. `attempt.readiness.multiple-ready-tickets`
17. `attempt.readiness.single-ready-ticket`（N01）
18. `ticket.readiness.blocker-maybe-resolved`
19. `attempt.readiness.patch-attempt-not-initialized`（N02）
20. `attempt.readiness.integration-carrier-unavailable`（N20）

**P2：消费 worker/reviewer 返回与当前 subject 的未完成动作**

21. `finding.fix.worker-envelope-invalid`（N15）
22. `ticket.implement.worker-incomplete-first`
23. `ticket.implement.worker-incomplete-second`
24. `ticket.implement.worker-blocked`
25. `ticket.verify.worker-incomplete`（N14）
26. `ticket.investigate.no-carrier`
27. `ticket.investigate.evidence-gap`
28. `finding.fix.parallel-fan-in-pending`（N17）
29. `finding.fix.reviewer-returned`
30. `finding.review.candidate-unverified`（N16）
31. `finding.review.closure-awaiting`（N13）
32. `attempt.review.reviewer-unavailable`（N18）
33. `ticket.review.awaiting-reviewer`
34. `ticket.review.required-trigger`
35. `finding.fix.main-session-discovered`
36. `finding.review.source-recheck-pending`

**P3：事实/合同/返工裁决与验证缺口**

37. `ticket.verify.contradictory-unresolved`
38. `ticket.verify.safety-invariant-unfalsified`
39. `attempt.verify.baseline-freshness-missing`（N03）
40. `attempt.verify.integration-evidence-unavailable`（N19）
41. `ticket.verify.post-fix-regression-pending`（N22）
42. `ticket.rework.evidence-conflict`
43. `ticket.rework.revision-diverged`
44. `ticket.rework.revalidation-pending`
45. `ticket.rework.rebase-conflicts-present`（N04）
46. `ticket.disposition.retire-undecided`
47. `ticket.route.multiple-business-outcomes`
48. `ticket.route.sources-conflicting`
49. `ticket.route.sources-uniquely-decide`
50. `attempt.rework.contract-changed`

**P4：acceptance 与全局收口**

51. `ticket.accept.acceptance-edge-held`
52. `ticket.accept.release-edge-unchecked`
53. `ticket.accept.satisfiable`
54. `attempt.verify.manual-result-missing`
55. `attempt.accept.completion-claim-unaudited`
56. `attempt.review.terminal-coverage-incomplete`
57. `finding.disposition.grading-undecided`
58. `attempt.disposition.findings-triage-pending`
59. `attempt.accept.all-tickets-terminal`
60. `attempt.gate.durable-delta-missing`
61. `attempt.gate.verdict-undecided`
62. `attempt.gate.comparison-mismatch`

**P5：记录层卫生**

63. `package.record.intake-backlog`

这里有意保留几条看似“反直觉”的顺序：

- A4 先于 A3：terminal/frozen 必须先阻止旧 attempt 推进；只有确认不是 frozen，才恢复 checkpoint。
- P0 的 C8 先于 C6/E1/E5：证据或结论已经存在但未入账时，先把事实落账，再把它当作 review/fix/triage 的输入。
- B1 先于 C1：先决定本轮选哪个 Ticket，再处理被选 Ticket 的 investigate carrier；不能让一个 Ticket 的 direct-implement escape 抢占 attempt-level 选择。
- E1 先于 E4/E5，E2 先于 E5：具体 finding 的消费或 source recheck 先于宽泛的 grading/terminal triage；但 C8 仍先于 E1/E5。
- C14 先于 C5：矛盾证据先处置，再做来源冲突/req-align 路由。
- C3 先于 D4；C4 先于 D4：Owner 的业务结果和已裁定的技术路线先落定，contract-change 的 affected-subset 记录随后承接。D1/D2 已经位于其前面，保护已满足结论的冲突和 revision divergence。
- C6 先于 C7/C13：已经明确等待 reviewer 时，先消费这个具体 review；required-trigger 和 acceptance-held 只作为 secondary。C7 先于 F3，只有在它确实是当前 Ticket 的 review trigger 时成立；没有 Ticket-level trigger 时由 F3 直接裁决 terminal coverage。
- C13 先于 F3，F2 先于 F3，F3 先于 E5：不能用 terminal coverage 或 finding triage 掩盖 acceptance edge、completion claim 或完整终审尚未成立。
- C15 先于 B3/F6：Ticket satisfy 的 CLI 结果先确定，才进入“全部 Ticket terminal”或 Gate verdict。

这套顺序能对本次 61 个多重命中逐类给出唯一 primary；若未来新增行，必须先放入某一 P 组并写明与相邻行的判定线，不能只追加到 YAML 末尾。

### 2.3 61 个多重命中的逐类裁决

下表按无方向的 slug 对归并；报告里写成 `A+B` 或 `B+A` 的视为同一类。代码沿用人读枚举的 A–G 行号；`Nxx` 指本报告 1.1 的候选行。

| 同时命中的行 | 次数 | 唯一 primary | 裁决理由 |
| --- | ---: | --- | --- |
| A3 + A4 | 2 | A4 | frozen 的 fail-closed 先于恢复。 |
| A3 + E1 | 1 | A3 | 先恢复最小权威记录，再消费 carried finding。 |
| B1 + C1 | 1 | B1 | attempt-level Ticket 选择先于 Ticket-level direct-implement escape。 |
| C1 + C7 | 1 | C1 | 先确认无调查载体的当前 subject，再设置 review trigger。 |
| C10 + C7 | 1 | C10 | 未完成 worker 返回先消费，不能先派新的 review。 |
| C10 + C9 | 1 | N14（verify mode） | worker mode 是必要判据；verify INCOMPLETE 不得回 implement。若 mode=implement，才由 C10 裁决。 |
| C13 + F3 | 3 | C13 | acceptance edge held 先于 global terminal coverage。 |
| C14 + C5 | 2 | C14 | 先处理矛盾证据，再判断是否是来源冲突/req-align。 |
| C15 + B3 + F6 | 1 | C15 | satisfy 的 CLI 结果先于全部 terminal 和 Gate verdict。 |
| C3 + C5 | 1 | C3 | 多个业务结果先请 Owner 选定，再处理来源冲突。 |
| C3 + D4 | 1 | C3 | contract 传播不能替代尚未完成的业务选择。 |
| C4 + C7 | 2 | C4 | 技术路线已唯一裁定，review trigger 作为后续约束。 |
| C4 + D4 | 3 | C4 | 已有 route 结论先消费；D4 负责记录 affected subset，不重夺路线裁决。 |
| C6 + C5 | 1 | C5 | 来源冲突不能被普通 reviewer dispatch 掩盖。 |
| C6 + C7 | 7 | C6 | 已有 DONE + review pending 的具体动作先于泛化 required-trigger。 |
| C6 + C8 | 2 | C8 | evidence 未入账时先记账；review 不能消费一个不可索引的事实。 |
| C6 + C13 | 2 | C6 | reviewer pending 先于 acceptance held 的继续推进。 |
| C6 + F3 | 5 | C6 | Ticket-level review pending 先于 attempt-level terminal coverage。 |
| C7 + C13 | 1 | C7 | required review 先建立，acceptance edge 继续保持 held。 |
| C7 + F3 | 3 | C7 | 有明确 Ticket-level trigger 时先建立 required review；没有该 trigger 时只命中 F3。 |
| C8 + C13 | 1 | C8 | evidence 入账先于 acceptance edge 解释。 |
| C8 + E1 | 2 | C8 | reviewer finding 的事实先入账，再派 fresh fixer。 |
| C8 + G1 | 1 | G1 | checkpoint 缺失是更高阶的恢复完整性问题。 |
| C8 + E5 | 1 | C8 | evidence 先于 terminal findings triage。 |
| C9 + E1 | 1 | E1 | 已返回 finding 先进入 fix 路由，安全不变量验证随后必须补齐。 |
| D1 + D4 | 1 | D1 | 已满足 claim 被新证据触及的保护先于一般 contract-change 记录。 |
| D2 + D4 | 1 | D2 | acceptance revision divergence 先重验，再处理 contract affected subset。 |
| E1 + C3 | 1 | E1 | 已返回 reviewer finding 先被消费；业务歧义仍保留为 secondary。 |
| E1 + C4 | 1 | E1 | finding 先进入 fix/review 消费，不能被 route shortcut 吞掉。 |
| E1 + C6 | 1 | E1 | fresh fix/closure 的具体 finding 动作先于新一轮普通 reviewer dispatch。 |
| E1 + E4 | 1 | E1 | reviewer finding 先保留 fresh-fix 约束，grading 是 secondary 判断。 |
| E1 + E5 | 3 | E1 | 具体 finding 先消费，attempt-level triage 随后处理剩余项。 |
| E2 + E5 | 1 | E2 | source recheck 是同一 ReviewRun 的具体一次性动作，先于全局 triage。 |
| E4 + E5 | 1 | E4 | 先确定 P1/P2/editorial，再决定四路 durable 分流。 |
| E5 + F3 | 1 | F3 | terminal coverage 不完整时不能先做最终 findings triage。 |
| F2 + F3 | 1 | F2 | completion claim 先审计，才继续补 terminal coverage。 |
| F3 + G1 | 1 | G1 | 交接前 checkpoint 缺失先补 durable 载体。 |
上表的次数合计为 61。报告中写成 `C8+C6` 的反向形式已并入 `C6+C8`，不产生第二类。

## 3. 跳步与 record 缺口

### 3.1 跳步总览

| 检测项 | 严格确认 | 证据受限/观察到 | 分布与结论 |
| --- | ---: | ---: | --- |
| 无 investigate carrier 直接进入 implement | 2 | case1 有 1 次 direct-implement 行为但 C1 两个机械谓词未完整显示；case2b 有 2 个、case3 有 2 个候选因字段不可见未确认；case2c 只说明跨片不足，未给可加总数 | 严格确认只来自 case2a 的 2 次。它们有 explicit reason，C1 的 escape 本身允许 direct implement；应补 C1 的轨迹字段和 N01，而不是把所有 direct implement 都判成违规。 |
| worker/reviewer 返回后未入 evidence 就推进 | 5 个严格/明确滞后批次 | 34 个 evidence-limited 批次 | 见 3.2；这是最重要的 record 读数。 |
| 未经独立 review 就宣称完成或 satisfy | 0 | case1 有 1 次 sub-finding closure reviewer timeout 后仍写 judgment 的 near-miss，但没有 Ticket satisfy；其它报告也没有确认异常 | “代码/worker scope 完成”与 package closure 被成功区分，表的 review/accept 规则方向正确。 |
| 已 SATISFIED Ticket 被新证据触及后未处置 | 1 次真实处置 | case3 有 1 个 evidence boundary 不足；case2c 的早期状态在片外 | case2a DPAP-01 完整走了 evidence conflict → stale/needs-revalidation → revalidate → SATISFIED；这是现有 D1/D2/D3 的有效样本。 |

### 3.2 evidence 未入账：39 批，5 批已确认、34 批只能标 evidence-limited

这里把“报告明确证明回执先被用于推进、之后才入账”与“只看到回执后动作、但看不到 evidenceIndex”分开，避免把截断造成的空白写成事实。

| 报告 | 已确认的 return→next action→later evidence | 只观察到未见入账、不能证明永久漏记 | 说明 |
| --- | ---: | ---: | --- |
| case1 | 2 | 0 | T2 直到后续才 `evidence add`；T3 返回后继续 review/fix/browser/commit，报告按两批记录。 |
| case2a | 3 | 2 | 3 批明确先消费 worker/reviewer 回执再落 package evidence；2 批是跨 package 调研输出，evidenceIndex 不可见。 |
| case2b | 0 | 3 | DMI 三个合法 worker envelope 的后续 evidence 是否已写入在截断时间线中不可核验。 |
| case2c | 0 | 11 | 11 批可见回执后立即进入下一动作；本片还明确有“不允许修改 evidence”的权限边界。 |
| case2d | 0 | 8 | 8 批回执后推进，但 later ER/evidence index 同步在别处可见，具体先后受 nested tool-call 截断影响。 |
| case3 | 0 | 10 | 10 个返回→下一动作 bundle 没有可见 `evidence add`，但报告不把缺命令当成永久漏记。 |
| **合计** | **5** | **34** | **39 个被追踪批次；严格已确认 5 个。** |

这组读数说明的是“两件事叠加”，不是单一的规则错误：

1. **规则侧：** C8 是 `prose`，没有 CLI 强制；5 个明确样本证明主控确实会先推进再补账。当前优先级还把 C8 放在 C6/E1/E5 之后，进一步放大了这种行为。
2. **成本/可见性侧：** 34 个批次受到旧版执行形态、截断、跨 package evidence、权限边界和 nested tool-call 影响。即使最终有 ER/evidence index，也无法从回放证明“同一动作内原子落账”还是“后补账”。这更像记账太贵、太晚、太难观察，而不是 34 条已证实规则逃逸。

建议提前做 intake，但只做轻量前沿载体：worker/reviewer 返回时立即记录 `subject`、`source_kind`、artifact/hash、`returned_at`、`intake_id` 和 `indexed=false`；完整 `evidence add` 可以异步 drain。这样既能让 N/C8 在下一轮有机械信号，又保留首版显式写行的漏记率读数，不需要立即修改 `impl_package_state.py` 或把所有语义命令改成自动写轨迹。没有这层 receipt，继续争论 basis 是 `prose` 还是 `observed` 都不可靠。

### 3.3 其它 record 缺口的合并读数

| record/恢复缺口 | 原始 unmatched 次数 | 对应提案 | 判断 |
| --- | ---: | --- | --- |
| judgment/conclusion 未入账 | 2 | N10 | 应进表；它符合 `verify/record` 判定线的“结论存在但未入账”。 |
| active checkpoint 已有但需要刷新 | 2 | N09 | 应进表；不能套 G1 的 missing。 |
| handoff/relay 在途 | 7 | N05 | 应进表；正常 handoff 本身需要载体，不应只在恢复成功后才可见。 |
| anchor 表示/规范化不匹配 | 2 | N06 | 应进表；事实存在但表示差异使恢复失败。 |
| handoff target/order 校正 | 2 | N08 | 应进表；它改变 continuation 的实际目标。 |
| handoff bootstrap/incomplete | 2 | N07 | 应进表；工具层失败会直接影响恢复安全。 |
| checkpoint projection race | 1 | N11 | 虽只有一次，但属于记录完整性/并发安全，不是偶发环境噪声，保留。 |
| bookkeeper 部分写入 | 1 | N12 | 虽只有一次，但会造成部分 artifact 事实丢失，保留。 |
| comparison head 未固定/不可信 | 6 | N21 | case2c、case2d、case3 都出现，属于 review 与 record 的共同边界。 |
| 规划 lifecycle 未初始化 execution | 11 | M01 | 不进入 dev-with-track；需要另一个 phase/表的设计决策。 |

## 4. 表本身的矛盾与具体修法

下表把六份报告反复指出的问题与已知五条一起收敛为可修改的文件/章节位置。本轮只写提案，不执行这些修改。

| 问题 | 精确修法 |
| --- | --- |
| `package.record.projection-drift` 被迫写 `manual`，而判据要读 `progress.md`，但 progress 被排除在推导输入外 | 改 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml` 中 `package.record.projection-drift` 的 `when: manual`：改为消费统一命名的 `package.validate.projection_drift: true`，删除 `manual_reason`。README §8 将“progress.md 不作为推导输入”改成“progress.md 仍不作为输入；projection drift 由 `package validate` 基于 authoritative state/contract 生成诊断”。人读枚举 A2 也改成“`package validate` 报告 projection drift”。这不是把 progress 偷塞回输入，而是让 CLI 报告成为判据来源。 |
| 人读枚举头部写 `situations/dev-with-track.yaml`，README §10.1 写 `skills/dev-with-track/situations.yaml` | 改 `situation-table-dev-with-track.md` 头部：正式来源统一写 `skills/dev-with-track/situations.yaml`，并补本仓库实际路径 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`。README §10.1 保留相对 skill 目录写法，两个文档都不要再出现 `situations/dev-with-track.yaml`。 |
| README §1 仍写“命名空间与落地形式待定” | 改 README §1 第 6 行为：`方向讨论完成；命名空间固定为 <对象>.<环节>.<状况>，正式机读来源固定为 skills/dev-with-track/situations.yaml；字段/优先级仍以试运行读数为准。本文不授权实施。` |
| 优先级第 2 组与第 3 组行号重叠，且漏列 A3、E5 等 | 同时改 YAML 顶层 `priority` 和人读枚举“命中优先级”：删除第 3 组重复的 C6/C10–C12；把 A3、G1、C8、E2–E5 和新增行按本报告 §2.2 的 P0–P5 加入唯一序列。第 2 组只保留返回/协议消费，不再用组名暗示所有 subject 推进。 |
| `when` 的 `">1"`、`">0"` 比较表达式没有在设计中定义，已成为事实契约 | 在 README §10.1 字段形态后新增 `when` grammar：布尔值是严格布尔比较；未加操作符的标量是 equality；带引号的 `> >= < <= == !=` 只允许数值字段；`manual` 是显式不可推导 sentinel；字段缺失结果为 `unknown`，不得当作 false 静默吞掉。补 `attempt.ready_ticket_count: ">1"`、`evidence.count: ">0"` 的解析例子和非法表达式例子，并让 renderer/validator 对未知字段报错。 |
| worker outcome 没有与环节绑定，verify/fix 的 INCOMPLETE/BLOCKED 会撞到 implement 行 | 在 YAML C10–C12 的 `when` 中加入 `trail.last_worker_mode: implement`；增加 N14 的 `worker_mode=verify`；N15 的判据使用 finding/fix scope 与 envelope validity，不复用 ticket implement 状态。README §7 的轨迹字段表补 `worker_mode`、`envelope_valid`、`outcome_count`。 |
| C8 的 direct evidence 边界和时间语义不清，reviewer report、bookkeeper 回执、worker verification envelope 是否都算 evidence 没有定义 | 在 README §9.5/§10.1 和 trail schema 的 evidence 字段中定义 `source_kind`、`returned_at`、`intake_at`、`indexed_at`、`receipt_id`；明确“返回即有 artifact，但 indexed=false 仍属 record 缺口”，bookkeeper write receipt 只有在能指向 artifact/hash 时算 direct evidence。renderer 显示 return→intake→index 的顺序，而不是只显示一个 `indexed` 布尔值。 |
| fix 后 finding closure review 没有等待行，reviewer-returned 的 direct-fix 边界也含糊 | 增加 N13；并在 `finding.fix.reviewer-returned` 的 actions 中加入带 `requires_reason` 的 `main-session-direct-fix` escape，要求后续同 scope review；`finding.fix.main-session-discovered` 继续按 finding 来源区分，不按执行者偷换语义。人读枚举 E1/D1 展开补上“fixer unavailable/Owner direct fix/fresh review”三种分支。 |
| 正常单 ready、baseline freshness、rebase conflict、integration carrier 和 dirty comparison head 没有精确承载 | 增加 N01、N03、N04、N19、N20、N21；它们均使用现有矩阵，不新增 phase。README §9.5 的相邻线补充：能不能开始是 readiness；证据不存在是 verify；已存在但未入账是 record；接受结论/比较点不可信不能伪装成 Gate mismatch。 |
| parallel fan-in、bookkeeper 部分写入、projection race、anchor 表示差异没有记录层/对象层行 | 增加 N05–N12、N17；把并行 fan-in 放在 `finding.fix`，bookkeeper/hand-off/projection/anchor 放在 `attempt.record`，不新增 `parallel`、`bookkeeping` 或 `worker` phase。README §9.4 保持“循环外记录层统一用 record”的规则。 |
| Gate 只有 pass/blocked/fail/defer，实际流程保持 open 时没有可执行动作 | 不新增 `pending-open` 行。改 `attempt.gate.verdict-undecided` 的 action 说明：`gate defer` 明确定义为“Gate 保持 open，不产生 terminal verdict，必须带 pending reason 和下一检查点”；renderer 把自然语言“保持 open”归一为 `defer`，禁止把 help 查询当状态转换。 |
| `finding.disposition.grading-undecided`、`attempt.disposition.findings-triage-pending`、terminal review 的关系不清 | 在人读枚举 E4/E5/F3 下方写明：specific finding 先 grade；完整 terminal coverage 未齐先补 F3；全部 coverage 后才做 E5 四路分流；record evidence 优先于三者。把 E5 加入 priority，按 §2.2 排序。 |
| planning/req-align 的大量 unmatched 若硬塞进 dev-with-track 会污染对象与 phase | README §11 增加一句“回放中出现的 planning bundle、design preview、runtime state init 未进入本表；需要另表或显式新增 phase 的 Decision”。保留 M01 作为重大变更备选，不在本轮修改 `phases`/`allowed`。 |
| backend Gate、component conditional PASS 和产品 UI 验收边界容易被读成一个 closure | README §10.1 的渲染输出增加 `scope`/subject context 的显示要求；`attempt` Gate 只声明当前 package/attempt 的范围，不能由表新增一个“全产品 closed”状态。验收/报告模板要显示 package scope 和未覆盖的外部 UI/manual 边。 |

### 4.1 建议的最小 apply 顺序

如果 Owner 批准修表，建议按以下依赖顺序落地：

1. 先更新 README §10.1 的 `when` grammar、trail/evidence timing 和 projection-drift 的 `package validate` 判据；否则新增行会建立在未定义的输入契约上。
2. 再更新 YAML priority 为 P0–P5，并加入 A3/E5/现有遗漏行；priority 必须先于新增 situation，否则 61 个多重命中仍无法验证。
3. 再加入 22 个现有 phase 的候选行，优先 N21、N05、N20、N18、N15、N13、N09–N12；M01 不进入本轮。
4. 用新的 intake receipt 做一轮短 replay，再决定哪些 `prose` 行可以升 `observed`；不要直接从旧版回放把 basis 升级。

## 5. 版本干扰：不应据此改表的结论

以下结论受到“回放时 SKILL/tool 版本与现在不同”的影响，不能直接作为新表规则：

- case1、case2a、case2b、case2c、case3 都有旧 cache 路径或 0.2.9/0.3.0/0.3.1 切换；路径读取失败、旧帮助命令失败和重新定位不应映射为处境行。
- 回放发生在表设计完成前，时间线没有证明当时存在当前的 renderer、三段式 slug、按 subject 的 trail.jsonl 或显式 `evidence add`；这是 overlay mapping，不是“当时 agent 已经收到当前表”的实验。
- case1 的 retired Runtime Acceptance projection、case3 的 dirty package Ticket ID validator 错误，可能是旧 artifact/schema 与新版 validator 的兼容问题；不能据此把 projection-drift 或 state-missing 的 basis 改成 observed，也不能直接新增 projection-stale。
- 旧版的 `FIX_COMMITTED`、`IMPLEMENTED_PENDING_REVIEW`、`multi_agent_v1`、Grok wrapper 和自然语言 envelope 不等于当前 trail/state 字段。尤其 C10/C11/C12、C8 和 envelope invalid 的具体映射，必须用当前版本重放确认。
- case3 的 initial `pass/frozen@5b2db297` 是先前 Probe attempt；后续 UI patch 是新的行为合同。A4、D4、F3 的含义必须按 attempt 边界分开，不能把合法的新 patch 误判为继续旧 terminal attempt。
- case1 的 `dev` 授权、case3 的 Owner 指令“修复后直接 terminal-final”、case2c 的“本 session 不得改 evidence”等是本次运行中的授权/权限边界，不是默认规则，也不能直接改 basis。
- case2b 的同一 Grok context 复用、case1 的 reviewer timeout 后 judgment、case2d 的 wrapper failure 可能是旧工具行为或一次 escape；先保留为 evidence/escape，不因单片样本改写 E1 的默认 fresh fixer 契约。
- case2a/c/d 是分片，片外的 initial investigate、Ticket state、evidenceIndex 和 checkpoint 不能用“本片没看到”证明从未发生；这些位置只能标 insufficient-evidence。
- tool output、user/assistant、reasoning 和 nested tool-call 的截断会制造“未见 `evidence add`”的假象；因此 34 个批次只能标 evidence-limited，不能当作 34 次永久漏记。

不受这些版本干扰、可以直接用于修表的，是跨多个报告重复出现的结构性边界：多重命中排序缺口、正常 handoff/anchor 的缺行、reviewer 不可用、parallel fan-in、integration carrier/readiness、dirty comparison head，以及已明确发生的 5 批 evidence 滞后。

## 最终交付结论

- 去重后的候选新增行总数：**23 条**（22 条使用现有环节，1 条 M01 需要新增 `plan/align` 环节且当前不建议加入）。
- 其中需要新增环节取值：**1 条重大变更备选**；实际建议本轮进入 dev-with-track 的 22 条为 **0 条**需要新增环节。
- 优先级修正一句话：**把 fail-closed/record 完整性置顶，删除第 2/3 组重复，补入 A3/E5 等遗漏，并用“证据先入账、具体 worker/review 先于宽泛 triage、acceptance/claim 先于 global closure”的严格顺序裁决 secondary hit。**
- evidence 未入账总批次：**39 批可追踪，其中 5 批已确认滞后、34 批因版本/截断/权限只能标 evidence-limited**。

最该先做的三件事：

1. 先 apply P0–P5 的完整 priority 与 `when`/worker-mode 语法，消除 61 个多重命中的机械不确定性。
2. 先做轻量 evidence intake receipt，记录 return→intake→index 时间，验证“规则错”与“记账成本”各占多少。
3. 再加入高频且高风险的 N21 comparison-head、N05 handoff、N20 integration carrier、N18 reviewer unavailable、N15 envelope 和 N09–N12 record 行；规划 lifecycle M01 保持表外。
