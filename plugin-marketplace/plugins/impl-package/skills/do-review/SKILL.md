---
name: do-review
description: Orchestrate independent leaf reviewer agents for PR/code review, N-round review, loop/until-converged review, custom reviewer selection, and closure verification. Pins a committed comparison HEAD first; must use a leaf subagent for every selected track. Uses Grok for finding closure and the selected leaf agents for review tracks.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

`do-review` 是唯一 orchestrator：固定一个 immutable ReviewRun，解析 topology/capacity，派发独立 leaf，拥有 canonical ledger，验证并分类候选，控制收敛并 fail-closed 报告；main session 不是另一名 reviewer。

每个选中的 track 都派发对应 leaf：Track A=`review-track-code`/`review-code`，Track B=`review-track-standards`/`review-code-by-standards`，Track C=`review-track-spec`/`review-code-by-spec`，Conditional Safety=`review-track-safety`/`safety-review`。leaf 定义拥有 skill 和 leaf brief；parent 传 common ReviewRun 与 phase addendum。leaf 不得调用 `do-review`、再派 agent/subagent、重算 topology/capacity、查看同轮其它 track 输出、分类跨 track 结果或决定总 verdict；review skill 的 primary intent 不是排他能力边界，证据充分的跨域候选回 parent 归因分类。

带到达路径的 claim，reviewer 必须检查证据是否真的走过该路径：连上真实依赖并经过 composition root；只审单层文件不能替代路径证据。

## Gate 0（判断）

ReviewRun 创建前先提交完整 review unit 以固定比较 `HEAD`；review 相关未提交改动阻断，剩余 dirty 文件明确记为 out of scope。每个 selected track 恰好派发一次匹配的独立 leaf invocation；leaf 或其执行 worker 不可用/未授权时，在创建 ReviewRun 前停止并询问“停止，或授权精确命名的 degraded 单 session 列表”，绝不自行降级。scope、phase、topology 固定前不预留 capacity。

## 判断启发式（保留）

- **Safety admission**：diff 触及 auth/session/credential、authorization/permission/tenant isolation、data integrity/durable write/reconciliation/money/order/customer state、concurrency/transaction/idempotency/locking/retry、schema migration/backfill/rollback 或 payment/webhook/job/remote storage/third-party mutation 等 external side effect 时适用；关键词只是线索，必须记录匹配边界与 diff/contract 事实。Safety 适用却未列入显式 `terminal-final` → coverage `INCOMPLETE`，不能支持 terminal PASS。
- **Aggregate fail-closed**：无 required track → `INCOMPLETE`；任一 required `FAIL` → Overall `FAIL`；否则任一 required `UNCERTAIN` → Overall `UNCERTAIN`；否则任一 required track 不是 `PASS`（含缺 verdict）→ `INCOMPLETE`；只有每个 required track 都 PASS 才 PASS。terminal Safety 遗漏沿用 Safety admission 规则。
- **Finding acceptance/dedup/classification**：leaf 输出先是 candidate evidence，parent 写入唯一 canonical ledger 后才采信；按 broken invariant/observable failure 去重，不按 path/reviewer。blocker 是业务数据、money、inventory、order、customer state、安全或 runtime-visible product data 风险；follow-up 真实但不阻断；backlog 是非紧急清理。证据不足只能 disputed/downgraded/out-of-scope/`UNCERTAIN`，不能变成 verified blocker。
- **Track C source recheck**：finding 被接受并归类为 Spec fidelity 后，移交 implementation 前做一次 fresh independent reviewer source recheck，范围限 accepted finding、fixed-head 的 immutable Decision/Spec/`contract-design.md`（若有）和直接引用的 Ticket/cross-module authority；结果只记录一次，不能再派第二次。记录为 sources uniquely decide、require contract revision 或 leave an owner decision；source recheck 不可用或 incomplete 阻断 handoff，不能跳过；未触及的 legacy package 缺 `contract-design.md` 本身不是 gap。
- **Loop clean & convergence**：只有 parent 在完成 evidence verification、dedup、classification 且没有新 accepted blocker/follow-up 后才能判 track clean；连续两轮 clean 才 dormant，新 finding 让 track 回 active；convergence 是最新一轮无新 accepted 且所有 selected track dormant。
- **Closure ≠ terminal**：`finding-closure` 只核对命名 findings，不能替代 `terminal-final`；terminal 必须在最终 implementation `HEAD` 上以完整适用 topology 运行 `terminal-final`。

## 1. Create One Immutable ReviewRun

确定完整 change unit 与可靠 base/head refs；审查 supplied PR/package/branch range 的全部可达 package commits，不只看 `HEAD^`。按 tracker references → user paths → matching `docs/`、`specs/`、`.scratch/` → Impl-Package Decision/Spec/Plan/DAG 的顺序发现 Spec evidence，并记录搜索及空结果；无可用 evidence 时合理则询问，继续时记录 gap 且保留默认 Track C。

用 `scripts/review_ledger.py create` 原子创建 ledger 与 fixed scope，并为每个 path contract 重复 `--source`；CLI 负责解析 commits、拒绝空三点 diff、在写入前读取 resolved head 的 UTF-8 Git blob。把返回的 `ledger_path`、resolved SHAs、`diff_range` 和每个 `contract_sources` 的 path/object ID/SHA-256 当作 canonical ReviewRun；失败停在 reviewer selection 前，名称冲突用新 timestamp 重试。

Contract source 是 immutable revision evidence：reviewer 只能用 `git show <resolved-head>:<path>` 读取，不能从 working tree 读，也不能做第二次 hash/capture；tracker-only 内容留在 discovery record，不伪造 repository path。按 [subagent-briefs.md](references/subagent-briefs.md) 准备 common context：target、mode/round/cap、phase、resolved SHAs/range、included commits、constraints、standards、contract sources、Spec discovery/gap、Safety decision、user policy、prior canonical ledger、assigned track/name/path；每个 leaf 收同一个 ReviewRun，Impl-Package target 的 lifecycle/Gate 仍由 `/impl-package:dev-with-track` 拥有。

## 2. Resolve Mode, Phase, Topology And Capacity

选择 `N rounds`（默认一轮）、`Loop`（默认上限十轮）或只针对命名 findings 的 `Closure verification`，再读 [review-topology.md](references/review-topology.md) 处理 Safety admission、`initial`/`finding-closure`/`terminal-final`、final-HEAD 和 Loop lifecycle。无显式 reviewer 时按 registry defaults 顺序选 Track A/B/C，`initial` 与 `terminal-final` 按 Safety admission 条件追加 Safety；`finding-closure` 只用一个 fresh independent `reviewer`，不按 registry 拆 track，也不另起 Safety leaf，reviewer 只检查 named findings 内的 safety implications；reviewer 的 worker 选择独立于 topology，由 worker skill 负责 model/effort defaults，其它 phase 使用当前 host 对 caller target class 的 defaults（受显式约束）。显式 closure selection 仍必须解析成恰好一个 leaf，其它 phase 按声明顺序运行并顺序编号 label。

通过 [reviewer-registry.json](references/reviewer-registry.json) 与 matching leaf-agent map 解析 track，并在 dispatch 前用 `verify-reviewer-skills.py` 校验 canonical skill path；ambiguous、unreadable、escaping 或 frontmatter mismatch 一律拒绝。主 session 不加载 selected track skill，由 leaf agent 的 `skills` 字段加载；每个 selected leaf 预留一个 slot，能并发则并发，显式 reviewer selection 按声明的完整列表运行，capacity 不能删除 reviewer。

## 3. Dispatch Independent Rounds

先读 [subagent-briefs.md](references/subagent-briefs.md)：common block 每轮使用，closure brief 只给 Closure verification，anti-duplicate addendum 只在 round 1 后使用。派发 matching leaf，不让 generic subagent 自己拼 track brief；传入 verified reviewer `SKILL.md` path、canonical ledger path 和 parent-owned report artifact path。

Round 1 不传 prior findings；后续只传 parent 已验证的上一轮 canonical context，不传 raw reviewer output。每轮 fresh leaf，只有同轮中断 leaf 才恢复；`finding-closure` 恰好一个 fresh reviewer leaf 在后台经 `$grok-worker --no-subagents` 执行，带 assigned skill 和完整 closure brief，逐项返回 PASS/FAIL/UNCERTAIN；Grok incomplete 后确认进程清理，再允许一次 fallback 到当前 default reviewer。timeout、cancellation、`PARTIAL` 或缺 evidence 都是 incomplete，不是 PASS。等待所有 required active tracks；Loop 中已记录 dormant 的 track 不算 missing，其他 incomplete 会阻断，除非用户授权了该精确 degraded topology。

## 4. Canonicalize The Round

所有 leaf 返回后按 [output-templates.md](references/output-templates.md) 校验 ledger fields、evidence、dedup key、finding classification、convergence 和 atomic update；leaf 输出在 parent 写入唯一 canonical temp ledger 前只是 candidate，不建 per-round ledgers。Track C 的 source recheck 属于当前 ReviewRun 的 post-classification check，不创建新 phase/lifecycle；其它 accepted finding 和 unaccepted candidate 不触发它。

Loop 在分类后应用 topology 的 clean/dormant/convergence 规则；`finding-closure` 不能冒充 `terminal-final`，terminal result 必须在最终 implementation `HEAD` 以完整适用 topology 复核。

## 5. Report

读 `output-templates.md` 并使用最小匹配报告：先给 review phase、Safety applicability/coverage、每个 selected track verdict、material findings、stop reason 和 next action；ledger path 默认内部。任何 required `FAIL` 都 fail，随后 required `UNCERTAIN` 为 uncertain，其余只有所有 required track PASS 才 pass；无 required track、required 缺 verdict 或适用 Safety 未列入显式 terminal-final 都不能报告 PASS。

## Guardrails

除明确要求外不修改 code、issue、Git state、data 或 external system；reviewer 不修改 Git。不得把 Closure 扩成无关问题搜寻，也不得隐藏 unavailable/incomplete topology；不得创建、请求或推断 owner approval。GO attempt 将 findings 返回 `/impl-package:dev-with-track`，直接调用停在 review checkpoint；只有 reviewer skill 定义变化时才调整 reviewer responsibility/topology。
