# 回放映射 · case2a

## 整体判断

本片覆盖案例 2 的第 1/4 片，时间上是最早的一片；它包含案例整体前 9 个 session 中的前 6 个 session，完成了 DPAP-01 的实现、两轮独立 review、验收与一次 revalidation，并推进到 DPAP-02 初轮实现与 review findings 收口。按本片终点，DPAP-01=SATISFIED、DPAP-02=PENDING 且有 10 个待修 P1/P2、DPAP-03=PENDING、Gate=open；案例 2 后续 3 个 session 与最终 Gate 不在本片内，因此案例整体最终状态为 insufficient-evidence，不能据本片宣称 closed。

本片分析范围是 39 个主控决策点：27 个主命中、12 个 unmatched，主命中率 69.23%；确认的多重命中为 8 条。跳步检测结果为：无调查载体直接实现 2 次；worker 返回后未立即进 evidence 再推进 3 次（另有 2 次跨 package 调研输出为 insufficient-evidence）；未经独立 review 就宣称完成或 satisfy 0 次；已 SATISFIED Ticket 被新证据触及并进入处置 1 次。

“本片完成”只表示本片内对应阶段已结束：DPAP-01 的 review/验收/revalidation 已完成，DPAP-02 的初轮 review 已完成；不表示案例 2 的 implementation、verification、Gate 或 release 完成。

## 1. 概况

| 项目 | 本片事实 |
| --- | --- |
| 整体位置 | 案例 2 的第 1/4 片；整体 9 个 session 中覆盖前 6 个 |
| 输入 | .test-tmp/replay-timelines/timeline-case2-part1.jsonl，1,891 条 JSONL 记录 |
| 时间范围 | 2026-08-13 22:24:45 → 2026-08-14 08:35:04（约 10 小时 10 分） |
| session | 6 个：aef4bf30、d7d57874、441fc60e、8dcf0191、90dbad5a、a70f6169 |
| package | docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe/ |
| 相关仓库 | KaiSpan implementation worktree；OCR Entry point D:\CodeSpace\kaispan-workspace\ocr-service-dev |
| 主线 | DPAP-01 OCR profile → fresh fix → checkpoint review → satisfy；Owner comment 触发基线/合同复核 → OCR rebase/revalidation；DPAP-02 gateway/reducer → initial four-track review → fresh fix handoff |
| 本片终点 | DPAP-01 满足；DPAP-02 初轮 review 记录 10 个 blocking P1/P2；DPAP-03 未开始；Gate open；fresh DPAP-02 fixer 已启动 |
| 案例整体终点 | insufficient-evidence：后续 3 个 session 不在本片，不能推断最终修复、terminal-final review、Ticket acceptance 或 Gate verdict |

时间线摘要说明本案例存在截断：user 91 行、assistant 19 行、reasoning 10 行、tool_out 1,565 行被字符预算截断；命令型 tool_call 未按字符预算截断，但工具输出与 reasoning 仍只有摘要/前缀。以下凡依赖未显示的 state 字段均显式标 insufficient-evidence。

## 2. 决策点映射

计数口径：纯读取、等待、重复状态轮询、单纯测试命令和无路径变化的状态汇报不单独计点；同一因果动作的多个落账命令合并，独立的 Ticket 状态、evidence、checkpoint、handoff 和 worker/reviewer 路由选择分开。每个决策点只用一个 primary slug 计入命中率；同时命中的 secondary slug 放到“多重命中”。

| ID | 时间 | 主控决定 | seq | 映射与判定依据 |
| --- | --- | --- | --- | --- |
| D01 | 22:26:09 | 从 active checkpoint 恢复，不重做历史工作 | 19 | primary attempt.record.session-resumed；有 active checkpoint，恢复 session 尚无新动作。 |
| D02 | 22:26:29–22:31:43 | 在 DPAP-01/02 两个 ready Ticket 中先选 DPAP-01，并形成 implement 调度合同 | 23, 107, 134, 139 | primary attempt.readiness.multiple-ready-tickets；ready 数大于 1 且无 in-flight。另命中 ticket.investigate.no-carrier：DPAP-01 无 investigate 载体/Ticket evidence，选择带理由的 implement-direct。 |
| D03 | 22:31:29–22:32:58 | 历史 OCR anchor 缺失时，以当前 main 做 freshness gate，继续 implementation-only | 102, 130 | unmatched；这是“来源基线缺失但当前来源足以给出继续结论”的处境，现表没有对应行。 |
| D04 | 22:33:49–22:34:26 | 把“每次 compact 后先收 checkpoint、再 handoff，并携带两个仓库 anchor”设为后续 session 的持续规则 | 141, 143, 153 | unmatched；这是跨 session policy relay，不是当前 attempt.record.checkpoint-missing 的明确命中。 |
| D05 | 22:48:21–22:51:28 | worker 返回 DPAP-01 DONE/PENDING_REVIEW 后，固定 comparison point 并进入独立 checkpoint review | 252, 253, 287, 307 | primary ticket.review.awaiting-reviewer；DONE + review_required，且 scope 为 checkpoint。因 privacy/scope/idempotency/retry/provider seam 同时命中 ticket.review.required-trigger。 |
| D06 | 22:54:30–23:00:48 | review 返回 blocking findings 后，写 review evidence/ER/checkpoint，转 fresh-fix | 322, 327, 332, 337, 358, 391, 398, 400 | primary finding.fix.reviewer-returned；finding 来源是 reviewer，后续要求 fresh fixer，不复用原 implementation worker。 |
| D07 | 23:02:18 / 23:02:26（跨 session，时间戳非单调） | 首次 clean handoff 因 OCR branch anchor 多写 datev 而停止，重新创建正确 session | 429, 456, 464 | unmatched；这是 handoff anchor mismatch/重试，表中没有对应记录行。 |
| D08 | 23:04:10 | 新 session 通过 anchor 后，从 DPAP-01 fresh-fix-required checkpoint 恢复 | 490 | primary attempt.record.session-resumed；continuation 明确引用 active checkpoint，未回溯初轮实现。 |
| D09 | 23:05:32–23:06:22 | 按 reviewer findings 派 fresh DPAP-01 fix worker，限定 F-001..F-004/F-006 | 492, 530, 532 | primary finding.fix.reviewer-returned；fresh invocation 是 reviewer finding 的默认修复动作。 |
| D10 | 23:16:20–23:19:25 | fresh fixer 返回后，针对 dirty diff 进入第二次独立 checkpoint review | 634, 638, 650, 674 | primary ticket.review.awaiting-reviewer；fix worker DONE 且 review 仍 PENDING_REVIEW。同时保留 ticket.review.required-trigger 命中。 |
| D11 | 23:25:01–23:25:34 | reviewer 全部 PASS 但 fix 仍是 dirty tree，先只提交 5 个 tracked 文件以获得 immutable revision | 744, 750 | ticket.accept.acceptance-edge-held；已有证据但 acceptance 所需 revision edge 尚未释放，不能直接 satisfy。 |
| D12 | 23:25:46–23:29:08 | 绑定 OCR commit 23505b9，复跑 focused/full/compileall/hygiene，并将 review/claim evidence 入账 | 754, 777, 806, 812, 815 | ticket.record.evidence-unfiled；worker/reviewer 直接证据先返回，直到此处才形成可索引的 claim evidence。 |
| D13 | 23:29:20 | 在 Ticket satisfy 前执行 completion-claim audit | 817, 818 | attempt.accept.completion-claim-unaudited；明确先做 claim-to-evidence audit。 |
| D14 | 23:29:29 | 以 KaiSpan anchor + OCR revision/environment 证据满足 DPAP-01 | 820 | ticket.accept.satisfiable；CLI 收到 PENDING、可解析 revision、environment 与已支持 claims。 |
| D15 | 23:29:51 | DPAP-01 满足后把 next action 指向唯一 ready 的 DPAP-02 | 825, 826 | unmatched；现表有“多个 ready”和“全部 terminal”，没有“恰好一个 ready、正常推进”的正向 readiness 行。 |
| D16 | 04:10:27–04:13:30 | 按 checkpoint 创建下一个 clean local session，携带 DPAP-02 与 OCR anchor | 839, 841, 848, 857, 900 | unmatched；handoff 本身不是 checkpoint-missing 的明确命中，且 timeline 没有显示 handoff 前 active_checkpoint_present 的布尔值，G1 精确命中为 insufficient-evidence。 |
| D17 | 04:13:01–04:13:30 | 新 session 通过规范化路径比对后恢复 DPAP-02 checkpoint | 891, 893, 900 | attempt.record.session-resumed；anchor PASS 后 continuation 才恢复，不读取全历史。 |
| D18 | 04:15:25–04:19:40 | 对 GitHub Owner comment 做独立只读影响审阅，并派 reviewer 核对合同/基线 | 901, 903, 971 | unmatched；这是外部合同影响审阅，不等同于已有 ticket.route.sources-conflicting 的 req-align 决策。 |
| D19 | 04:28:07–04:29:10 | 将 comment 视为改变基线/失败语义的 post-acceptance 新证据，暂停 DPAP-02，并把 DPAP-01 按待重验处理 | 1049, 1055 | primary ticket.rework.evidence-conflict；新证据触及已 SATISFIED Ticket 的 claims。secondary attempt.rework.contract-changed；Owner comment 改变了 contract/baseline。 |
| D20 | 05:05:49–05:26:10 | 把“提交数”问题改成逐接口影响分析和隔离 rebase 实验，派 mode=investigate worker | 1067, 1071, 1140 | ticket.rework.revision-diverged；accepted revision 与 upstream/main 已分叉，选择 re-investigate 而不是直接保留原结论。也有 attempt.rework.contract-changed 的 secondary 命中。 |
| D21 | 05:38:16–05:40:29 | 将影响、结论、冲突处理指导写入用户 Temp，供任务包调整 | 1214, 1216, 1222, 1229 | unmatched；这是调研指导 artifact，不是 package evidence、checkpoint 或表内标准动作。 |
| D22 | 07:30:05–07:31:51 | Owner 同意真实 OCR feature rebase；先 preflight、建 backup ref，再改写 feature branch | 1253, 1255, 1268 | ticket.rework.revision-diverged；revision divergence 的处理从调查进入重新取证/重放。 |
| D23 | 07:31:44–07:35:24 | 按已验证 resolution 合并双方语义，处理共享 seam 的 rebase conflicts | 1272, 1284, 1308 | unmatched；D2 只给“重新取证/确认原结论”两类动作，没有“保留双方原意并手工解决 rebase conflict”的动作。 |
| D24 | 07:36:03–07:36:35 | rebase 到 origin/main@8194f78 后，以正确 OCR workdir 重跑 focused/full/hygiene | 1315, 1318, 1321 | ticket.rework.revision-diverged；这是对 diverged acceptance revision 的重新取证。第一次在错误 cwd 执行的 compile/test 被明确排除，不能算证据。 |
| D25 | 07:38:09–07:39:10 | 用户要求 handoff 后，重排为“先完成 package upgrade，再交接启动 impl” | 1334, 1346, 1348, 1350 | unmatched；是 handoff 与 package bookkeeping 的时序选择，现表没有该记录层处境。 |
| D26 | 07:41:54–07:42:35 | 将旧 23505b9 claim evidence 标 stale，Ticket 进入 NEEDS-REVALIDATION | 1374, 1376 | ticket.rework.revision-diverged；CLI 明确记录 acceptance revision 已因 rebase 分叉而失效。 |
| D27 | 07:42:07–07:42:42 | 为新 revision 添加 7 条 claim evidence、judgment 与 next checkpoint | 1378, 1384, 1386 | ticket.record.evidence-unfiled；新 revalidation 证据从文件进入 evidence index，并带 revision/environment。 |
| D28 | 07:42:26 | 以新 OCR f47ae49 证据重新满足 DPAP-01，释放 DPAP-02 typed barrier | 1382 | ticket.accept.satisfiable；前置状态为 NEEDS-REVALIDATION，新 claims 已支撑。 |
| D29 | 07:42:42–07:45:31 | 将恢复点交给新 session，随后启动唯一 ready 的 DPAP-02 implementation | 1386, 1390, 1402, 1413, 1428, 1431 | unmatched；handoff 选择本身不由现有 G1 完整表达；active checkpoint 的“缺失/存在”前置在片段中不可见，标 insufficient-evidence。 |
| D30 | 07:44:16–07:44:26 | 新 session 恢复 DPAP-02，确认 DPAP-01 satisfied、DPAP-02 唯一 ready | 1439, 1441 | attempt.record.session-resumed；continuation 与 checkpoint 对齐。 |
| D31 | 07:45:20–07:46:16 | 形成 closure-review 调度合同并直接派 DPAP-02 implement worker | 1463, 1469, 1471, 1475 | ticket.investigate.no-carrier；DPAP-02 PENDING、无 investigate 载体/自身 evidence，按 Plan 以明确理由选择 implement-direct。 |
| D32 | 08:12:50–08:13:30 | DPAP-02 worker 首次返回 INCOMPLETE 后，保留实现并推进固定 comparison point/独立 review | 1591, 1594, 1601 | primary ticket.implement.worker-incomplete-first；首次 INCOMPLETE。当前表默认动作是 fresh fallback，但主控选择先 review，构成表内动作偏离；另有 review trigger 的候选命中。 |
| D33 | 08:14:47 | worker 的测试通过声明与主 session 直接执行失败发生环境证据矛盾，先查依赖而不采信 | 1625, 1626 | ticket.verify.contradictory-unresolved；矛盾证据未解决前没有接受。是否同时满足 ticket.record.evidence-unfiled 取决于 evidence.indexed，本片未显示，故 secondary 为 insufficient-evidence。 |
| D34 | 08:15:10–08:15:20 | 规定本地验证优先复用主工作区配置，不复制 .env/凭证，并写入后续 relay | 1635, 1638, 1639 | unmatched；这是 configuration/secret-boundary relay，现表没有对应 record 行。 |
| D35 | 08:18:26–08:19:56 | 依赖补齐后固定 DPAP-02 immutable commit，创建四轨 closure review（含 Safety） | 1658, 1687, 1696, 1703 | ticket.review.required-trigger；OCR POST、幂等、重试、隐私/数据完整性 seam 触发 review。ticket.accept.acceptance-edge-held 同时可命中：有 implementation evidence 但 Ticket 尚未可 satisfy。 |
| D36 | 08:23:52–08:31:43 | 四轨 review 返回 findings，定级 10 个 blocking P1/P2、1 个非阻塞 follow-up，写 ledger/evidence/checkpoint 并转 fresh fix | 1722, 1729, 1734, 1738, 1798, 1801, 1803 | primary finding.fix.reviewer-returned；reviewer findings 必须由 fresh fixer 消费。secondary finding.disposition.grading-undecided；主控在 blocking 与 deferred follow-up 之间完成 grading。 |
| D37 | 08:31:49–08:34:43 | review checkpoint 落账后创建 clean handoff，让下一 session 从 fresh-fix checkpoint 接手 | 1805, 1816, 1825, 1832, 1847 | unmatched；handoff 动作没有独立表行；G1 是否因 active checkpoint 缺失而命中为 insufficient-evidence。 |
| D38 | 08:33:31–08:33:45 | 新 session 通过 anchor 后恢复 DPAP-02 findings checkpoint | 1863, 1866 | attempt.record.session-resumed；continuation 明确要求不重做初轮实现/review。 |
| D39 | 08:34:16–08:34:51 | 按 checkpoint 启动 fresh DPAP-02 fix worker，review scope 为 closure | 1877, 1890 | finding.fix.reviewer-returned；10 个已确认 findings 需要 fresh fix，后续 closure review 未在本片完成。 |

## 3. 读数

### 3.1 总量

| 指标 | 数值 |
| --- | ---: |
| 决策点总数 | 39 |
| 主命中 | 27 |
| unmatched | 12 |
| 主命中率 | 69.23% |
| 多重命中（确认） | 8 |
| 多重命中候选（不计入） | 1，insufficient-evidence |

命中率以 primary slug 计，不因 secondary 命中重复加权；否则同一动作会同时放大多个环节的读数。

### 3.2 按环节的 primary 命中分布

| 环节 | 命中数 | 对应决策点 |
| --- | ---: | --- |
| record | 7 | D01, D08, D12, D17, D27, D30, D38 |
| readiness | 1 | D02 |
| investigate | 1 | D31 |
| route | 0 | 本片没有一次首次技术路线裁决被表准确承接 |
| implement | 1 | D32 |
| fix | 4 | D06, D09, D36, D39 |
| verify | 1 | D33 |
| review | 3 | D05, D10, D35 |
| accept | 4 | D11, D13, D14, D28 |
| rework | 5 | D19, D20, D22, D24, D26 |
| disposition | 0 | 本片没有退休/正式 findings triage 到 Decision/Spec/ER/Durable Delta |
| gate | 0 | Gate 始终 open，没有 pass/blocked/fail/defer verdict |
| **合计** | **27** | |

### 3.3 多重命中

以下 8 条是基于可见条件确认的多重命中；primary 按 YAML priority 或当前 subject 的更具体边界选择。

| # | 决策点 | 同时命中 | 说明 |
| --- | --- | --- | --- |
| M1 | D02 | attempt.readiness.multiple-ready-tickets + ticket.investigate.no-carrier | attempt 层在 ready Ticket 间选择，ticket 层又处于无调查载体的直接实现前沿。 |
| M2 | D05 | ticket.review.awaiting-reviewer + ticket.review.required-trigger | DONE + review_required 与安全/幂等/隐私 seam 同时成立；前者优先派 reviewer。 |
| M3 | D10 | ticket.review.awaiting-reviewer + ticket.review.required-trigger | fresh fix DONE/PENDING_REVIEW，且同一 OCR seam 的 safety 触发仍在。 |
| M4 | D19 | ticket.rework.evidence-conflict + attempt.rework.contract-changed | Owner comment 既触及已 SATISFIED claim，又改变 attempt 的合同/基线。 |
| M5 | D20 | ticket.rework.revision-diverged + attempt.rework.contract-changed | 需要实际验证 upstream 变更是否让既有 contract 失效；这是 revision divergence 与 contract change 的交集。 |
| M6 | D32 | ticket.implement.worker-incomplete-first + review-trigger 候选 | 首次 INCOMPLETE 命中 C10；同时存在 review pending/安全 seam，但 C6 的 last_outcome=DONE 条件不成立。 |
| M7 | D35 | ticket.review.required-trigger + ticket.accept.acceptance-edge-held | 需要独立 closure review，同时 implementation evidence 尚不足以释放 acceptance edge。 |
| M8 | D36 | finding.fix.reviewer-returned + finding.disposition.grading-undecided | reviewer findings 需要 fresh fix，且主控还要区分 blocking P1/P2 与 deferred follow-up。 |

另有 1 条候选不计入：D33 可能同时命中 ticket.record.evidence-unfiled，但时间线没有显示当时 evidence.indexed，因而为 insufficient-evidence。

## 4. unmatched 清单

以下建议 slug 均符合 <对象>.<环节>.<状况>、当前对象×环节允许矩阵和字符规则；这里只报告，不修改表。

| 决策点 | 真实发生了什么 | 建议 slug | 为什么现表接不住 |
| --- | --- | --- | --- |
| D03 | 历史 anchor 不可取得，但当前 main 的 registry/application/analyzer 等 seam 被检查后决定继续 | attempt.verify.baseline-anchor-missing | 不是普通 evidence gap：它是 attempt 级 baseline freshness 判断，现有 verify 行没有该状况。 |
| D04 | 新增 compact 后 handoff relay 规则，并要求携带两个仓库 Entry point | attempt.record.handoff-relay-rule | 现表没有“持久化交接规则”的 record 行。 |
| D07 | handoff 子 session 的 OCR branch 拼写错误，anchor FAIL 后不发送 continuation，重新创建 | attempt.record.anchor-mismatch | session-resumed 只覆盖成功恢复，不覆盖 handoff anchor 失败与安全停止。 |
| D15 | 一个 Ticket 满足后正常选择唯一 ready Ticket | attempt.readiness.single-ready-ticket | 现表只显式描述多个 ready、全部边被挡和 blocker 重评，没有单 ready 的正常行。 |
| D16 | 创建并验证 DPAP-02 clean session 的 handoff | attempt.record.session-handoff | checkpoint-missing 只在 checkpoint 缺失时成立；本片未显示 handoff 前 checkpoint 布尔状态。此处精确命中为 insufficient-evidence。 |
| D18 | 外部 Owner comment 先进入独立影响审阅，尚未直接做 req-align/route 裁决 | attempt.review.external-contract-impact | 不是 terminal review，也不是 Ticket 的普通 required-trigger。 |
| D21 | 把跨仓库研究压缩为用户 Temp 下的影响/结论/指导文档 | attempt.record.impact-guidance-written | 现表没有 package 外部但对后续 package 调整有约束力的指导 artifact。 |
| D23 | 在 rebase 中按验证过的 resolution 手工保留双方 shared seam 语义 | ticket.rework.rebase-conflicts-present | revision-diverged 只给重新取证/确认原结论，没有冲突存在时的合法解决动作。 |
| D25 | 用户改变顺序，主控先升级 package 再 handoff、再开启下一个 impl session | attempt.record.handoff-order-reselected | 现表没有 bookkeeping 与交接次序的选择行。 |
| D29 | revalidation 完成后为 DPAP-02 创建新的 session 并继续 implementation | attempt.record.session-handoff | 同 D16；handoff 前 active checkpoint 是否“缺失”不可从截断输入确认，标 insufficient-evidence。 |
| D34 | “优先用主工作区配置、不得复制秘密”被持久化并传给后续 checkpoint/handoff | attempt.record.config-preference-relayed | 这是配置/秘密边界 relay，不是现有 checkpoint-missing 或 intake backlog。 |
| D37 | DPAP-02 findings checkpoint 写入后再 clean handoff 给 fresh fixer | attempt.record.session-handoff | 同 D16/D29；成功 handoff 没有独立处境行，G1 精确前置仍为 insufficient-evidence。 |

## 5. 跳步检测

| 检测项 | 次数 | seq | 判断 |
| --- | ---: | --- | --- |
| 没有任何调查载体就直接进入实现 | 2 | D02：107/134；D31：1463/1475 | 两次分别是 DPAP-01、DPAP-02；均有 explicit reason（freshness gate/approved Plan），所以是表允许的 implement-direct，但确实没有 Ticket-level investigate carrier。 |
| worker 返回后未记 evidence 就推进 | 3 次确认 | 252→253；634→638；1591→1594 | 三次都先消费 worker outcome、固定 diff 或进入 review，直到更后面才看到 package evidence add/正式 review evidence。 |
| worker 返回后未记 evidence 就推进（跨 package 调研输出） | 2 次 insufficient-evidence | 1049；1219→1222 | 外部 comment reviewer 与 rebase investigator 的结果被用于后续判断/Temp 指导，但本片没有对应 package evidenceIndex 快照，不能断言它们违反 C8。 |
| 未经独立 review 就宣称完成或 satisfy | 0 | DPAP-01 satisfy 在 820，前置 review 在 307/674；DPAP-02 没有 satisfy | 未观察到异常。DPAP-02 的 worker DONE/INCOMPLETE 均明确保持 PENDING_REVIEW，主控没有把它宣称为 closed。 |
| 已 SATISFIED Ticket 被新证据触及时是否处置 | 1 | 1049/1055 → 1376 → 1382 | DPAP-01 被 Owner comment/新 baseline 触及；先暂停 DPAP-02，后标 stale/NEEDS-REVALIDATION，刷新 evidence，再恢复 SATISFIED。这是一次实际发生且最终有处置的 D1/D2 链。 |

## 6. 表本身的问题

只报告观察，不修改 situations.yaml 或设计文档。

1. **正常单 ready 前沿缺行。** DPAP-01 满足后、以及 revalidation 后，DPAP-02 都是唯一 ready Ticket；主控必须做“正常选择并继续”，但现表只有 multiple-ready-tickets、all-edges-held 和 blocker 重评。D15 因此只能 unmatched，D31 只能借 C1 承接。

2. **baseline freshness 与 rebase conflict 没有独立承载。** D03 的“历史 anchor 缺失但当前来源可继续”和 D23 的“shared seam 手工合并”都不是普通 evidence-gap 或 D2 的二选一动作。若反复出现，建议分别补充 verify 级 baseline 行与 rework 级 conflict 行。

3. **INCOMPLETE 与 review pending 的边界不够机械。** D32 同时有首次 INCOMPLETE、实现 diff 已存在、review_state=PENDING_REVIEW。C10 默认 fresh fallback，但主控按 review pending 继续固定 diff/review；当前优先级中 C6 又要求 last_outcome=DONE，因此“先 review 还是先 fallback”没有稳定的 predicate/priority 结论。

4. **post-acceptance contract change 会跨三个边界。** D19 同时像 ticket.rework.evidence-conflict、attempt.rework.contract-changed，也可能被误读成 ticket.route.sources-conflicting。现表没有把“已满足 Ticket 被外部合同/基线触及”作为一条更具体的优先级组合，容易让 route 与 rework 竞争。

5. **handoff 的成功、失败和 relay 规则没有完整映射。** G1 只描述 checkpoint 缺失，但本片实际有 anchor FAIL 后停止、成功 handoff、handoff 次序重排和持续 relay 规则。若不补行，跨 session 的真实控制点会落成多个 unmatched，而不是可区分的 record 读数。

6. **显式 priority 不是 42 行的完备排序。** 机读 priority 没有显式列出 attempt.record.session-resumed、attempt.record.checkpoint-missing、attempt.readiness.multiple-ready-tickets、finding.disposition.grading-undecided 等行。D02、D36 这类事件仍可凭组级语义解释，但不能说所有多重命中都由 YAML 机械裁决；应先明确 omitted rows 的 fallback 顺序再评估命中率。

7. **证据滞后虽未造成 premature satisfy，但可见性不足。** D05/D10/D32 都先消费 worker/reviewer 回执，之后才形成 package evidence/ledger；表有 C8，但它需要 evidence.indexed=false，本片没有 state 快照，因此只能检测到“落账滞后”的事实，不能稳定判断是否已越过 record 边。

## 7. 版本干扰

- 本片执行主体显式使用 Impl-Package 0.3.0；更早的 session 曾尝试读取不存在的 0.2.9 cache 后纠正。不能把 0.2.9 路径错误或其行为当作 current table 的规则证据。
- 时间线发生在 2026-08-13/14，处境表设计说明日期为 2026-08-15；回放时的旧版 dev-with-track、subagent-driven-development、do-review 和当前 42 行表并非同一版本。尤其 D32 对 C10/C6 的解释，不应直接转成“当前表一定错误”。
- 时间线没有显示旧版处境渲染器或 situations YAML 实际参与执行；本报告是事后 overlay mapping，不证明当时 agent 已收到这些 slug/priority。
- review topology 在本片采用四条 leaf（behavior/standards/spec/safety），而表只抽象到 review_required/awaiting-reviewer；四条 leaf 的数量不能当成四个 Ticket 决策点，也不能据此推导表应新增四个 review 行。
- Owner comment、授权扩展、主工作区配置偏好和 handoff relay 是运行中新增的用户输入；它们改变了后续路线，但不应在没有跨版本对照的情况下直接回填成默认表规则。
- 案例整体还有后续 3 个 session；本片没有 DPAP-02 fresh fix 的结果、finding-closure、terminal-final review、DPAP-02/03 acceptance 或 Gate verdict。相关结论全部保持 insufficient-evidence。

## 8. 最值得注意的三个发现

1. **DPAP-01 的 SATISFIED 并非终点。** 外部 comment/新 baseline 触及已满足 Ticket 后，主控没有继续沿用旧证据，而是暂停下游、标 stale、重新取证并恢复满足；这是 D1/D2/D3/C15 链条在真实任务中的完整样本。

2. **表最缺的不是“是否 review”，而是 review 前后的交界动作。** INCOMPLETE + pending review、dirty diff 到 immutable revision、finding grading 到 fresh fix 都发生在 review 边界，现有行能部分命中，但动作集合与 priority 不能完全机械推出下一步。

3. **记录层仍是主要可观测性瓶颈。** 本片没有 premature satisfy，但多次 worker/reviewer 回执先被用于推进，后续才形成 evidence/ledger；同时正常 handoff、anchor mismatch、baseline freshness 和 rebase conflict 大量 unmatched。这说明表当前更能描述“验收条件是否满足”，还不能完整描述“跨仓库长跑如何安全恢复”。
