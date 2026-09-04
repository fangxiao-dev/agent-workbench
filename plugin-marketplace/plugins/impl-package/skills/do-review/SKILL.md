---
name: do-review
description: Orchestrate independent leaf reviewer agents for PR/code review, N-round review, loop/until-converged review, custom reviewer selection, and closure verification. Pins a committed comparison HEAD first and resolves the review strategy for every phase.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

`do-review` 是唯一 orchestrator：固定一个 immutable ReviewRun，解析 topology/capacity，派发独立 leaf，拥有 canonical ledger，验证并分类候选，控制收敛并 fail-closed 报告；main session 不是另一名 reviewer。

每个选中的 track 恰好派发一次对应的独立 leaf，映射见 [reviewer-registry.json](references/reviewer-registry.json)；leaf 定义拥有 skill 和 leaf brief，parent 传 common ReviewRun 与 phase addendum，派发经 native subagents。leaf 不得调用 `do-review`、再派 agent/subagent、重算 topology/capacity、查看同轮其它 track 输出、分类跨 track 结果或决定总 verdict；review skill 的 primary intent 不是排他能力边界，证据充分的跨域候选回 parent 归因分类。

带到达路径的 claim，reviewer 必须检查证据是否真的走过该路径：连上真实依赖并经过 composition root；只审单层文件不能替代路径证据。

## Gate 0（判断）

1. ReviewRun 创建前先提交完整 review unit 以固定比较 `HEAD`；review 相关未提交改动阻断，剩余 dirty 文件明确记为 out of scope。这样审查对象不会在派发后漂移，也不会把未纳入 review unit 的改动误当成证据。
2. 每个 selected track 恰好派发一次匹配的独立 leaf invocation。逐 track 固定派发，才能避免 required coverage 被重复派发或静默漏掉。
3. leaf 或其执行 worker 不可用/未授权时，在创建 ReviewRun 前停止并询问“停止，或授权精确命名的 degraded 单 session 列表”，绝不自行降级。否则缺失的独立证据会被误报为完整 review。
4. scope、phase、topology 固定前不预留 capacity。capacity 不能反过来决定应审哪些 track。

## 判断启发式（保留）

- **Safety admission**：diff 触及 auth/session/credential、authorization/permission/tenant isolation、data integrity/durable write/reconciliation/money/order/customer state、concurrency/transaction/idempotency/locking/retry、schema migration/backfill/rollback 或 payment/webhook/job/remote storage/third-party mutation 等 external side effect 时适用；关键词只是线索，必须记录匹配边界与 diff/contract 事实。Safety 适用却未列入显式 `terminal-final` → coverage `INCOMPLETE`，不能支持 terminal PASS。
- **Track B admission**：diff 引入/挪动 module boundary、新增 public interface/abstraction 或跨文件重构 module/目录结构时，`initial` 追加 `review-code-by-standards`；`terminal-final` 恒定包含 Track B（来自 `terminal_tracks`），不受此判断影响，Ticket 级 `initial` 省略它不构成 package 级 gap。
- **Aggregate fail-closed**：无 required track → `INCOMPLETE`；任一 required `FAIL` → Overall `FAIL`；否则任一 required `UNCERTAIN` → Overall `UNCERTAIN`；否则任一 required track 不是 `PASS`（含缺 verdict）→ `INCOMPLETE`；只有每个 required track 都 PASS 才 PASS。terminal Safety 遗漏沿用 Safety admission 规则。
- **Finding acceptance/dedup/classification**：leaf 输出先是 candidate evidence，parent 写入唯一 canonical ledger 后才采信；按 broken invariant/observable failure 去重，不按 path/reviewer。blocker 是业务数据、money、inventory、order、customer state、安全或 runtime-visible product data 风险；follow-up 真实但不阻断；backlog 是非紧急清理。证据不足只能 disputed/downgraded/out-of-scope/`UNCERTAIN`，不能变成 verified blocker。
- **Track C source recheck**：finding 被接受并归类为 Spec fidelity 后，移交 implementation 前做一次 fresh independent reviewer source recheck，范围限 accepted finding、fixed-head 的 immutable Decision/Spec/`contract-design.md`（若有）和直接引用的 Ticket/cross-module authority；结果只记录一次，不能再派第二次。记录为 sources uniquely decide、require contract revision 或 leave an owner decision；source recheck 不可用或 incomplete 阻断 handoff，不能跳过；未触及的 legacy package 缺 `contract-design.md` 本身不是 gap。
- **Loop clean & convergence**：只有 parent 在完成 evidence verification、dedup、classification 且没有新 accepted blocker/follow-up 后才能判 track clean；连续两轮 clean 才 dormant，新 finding 让 track 回 active；convergence 是最新一轮无新 accepted 且所有 selected track dormant。
- **Closure ≠ terminal**：`finding-closure` 只核对命名 findings，不能替代 `terminal-final`；`terminal-final` 必须固定最终 implementation `HEAD`，按终审 admission 规则处理候选轨。沿用已 PASS 的轨不等于用 closure 顶替终审：closure 只核对点名 findings；沿用 PASS 的依据是该轨输入未变、结论继续成立。两者依据不同，不可互相替代。

## 1. Create One Immutable ReviewRun

1. 确定完整 change unit 与可靠 base/head refs；审查 supplied PR/package/branch range 的全部可达 package commits，不只看 `HEAD^`。完整 change unit 是后续 coverage 的边界，避免只凭最近一个父提交漏掉可达变更。
2. 按 tracker references → user paths → matching `docs/`、`specs/`、`.scratch/` → Impl-Package Decision/Spec/Plan/DAG 的顺序发现 Spec evidence，并记录搜索及空结果；无可用 evidence 时合理则询问，继续时记录 gap 且保留默认 Track C。记录空结果是为了让缺失合同成为可见 gap，而不是被静默当成没有约束。

3. 用 `scripts/review_ledger.py create` 原子创建 ledger 与 fixed scope，并为每个 path contract 重复 `--source`；CLI 负责解析 commits、拒绝空三点 diff、在写入前读取 resolved head 的 UTF-8 Git blob。把返回的 `ledger_path`、resolved SHAs、`diff_range` 和每个 `contract_sources` 的 path/object ID/SHA-256 当作 canonical ReviewRun；失败停在 reviewer selection 前，名称冲突用新 timestamp 重试。原子创建和 fixed scope 让后续 leaf 共享同一个不可变审查对象。

4. Contract source 是 immutable revision evidence：reviewer 只能用 `git show <resolved-head>:<path>` 读取，不能从 working tree 读，也不能做第二次 hash/capture；tracker-only 内容留在 discovery record，不伪造 repository path。这样 reviewer 不会把可移动工作树或重复 capture 当成同一份合同证据。
5. 按 [subagent-briefs.md](references/subagent-briefs.md) 准备 common context：target、mode/round/cap、phase、resolved SHAs/range、included commits、constraints、standards、contract sources、Spec discovery/gap、Safety decision、user policy、prior canonical ledger、assigned track/name/path；每个 leaf 收同一个 ReviewRun，Impl-Package target 的 lifecycle/Gate 仍由 `/impl-package:dev-with-track` 拥有。共同上下文保证各 track 在同一比较点上工作，而不让 leaf 重新裁决 lifecycle/Gate。

## 2. Resolve Mode, Phase, Topology And Capacity

1. 选择 `N rounds`（默认一轮）、`Loop`（默认上限十轮）或只针对命名 findings 的 `Closure verification`，再读 [review-topology.md](references/review-topology.md) 处理 Safety admission、`initial`/`finding-closure`/`terminal-final`、final-HEAD 和 Loop lifecycle。先确定 phase 和 lifecycle，避免把 closure 当成 terminal 或把 Loop 的规则临时改写。
2. 无显式 reviewer 时，`initial` 从 registry `default_tracks`（Track A/C）起步，按 Track B admission、Safety admission 条件分别追加 `review-code-by-standards`、`safety-review`；`terminal-final` 无显式 reviewer 时始终从 registry `terminal_tracks`（Track A/B/C）起步——不受本次 ReviewRun 中 `initial` 或任何更早阶段实际选中子集的影响——按 Safety admission 条件追加 Safety；`finding-closure` 只用一个 independent `reviewer`，不按 registry 拆 track，也不另起 Safety leaf，reviewer 只检查 named findings 内的 safety implications；复用遵循 `/impl-package:subagent-driven-development` 的同 Topic review lane lifecycle。显式 closure selection 仍必须解析成恰好一个 leaf，其它 phase 按声明顺序运行并顺序编号 label。这样 closure scope 不会被扩成一次新的全量发现。
3. reviewer 的 worker 选择独立于 topology，由 worker skill 负责 model/effort defaults，其它 phase 使用当前 host 对 caller target class 的 defaults（受显式约束）。worker 选择不应反向改变 required topology。

4. 通过 [reviewer-registry.json](references/reviewer-registry.json) 与 matching leaf-agent map 解析 track，并在 dispatch 前用 `verify-reviewer-skills.py` 校验 canonical skill path；ambiguous、unreadable、escaping 或 frontmatter mismatch 一律拒绝。主 session 不加载 selected track skill，由 leaf agent 的 `skills` 字段加载；每个 selected leaf 预留一个 slot，能并发则并发，显式 reviewer selection 按声明的完整列表运行，capacity 不能删除 reviewer。路径校验失败或 capacity 不足时不能用近似 leaf 填空。

## 3. Dispatch Independent Rounds

1. 先读 [subagent-briefs.md](references/subagent-briefs.md)：common block 每轮使用，closure brief 只给 Closure verification，anti-duplicate addendum 只在 round 1 后使用。派发 matching leaf，不让 generic subagent 自己拼 track brief；传入 verified reviewer `SKILL.md` path、canonical ledger path 和 parent-owned report artifact path。brief 由 parent 固定，避免 generic worker 临场改变 track 合同。

2. Round 1 不传 prior findings；后续只传 parent 已验证的上一轮 canonical context，不传 raw reviewer output。按已解析 topology 与 matching leaf 执行本轮审查，逐项返回 PASS/FAIL/UNCERTAIN；canonical context 保持轮次之间的证据边界。
3. timeout、cancellation、`PARTIAL` 或缺 evidence 都是 incomplete，不是 PASS。等待所有 required active tracks；Loop 中已记录 dormant 的 track 不算 missing，其他 incomplete 会阻断，除非用户授权了该精确 degraded topology。否则“没有返回”会被错误收敛为通过。

## 4. Canonicalize The Round

1. 所有 leaf 返回后按 [output-templates.md](references/output-templates.md) 校验 ledger fields、evidence、dedup key、finding classification、convergence 和 atomic update；leaf 输出在 parent 写入唯一 canonical temp ledger 前只是 candidate，不建 per-round ledgers。先 canonicalize 再采信，才能防止 candidate evidence 绕过 parent 的验证与去重。
2. Impl-Package target 在 ledger 原子更新后，必须按 [output-templates.md](references/output-templates.md) 的 Canonical Finding Summary 调用 `python <plugin-root>/scripts/review_track_stats.py record --package <package>`，把本轮完整 accepted finding 集合写入 package trail 的 `review.canonical_summary` fact。`findingKey` 按 broken invariant/observable failure 稳定命名；多轨共同发现保留全部 `tracks`。记录失败使本轮 canonicalization `INCOMPLETE`，不得只留下 Markdown ledger 或从 reviewer prose 推导统计。
3. Track C 的 source recheck 属于当前 ReviewRun 的 post-classification check，不创建新 phase/lifecycle；其它 accepted finding 和 unaccepted candidate 不触发它。将 recheck 限在已接受的 Spec fidelity finding，避免重复派发或把未采信候选升级成 handoff 阻断。

4. Loop 在分类后应用 topology 的 clean/dormant/convergence 规则；`finding-closure` 不能冒充 `terminal-final`，terminal result 必须在最终 implementation `HEAD` 以完整适用 topology 复核。只有完成分类与最终 HEAD 复核，收敛或 terminal PASS 才有完整证据。

## 5. Report

1. 读 `output-templates.md` 并使用最小匹配报告：先给 review phase、Safety applicability/coverage、每个 selected track verdict、material findings、stop reason 和 next action；ledger path 默认内部。先报告 coverage 与 stop reason，读者才能区分没有 finding、没有证据和没有运行 required track。
2. 任何 required `FAIL` 都 fail，随后 required `UNCERTAIN` 为 uncertain，其余只有所有 required track PASS 才 pass；无 required track、required 缺 verdict 或适用 Safety 未列入显式 terminal-final 都不能报告 PASS。fail-closed 把缺失或不确定证据留在可见状态，不会被压成绿色结论。

## Guardrails

除明确要求外不修改 code、issue、Git state、data 或 external system；reviewer 不修改 Git。不得把 Closure 扩成无关问题搜寻，也不得隐藏 unavailable/incomplete topology；不得创建、请求或推断 owner approval。GO attempt 将 findings 返回 `/impl-package:dev-with-track`，直接调用停在 review checkpoint；只有 reviewer skill 定义变化时才调整 reviewer responsibility/topology。
