# 回放映射 · case2b

## 结论摘要

本片不是案例 2 的完整回放，而是 4 片中的第 2 片。按“连续同一主控意图合并、纯轮询不单列”的口径，共抽出 34 个决策点：

- 确定命中处境表：25 个
- 明确 unmatched：7 个
- 只能标 insufficient-evidence：2 个
- 命中率：25 / 34 = 73.5%；分母把证据不足按未命中计
- 表内多重命中：11 个决策点

本片只覆盖返工、修复、验证与复审，不覆盖初始需求对齐、首次调查或最终 Gate 收口。片尾两个 package 都不能称为 closed：DPAP-02 仍在新的 finding-closure / terminal-final 之前，DMI-05 的最新 terminal-final 四轨仍在运行，且集成证据受 P1001 阻断。

## 1. 概况

### 本片位置与任务

案例 2 的全局摘要显示共有 9 个 session；本片实际包含其中 2 个 session，记录范围为 seq 1892–4074，共 2,183 条记录，时间跨度为 2026-08-14T08:34:53Z–11:25:37Z。两个 session 有时间重叠，因此下表按 session 和 seq 解释，不把文件顺序误当成单线程墙钟顺序。

| session | package / worktree | 本片阶段 | seq / 时间 |
| --- | --- | --- | --- |
| a70f6169 | DPAP-02；docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe；D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning | 既有 reviewer findings 的 fresh fix；finding-closure PASS；完整 terminal-final 发现 F-C1/F-C2；第二轮 fresh fix、同 revision 验证并准备交接 | 1892–2490；08:34:53–09:42:58Z |
| ccaea2f3 | DMI-05；docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import；D:\CodeSpace\kaispan-dev\.worktrees\260812-datev-mandant-profile-import-planning | 从 active checkpoint 恢复 BLOCKED；四条并行 fix seam；同 revision 验证；terminal-final FAIL；publication seam 串行返工；Grok review/fix；最新 terminal-final 四轨运行中 | 2491–4074；08:50:40–11:25:37Z |

### 片尾状态

- DPAP-02：第二轮修复固定在 revision 5b0b5763…，32 个定向测试、格式、lint、package validate 和目标目录 typecheck 证据已记录；新的 finding-closure、terminal-final、acceptance 与 Gate 仍待继续。
- DMI-05：四个初始 business seam 已集成到 e0b8d60a，后续修复经过 83342bb0…、074aeceb…、7f5b4b7d…；最新四轨 terminal-final 在 f45dda1… → 7f5b4b7… 上运行中。集成测试仍因 127.0.0.1:5433 无 PostgreSQL 返回 P1001。没有看到 Ticket satisfy 或 Gate pass。

## 2. 决策点与映射

映射理由中的短语直接对应当前表的条件：DONE + review required 对应 ticket.review.awaiting-reviewer；已有证据但 acceptance 边未释放对应 ticket.accept.acceptance-edge-held；reviewer 返回 finding 后交 fresh fixer 对应 finding.fix.reviewer-returned；terminal-final coverage 未完成对应 attempt.review.terminal-coverage-incomplete。

| # | session / 时间 | seq | 主控决定 | 映射与判定依据 |
| ---: | --- | ---: | --- | --- |
| 1 | a70f6169 / 08:35:14Z | 1895 | 为 DPAP-02 的 recorded-findings 启动 fresh fix worker | insufficient-evidence → finding.fix.reviewer-returned。source_unit 和 review comparison point 支持“既有 reviewer findings”，但触发该修复的 reviewer 返回发生在本片之前。 |
| 2 | a70f6169 / 08:53:32Z | 1995 | 不把 worker 对停止提示的确认当成 DONE，先读工作区产物和 diff | unmatched；这是 ack-only / 无合法 envelope，表只有 INCOMPLETE、BLOCKED 等 worker 终态，没有“协议 envelope 无效”。 |
| 3 | a70f6169 / 08:54:58Z | 2008 | 接受 fresh fixer 的 DONE 作为待审结果，先做主 session 同 revision 验证 | ticket.review.awaiting-reviewer；明确有 DONE、review_state=PENDING_REVIEW，所以尚不能接受或关闭。 |
| 4 | a70f6169 / 08:56:32Z | 2037 | 固定 10 个代码/测试文件，启动 finding-closure 四轨 review | ticket.review.awaiting-reviewer + ticket.review.required-trigger；worker 已 DONE，且 review 明确为 required。 |
| 5 | a70f6169 / 09:02:47Z | 2107 | 将 fixer 和同 revision 验证事实写入 evidence/ER，并推进 active checkpoint | ticket.record.evidence-unfiled；直接 evidence 返回后，主控执行记录入账。checkpoint 是否在动作前缺失，输入不足，不能另命中 G1。 |
| 6 | a70f6169 / 09:06:47Z | 2162 | finding-closure 全 PASS 后，转入完整 DPAP-02 terminal-final review | attempt.review.terminal-coverage-incomplete；局部 finding closure 已通过，但完整 change unit 的 terminal coverage 尚未完成。 |
| 7 | a70f6169 / 09:16:06Z | 2255 | Track C 新 findings 出现时不推进 acceptance，等待其余轨道并先核验证据 | ticket.accept.acceptance-edge-held；新 P1/P2 finding 使 acceptance 边继续保持未释放。 |
| 8 | a70f6169 / 09:18:28Z | 2278 | 不直接采信 reviewer candidate，先由 parent 核验是否真是 findings | unmatched；这是“candidate finding 的事实核验”，不同于已进入定级的 finding.disposition.grading-undecided。 |
| 9 | a70f6169 / 09:19:31–09:20:58Z | 2297–2311 | 将 F-C1/F-C2 canonicalize 为 FAIL，写入 evidence/ER/checkpoint，再启动第二轮 fresh fixer | ticket.record.evidence-unfiled + finding.fix.reviewer-returned；reviewer findings 先落账，随后按 fresh-fix 路由返工。 |
| 10 | a70f6169 / 09:36:14Z | 2389 | 第二轮 worker 返回 INCOMPLETE 后，由主 session 补做同 revision 验证，不继续无界等待 | insufficient-evidence → ticket.implement.worker-incomplete-first；有 INCOMPLETE 事实，但本条是 mode=fix，且 first/second 计数没有在本片给出，不能确定 C10/C11。 |
| 11 | a70f6169 / 09:39:34Z | 2449–2453 | 写入第二轮修复 judgment/evidence 和 recovery checkpoint，固定下一步 review | ticket.record.evidence-unfiled；本次动作正是把直接验证结果与下一步 checkpoint 落账。 |
| 12 | a70f6169 / 09:39:55Z | 2456 | 按 checkpoint 准备 handoff-to-new-session | unmatched；当时已有 active checkpoint，不能硬套 attempt.record.checkpoint-missing。 |
| 13 | ccaea2f3 / 08:51:26Z | 2499 | 从 DMI-05 active checkpoint 恢复最小记录，并沿已确认 blockers 调度并行 fixes | attempt.record.session-resumed + finding.fix.reviewer-returned；用户 continuation 明确写出“从 checkpoint 恢复”，且 blockers 的来源是既有 terminal review。 |
| 14 | ccaea2f3 / 08:54:32Z | 2554 | preflight READY 后，以不重叠 ownership 并行启动四个 fresh fix workers | finding.fix.reviewer-returned；七个 P1 business blockers 已由前一轮 review 确认，动作是 fresh fix。并行 admission 的 fan-out 细节不在现有行中。 |
| 15 | ccaea2f3 / 09:00:24–09:05:22Z | 2649–2721 | 部分 worker 已回报 commit/evidence，但仍等待其余 seam 返回后统一集成 | unmatched；表没有“多个 finding 并行 fix 的 fan-in pending”处境。 |
| 16 | ccaea2f3 / 09:07:51Z | 2747 | F-001 已有 commit 但没有完整 envelope，停止残余进程，改由 owner 检查 diff 和直接验证 | unmatched；同样是 fix-mode worker envelope 无效/不完整，不等同于业务 BLOCKED。 |
| 17 | ccaea2f3 / 09:08:34Z | 2765 | owner 检查四个 commit 边界后，在固定 implementation HEAD 运行受影响 API suites | ticket.accept.acceptance-edge-held；局部 evidence 存在，但仍要经过 integration、claim audit 和独立 review，不能 satisfy。 |
| 18 | ccaea2f3 / 09:09:27–09:11:14Z | 2776–2797 | 选择 local-test；发现 loopback DB/Docker 不可用后只尝试一次幂等 prepare | unmatched，最接近 ticket.accept.acceptance-edge-held。真实处境是“所需验证环境不可用”，建议 ticket.verify.environment-unavailable；这是 verify 而不是 record，因为该 integration evidence 尚不存在。 |
| 19 | ccaea2f3 / 09:11:27–09:14:02Z | 2802–2823 | prepare fail-closed 后保留 lower-layer evidence，改跑 governance/static/full API，并计划 claim audit + terminal review | ticket.accept.acceptance-edge-held + attempt.review.terminal-coverage-incomplete；不以 unit/static 结果替代缺失 integration，也未进入 acceptance。 |
| 20 | ccaea2f3 / 09:15:11–09:19:24Z | 2843–2892 | 完成 full API、OpenAPI、contracts、Web/DB/root tests 和静态检查后，仍直接判定 loopback integration | ticket.accept.acceptance-edge-held；所有动作都在补 acceptance 前证据，且明确不把 build 或 lower-layer 结果冒充 integration。 |
| 21 | ccaea2f3 / 09:22:06Z | 2951 | 固定 f45dda1… → e0b8d60a… ledger，启动四条独立 terminal-final reviewer | ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete；完整 change unit 的 required review 尚未覆盖，且四轨均适用。 |
| 22 | ccaea2f3 / 09:39:43Z | 3126 | 三条 reviewer 长时间未返回时只发送一次 bounded 收口提示，之后按 incomplete/UNCERTAIN 处理 | unmatched；这是 reviewer timeout / escalation，而不是新建 review 或 manual result missing。 |
| 23 | ccaea2f3 / 09:43:20–09:44:53Z | 3169–3200 | parent 核验四轨 candidate，确认三个 P1、保留一个 UNCERTAIN/owner decision，并把 canonical ledger 固定为 FAIL | finding.disposition.grading-undecided；finding 需要 parent 定级/分类，且本片显示了 P1 与 UNCERTAIN 两类结果。 |
| 24 | ccaea2f3 / 09:46:24–09:47:45Z | 3218–3231 | 对已核实 blockers 重新调度 publication recovery 与 authorization 两个 fresh fix seam | finding.fix.reviewer-returned；reviewer finding 已被 parent 确认，进入 fresh fix，且两个写集不重叠。 |
| 25 | ccaea2f3 / 09:55:22Z | 3309 | authorization worker 已完成，但继续等待 publication worker，不提前 review/close | ticket.accept.acceptance-edge-held；已有局部修复结果，但整个 acceptance 仍被剩余 seam 和 review 持有。 |
| 26 | ccaea2f3 / 10:07:24Z | 3432 | 两个修复都落地后，先核对 commit/diff，再做同 revision focused/full/static 验证 | ticket.review.awaiting-reviewer + ticket.accept.acceptance-edge-held；worker 结果仍是 review pending，acceptance 也明确未释放。 |
| 27 | ccaea2f3 / 10:09:18–10:12:23Z | 3455–3483 | 在 83342bb0… 重跑全套测试、静态和 schema；schema 失败后按共享 profile 重试 | ticket.accept.acceptance-edge-held；是在 review/integration 前继续补证据，不构成 satisfy。 |
| 28 | ccaea2f3 / 10:13:32–10:14:04Z | 3505–3512 | integration 仍 P1001，保持 Gate BLOCKED，并为新 head 创建独立 terminal-final ReviewRun | ticket.accept.acceptance-edge-held + attempt.review.terminal-coverage-incomplete；这里的 BLOCKED 是 carried state，不是本片新执行的 Gate verdict。 |
| 29 | ccaea2f3 / 10:16:19Z | 3555 | 建立 f45dda1… → 83342bb0… 的四轨独立终审，拒绝复用旧 revision 结论 | ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete；新 revision 必须重新覆盖 terminal-final。 |
| 30 | ccaea2f3 / 10:31:20–10:36:18Z | 3619–3720 | 四轨一致 FAIL 后，把共同 publication blockers 交给单一 owner worker 串行 fresh repair | finding.fix.reviewer-returned；reviewer findings 已回收并确认，且为了避免状态机写集互相覆盖而改为串行。 |
| 31 | ccaea2f3 / 11:00:14Z | 3783–3797 | bounded repair 074aeceb… 后，按用户要求启动 Grok 只读 review，同时保留本地验证 | ticket.review.awaiting-reviewer + ticket.review.required-trigger；fix result 仍待独立 review，且主控明确不把 Grok 结果替代 Gate。 |
| 32 | ccaea2f3 / 11:11:26–11:11:58Z | 3921–3929 | Grok 找到新的 P1 后，复用同一 Grok review context 直接做最小 fix | finding.fix.reviewer-returned，但 chosen=escape/nonconforming；表要求 fresh fixer，不得复用发现 finding 的进程。 |
| 33 | ccaea2f3 / 11:13:51–11:17:43Z | 3950–3988 | 7f5b4b7d… 修复后做同 revision tests/build/schema/integration 补证据，准备最新终审 | ticket.review.awaiting-reviewer + ticket.accept.acceptance-edge-held；新 fix 已验证但仍未取得 review/acceptance。 |
| 34 | ccaea2f3 / 11:18:50Z | 4005 | 在最新 head 上启动四条新的 terminal-final independent review tracks | ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete；片尾四轨仍运行，未进入 Gate。 |

## 3. 读数

### 总量

| 指标 | 数量 |
| --- | ---: |
| 决策点总数 | 34 |
| 确定命中 | 25 |
| 明确 unmatched | 7 |
| insufficient-evidence | 2 |
| 命中率（25 / 34） | 73.5% |
| 表内多重命中 | 11 |

### 按环节的确定命中分布

以下只按每个决策点的主映射计数；多重命中的次映射不重复计入本表。

| 环节 | 命中数 | 代表 slug |
| --- | ---: | --- |
| record | 4 | ticket.record.evidence-unfiled、attempt.record.session-resumed |
| readiness | 0 | — |
| investigate | 0 | — |
| route | 0 | — |
| implement | 0 | —（有 1 个 fix-mode INCOMPLETE 候选，但证据不足） |
| fix | 4 | finding.fix.reviewer-returned |
| verify | 0 | —（环境不可用另列为 unmatched） |
| review | 9 | ticket.review.awaiting-reviewer、ticket.review.required-trigger、attempt.review.terminal-coverage-incomplete |
| accept | 7 | ticket.accept.acceptance-edge-held |
| rework | 0 | —（本片的返工由 finding fix 路由承接） |
| disposition | 1 | finding.disposition.grading-undecided |
| gate | 0 | —（没有新的 gate pass/blocked/fail/defer 命令） |
| **合计** | **25** |  |

### 多重命中

按处境表现有 slug 计算，多重命中为 11 个：

1. seq 2037：ticket.review.awaiting-reviewer + ticket.review.required-trigger
2. seq 2297–2311：ticket.record.evidence-unfiled + finding.fix.reviewer-returned
3. seq 2499：attempt.record.session-resumed + finding.fix.reviewer-returned
4. seq 2802–2823：ticket.accept.acceptance-edge-held + attempt.review.terminal-coverage-incomplete
5. seq 2951：ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete
6. seq 3432：ticket.review.awaiting-reviewer + ticket.accept.acceptance-edge-held
7. seq 3505–3512：ticket.accept.acceptance-edge-held + attempt.review.terminal-coverage-incomplete
8. seq 3555：ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete
9. seq 3783–3797：ticket.review.awaiting-reviewer + ticket.review.required-trigger
10. seq 3950–3988：ticket.review.awaiting-reviewer + ticket.accept.acceptance-edge-held
11. seq 4005：ticket.review.required-trigger + attempt.review.terminal-coverage-incomplete

优先级能给出主映射，但不能消除次命中：尤其 C6/C7/F3 在每次 closure 或 terminal-final review 启动时会同时成立。

## 4. unmatched 清单

以下 slug 只是本片报告建议，均遵守对象×环节允许矩阵；不修改表。

| seq | 真实处境 | 建议 slug | 为什么用这个对象/环节 |
| --- | --- | --- | --- |
| 1995 | worker 只确认停止提示，没有返回结构化结果 envelope | finding.fix.worker-envelope-invalid | 已知 finding 的 fix worker 协议失效，属于 finding.fix，不是 ticket.implement。 |
| 2278 | reviewer 返回 candidate finding，parent 先核验事实、暂不定级 | finding.review.candidate-unverified | 对象是 finding，活动是 review；证据尚未足以进入 disposition。 |
| 2456 | 已有 active checkpoint，主控准备跨 session handoff | attempt.record.handoff-pending | 是 attempt 级记录/交接状态，不符合 checkpoint-missing。 |
| 2649–2721 | 多个 finding fix 并行返回，主控等待剩余 worker 后再 fan-in | finding.fix.parallel-fan-in-pending | 处于已知 findings 的 fix 收口，现有表没有并行 fan-in 状态。 |
| 2747 | F-001 有 commit/diff，但 worker 没有完整 envelope，主控停止残余进程并改走直接验证 | finding.fix.worker-envelope-invalid | 与 seq 1995 是同一未覆盖处境的第二次出现。 |
| 2776–2799 | 必需 local-test / PostgreSQL / Docker 环境不可用，无法取得 integration evidence | ticket.verify.environment-unavailable | 对象是 DMI-05 Ticket，验证证据尚不存在，因此应落 verify，不是 record。 |
| 3126 | terminal-final reviewer 长时间不返回，主控发送一次收口提示并准备按 incomplete/UNCERTAIN 处理 | attempt.review.reviewer-timeout | 是 attempt 级 review 超时/升级，既不是 manual owner 缺结果，也不是重新创建 terminal coverage。 |

## 5. 跳步检测

| 检测项 | 计数 | seq | 判断 |
| --- | ---: | --- | --- |
| 没有任何调查载体就直接进入实现 | 0 个已证实 | — | 本片可见的 worker 全部是针对既有 reviewer findings 的 fix，没有可见的 sdd mode=implement；seq 1895 和 2499 的上游调查是否发生在本片前不可见，保留 insufficient-evidence，不判违规。 |
| worker 返回后未记 evidence 就推进 | 0 个已证实；3 个需核验 | 2644、2707、2721 | DPAP-02 在 seq 2107、2449–2453 明确落账；DMI-05 三个合法 worker envelope 的 evidence 后续是否写入 evidenceIndex，在截断时间线中没有可核验的 evidence add 证据，而主控已经继续集成/验证，故只能标 insufficient-evidence，不把“未见命令”当成事实。F-001 seq 2747 没有合法 envelope，不计入此项。 |
| 未经独立 review 就宣称完成或 satisfy | 0 | — | 两条线都显式保持 PENDING_REVIEW、BLOCKED 或“不能 closed”；没有看到 ticket satisfy、completion claim 通过或 Gate pass。worker 局部文字“bounded repair closed”也被主控明确限定为局部修复，不是 package closure。 |
| 已 SATISFIED 的 Ticket 被新证据触及时是否处置 | 0 个已观察 | — | DPAP-02 在本片为 PENDING，DMI-05 为 active/BLOCKED；continuation 中 DPAP-01 的 SATISFIED 只是背景状态，没有看到新证据触及它。 |

## 6. 表本身的问题

这里只报告观察到的覆盖/边界问题，不修补 situations.yaml 或设计文档。

1. **fix-mode worker 协议异常没有对应行。** seq 1995、2386、2747 出现 ack-only、INCOMPLETE 或 commit 后缺完整 envelope。现有 C10–C12 是 ticket.implement 下的 worker outcome，E1 只描述 reviewer finding 后要 fresh fix；无法表达“finding.fix worker 的 envelope 无效/未完成”。建议下一轮专门验证 finding.fix.worker-envelope-invalid 与 finding.fix.worker-incomplete 是否需要成为正式行。

2. **并行 fan-out/fan-in 没有处境。** seq 2554 明确采用四条 disjoint seam 并行修复，seq 2649–2747 展现了部分完成、等待剩余 worker、残余进程处置。attempt.readiness.multiple-ready-tickets 只适用于多个 ready Ticket，不能表达“一个 Ticket 的多个 finding/seam 并行收口”。

3. **验证环境不可用的边界缺失。** seq 2776–2802、2892、3505 以及片尾的 integration 尝试都显示 PostgreSQL/Docker 不可达。attempt.verify.manual-result-missing 要求 manual owner，和这里的自动 integration 环境阻断不同；ticket.accept.acceptance-edge-held 能表达“不能收”，但不能表达“为什么无法取得 verify evidence”。

4. **candidate finding 的 parent 核验与正式定级之间有空档。** seq 2278 先核验 reviewer candidate，seq 3169–3200 又把 P1 和 UNCERTAIN/owner decision 分开处理。E4 只能问 P1/P2/editorial，不能清楚表达“事实尚未确认”或“暂存 UNCERTAIN 等 owner 决定”。

5. **review/fix 的重用约束与实际动作冲突。** seq 3921–3929 让发现 P1 的同一个 Grok context 继续执行 fix，而 E1 的默认动作明确要求 fresh fixer，不得复用发现它的进程。该事件应作为规则逃逸或版本差异观察，不应直接据此改 basis。

6. **review 启动时的多重命中较多。** seq 2037、2951、3555、4005 同时落在 C7 与 F3，worker DONE 后又常同时落 C6/C13。现有优先级足以选主行，但渲染需要保留次命中，否则会把 review required、terminal coverage 和 acceptance held 混成一个原因。

本片没有足够证据把某个现有行的 basis 从 prose 升为 observed，也没有足够证据断言某个 cli 行错误。

## 7. 版本干扰

- 当前处境表是 version 1、2026-08-15 的设计输入；时间线发生在 2026-08-14，实际读取/调用的是 Impl-Package 0.3.0 及其当时的 subagent-driven-development、do-review 和 call-grok 合同。不能把旧版命令名或旧版 envelope 直接当作新版规则的反例。
- 时间线使用 FIX_COMMITTED、IMPLEMENTED_PENDING_REVIEW、DONE、INCOMPLETE、PENDING_REVIEW 等状态词；当前表的推导输入主要是 trail/state 的标准字段。部分映射只能依据主控叙述近似，尤其 C10/C11、C8 和 evidenceIndex 状态。
- 本片从 DPAP-02 的等待中间点开始，从 DMI-05 的 active checkpoint 直接恢复；前片可能包含调查载体、初始 evidence 和 Ticket 状态转换。本报告没有读取原始 rollout，也不以本片缺少这些内容证明它们从未发生。
- terminal-final、finding-closure、Grok review/fix 是实际执行拓扑名，不是处境表的一一对应阶段。它们被分别映射到 review、fix、record、accept 的处境，不能反向要求表增加同名环节。
- seq 3921–3929 的 Grok 同 context 修复，既可能是当时 skill 的授权路径，也可能是一次明确 escape；在当前版本重放前，不应单凭这一片把 E1 标为错误 basis。

## 8. 最值得注意的三个发现

1. **本片的工作重心是 review/fix/accept，而不是调查或 route。** 25 个确定命中的主映射中，review 9、accept 7、fix 4、record 4、disposition 1；investigate、route、gate 都没有确定命中。这是本片所处的返工阶段读数，不代表全案例没有调查或 Gate。

2. **主控在 closure 上持续 fail-closed。** DPAP-02 的新 Spec findings、DMI-05 的 P1 与 P1001 环境缺口都没有被低层测试结果覆盖掉；本片没有观察到未经独立 review 的 satisfy 或 Gate pass。相对的风险是 DMI-05 三个 worker evidence 的落账链在截断输入中无法证实，必须保持 insufficient-evidence。

3. **fresh-fix 规则是最清晰的实际冲突点。** 大多数 reviewer finding 都进入 fresh fix；但 Grok 在 seq 3921–3929 被复用为 fixer，正好触及 E1 的“不得复用发现它的进程”边界。这既是表的行为检验点，也是最需要先排除版本差异的观察。

