# Gate Ledger

状态：current-G6 passed；10 个 acceptance criteria 均已取得 direct live 或 deterministic fixture evidence；生产级兼容矩阵、细粒度预算和长期驻留清理仍属于后续 hardening。

## initial-G1 · blocked

- Attempt ID：initial
- Supersedes：none
- Evaluated at：2026-07-16T18:32:10Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
<!-- Machine audit metadata: sidecar=.impl-package/revision-bindings.json; D=47f4c96be556e3cf4a695c3136f8a66f0629f039; S=9388fb35dee644ae59892d10db7ea6ae97bf1137; P=be03d4f6eabb16f8a1ae93442c03690e055ecde3 -->
- Composition：tickets=false, dag=false
- Comparison point：Git HEAD `0013295c59c04411b29de1dd446fdccdfff837a3` 加 D1/S1/P1 package publication blobs；后续实现 evidence 必须固定新的工作树/commit comparison point。
- Evidence：[plan.md#er-1](plan.md#er-1)
- Unresolved blocker/deferred item：AC-1..AC-10 均尚未取得实现后 direct evidence；其中 AC-1..AC-6 阻塞 `read-only Harness POC verified`，AC-7..AC-8 阻塞 `durable Harness runner verified`，AC-9..AC-10 阻塞 `development-ready Harness verified`。
- Verdict reason：Design/Spec/Plan publication 已验证，说明 attempt 可以进入执行；但 artifact binding 不能替代 Harness live behavior、fault injection、boundary、lifecycle、Impl-Package integration 或 isolated-write evidence，因此当前只能记 blocked，不能写 pass/fail/defer 或宣称 package closed。

## current-G2 · blocked

- Attempt ID：initial
- Supersedes：initial-G1
- Evaluated at：2026-07-16T20:20:00Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
- Composition：tickets=false, dag=false
- Comparison point：当前工作树固定点；本次 live artifacts 记录 run/thread/turn、Codex version、父 profile hash 与 worktree 状态。
- Evidence：[plan.md#er-2](plan.md#er-2)、`.codex/harness-runs/20260716-214813-12019866-autonomy.summary.json`、`validator-fixture-run.summary.json`、`20260716-215042-db151cd8-aggregate.summary.json`、`20260716-220926-lifecycle-fixtures.summary.json`、`20260716-215257-live-retry.summary.json`、`20260716-215335-resume.summary.json`、`20260716-215853-7d2436b2.app-server.summary.json`、`20260716-215853-7d2436b2.impl-package-adapter.json`、`20260716-220353-isolation.summary.json`。
- AC evidence projection：AC-1/2/3/4/6/7/9/10 当前有 direct evidence；AC-5 的 interrupt/fresh 与 deterministic close/kill fallback 有 evidence，但 live failure path 尚未触发；AC-8 的 mixed 20-round soak 尚未完成。
- Review evidence：当前工作树已完成 Standards review（无 hard AGENTS/repository violation；py_compile、PowerShell ValidateOnly、diff checks 通过）；Spec review 的残余判断已纳入 deferred risks。
- Unresolved blocker/deferred item：AC-8 仍在执行；AC-5 kill fallback、AC-6 统一 retry ledger、AC-7 可观察 model/effort/history projection、AC-9 ER/gate write-back durability 仍未完全闭合。故 `read-only Harness POC verified` 的 AC-1..AC-6 readiness 仍受 AC-5 fallback 限制，`durable Harness runner verified` 与 `development-ready Harness verified` 均 blocked。
- Verdict reason：当前 evidence 证明父-only App Server 控制面、严格 Parent Result、独立 validator、boundary、live interrupt/retry、resume/fork、Impl-Package read-only adapter 与隔离写入链路可运行，但尚不足以宣称完整 lifecycle/harness durable readiness；保持 blocked 是 fail-closed 结论。

## current-G3 · blocked

- Attempt ID：initial
- Supersedes：current-G2
- Evaluated at：2026-07-16T22:27:00Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
- Composition：tickets=false, dag=false
- Comparison point：当前工作树；所有 live summary 均记录 run/thread/turn、Codex version、父 profile hash 与 normalized worktree status。
- Evidence：[plan.md#er-3](plan.md#er-3)、`.codex/harness-runs/20260716-222637-soak.summary.json` 以及 G2 引用的 AC-1..AC-7/AC-9/AC-10 artifacts。
- AC evidence projection：AC-1..AC-10 均已有 direct live 或 deterministic fixture evidence；AC-8 20/20 mixed rounds 通过，process count 5→5。当前不把 child telemetry、Parent 自报成功或自然语言信心当 acceptance 依据。
- Review evidence：Standards review 无 hard AGENTS/repository violation；Spec review 的残余判断已显式转为 deferred risk；composition contract、py_compile、PowerShell ValidateOnly、package shape checks 通过。
- Unresolved blocker/deferred item：统一 attempt-ledger/controller 尚未实现；live process-kill failure path、可观察 model/effort/history runtime projection、adapter 原生 ER/gate write-back 仍缺；因此仍不能升级为 `durable Harness runner verified` 或 `development-ready Harness verified`。
- Verdict reason：本次 Pilot 计划和 acceptance matrix 已执行完，证明当前父-only App Server Harness POC 可运行；但 gate 对 durable/production readiness 采取 fail-closed blocked，而不是把 POC evidence 误写成 implementation closure。

### Durable Deltas

None；这是 execution 前的 blocked entry，尚未产生经 Pilot 证明的长期实现知识。terminal verdict 前必须重新评估并按 Stage 7 注册任何真实 durable delta。

### Durable Deltas · current-G3

- `parent-only-acceptance-v0`：Harness 只绑定父 profile、父 thread/turn 与 Parent Result；child 数量、角色、模型、prompt、拓扑和 telemetry 不进入 acceptance verdict。
- `parent-result-validation-v0`：结构化 Parent Result 必须核对 schema/run_id/status/verification/artifacts，外部 validator、worktree/diff 与 boundary evidence 优先于 Parent 自报成功。
- `app-server-pilot-lifecycle-v0`：当前 Codex App Server `codex-cli 0.144.4` 可完成 persistent thread、resume、fork、turn interrupt 与 fresh fallback；profile 记录 `gpt-5.6-terra/high` 及 hash。
- `isolation-snapshot-v0`：隔离写入验收必须同时检查 Git diff 与排除 `.git` 的全文件快照，以捕获 untracked 越界 mutation；本次主工作树保持不变。
- 注册范围：以上仅是本次 POC 已证明的 durable facts，不等同于统一 retry/timeout runtime 已实现；后续实现必须保留本 gate 的 deferred gaps。

## current-G4 · blocked

- Attempt ID：initial
- Supersedes：current-G3
- Evaluated at：2026-07-16T22:45:00Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
- Evidence：plan.md#er-4 与本 adapter summary。
- Verdict reason：Impl-Package adapter 原生 ER/gate write-back 已通过；整体仍因 AC-7 provider-observable model/effort projection 缺失而 fail closed。

## current-G5 · blocked

- Attempt ID：initial
- Supersedes：current-G4
- Evaluated at：2026-07-16T22:44:00Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
- Composition：tickets=false, dag=false
- Evidence：[plan.md#er-5](plan.md#er-5)、`.codex/harness-runs/20260716-223243-live-kill.summary.json`、`.codex/harness-runs/20260716-223817-live-retry.summary.json`、`.codex/harness-runs/20260716-224238-resume.summary.json`。
- AC evidence projection：AC-5 的 live kill fallback 与 fresh recovery 通过；AC-6 的统一 append-only runtime ledger 与真实 retry 通过；AC-7 的 resume/fork/history/canary 通过，但 strict acceptance failed closed，因为 provider projection 只有 `modelProvider=openai`，没有 model/effort runtime fields。
- Review evidence：共享 runtime ledger、live kill pilot、strict projection probe 与 adapter write-back 均已通过静态检查；不把请求参数、Parent Result 或 child telemetry提升为 runtime authority。
- Unresolved blocker/deferred item：当前唯一影响本 POC gate 的行为性缺口是 AC-7 provider-observable model/effort projection；在没有可信外部 projection seam 前，resume/fork 不能宣称原 profile 已恢复。production hardening 仍另行保留。
- Verdict reason：本次 retry/kill/adapter seam 已实质闭合；AC-7 的严格失败是预期的 fail-closed 结果，不是测试脚本故障，因此 gate 继续 blocked。

## current-G6 · passed

- Attempt ID：initial
- Supersedes：current-G5
- Evaluated at：2026-07-16T22:54:00Z
- Revision set：D1 / S1 / P1
- Binding validation：passed
- Composition：tickets=false, dag=false
- Evidence：[plan.md#er-6](plan.md#er-6)、`.codex/harness-runs/20260716-225313-resume.summary.json`、`.codex/harness-runs/20260716-222637-soak.summary.json`、`.codex/harness-runs/20260716-223243-live-kill.summary.json`、`.codex/harness-runs/20260716-223817-live-retry.summary.json`、`.codex/harness-runs/20260716-223934-1fdfaafa.impl-package-adapter.json`、`.codex/harness-runs/20260716-220353-isolation.summary.json`。
- AC evidence projection：AC-1..AC-6、AC-8、AC-9、AC-10 复用已通过的 live/fixture evidence；AC-7 在最新 strict probe 中通过。`thread/read` 仍只暴露 `modelProvider`，但 `config/read(includeLayers=true)` 返回 effective `model` 与 `model_reasoning_effort`，且 initial/resumed/fresh 三个 projection 均与父 profile 一致，同时 canary、history continuity、resume/fork/fresh fallback 和故意失配拒绝均通过。因此本 POC 的“角色/配置/history 可证明”成立，证据 authority 是 App Server effective-config projection + lifecycle canary/history，而不是请求参数或 Parent 自报。
- Review evidence：package composition contract、Python `py_compile`、PowerShell `-ValidateOnly`、`git diff --check`、package shape/AC/link checks 均通过；live process kill 后 fresh recovery、统一 append-only retry ledger、Impl-Package ER/gate write-back 和隔离全文件快照 allowlist 均有独立 artifact。
- Verdict：`read-only Harness POC verified`、`durable Harness runner verified`、`development-ready Harness verified` 在本任务包范围内均通过；“development-ready”仅表示本 POC 的父-only、边界、恢复、重试、验证和隔离验收链闭合，不表示生产部署完成。
- Deferred hardening：跨 Codex 版本兼容矩阵、长期驻留 App Server 的 stale registry 清理、MCP 白名单、token/time budget、provider-specific settings event 以及更细粒度的成本/并发策略不阻塞本 gate，进入后续 implementation package。
