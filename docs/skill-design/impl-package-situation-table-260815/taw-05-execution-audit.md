# TAW-05 执行 session 三处偏离审计

> 审计对象：Grok session `01a016d1-7e92-7213-925a-f1a3ba897bb0`；审计边界截至 session 最后一个 tool event（UTC `2026-08-19T07:00:55.980Z`，summary 最后更新时间约 `07:12Z`）的目标 worktree HEAD `3e89f920b5f7b25cc8fbe271a600ee4ac995916d`。活动 trail 最后一条 seq 319 的事件时间约为 `2026-08-19T00:15:48Z`，之后 session 仍完成了 commit 操作，但没有再补写 TAW-05 trail。
>
> 目标 worktree 在 session 结束后又追加了 trail 行；本报告只用 `git show 3e89f920:<path>` 得到的 session 末态快照，不把后续追加的 terminal-final 行算入本 session。

## 结论先行

### Q1：do-review 全量审核

结论：不是单一 leaf 漏派，而是三层同时偏离：没有创建正式 ReviewRun/ledger，也没有完成 initial 的完整拓扑；所谓 terminal-final 实际只是 3 个 raw `spawn_subagent`，漏了 Track B/standards，且没有钉 immutable comparison point 或最终 HEAD。它们确实产生了 Code `FAIL`、Spec `not-satisfied`、Safety `PASS` 三份意见，但不能构成规定意义上的 terminal-final。

### Q2：fix 之后没有重跑

结论：terminal reviewer 返回 P0/P1 后确实做了代码、测试和集成修复，并把 integration 重新跑到 exit 0；但没有对 named findings 做 fresh finding-closure，也没有在最终 HEAD 上重跑完整 terminal-final，更没有执行 verification-before-completion。session 的“未钉最终 HEAD 重跑正式 terminal-final，也未 SATISFY/Gate，仍停在 Owner PASS”三点都准确，但低估了偏离：前一轮 3 个 generic reviewer 本身也不是正式 do-review terminal-final，且修复后的 evidence/claim 没有重新绑定到最终 revision。

### Q3：记账漏项

结论：目标快照中实际派发 13 个 subagent，但活动 trail 只有 9 条 dispatch，漏 4 条；13 个 subagent 都有返回文件，但 trail 只有 10 条 worker-return，漏 3 条；只有 1 条 escape，另有 5 个可从原始行为识别的偏离决策未记 escape；7 份 TAW-05 evidence 没有进入 evidenceIndex；没有本 session 的 TAW-05 Execution Record judgment。TAW-05 没有发生 state ticket transition，因此“state 转换无对应 trail”是 0，不应虚报为漏项。

## 审计规则基线

已安装插件来自 `C:\Users\Xiao\.claude\plugins\installed_plugins.json:33-40`：

- 插件：`impl-package@agent-workbench`
- 版本：`0.4.1`
- `gitCommitSha`：`7c8cee1c714053996472e1a0596b42a7eb706930`
- 安装目录：`C:\Users\Xiao\.claude\plugins\cache\agent-workbench\impl-package\0.4.1`

本次相关规则的 installed/dev 对照：

- `do-review/SKILL.md`、`do-review/references/review-topology.md`、`reviewer-registry.json`、`verification-before-completion/SKILL.md` 完全相同。
- 开发版 `dev-with-track/SKILL.md:37-39` 多出 Ticket 激活 `execution-preflight` 规则；installed 版没有。session 实际在 `45448454-fe00-4e75-8dac-97c5c16c4cad.json:chat_history[138]` 做过 READY preflight，因此这条差异不改变本审计结论。
- 开发版 `dev-with-track/situations.yaml:395-400` 多出 `git.accepted_seam_changed: true` 条件；installed 版没有。它不参与本次 Q1/Q2/Q3 的规则判定。
- installed 版 `dev-with-track/SKILL.md:33-34` 与开发版同位置文字不同，但不改变 review topology、comparison-head、trail、evidence 或 ER 的结论。以下判定以 installed 版为准。

## Q1 规定的 topology 与完整判据

规则位置均为 installed 插件：

- `skills/do-review/SKILL.md:13-24`：`do-review` 是唯一 orchestrator；每个 selected track 必须派给对应 leaf：Track A=`review-code`、Track B=`review-code-by-standards`、Track C=`review-code-by-spec`、条件 Safety=`safety-review`。
- `skills/do-review/SKILL.md:29-35`：`initial` 和 `terminal-final` 默认 A/B/C，Safety 按适用性追加；`finding-closure` 恰好一个 fresh independent reviewer，不能拆成全拓扑；每个 selected leaf 都必须有独立 invocation，不能静默降级。
- `skills/do-review/SKILL.md:37-51`：必须先以完整 change unit、可靠 base/head 创建一个 immutable ReviewRun；`review_ledger.py create` 输出的 resolved SHAs、diff range、contract sources 才是 canonical ReviewRun。
- `skills/do-review/SKILL.md:68-82`、`references/review-topology.md:22-32`：每一轮都要 fresh leaf；finding-closure 只关闭 named findings，不能替代 terminal-final；terminal-final 必须钉最终 implementation `HEAD`，并重新跑完整适用 topology。
- `skills/do-review/references/review-topology.md:7-20`：TAW-05 涉及 tenant isolation、durable writes、transactions/idempotency、schema migration、external side effects，Safety 明确适用；所以完整 initial/terminal-final 应为 A/B/C/Safety。
- `skills/do-review/SKILL.md:84-88`：任一 required `FAIL` 使总体 FAIL；适用 Safety 被省略时 coverage=`INCOMPLETE`，不能支持 terminal PASS。

因此，Q1 的完整判据是：有 immutable ReviewRun；phase 正确；initial/terminal-final 对 TAW-05 覆盖 A/B/C/Safety；每个 leaf 有独立 dispatch、回传和 parent ledger 记录；terminal-final 的 comparison point 是最终实现 HEAD。仅有几个 reviewer 文本或 PASS 标签不满足这个判据。

## Q1 实际派发的 review

以下时间均为 UTC；派发方式均为 raw `spawn_subagent`，不是 `/impl-package:do-review` 产生的 matching leaf dispatch。

| 时间 | 原始记录与方式 | target / comparison point | 结论 |
| --- | --- | --- | --- |
| `2026-08-18T22:14:18.842Z` | `events.jsonl` tool_started #113；`compaction_requests/45448454-fe00-4e75-8dac-97c5c16c4cad.json:chat_history[194]` 的 `spawn_subagent` | `TAW-05-slice-1-publication-seams`，checkpoint；明确写的是 dirty worktree vs `HEAD 1506f21b7e8ba3e95a04864de152fc6b162e584d`，不是 immutable ReviewRun | `subagents/01a016f0-8de5-76e0-989b-df90727b5431/output.json:1`：`PASS`；P0/P1 无，但列出 Prisma persist、actor 和 command-fact residual gaps |
| `2026-08-18T23:00:48.833Z` | `events.jsonl` tool_started #456；`chat_history.jsonl:224` 的 `spawn_subagent` | `TAW-05-persist-repo-unit`，checkpoint；prompt 只给 worktree、source unit、3 个路径和 AC，没有 base/head/comparison SHA | `subagents/01a0171b-2092-7e80-a030-ba5c5795cf9d/output.json:1`：`PASS`，无 P0/P1 |
| `2026-08-18T23:00:48.836Z` | `events.jsonl` tool_started #457；同一 `chat_history.jsonl:224` 的第二个 `spawn_subagent` | `TAW-05-persist-integration`，checkpoint；同样没有 immutable comparison point | `subagents/01a0171b-2092-7e80-a030-ba6d153b1e34/output.json:1`：`PASS`，无 P0/P1 |
| `2026-08-18T23:53:47.223Z` | `events.jsonl` tool_started #592；`chat_history.jsonl:489` 的 `spawn_subagent` | 标题为 terminal-final code；target 是未提交实现及 fixes；prompt 没有 base/head/comparison SHA | `subagents/01a0174b-a029-78c0-8475-b9d5fd817354/output.json:1`：`FAIL`，2 个 P0、1 个 P1 |
| `2026-08-18T23:53:47.226Z` | `events.jsonl` tool_started #593；`chat_history.jsonl:489` 的第二个 `spawn_subagent` | terminal-final spec；Ticket/AC/evidence；没有 comparison SHA | `subagents/01a0174b-a02a-7c31-8a83-5260c0bb6fbb/output.json:1`：`not-satisfied`；AC-04 真实 Postgres 证据不足，AC-06 保持 Owner HITL 未满足 |
| `2026-08-18T23:53:47.237Z` | `events.jsonl` tool_started #594；`chat_history.jsonl:489` 的第三个 `spawn_subagent` | terminal-final safety；migration、tenant、actor、idempotency、cleanup；没有 comparison SHA | `subagents/01a0174b-a02a-7c31-8a83-5278c300a253/output.json:1`：`PASS`，带 P1 residual risks |

全量历史中没有 `review_ledger.py create`、正式 `/impl-package:do-review` invocation，也没有 `review-track-standards`/`review-code-by-standards` 的 spawn；session 只在 `45448454-fe00-4e75-8dac-97c5c16c4cad.json:chat_history[183]` 和 `chat_history.jsonl:62` 读取过 do-review 文件。目标快照的 trail 也只记到两个 checkpoint review，见 `git show 3e89f920:.../execution/initial/trail.jsonl:13-14,28-31`，没有 terminal review dispatch。

## Q1 差距分类

| 编号 | 偏离 | 规则位置 | session 实际 | 分类 |
| --- | --- | --- | --- | --- |
| Q1-1 | 没有创建 immutable ReviewRun / canonical ledger | installed `do-review/SKILL.md:37-51`、`41-49` | 无 `review_ledger.py create`，而是直接 raw spawn | **D**：规则已写；ledger create、resolved SHA 和 leaf dispatch 都有明确命令载体；没有执行 |
| Q1-2 | 没有跑 initial 的完整 A/B/C/Safety topology | installed `do-review/SKILL.md:29`、`references/review-topology.md:22-28` | 只跑了 checkpoint；全历史没有 initial full review | **D**：规则已写在实际 review route，且有 spawn/ledger 载体；被跳过 |
| Q1-3 | terminal-final 漏 Track B/standards | installed `do-review/SKILL.md:15-22,29`、`reviewer-registry.json:2-28` | 23:53 只派 Code、Spec、Safety 三个 generic reviewer，没有 standards leaf | **D**：selected leaf、registry 和独立 spawn 都有载体；明确漏派 |
| Q1-4 | terminal-final 没钉 comparison point/最终 HEAD | installed `do-review/SKILL.md:39,47-51,82`、`review-topology.md:28-32` | 三个 terminal prompt 都只说 uncommitted implementation/fixes，无 base/head；且之后 HEAD 还从 dirty `1506f21` 变成 5 个 commit | **D**：规则已写且 reviewer prompt/ledger 本应携带 SHA；没有执行固定比较点 |

Q1 的四项都不是 A/B/C：installed 插件中有明确规范；动作发生在 `dev-with-track` 的 review 分流位置，且有 `review_ledger.py`、leaf spawn、comparison SHA 等载体。实际原因是执行时没有走规定的 orchestrator 和 topology，属于 D。

## Q2 规定与实际修复链

规则位置：

- `dev-with-track/situations.yaml:460-472`：reviewer 返回 finding 后，派 fresh fixer；修复后由同 scope reviewer 重审。
- `dev-with-track/situations.yaml:853-868`：closure review pending 时，默认以 `/impl-package:do-review scope=closure subject=<finding-id>` 关闭；直接 fix 后再 review 也必须有 reason。
- `dev-with-track/situations.yaml:573-584`、`do-review/SKILL.md:82`、`review-topology.md:28-32`：terminal coverage 不完整时补 terminal-final；必须在最终 implementation HEAD 上重新跑完整适用 topology，closure 不能替代 terminal-final。
- `verification-before-completion/SKILL.md:16-25`、`46-64`、`76-78`：在 implementation review/findings closure 后、写 terminal pass 前审计 current Attempt；evidence 必须与 claim 的 revision/environment 一致，stale、缺失或行为代码变化后的 evidence 不能支持 completion claim。
- 目标包自身的 `plan.md:42,50,172` 把顺序写得更具体：TAW-05 technical evidence → verification-before-completion + claim audit + independent terminal-final → `ready for final owner acceptance`；任何改变 implementation/evidence revision 的 fix 都使相关技术复审、claim audit 和最终验收失效并重做。

### Terminal findings 之后确实发生的 fix

terminal generic reviewer 的原始结论来自 `subagents/01a0174b-a029-78c0-8475-b9d5fd817354/output.json:1`、`01a0174b-a02a-7c31-8a83-5260c0bb6fbb/output.json:1`、`01a0174b-a02a-7c31-8a83-5278c300a253/output.json:1`：

1. Code P0：delegated Tx-A 首次发布/旧 Current 场景不能正确进入 `publication_verification_pending`；migration transition guard 错把 `verification_pending` 也要求为 current lineage。
2. Code P0：Tx-B `published_verified` 没清 `delegatedActiveScopeKey`，one-active candidate 不能关闭。
3. Code P1：live mapper 不发 `nextAction=abandon`。
4. Spec review 另指出 AC-04 的真实 Postgres 证据未覆盖完整 delegated dry-run/publish/resume；AC-06 必须继续保持 Owner HITL 未满足。

主 session 在 `events.jsonl` tool_started #614-617（`2026-08-19T00:02:15.641Z`–`00:02:15.649Z`，对应 `chat_history.jsonl:531`）修改了 migration guard、verified projection 清 key、tenant CAS allowlist 和 mapper；#625-627（`00:03:10.047Z`–`00:03:10.059Z`，对应 `chat_history.jsonl:551`）补了 tax-web abandon action；#632（`00:03:45.238Z`，对应 `chat_history.jsonl:565`）更新了对应 tenant expectation。

这些变化最终分布在 session 的 5 个 commit 中：

| commit | 与 finding/final state 的关系 |
| --- | --- |
| `8934a1ec` | DB migration、`publication_verification_pending` guard、verified projection 清 `delegatedActiveScopeKey`、tenant CAS allowlist |
| `6364ce51` | delegated publication/recovery API、mapper 与 generated contract/client |
| `78fe88ca` | tax-web publish/recovery/abandon UI |
| `84a2e19d` | integration/QA case、cleanup 与修复后的测试归档 |
| `3e89f920` | evidence、progress、state、trail 和 Owner readiness 文档；session 最终 HEAD |

commit 的原始记录在 `events.jsonl` tool_started #650-654、`chat_history.jsonl:616,619,622,625,628`；5 个 commit 的内容与统计也可由目标仓库 `git show --stat` 重现。

### Fix 后实际跑了什么

- #630（`2026-08-19T00:03:17.399Z`，`chat_history.jsonl:557`）：API mapper、DB tenant specs、tax-web spec 聚焦测试；初次 DB 批次有 1 个 expectation failure。
- #633（`00:03:45.243Z`，`chat_history.jsonl:565`）：修正 expectation 后，`datev-mandant-policy-import-tenant.spec.ts` 25/25 通过。
- #635（`00:03:53.748Z`，`chat_history.jsonl:569`）：第一次 fix 后 integration 退出 1，随后发现还需 tenant-scoped projection allowlist 调整。
- #639（`00:08:21.049Z`，`chat_history.jsonl:582`）：DB tenant specs 78/78 通过。
- #641/#643（`00:08:29.581Z` / `00:08:57.130Z`，`chat_history.jsonl:585,589`）：第二次 integration exit 0；输出明确为 clean lane、blockers 为空。

### Fix 后没有跑什么

- 没有任何新的 `spawn_subagent`，也没有新的 `review-track-code`、`review-track-standards`、`review-track-spec` 或 `review-track-safety`；原 terminal 三个 reviewer 的返回在修复前已经结束。
- 没有 `finding-closure` fresh reviewer；没有 formal `/impl-package:do-review`、ReviewRun 或 ledger。
- 没有调用 `/impl-package:verification-before-completion audit current Attempt`。相反，#644 在 `chat_history.jsonl:593` 仅把 todo `verification-before-completion + terminal-final → ready for Owner` 标为 completed，随后 #645 直接写了 checkpoint。
- 没有在 5 个 commit 尤其是最终 `3e89f920` 之后再做一次 revision-bound verification。原 evidence 文件仍写着 dirty `1506f21b7e8ba3e95a04864de152fc6b162e584d`，例如 `evidence/initial/taw-05-ac-01.md:5-8`；最终 commit 后没有刷新这些 claim 的 revision/environment。
- 没有 SATISFY 或 Gate。目标快照 `.impl-package/state.json:45-49,868-870` 显示 `TAW-05.state=PENDING`、`gate=null`、active checkpoint 仍是“Technical remaining-completion done；HITL Owner AC-06 only”；`progress.md:20,31` 同样显示 `PENDING | none`。

### 对 session 自己收尾记录的核实

`chat_history.jsonl:600` 明确承认“最后一版修过的代码没有再独立复审”；`:603` 明确承认没有完成“钉最终实现 HEAD 的正式 terminal-final”；`:631` 记录 5 个 commit 并说明 commit 前未重跑；`:640` 进一步承认把 integration 绿和 Owner HITL 混成了可停点。故原句不是高估，而是低估：它没有写出正式 ReviewRun/standards、finding-closure、verification-before-completion 和最终 revision-bound evidence 也都缺失。

## Q2 偏离分类

| 编号 | 偏离 | 规则位置 | session 实际 | 分类 |
| --- | --- | --- | --- | --- |
| Q2-1 | findings 修复后没有 fresh finding-closure / same-scope re-review | installed `situations.yaml:460-472,853-868` | 修复 #614-627 后只跑 tests/integration；没有 reviewer spawn | **D**：closure dispatch 和 fresh reviewer 都是明确载体，规则在执行处境表中，未执行 |
| Q2-2 | 没有在最终 HEAD 上重跑完整 terminal-final topology | installed `do-review/SKILL.md:82`、`review-topology.md:28-32` | 最后一轮 reviewer 在 23:53；修复后直到 HEAD `3e89f920` 没再派 reviewer | **D**：final-head comparison 与四类 leaf 都有明确载体，未执行 |
| Q2-3 | completion claim 前没有 verification-before-completion audit | installed `verification-before-completion/SKILL.md:16-25`、`situations.yaml:560-571` | todo 标 completed 后直接 checkpoint/Owner HITL，未调用 audit | **D**：命令、state/evidence 审计和阻断 claim 的载体均存在，未执行 |
| Q2-4 | fix 后的 claim evidence 没重新绑定最终 revision/environment | installed `verification-before-completion/SKILL.md:46-64`；包 `plan.md:50,172` | 7 份 evidence 仍标 dirty `1506f21`，最终实现已变为 5 个 commit；只重跑测试，没有刷新 claim evidence | **D**：same-revision evidence 规则和 evidence 文件/索引载体都存在，使用了 stale evidence |

## Q3 轨迹、状态与产物对账

### 1. dispatch：实际派了但没有 dispatch 行

目标 session 的完整历史由 compaction 前 `compaction_requests/45448454-fe00-4e75-8dac-97c5c16c4cad.json.chat_history` 与 compaction 后 `chat_history.jsonl` 拼接得到；其中显式 `spawn_subagent` 共 13 个，时间和 target 见 Q1 表及下表。session 末态的活动 trail 是 `git show 3e89f920:docs/domains/finance-assistant/implementations/2026-08-15-datev-tax-advisor-import-workbench/execution/initial/trail.jsonl`，共 34 行、9 条 dispatch（lines 10,13,16,20-23,28-29）。因此缺 4 条独立 dispatch：

- `2026-08-18T21:48:54.748Z` 的 `Inventory tax-web publish UI`，subagent `01a016f8-d87c-7633-a8a4-d3e8938b6c82`；它与 slice-1 implement 共用 trail seq 295（trail line 10），没有自己的 dispatch 行。原始 spawn 在 compaction 前 `chat_history[128]`，返回在 `subagents/01a016f8-d87c-7633-a8a4-d3e8938b6c82/output.json:1`。
- `2026-08-18T23:53:47.223Z` 的 terminal-final code，subagent `01a0174b-a029-78c0-8475-b9d5fd817354`；events tool_started #592，原始 spawn 在 `chat_history.jsonl:489`，trail 没有对应 id。
- `2026-08-18T23:53:47.226Z` 的 terminal-final spec，subagent `01a0174b-a02a-7c31-8a83-5260c0bb6fbb`；events #593，原始 spawn 在 `chat_history.jsonl:489`，trail 没有对应 id。
- `2026-08-18T23:53:47.237Z` 的 terminal-final safety，subagent `01a0174b-a02a-7c31-8a83-5278c300a253`；events #594，原始 spawn 在 `chat_history.jsonl:489`，trail 没有对应 id。

这不是把 `dispatch.returned=false` 误判为漏记：该 schema 允许 dispatch 行先写 `returned=false`，再以独立 worker-return 关闭；这里比较的是实际独立 spawn 数与 dispatch id 数，故只计以上 4 条。

### 2. worker-return：实际返回但没有 worker-return 行

13 个 subagent 的 `meta.json`/`output.json` 均存在，且 terminal 三个返回被主 session 在 events/tool #597-598（`chat_history.jsonl:499,503`）取回；但目标 trail 最后一条只到 seq 319，worker-return 只有 10 条（lines 11-12,14,17,24-27,30-31）。缺失的 3 条是：

- Code：`subagents/01a0174b-a029-78c0-8475-b9d5fd817354/output.json:1`，`verdict: FAIL`。
- Spec：`subagents/01a0174b-a02a-7c31-8a83-5260c0bb6fbb/output.json:1`，`verdict: not-satisfied`。
- Safety：`subagents/01a0174b-a02a-7c31-8a83-5278c300a253/output.json:1`，`verdict: PASS`。

这 3 个返回缺失尤其重要：若只读 trail，会误以为 terminal-final 从未产生任何结果；实际结果在 subagent/session 记录中存在，但没有进入 append-only execution trail。

### 3. escape：偏离建议但没有 escape 行

installed `dev-with-track/SKILL.md:71` 明确要求每次偏离 renderer 建议都写 `kind=escape`，带 `subject`、`deviation`、`reason`；`references/situation-inputs.md:458-484` 给出 `trail append` 载体和字段。目标 trail 只有 1 条 escape：line 8 / seq 293，记录 `implement-direct instead of dispatch-investigate`，这一处已记账。

结合完整 session history 和 trail，仍有以下 5 个可区分的偏离决策没有 escape：

1. slice-1 implement 返回后，`ticket.review.awaiting-reviewer` 的建议是走 `/impl-package:do-review scope=<checkpoint|closure>`（installed `situations.yaml:215-227`）；实际在 events #113 直接 raw `spawn_subagent` checkpoint reviewer，trail 只新增 seq 298（line 13），无 escape。
2. persist-repo-unit 返回后，实际在 events #456 raw `spawn_subagent`，trail 只新增 seq 313（line 28），无 escape。
3. persist-integration 返回后，实际在 events #457 raw `spawn_subagent`，trail 只新增 seq 314（line 29），无 escape。
4. terminal coverage/正式 closure route：实际在 events #592-594 直接并行派 3 个 generic reviewer，没有 `/impl-package:do-review` 和 Track B，trail 没有任何 terminal dispatch 或 escape；这里把三次并行 spawn 作为一个 route decision 计 1 处。
5. terminal code/spec 返回 findings 并完成 fixes 后，主 session 没有按 `finding.fix.reviewer-returned`/`finding.review.closure-awaiting`/`attempt.review.terminal-coverage-incomplete`（installed `situations.yaml:460-472,573-584,853-868`）再次 closure/terminal-final，直接写 seq 319 checkpoint并交 Owner；没有 escape。

所以 escape 不是“完全没有载体”：有明确 schema 和已有 seq 293 示例；是对后续 5 个偏离没有执行已有载体。

### 4. evidence：有产物但没有进 evidenceIndex

目标 commit `3e89f920` 中新产生的 TAW-05 evidence 文件共 7 份：

- `evidence/initial/taw-05-ac-01.md`
- `evidence/initial/taw-05-ac-02.md`
- `evidence/initial/taw-05-ac-03.md`
- `evidence/initial/taw-05-ac-04.md`
- `evidence/initial/taw-05-ac-05.md`
- `evidence/initial/taw-05-ac-07.md`
- `evidence/initial/taw-05-owner-acceptance-readiness.md`

每份都有 Ticket/Claim/Revision/Environment 或 Owner readiness 内容；例如 AC-01 在 `taw-05-ac-01.md:3-8` 明确写了 claim、dirty revision、environment、command、result。可是目标 `.impl-package/state.json:49-51` 的 `evidenceIndex` 只有 `TAW-01`、`TAW-02`、`TAW-03`、`TAW-04`，没有 `TAW-05`；`state.json:868-872` 的 `ticket:TAW-05` active checkpoint `evidence=[]`；`progress.md:20,31` 为 `TAW-05 | PENDING | none`。

规则载体是 installed `dev-with-track/situations.yaml:242-254`（`ticket.record.evidence-unfiled` → `impl_package_state.py ... evidence add`）及 `references/situation-inputs.md:339,356-365,460-484`（嵌套 evidenceIndex 与 direct-evidence tuple）。因此这 7 份产物未登记是 7 个可数的 evidence bookkeeping omission，不是规则不存在。

另有一个相邻事实：target trail 的 worker-return 行 296-297、299、302、309-316 没有规范的 `artifact/claim/revision/environment` direct-evidence payload；行 296 只有 prose evidence，其他 implement/review return 主要只有 outcome。故 renderer 不能凭这些行自动建立完整 indexed tuple；这解释了为什么 state 没有自动补齐，但不消除主 session 已生成 7 个文件却未执行 `evidence add` 的漏项。

### 5. Execution Record：有判断/收尾但没有本 session 的 ER judgment

installed `dev-with-track/SKILL.md:54-67` 规定主 session 通过 `recovery judgment` 写长期判断，checkpoint 只写下一动作；`situations.yaml:520-544` 也把 findings triage 分流到 Execution Record 作为明确载体。目标 `execution/initial/execution-record.md` 只有 `initial-ER-001` 至 `initial-ER-034`（最后一个标题在 line 659，文件止于 line 674），没有本次 TAW-05 remaining-completion、terminal finding、fix closure 或 Owner readiness 的新 ER judgment。文件中出现的 TAW-05 字样（如 lines 59、128、292）是既有历史判断中的状态描述，不是本 session 的 TAW-05 judgment。

因此这里计 1 个 package-level ER 漏项；不是把 6 个 checkpoint 逐条误算成 6 个 ER 漏项，因为 checkpoint 本身已有 trail lines 9,15,18,32-34，且规则没有要求每个 checkpoint另写 ER。

### 6. state transition 对账：0 个不匹配

目标 state 中 `TAW-05` 仍为 `PENDING`，没有 `SATISFY`/`Gate`/`ticket-state` transition；trail 也没有伪造一个完成 transition。已有 TAW-01..04 的历史 transition 属于此前轨迹/历史状态，不是本 session 新转换。故该项结果为：state transition 缺失且无对应 trail = **0**。

## Q3 偏离分类

| 编号 | 偏离 | 规则位置 | session 证据 | 分类 |
| --- | --- | --- | --- | --- |
| Q3-1 | 4 个实际 spawn 没有独立 dispatch 行 | installed `dev-with-track/SKILL.md:71`、`references/situation-inputs.md:460-483` | inventory subagent 被合并进 seq 295；terminal code/spec/safety 无 dispatch | **D**：trail append 是明确 carrier，实际派发后未追加 |
| Q3-2 | 3 个 subagent 返回没有 worker-return 行 | 同上 | 3 个 terminal `output.json`/取回记录存在，trail 无 return | **D**：worker-return carrier 已被前 10 次使用，3 次漏写 |
| Q3-3 | 5 个偏离建议没有 escape | installed `dev-with-track/SKILL.md:71`、`situations.yaml:215-227,460-472,573-584,853-868` | 只有 seq 293；后续 review route、terminal route、post-fix stop 均无 escape | **D**：escape schema、CLI 和已有示例都在位，未执行 |
| Q3-4 | 7 份 TAW-05 evidence 没进入 evidenceIndex | installed `situations.yaml:242-254`、`references/situation-inputs.md:339,356-365` | 7 个文件存在；state 无 TAW-05 evidenceIndex，checkpoint evidence=[] | **D**：`evidence add` 与嵌套 index 是现成载体，未执行 |
| Q3-5 | 1 个 TAW-05 package-level ER judgment 缺失 | installed `dev-with-track/SKILL.md:54-67`、`situations.yaml:520-544` | `execution-record.md` 无本 session 的 TAW-05 ER，仅有旧 ER-001..034 | **D**：`recovery judgment` 有明确入口，未执行 |
| Q3-6 | state transition 没有对应 trail | state/trail contract：installed `references/situation-inputs.md:178-180` | TAW-05 没有 transition；没有错误 transition | **不构成偏离，数量 0** |

Q3 的 5 类实际漏项均为 D。没有 A：规则存在；没有 B：这些规则分别在 `situations.yaml`、dev-with-track 执行段或 state/trail schema 的实际动作位置；没有 C：每类都有真实 CLI/file carrier，且前序同类行已证明 carrier 会产出记录。

## A/B/C/D 分类总表

计数口径：按独立的“规则偏离项”计数；同一时刻同时违反 review contract 和 trail bookkeeping contract 时，分别计为两条规则偏离。Q3 的 dispatch/return/escape/evidence 数量是原始实例数，列在表内，不替代规则项计数。

| 分类 | 数量 | 规则偏离项 |
| --- | ---: | --- |
| A：规则没写 | **0** | Q1/Q2/Q3 所涉规则在 installed plugin 中均有原文。 |
| B：写了但不在执行位置 | **0** | review topology、finding closure、verification、trail、evidence add、ER judgment 都有实际执行入口或处境表动作；不是只存在于不可达 reference。 |
| C：写了且在位但没有载体 | **0** | ReviewRun/leaf spawn/comparison SHA、trail append、escape、evidence add、recovery judgment 均有明确 carrier，且 session 已成功使用过其中一部分。 |
| D：规则到位且有载体但未执行 | **13** | Q1-1～Q1-4（4）；Q2-1～Q2-4（4）；Q3-1～Q3-5（5）。 |

D 类的原始实例明细为：4 个 dispatch 漏行、3 个 worker-return 漏行、5 个 escape 漏行、7 个 evidenceIndex 漏项、1 个 TAW-05 ER judgment 漏项；state transition 不匹配为 0。合计 20 个 Q3 记账实例，另有 Q1/Q2 的 8 个流程规则偏离实例；这些是审计证据数量，不改变上表 13 个规则偏离项的分类计数。

## 证据附录

### A. 文件与版本边界

- Installed plugin manifest：`C:\Users\Xiao\.claude\plugins\installed_plugins.json:33-40`。
- Installed plugin rules：`C:\Users\Xiao\.claude\plugins\cache\agent-workbench\impl-package\0.4.1\skills\do-review\SKILL.md`、`references/review-topology.md`、`references/reviewer-registry.json`、`skills/dev-with-track\SKILL.md`、`skills/dev-with-track\situations.yaml`、`skills/verification-before-completion\SKILL.md`。
- Development rules：`D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\` 对应文件。相关差异只有本文“审计规则基线”列出的 preflight 和 `accepted_seam_changed`，以及 installed/dev-with-track 入口段文字差异；核心 review/verification 规则相同。

### B. Session 全量解析方法

- `summary.json`：session 元数据、11 turns、654 tool calls、13 subagents、5 commits、约 9.46 小时。
- `signals.json`：统计交叉核对。
- 历史按用户指定方式拼接：compaction 前 `compaction_requests\45448454-fe00-4e75-8dac-97c5c16c4cad.json` 的 `chat_history` 554 条，加上 `chat_history.jsonl` 640 条；二次解析 assistant `tool_calls[].arguments` 后得到 13 个 `spawn_subagent`，与 `events.jsonl` 的 654 个 `tool_started` 对齐。
- `events.jsonl` 只用于时间和 tool ordinal；参数、target、结论来自对应 `chat_history`、`subagents/*/meta.json` 和 `output.json`。

### C. 目标末态与后续追加记录的隔离

- 审计使用 `git show 3e89f920:<package-relative-path>` 的目标末态：活动 trail 34 行，最后 seq 319；state 中 TAW-05 仍 PENDING，Gate 为 null。
- 当前 worktree 中后来追加的 seq 320 以后记录（包括 `2026-08-19T07:45Z` 左右的 terminal-final Track A/B/C/D dispatch）发生在目标 session 结束后，未纳入本报告。
- 该隔离避免后续记录掩盖目标 session 的 4 个 dispatch、3 个 return 和 final review 缺口。

### D. 关键原始证据索引

| 事实 | 原始证据 |
| --- | --- |
| 只有 1 条 escape | target `execution/initial/trail.jsonl:8`，seq 293 |
| 目标 trail 的 9 dispatch / 10 worker-return / 6 checkpoint | target `execution/initial/trail.jsonl:10-34` |
| TAW-05 仍 PENDING、无 Gate | target `.impl-package/state.json:45-49,868-872`；`progress.md:20,31` |
| state evidenceIndex 没有 TAW-05 | target `.impl-package/state.json:49-51`，解析后的 keys 只有 TAW-01..04 |
| 本 session 没有 TAW-05 ER judgment | target `execution/initial/execution-record.md:8-674`；当前 ER headings 只到 `initial-ER-034`（line 659） |
| terminal code/spec/safety 三份结论 | `subagents/01a0174b-a029-78c0-8475-b9d5fd817354/output.json:1`、`01a0174b-a02a-7c31-8a83-5260c0bb6fbb/output.json:1`、`01a0174b-a02a-7c31-8a83-5278c300a253/output.json:1` |
| fix 操作发生时间 | `events.jsonl` tool_started #614-617、#625-627、#632 |
| fix 后测试 | `chat_history.jsonl:557,565,569,582,585,589`；对应 events #630、#633、#635、#639、#641、#643 |
| 5 个 commit 与最终 HEAD | `chat_history.jsonl:616,619,622,625,628`；最终 `3e89f920` |
| session 自己承认未复审、未正式 terminal-final、commit 前未重跑 | `chat_history.jsonl:600,603,631,640` |

### E. 本报告自身的变更边界

本次审计只在 `D:\CodeSpace\agent-workbench` 新建并分阶段写入本报告；没有修改 `D:\CodeSpace\kaispan-dev`，没有修改任何代码、skill、插件包或 session 文件，也没有 commit。
