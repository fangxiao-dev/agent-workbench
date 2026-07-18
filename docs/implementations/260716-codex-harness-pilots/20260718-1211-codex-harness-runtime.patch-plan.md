# Codex Harness Runtime Policy 与 Impl-Package 3.2 Implementation Plan

创建时间（Created）：2026-07-18
执行尝试 ID（Attempt ID）：20260718-1211-codex-harness-runtime
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D2
规格修订（Spec Revision）：S2
计划修订（Plan Revision）：P1
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=false, dag=false
任务包 ID（Package ID）：260716-codex-harness-pilots
发布时绑定校验（Binding Validation at Publication）：working-tree passed; committed validation pending same-commit publication
决策：[decision.md](decision.md)
规格：[spec.md](spec.md)
门禁账本：[gate.md](gate.md)

> 本文件是当前唯一 active attempt plan，直接遵循 Impl-Package 3.2 schema；不读取或兼容旧 plan/gate 形状。

## 摘要

把已批准的 canonical runtime policy 设计收敛成可验证的 runtime seam，并修复 Harness 对 Impl-Package 3.2 当前 schema 的读取、生命周期和 binding 误判。父 agent 仍在边界内自主选择实现方式；本 attempt 只由主会话集成，不创建 tickets 或 DAG runtime state。

## 输入与权威来源

- 需求 / implementation 来源：Owner 于 2026-07-18 批准 runtime policy、跨任务 fresh context、single-writer continuation、resource ledger、decision routing、terminal disposition 与 Impl-Package 3.2 schema migration。
- 行为合同：[spec.md](spec.md) D2/S2；runtime policy JSON/Schema 只承载 canonical strategy values，lease/ledger/disposition event shape 由 Spec 第 2 节的 runtime-private contract 固化，不复制成第二份可配置 policy。
- package 权威：Impl-Package contract 3.2、`skills/impl-package/scripts/impl_package_state.py`、`.impl-package/revision-bindings.json`、`.impl-package/runtime-state.json` 与 `gate.md` resolver。
- 聚焦代码 / 测试事实：本 patch 已形成 policy loader、ThreadLease、ResourceLedger、decision routing、App Server/package runner lifecycle instrumentation 与 3.2 canonical adapter 的最小 seam；剩余差距是所有入口的 failure-path/continuation evidence 尚未闭合，不能直接升级 `runtime_enforced`。
- 当前 attempt 没有先前 terminal gate；所有 runtime policy 与 schema migration evidence 直接归属于 D2/S2/P1。

## 执行组合决策

- 是否 earned tickets：no。
- Tickets 理由：本 patch 的 policy、lifecycle 与 package adapter 是同一 exploratory Harness capability 的内部 area，不产生独立 delivery slice 或独立 acceptance status。
- 是否 earned DAG：no。
- DAG 理由：owner-approved coarse mode 继续由主会话集成；实施 area 共享 runtime contract，且不引入多个独立 execution-state owner。并行 worker 不是本 attempt 的 package SoT。
- 执行状态来源：无 task runtime record；Execution Record 与新 gate entry 是本 attempt 的过程/判决证据。
- 验收状态来源：`spec.md` AC-1..AC-16、append-only Execution Record、canonical CLI validation 与 `gate.md` 最新适用 entry。

## Coverage And Change Map

| Spec coverage | 预计责任位置 | 集成点 |
| --- | --- | --- |
| AC-11 policy load/version/maturity/fail-closed | `scripts/codex_harness_policy.py`、policy fixtures、App Server/package entrypoints | canonical JSON/Schema identity 与每次 run summary |
| AC-12 fresh context/single-writer continuation | `scripts/codex_harness_runtime.py` lease seam、App Server continuation guard、deterministic contention fixture | thread identity、owner token、heartbeat/expiry、fresh fallback |
| AC-13 resource ledger/reconciliation | `scripts/codex_harness_runtime.py` append-only JSONL、runner lifecycle instrumentation、tamper fixture | run/thread/turn/worktree/process/lease/disposition event chain |
| AC-14 bounded autonomy/decision routing | policy guard、Parent Result/Harness summary envelope、boundary fixtures | harness-resolvable vs owner-required request routing |
| AC-15 disposition/cleanup | runner finalization, lease release, orphan reconciliation fixtures | promote/retry/discard/needs_owner and cleanup evidence |
| AC-16 Impl-Package 3.2 compatibility | `scripts/codex_harness_package.py`、`scripts/codex_harness_prepare.py`、adapter pilot、package fixtures、canonical state CLI | optional decision/DAG, runtime-state/gate/frozen attempt, plan contract/ER append |
| Existing AC-1..AC-10 regression | existing pilots and validators | no regression of Parent Result, retry, isolation and prior POC evidence |

## 执行策略

- 先通过 canonical CLI 的 `register-revisions` 完成 D2/S2 与新 patch P1 的原子 revision registration，刷新 machine-owned projections，再以 working-tree validation 作为唯一当前 package preflight。
- Policy loader 消费 JSON Schema 的已实现子集并 fail closed；不把 policy values 复制进 Markdown，也不在 prompt 中提供隐式默认。
- Lease 与 resource ledger 只写 Harness-owned `.codex/harness-runs` 资源目录；不在 target worktree 设锁，不把 worktree isolation 宣称为物理冲突消除。
- App Server runner、package runner 与 resume/fixture entrypoint 在已接入处共享 canonical loader/guard；未覆盖的 failure-path、continuation 和 orphan recovery fixture 明确不纳入 `runtime_enforced` claim。
- Impl-Package adapter 为 source snapshot 创建短生命周期 detached Git worktree，在该 worktree 内调用 canonical state CLI `validate --committed` 与 `resolve-gate`，再读取当前 Composition、gate resolution 与 optional artifacts；不复制 sidecar schema，不直接写 gate/plan。
- Rollout / rollback：运行证据保留在 runner-owned artifact 目录；失败时保留 ledger/summary，停止当前 attempt，不自动提权、不自动清理未知外部资源；gate 与 ER 只按当前 schema 追加。
- `maturity` 初始保持 `design_baseline`；只有 AC-11..AC-16 的 direct evidence、独立 verifier、failure path 和 policy hash identity 全部闭合后，才允许由 owner-approved atomic artifact transition 升为 `runtime_enforced`。

## 计划验证

| Policy / 场景来源 | 选定检查 | 预期结果 | 证据 owner |
| --- | --- | --- | --- |
| Impl-Package 3.2 current contract | `contract-status`、`validate --working-tree`、`resolve-gate`；commit 后 `validate --committed` | current contract、D2/S2/patch P1 binding、runtime-state、projection 与 gate resolution 一致 | Main session / package adapter |
| AC-11 | policy schema normal/malformed/unknown enum/unknown maturity fixtures；policy loader pilot | canonical path/hash/version/maturity 记录；错误输入 fail closed | Policy seam |
| AC-12 | fresh-thread boundary、lease contention、expiry/heartbeat、wrong-token release fixture | 跨任务复用拒绝；同一 continuation 单写者；token mismatch 不释放 | Lifecycle seam |
| AC-13 | append-only JSONL chain、tamper/truncation、missing terminal、orphan reconciliation fixture | identity/hash/order 可复核；orphan candidate 可观察且不静默删除 | Resource ledger seam |
| AC-14 | no-child/different-topology comparator、policy blocked、owner-required route fixture | 父自主不改变 verdict；不自动提权；owner-required 不普通重试 | Decision routing seam |
| AC-15 | disposition replay、cleanup success/failure、unknown side-effect fixture | terminal disposition 互斥幂等；cleanup residual/orphan 可观察 | Lifecycle seam |
| AC-16 | no-DAG/optional-decision、missing runtime-state、optional gate/no-verdict、frozen attempt、plan ER append package fixtures | 合法 no-DAG 与无 gate package 可识别；missing runtime-state、gate mismatch/frozen attempt 与 schema drift fail closed；不复制 package schema | Impl-Package adapter |
| Existing AC-1..AC-10 | existing deterministic fixtures、relevant live pilots、`py_compile`、`git diff --check` | 既有 Parent Result、retry、isolation 与 gate evidence 不回归 | Main session |
| Review policy | task-independent code review、module-review、safety-review、verification-before-completion | findings 有明确 disposition；未验证项不得写 terminal pass | Main session / reviewers |

## 执行记录

<!-- 仅允许追加。本 plan 的 ER 从 ER-1 开始。 -->

### ER-1 · 2026-07-18 runtime seam 与 3.2 compatibility

- Design / Spec / Plan 修订：D2 / S2 / patch P1；Composition=`tickets=false, dag=false`。
- 执行发现：Impl-Package 3.2 的 runtime-state 是必需 current-contract 输入；decision/gate/DAG 都是按当前 sidecar、Composition 和 canonical config 派生的可选/条件 artifact，不能由 adapter 固定假设 `decision.md`、`dag.md`、`plan.md` 或 terminal gate。
- 实现范围：新增 canonical runtime policy loader/schema/identity；ThreadLease 的 fresh-context/single-writer guard；hash-chained ResourceLedger、terminal disposition、typed decision routing；App Server、package runner 和 resume pilot 在已接入入口记录 policy/lifecycle evidence；Impl-Package adapter/prepare 改用 skill-owned 3.2 config grammar，支持 lightweight Decision、optional gate/DAG、plan ER append、attempt-bound binding 与 frozen/history gate 解析。
- 验证命令与结果：`python -m pytest tests/test_impl_package_state.py -q` → `23 passed`；`python scripts/run-codex-harness-runtime-policy-pilot.py` → policy/lease/ledger/routing checks 全部 true；`python scripts/run-codex-harness-package-fixtures.py`、`run-codex-harness-prepare-fixtures.py`、`run-codex-harness-prepare-upgrade-fixture.py` → 全部预期通过/拒绝；`python scripts/run-codex-harness-package-live-smoke.py` → run `20260718-125600-smoke-8128353d` passed，Parent Result、external verifier、policy identity 与 terminal-last resource ledger 均有 evidence；`py_compile` 与 `git diff --check` 仍待本 ER 后最终复跑。
- Impl-Package 当前状态：`contract-status` 与 `validate --working-tree` 已通过 D2/S2/P1；`resolve-gate` 返回当前 attempt 尚无 gate，`gateResolution=null`。`validate --committed` 与 terminal gate 仍待同一发布提交后执行，不宣称当前 attempt 已 closed。
- 成熟度判定：canonical policy 继续保持 `design_baseline`；本 ER 只证明已接入的 runtime seams 和 compatibility fixtures，不满足 AC-11..AC-16 全部入口/失败路径闭合条件。

### ER-2 · 2026-07-18 final preflight

- 检查：`contract-status`、`validate --working-tree`、`resolve-gate`、runtime policy JSON Schema validation、全量相关脚本 `py_compile` 与 `git diff --check`。
- 结果：Impl-Package contract `3.2` current；D2/S2/P1 working-tree validation passed；gate resolver 返回当前 attempt 尚无 gate；policy schema passed；syntax/diff checks passed。
- 发布边界：当前工作树尚未把 D2/S2/patch P1 与 revision sidecar 提交到同一 HEAD，因此本 ER 不运行或宣称 `validate --committed`、新 terminal gate、`runtime_enforced` 或 task closed；提交后必须在 committed context 重跑 canonical validation，再由 owner/review gate 决定是否收口。

### ER-3 · 2026-07-18 App Server lifecycle regression

- 检查：`python scripts/run-codex-app-server-pilot.py --scenario simple --timeout-seconds 180`。
- 结果：run `20260718-130024-f08ed841` passed，Parent Result schema、read-only worktree、turn completion、policy identity 和 resource ledger 均通过；ledger 顺序为 `run/thread/turn → process closed → terminal_disposition`，terminal record 为最后事件，验证了 terminal freeze 与正常关闭顺序兼容。

### ER-4 · 2026-07-18 final schema and runtime preflight

- 检查：`contract-status`、`validate --working-tree`、`resolve-gate`、`python -m pytest tests/test_impl_package_state.py tests/test_impl_package_step8_evals.py -q`、package/prepare fixtures、runtime-policy pilot、相关脚本 `py_compile` 与 `git diff --check`。
- 结果：Impl-Package contract `3.2` current；D2/S2/patch P1 working-tree validation passed；state/eval regression `25 passed`；package runner 与 prepare fixtures passed；runtime-policy pilot 的 normal、maturity、lease contention/expiry、ledger tamper/replay、terminal-final、routing checks 全部 passed；policy JSON Schema、syntax 与 diff checks passed。
- Gate / publication boundary：当前工作树尚未形成同一提交，因此不宣称 `validate --committed`、terminal gate、`runtime_enforced` 或 task closed。提交后仍需在 committed context 重跑 canonical validation，再由 owner/review gate 决定是否收口。

### ER-5 · 2026-07-18 direct Impl-Package 3.2 migration

- 迁移：删除旧 `plan.md`，当前 attempt 唯一使用 `20260718-1211-codex-harness-runtime.patch-plan.md`；清空旧 gate allocation/entry；revision sidecar 只保留当前 D2/S2/P1 binding；不再保留旧 schema 或旧 gate 的消费路径。
- 验证：`contract-status` 返回 `3.2/current`；`validate --working-tree` 返回 D2/S2/P1 `ok=true`；`resolve-gate` 返回当前 attempt 尚无 gate；Impl-Package state/eval regression `25 passed`；package/prepare fixtures passed。
- 边界：这是当前 package state 的直接 schema migration，不是 backward-compatibility layer；未写入 terminal gate，`runtime_enforced` 与 task closed 仍需后续 committed validation 和 gate decision。

## 执行尝试产物交接

- Ticket 集合：N/A；tickets=false。
- DAG：N/A；dag=false。
- 进度账本：N/A；如发生跨 session/blocker，再按 contract 创建 attempt progress ledger。
- 执行发现：待有可复用的执行发现时创建 `execution-findings.md`，不把临时待办写入本 plan。

## 计划修订历史

| 前一修订 | 新修订 | 策略 / Composition / 验证变化 | 原因 | 产物迁移 | 日期 |
| --- | --- | --- | --- | --- | --- |
| none | P1 | runtime policy/lifecycle implementation、Impl-Package 3.2 schema migration、AC-11..AC-16；tickets=false, dag=false | Owner 批准的探索性 implementation | 直接以当前 D2/S2/P1 state 作为唯一 package state | 2026-07-18 |
