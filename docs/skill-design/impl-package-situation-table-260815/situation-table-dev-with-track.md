# dev-with-track 处境表（设计草稿）

> **本页是设计期草稿。** YAML 落地后，正式来源以 `skills/dev-with-track/situations.yaml` 为准（本仓库实际路径为 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`），人读全表跑渲染器打印；本页只保留枚举过程与讨论记录，不作为事实源。

slug 采用 `<对象>.<环节>.<状况>` 三段式，规则见 [README 第 9 节](README.md#9-命名空间)。

**字母行号（A1、C8……）只是本页的阅读编号，不是键。** slug 才是键；同一阅读分组内的行可以落在不同环节上。

标记说明：

- **判** = 判断行（两个以上合法动作，选哪个取决于本次具体事实），其余为记忆行。
- **basis** = 这条规则靠什么成立。`cli` 表示 CLI 本来就会拒绝违反者；`prose` 表示只有散文这么说，没有任何强制——**表在赌它是对的**。

## 命中优先级

多行同时命中是常态。保留 P0–P5 的层间顺序，但层内不再构造全序；当前正式表共 56 行：

```text
P0（严格顺序）. fail-closed 与记录完整性  [A4, A1, A2, N06, N07, N08, A3, G1, N09, N05, C8, N10]
P1（无序集合）. attempt admission 与验证载体准入  {Owner, B2, B1, B4, N20}
P2（无序集合）. 返回与未完成动作  {N15, C10, C11, C12, C1, C2, E1, N13, N18, C6, C7, E3, E2}
P3（无序集合）. 事实/合同/返工/验证缺口  {C14, C9, N21, N19, D1, D2, D3, D5, C3, C5, C4, D4}
P4（无序集合）. acceptance 与全局收口  {C13, F4, C15, F1, F2, F3, E4, E5, B3, F5, F6a, F6, F7}
P5（无序集合）. 记录层卫生  {G2}
```

P0 命中时按严格顺序取第一条，其他 P0 命中列为 secondary，不展示更低层。未命中 P0 时取最高命中层，该层全部命中并列展示，不指定主 slug；更低层命中作为 secondary 一行带出。全部命中仍保留在结构化结果中。

本轮只把回放中出现频次达到门槛的候选加入正式表；N21 在 consolidated §2.2 的编号序列中漏列，但它已获准加入，因此按其 comparison-head 的 review 完整性语义放入 P3。

## A. 入口与恢复

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| A1 | `package.record.state-missing` | cli | `state_invalid`：state 缺失、schema/交叉校验失败或 `package validate` 失败 | 只能 `package validate` / `package init` |
| A2 | `package.record.projection-drift` | cli | `package validate` 报告 projection drift | `package refresh-progress` |
| A3 | `attempt.record.session-resumed` | prose | active checkpoint 存在，且该 checkpoint 之后 trail 尚无动作 | 按恢复序列读 checkpoint，不读全史 |
| A4 | `attempt.gate.terminal-frozen` | cli | terminal Gate 已写，仍有推进请求 | fail closed，回 `impl-planning` 开 patch attempt |
| N05 | `attempt.record.handoff-in-flight` | prose | handoff/relay 正在发送或等待 continuation | `$handoff-to-new-session` + `recovery checkpoint` |
| N06 | `attempt.record.anchor-mismatch` | prose | anchor 存在但表示不一致导致校验失败 | `$handoff-to-new-session` 重跑 anchor 校验 |
| N07 | `attempt.record.handoff-recovery-needed` | prose | handoff bootstrap、重命名或创建失败 | `$handoff-to-new-session` 一次受控 retry |
| N08 | `attempt.record.handoff-target-corrected` | prose | handoff target/order 已被纠正 | `$handoff-to-new-session` 按 corrected target/order 重发 |
| N09 | `attempt.record.checkpoint-refresh` | prose | active checkpoint 已有但下一动作发生变化 | `recovery checkpoint` |
| N10 | `ticket.record.judgment-unfiled` | prose | judgment/conclusion 已形成但未进入记录 | `recovery judgment` |

## B. 选下一个单元

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| **B1 判** | `attempt.readiness.multiple-ready-tickets` | prose | 有多个 readyTicket，无 in-flight 工作 | 选一个开工；依据依赖、集成顺序与共享资源 |
| B2 | `attempt.readiness.all-edges-held` | cli | 无 readyTicket，但有 PENDING | implementation 边全被挡，查阻塞源，不得硬上 |
| B3 | `attempt.accept.all-tickets-terminal` | prose | 全部 Ticket 为 SATISFIED 或 RETIRED | 进入 completion claim audit |
| B4 | `ticket.readiness.blocker-maybe-resolved` | prose | 有 BLOCKED，且其 blocker 可能已解 | 重评 blocker；BLOCKED 不释放依赖 |
| Owner | `attempt.readiness.worker-still-running` | prose | 已派出的 worker 尚未返回，主控准备另起动作或打断 | `wait_threads` 等待 result；打断必须写 reason |
| N20 | `attempt.readiness.integration-carrier-unavailable` | prose | integration carrier 不可用 | 先查本仓库是否有预置的环境启动能力（例如名为 `start-env` 一类的 skill 或脚本）并调用它；环境配置在主工作区执行，不在 worktree 内；禁止修改配置文件或连接远程库。 |

## C. 单个 Ticket 推进

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| **C1 判** | `ticket.investigate.no-carrier` | prose | PENDING，当前 Ticket 没有 investigate 派发或 early-falsification evidence，且没有其它已明确的 typed 处境与 evidence 记录 | 派 investigate；或直接实现并记理由 |
| C2 | `ticket.investigate.evidence-gap` | prose | investigate 返回 `EVIDENCE_GAP` | 补取证，不进实现 |
| **C3 判** | `ticket.route.multiple-business-outcomes` | prose | 存在多个合理业务结果 | 请求 owner decision；没有结论前不派修复 |
| C4 | `ticket.route.sources-uniquely-decide` | prose | 来源唯一裁决 | 按 implementation defect 修复并重验 |
| **C5 判** | `ticket.route.sources-conflicting` | prose | 来源缺失、含糊或冲突 | 回 `req-align` 更新 Spec ensemble，再进入实现 |
| C6 | `ticket.review.awaiting-reviewer` | prose | implement DONE 且 `review=required` | 派 reviewer，scope 必须显式 checkpoint 或 closure |
| C7 | `ticket.review.required-trigger` | prose | 命中 shared seam、安全、数据完整性、并发、migration 或不可逆外部副作用 | 置 `review=required`；非显然地选 `none` 时记 reason |
| C8 | `ticket.record.evidence-unfiled` | prose | worker 已返回直接证据，但对应 direct-evidence tuple 尚无未失效 index record | `evidence add`，必须带 `timing` |
| C9 | `ticket.verify.safety-invariant-unfalsified` | prose | 至少一个安全不变量 claim 尚无 active evidence，仍未验证 | 不得推迟到加固组 |
| C10 | `ticket.implement.worker-incomplete-first` | prose | worker 第一次返回 `INCOMPLETE` | 允许一次 fresh fallback |
| C11 | `ticket.implement.worker-incomplete-second` | prose | worker 第二次返回 `INCOMPLETE` | 归一为 BLOCKED |
| C12 | `ticket.implement.worker-blocked` | prose | worker 返回业务 `BLOCKED` | 不 fallback；`ticket block` 或上交 owner |
| C13 | `ticket.accept.acceptance-edge-held` | cli | 有 evidence 但 acceptance 边未释放 | 可继续实施，不可 SATISFIED |
| **C14 判** | `ticket.verify.contradictory-unresolved` | cli | required claim 带矛盾或不确定证据 | 处置后方可 satisfy |
| C15 | `ticket.accept.satisfiable` | cli | 同一 acceptance pair 的全 claim 有支撑、无 active contradictory/inconclusive、入边已释放且 revision 可解析 | `ticket satisfy --expect --revision --environment` |

## D. 返工与重开

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| **D1 判** | `ticket.rework.evidence-conflict` | prose | 已 SATISFIED，新证据触及其 claim | 四选一，见下方展开 |
| **D2 判** | `ticket.rework.revision-diverged` | cli | acceptance revision 与当前 HEAD 已分叉 | 重新取证；或确认原结论仍成立 |
| D3 | `ticket.rework.revalidation-pending` | cli | Ticket 处于 NEEDS-REVALIDATION | 走重验计划 → `ticket pending` → 重新 satisfy |
| D4 | `attempt.rework.contract-changed` | prose | plan 或 contract 实际变化 | 记录 affected subset，沿用 initial bundle approval，保留未受影响 evidence |
| **D5 判** | `ticket.disposition.retire-undecided` | cli | 不再需要完成 | `waived` 或 `superseded`；后者必须有 successor |

D5 落在 `disposition` 而非 `rework`：退休是给一个已知项定归宿，`rework` 只覆盖已达成的验收结论被推翻之后的处置。

### D1 展开

```text
slug: ticket.rework.evidence-conflict
可选动作:
  a. evidence invalidate --ticket <id> --claim <id> --invalidated-by <reason>
     后果: claim 失去支撑，不自动改 Ticket 状态
     执行者: main-session
  b. ticket needs-revalidation <id> --expect SATISFIED --claim <id> --invalidated-by <reason>
     后果: 不释放依赖，下游 acceptance 边被卡；Progress 标 stale
     执行者: main-session
  c. 记为独立 finding，不动本 Ticket
     适用: 这是新需求，不是原 claim 被证伪
  d. ticket retire <id> --disposition superseded --successor <id>
     后果: successor 满足前不释放边
判断点: 这条证据是证伪了原 claim，还是提出了新要求
逃逸: 以上都不适用时按判断行动，记一行 reason
```

## E. Findings

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| E1 | `finding.fix.reviewer-returned` | prose | reviewer 返回 finding | 交 fresh fixer，不得复用发现它的进程；修复后由同 scope reviewer 重审 |
| E2 | `finding.review.source-recheck-pending` | prose | accepted Track C 或 Spec fidelity finding | 先消费 `do-review` 同一 ReviewRun 内的一次性独立 source recheck |
| E3 | `finding.fix.main-session-discovered` | prose | 主控自己发现 finding | 可直接进 fresh fixer，不必先过 reviewer |
| N13 | `finding.review.closure-awaiting` | prose | fix 已完成但等待同 scope finding-closure reviewer | `/impl-package:do-review`，scope=closure |
| N15 | `finding.fix.worker-envelope-invalid` | prose | finding fixer 的 envelope 不完整或不可采信 | `/impl-package:subagent-driven-development mode=fix` fresh invocation |
| **E4 判** | `finding.disposition.grading-undecided` | prose | finding 待定级 | P1/P2 阻断 Gate 并需 closure verify；editorial 不阻断 |
| **E5 判** | `attempt.disposition.findings-triage-pending` | prose | `execution-findings.md` 未分流且接近 terminal Gate | 四路分流：Decision rationale → Decision，规范行为 → Spec，执行判断 → Execution Record，长期知识 → Durable Delta 与 `_pending.md` |

## F. 验证与 Gate

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| F1 | `attempt.verify.manual-result-missing` | prose | Planned Verification 有 manual owner 且无结果 | 使用 manual-acceptance-readiness 模板，取得结果 evidence |
| F2 | `attempt.accept.completion-claim-unaudited` | prose | 准备声明完成 | 先走 `/impl-package:verification-before-completion` |
| F3 | `attempt.review.terminal-coverage-incomplete` | prose | terminal-final coverage 不完整 | 回 `do-review` |
| N18 | `attempt.review.reviewer-unavailable` | prose | reviewer timeout、无效 envelope 或旧 ReviewRun 不可采信 | `/impl-package:do-review` 关闭旧 run 并重开 fresh review |
| N19 | `attempt.verify.integration-evidence-unavailable` | prose | 所需 integration evidence 载体不可取得 | 先查本仓库是否有预置的环境启动能力（例如名为 `start-env` 一类的 skill 或脚本）并调用它；环境配置在主工作区执行，不在 worktree 内；禁止修改配置文件或连接远程库。 |
| N21 | `attempt.review.comparison-head-unfixed` | prose | review 没有可信 immutable comparison head | `/impl-package:do-review` 以固定 head 重开 |
| F4 | `ticket.accept.release-edge-unchecked` | prose | acceptance 条件满足、真实存在 release 边，但 release 边未复核 | Gate 前复核 release 边 |
| F5 | `attempt.gate.durable-delta-missing` | cli | terminal Gate 前 Stage 7 未完成 | 记 Durable Delta 与 truth pointer，或 `--no-durable-delta-reason` |
| F6a 判 | `attempt.gate.missing` | prose | 所有 Ticket 已 terminal，但 Gate 尚未写入 | 选择并写入 `pass` / `blocked` / `fail` / `defer` |
| **F6 判** | `attempt.gate.verdict-undecided` | prose | Gate 已写入但 Verdict 显式为 `undecided` | 选择 `pass` / `blocked` / `fail` / `defer` |
| F7 | `attempt.gate.comparison-mismatch` | cli | 准备判 pass 但当前 HEAD（将用作 comparison commit）与 acceptance revision 不匹配 | 先对齐 comparison commit 与 acceptance revision，再写 Gate |

## G. 交接与落账

| # | slug | basis | 处境 | 可选动作 |
| --- | --- | --- | --- | --- |
| G1 | `attempt.record.checkpoint-missing` | prose | 需要跨 session 交接或长任务收口 | 先写 active checkpoint，durable 写入先落盘再输出叙述 |
| G2 | `package.record.intake-backlog` | prose | 待落账队列积压 | drain |

## 统计

### 按阅读分组

| 分组 | 行数 | 判断行 |
| --- | --- | --- |
| A 入口与恢复 | 10 | 0 |
| B 选下一个单元 | 6 | 1 |
| C 单个 Ticket 推进 | 15 | 4 |
| D 返工与重开 | 5 | 3 |
| E Findings | 7 | 2 |
| F 验证与 Gate | 11 | 1 |
| G 交接与落账 | 2 | 0 |
| **合计** | **56** | **11** |

### 按环节与 basis

| 环节 | 行数 | cli | prose | 行号 |
| --- | --- | --- | --- | --- |
| `record` | 12 | 2 | 10 | A1 A2 A3 C8 G1 G2 N05 N06 N07 N08 N09 N10 |
| `readiness` | 5 | 1 | 4 | B1 B2 B4 Owner N20 |
| `investigate` | 2 | 0 | 2 | C1 C2 |
| `route` | 3 | 0 | 3 | C3 C4 C5 |
| `implement` | 3 | 0 | 3 | C10 C11 C12 |
| `fix` | 3 | 0 | 3 | E1 E3 N15 |
| `verify` | 4 | 1 | 3 | C9 C14 F1 N19 |
| `review` | 7 | 0 | 7 | C6 C7 E2 F3 N13 N18 N21 |
| `accept` | 5 | 2 | 3 | B3 C13 C15 F2 F4 |
| `rework` | 4 | 2 | 2 | D1 D2 D3 D4 |
| `disposition` | 3 | 1 | 2 | D5 E4 E5 |
| `gate` | 5 | 3 | 2 | A4 F5 F6a F6 F7 |
| **合计** | **56** | **12** | **44** | |

十二个取值都有行，无单行取值。分布最重的 `record` 12 行，最轻 2 行。

### basis 读数

**44 / 56 是赌的**（约 79%）。本轮新增的 Gate 缺失行是 `prose`，并把
`ticket.accept.release-edge-unchecked` 从 `cli` 更正为 `prose`；没有把回放证据升级为 `observed`。

```text
investigate  route  implement  fix  review       18 行，cli 强制 0 条
accept  gate  rework                             14 行，cli 强制 7 条
```

**关于"怎么工作"的五个环节，没有一条规则有强制；关于"记账是否正确"的三个环节，强制占了大半。** 这解释了流程被跳过的现象——不是规则缺失，而是全部强制预算都花在了记账正确性上，工作方法那一侧一条也没有。

处境表是第一个触及工作方法那一侧的机制。它不增加强制，但让这 18 行第一次有了读数。

## 对象与环节的组合

段 1 与段 2 不自由组合，允许矩阵由**对象有没有这种活动**决定：

| 对象 | 允许的环节 | 理由 |
| --- | --- | --- |
| `package` | `record` | package 是容器，本身不承担工作；只有记录层的事 |
| `attempt` | `record` `readiness` `verify` `review` `accept` `rework` `disposition` `gate` | Gate 与 findings 分流是 attempt 级；不做 investigate / route / implement / fix，那些作用在更细的对象上 |
| `ticket` | `record` `readiness` `investigate` `route` `implement` `verify` `review` `accept` `rework` `disposition` | 除 `gate`（attempt 级）与 `fix`（对象是 finding）外全部适用 |
| `finding` | `record` `fix` `review` `disposition` | finding 是被处置的项 |

23 个允许组合，当前用到 22 个。未列出的组合由校验拒绝，并提示"要用先显式修改矩阵"——与"段 2 新增取值属于重大变更"同一种姿态：可以做，但必须是有意的。

## 推导输入

| 输入 | 读什么 | 供给哪些行 |
| --- | --- | --- |
| `.impl-package/state.json` | attempt lifecycle、Ticket states、evidenceIndex 的 timing/conclusion/invalidatedBy/revision/environment、activeCheckpoints | A1 A3 A4 B1-B4 C8 C9 C13-C15 D1 D3 |
| `tickets/*.md` | AC claim id 与 required 集合、typed dependency、acceptance 的 revision 与 environment | B1 B2 C13 C15 D2 D5 F4 |
| git | HEAD；acceptance revision 与 HEAD 的关系；上次轨迹行以来 HEAD 是否推进 | D2 F7，以及全部交叉校验 |
| `execution/<attempt>/trail.jsonl` 尾部 | 按 subject 聚合：有无 investigate、上次 outcome、连续 INCOMPLETE 计数、悬空 decision | C1 C6 C8 C10 C11 C12 E3 |
| `gate.md` | 是否存在、verdict | A4 F6 F7 |
| `execution-findings.md` | 未闭合 finding 及其定级状态 | E4 E5 F3 |
| intake 队列 | 深度与最老一条的年龄 | G2 |

`progress.md` 不是输入，理由见 [README 第 8 节](README.md#8-与现有体系的关系)。

全部为本地文件读加两三次 git 调用，一次推导应在百毫秒级。

## 每轮投递样例

```text
处境层: P3（并列命中，由主控选择）
并列处境: ticket.rework.evidence-conflict (TKT-2) [invalidate/needs-revalidation/record-finding/retire]
判断点: 先选一个处境，再选其动作
secondary（较低层）1 个: attempt.disposition.findings-triage-pending (attempt)
待落账: 1 条（6 分钟）
```

约 120 token。对比入口一次性加载 4 至 6k 的散文，且到达率更高。
