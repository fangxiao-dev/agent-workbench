# Codex Harness Pilots 初始实施计划

创建时间（Created）：2026-07-16
执行尝试 ID（Attempt ID）：initial
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D1
规格修订（Spec Revision）：S1
计划修订（Plan Revision）：P1
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=false, dag=false
任务包 ID（Package ID）：260716-codex-harness-pilots
发布时绑定校验（Binding Validation at Publication）：Passed
决策：[decision.md](decision.md)
规格：[spec.md](spec.md)
门禁账本：[gate.md](gate.md)

> decision/spec 是当前 contract SoT。本 plan 只记录 initial attempt 的粗粒度执行策略、验证选择和过程证据。terminal gate verdict 后冻结。

## 摘要

以现有 App Server pilot 为起点，先闭合父 profile → parent thread/turn → Parent Result → external validator 的只读链路，再增加 false-PASS、边界、timeout/retry、resume/fork 与 soak fault matrix，最后接入真实 Impl-Package 和隔离写入。每层 readiness 只按 `spec.md` 对应 AC evidence 派生。

## 输入与权威来源

- 需求 / patch 来源：Owner 要求基于现有 Harness 设计创建粗粒度探索性任务包，重点固化 Spec 与 Gate。
- 已检查的当前 module knowledge：无；仓库没有适用于该新 Harness 模块的 `docs/module-knowledge/` 文件。
- 聚焦代码 / 测试事实：`scripts/run-codex-app-server-pilot.py`、`scripts/run-codex-subagent-pilot.ps1`、`.codex/harness/parent.toml`、`.codex/config.toml`、`skills/codex-harness/`。
- D/S gate 证据：[decision.md](decision.md) Decision Gate PASSED；[spec.md](spec.md) Spec Gate PASSED。
- 上一个 terminal gate entry（仅 patch）：N/A；initial attempt。
- Module Knowledge Watermark：None；本 attempt 未引用现有 module-knowledge 文件。

## 执行组合决策

- 是否 earned tickets：no。
- Tickets 理由：10 个 Pilot 是同一 Harness 的 acceptance matrix，不产生多个需要独立发布/验收的 delivery slice；验收状态由 spec AC、plan ER 和 gate entry 唯一维护。
- 是否 earned DAG：no。
- DAG 理由：当前是单 owner、粗粒度探索执行；阶段顺序可以由本 plan 约束，不需要多 owner/cohort 或独立 task runtime SoT。
- 执行状态来源：无 task artifact；跨 session、blocker 或大量证据出现时按需创建 `tasks/initial-progress.md`，本 plan 不保存 task checklist。
- 验收状态来源：`spec.md` AC-1..AC-10、append-only Execution Record 与 `gate.md` 最新 entry。

## Coverage And Change Map

| Spec coverage | 预计责任位置 | 集成点 |
| --- | --- | --- |
| AC-1..AC-4 父闭环、独立验收和边界 | App Server runner、父 profile loader、Parent Result schema/validator、fault fixtures | Parent Result 与 repository/runtime direct evidence 合并为 Harness verdict |
| AC-5..AC-6 timeout、cancel、retry | App Server lifecycle controller、attempt ledger | `turn/interrupt`、process fallback 与 immutable retry lineage |
| AC-7..AC-8 resume/fork、cleanup、soak | capability/version probe、role canary、session/process cleanup、resource observer | 恢复策略与 fresh-thread fallback |
| AC-9 Impl-Package | Harness work-package adapter、plan ER/gate writer | approved package input 与 Impl-Package evidence/gate contract |
| AC-10 隔离写入 | 临时 repo/worktree、path allowlist、diff/test validator | mutation result 与外部 gate，失败时丢弃隔离环境 |
| 文档/Skill 收敛 | `skills/codex-harness/` asset、workflow、必要脚本 | 只有 Pilot 证明的稳定规则才进入 Skill；terminal gate 捕获 durable delta |

## 执行策略

- 有序实施方式：第一阶段完成 AC-1..AC-4 的只读父闭环与 deterministic false-PASS/boundary matrix；第二阶段完成 AC-5..AC-8 的 lifecycle、恢复和 soak；第三阶段完成 AC-9..AC-10 的真实 work package 与隔离写入。
- 具体迁移 / 集成操作：把当前 pilot 中的 profile 映射、事件读取和 minimal parser 收敛为单一 Harness runner；引入版本化 Parent Result、validator/fault fixtures 和 attempt ledger；通过接口适配接入 Impl-Package，不把 package contract 复制进 runner。
- Rollout / rollback 操作：所有写入 Pilot 在临时 repo/worktree 执行；runner/Skill 变化在 gate 前保持 POC 标识。失败时保留 attempt evidence，回退 runner delta 或丢弃隔离 worktree，不修改旧 gate/ER。
- 依赖与前置条件：AC-1 是其余 live Pilot 的前置；AC-3/4 在扩大到 lifecycle/write 前通过；AC-5/6 在 AC-7/8 前形成可靠中断与重试基础；AC-1..8 在 AC-9/10 readiness claim 前通过。
- 目标分支：当前本地 `main`；默认不在 terminal gate 前集成到其他分支。
- 集成顺序：gate-before-merge。
- Gate 前集成的 owner 决策证据：N/A。

## 计划验证

| Policy / 场景来源 | 选定检查 | 预期结果 | 证据 owner |
| --- | --- | --- | --- |
| `spec.md` AC-1/2 | 三次 live parent run + 三类自主任务 verdict comparison | profile/result 闭环稳定，child 只为 telemetry | Harness runner owner |
| `spec.md` AC-3/4 evidence-integrity | malformed/identity/artifact/command/stale/NeedsOwner fixtures + read-only 越权 probe | false PASS=0，越权无副作用 | Validator/boundary owner |
| `spec.md` AC-5/6 | long-running interrupt、process fallback、retry classification/lineage | 中断有界、重试不覆盖旧 evidence 且不误重试 | Lifecycle owner |
| `spec.md` AC-7/8 | restart/resume/fork canary、20 轮 mixed soak | 配置漂移 fail closed，无持续 slot/process leak | Lifecycle/resource owner |
| `spec.md` AC-9 | 一个真实 approved Impl-Package 的 read-only execution/gate chain | work package、ER、gate 引用可解析且不依赖 child | Impl-Package owner |
| `spec.md` AC-10 | 隔离允许写入、越界 diff fixture、失败丢弃 | 合法改动/测试通过，越界拒绝，主工作树不污染 | Isolation/validator owner |
| Impl-Package review policy | implementation 后运行 code-review；涉及 interface/lifecycle/evidence authority 时运行 module-review 与 safety-review | findings 闭环后才进入 terminal completion audit | Review owner |

## 执行记录

<!-- 仅允许追加。旧 entry 不改；补证新增 ER-n。 -->

### ER-1

- 记录时间：2026-07-16T18:32:10Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：解析 `.impl-package/revision-bindings.json`；用 `git hash-object` 复核 D1/S1/P1 publication blobs；检查 Design/Spec gate header、10 个 AC、Composition 与 artifact 互链。
- 结果：Passed；D1/S1 exact-blob 与 P1 plan-contract-v1 baseline 均匹配，Design/Spec Gate 投影一致，AC 数量为 10，Composition 为 `tickets=false, dag=false`。
- 证据路径：`.impl-package/revision-bindings.json`、本 ER-1、`decision.md`、`spec.md`。
- 剩余风险 / 后续动作：该证据只证明任务包 publication/binding 可用；AC-1..AC-10 尚无 live Pilot evidence，不能声明 Harness POC、durable runner 或 development-ready。

### ER-2

- 记录时间：2026-07-16T20:20:00Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：连续执行 `python scripts/run-codex-app-server-pilot.py --scenario simple --timeout-seconds 180` 三次；执行 `run-codex-harness-autonomy-pilot.py`、`run-codex-harness-validator-pilot.py`、boundary scenario；执行 timeout aggregate、live retry 和 resume/fork pilots；执行 `run-codex-harness-impl-package-pilot.py` 对最新 Impl-Package parent summary；执行 isolation pilot；运行 `py_compile` 与 PowerShell `-ValidateOnly`。
- 结果：AC-1 通过（`214400`、`214441`、`214518`）；AC-2 通过（`20260716-214813-12019866-autonomy.summary.json`，simple/parallel/ambiguous verdict normalized 相同且 child telemetry 不参与 verdict）；AC-3 通过（`validator-fixture-run.summary.json`，false_pass_count=0）；AC-4 通过（`20260716-214911-e8a00c6a.app-server.summary.json`，sentinel 被只读边界拒绝，工作树未变化）；AC-5 取得 live timeout/interrupt + fresh-run 证据（`20260716-215042-db151cd8-aggregate.summary.json`），并通过 deterministic close/kill fallback fixture（`20260716-220926-lifecycle-fixtures.summary.json`）；AC-6 通过 live retry lineage（`20260716-215257-live-retry.summary.json`）与 append-only retry ledger（`20260716-221520-retry.summary.json`，interrupted → succeeded，确定性失败/NeedsOwner/边界拒绝/未知副作用均不重试）；AC-7 通过 canary/resume/fork/fresh fallback（`20260716-215335-resume.summary.json`）；AC-9 通过真实 parent package inspection 与 adapter（`20260716-215853-7d2436b2.app-server.summary.json`、同名 `.impl-package-adapter.json`）；AC-10 通过（`20260716-220353-isolation.summary.json`，canonical artifact path、含 untracked 的全文件快照 allowlist、主工作树无污染）。
- 证据路径：`.codex/harness-runs/` 中上述 summary/adapter artifacts；`scripts/run-codex-*.py`；`.codex/harness/parent.toml`；`.codex/config.toml`。
- 剩余风险 / 后续动作：AC-8 mixed 20-round soak 正在执行；AC-5 的 process-kill fallback 已有 deterministic fixture，但尚无 live failure path 触发证据；AC-6 live retry lineage 仍由 pilot wrapper 归纳，未成为统一 attempt-ledger runtime；AC-7 的 model/effort/history 是请求值与 canary 投影，需后续补充更强 runtime projection；AC-9 的 ER/gate write-back 仍待本次 gate 更新。故当前不能称 `durable runner verified` 或 `development-ready`。

### ER-3

- 记录时间：2026-07-16T22:27:00Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：完成 `python scripts/run-codex-harness-soak-pilot.py`（默认 20 轮 mixed cycle）；完成 package shape/AC/link checks、Impl-Package composition contract eval、Python `py_compile`、PowerShell `-ValidateOnly` 与 `git diff --check`。
- 结果：AC-8 通过，`20260716-222637-soak.summary.json` 显示 20/20 completed、simple/parallel/ambiguous 各 5 轮 passed、timeout 5 轮 interrupted、process_count_before=5、process_count_after=5；静态与运行时验证均通过。至此 10 个 AC 均有对应 direct/fixture evidence，但 readiness 仍按 gate 保守派生。
- 证据路径：`.codex/harness-runs/20260716-222637-soak.summary.json`、本 ER-3、`20260716-220926-lifecycle-fixtures.summary.json`、`20260716-221520-retry.summary.json`；验证命令输出留在本次执行记录上下文。
- 剩余风险 / 后续动作：仍需把 retry/timeout/cleanup 逻辑收敛为统一 runtime ledger/controller；补充 live process-kill failure path、真实 model/effort/history runtime projection、以及 adapter 原生 ER/gate write-back。当前 POC pilot matrix 已执行完，但不宣称 production/durable implementation closed。

## 执行尝试产物交接

- Ticket 集合：N/A；tickets=false。
- DAG：N/A；dag=false。
- 进度账本：N/A until cross-session/blocker trigger。
- 发现 inbox：N/A until a reusable investigation fact/risk needs capture。

## 计划修订历史

| 前一修订 | 新修订 | 策略 / Composition / 验证变化 | 原因 | 产物迁移 | 日期 |
| --- | --- | --- | --- | --- | --- |
| none | P1 | 初始粗粒度三阶段策略；tickets=false, dag=false；验证覆盖 AC-1..AC-10 | Owner 授权探索性轻量 package | 无 | 2026-07-16 |

### ER-4

- 记录时间：2026-07-16T22:45:00Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：`python scripts/run-codex-harness-impl-package-pilot.py --summary .codex/harness-runs/20260716-223934-1fdfaafa.app-server.summary.json --write-back`。
- 结果：Impl-Package adapter 已消费真实 Parent Result，核对 package documents、10 个 AC、binding sidecar、parent-only finding、当前 gate chain 与 worktree 状态，并将本次 adapter evidence 写回 plan/gate。
- 证据路径：`.codex/harness-runs/20260716-223934-1fdfaafa.impl-package-adapter.json`、`.codex/harness-runs/20260716-223934-1fdfaafa.app-server.summary.json`。
- 剩余风险 / 后续动作：adapter write-back 已闭合，但 AC-7 runtime profile projection 缺少 provider-observable model/effort，继续保持 fail-closed。

### ER-5

- 记录时间：2026-07-16T22:44:00Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：执行 `run-codex-harness-live-kill-pilot.py`、共享 `AttemptLedger` 驱动的 `run-codex-harness-live-retry-pilot.py` 与 synthetic retry pilot；执行带 strict runtime projection 的 `run-codex-harness-resume-pilot.py`。
- 结果：AC-5 live kill fallback 通过（`20260716-223243-live-kill.summary.json`，真实 App Server process kill 后 fresh run 通过）；AC-6 通过统一 runtime ledger（`20260716-223817-live-retry.summary.json` 及其 `.ledger.jsonl`，真实 interrupted→succeeded，旧 attempt 保留）；AC-7 canary/history/resume/fork/fresh 均通过，但 strict verdict 正确为 failed（`20260716-224238-resume.summary.json`），因为 thread/read 只暴露 `modelProvider=openai`，没有 provider-observable model/effort，故 Harness fail-closed。
- 证据路径：`.codex/harness-runs/20260716-223243-live-kill.summary.json`、`.codex/harness-runs/20260716-223817-live-retry.summary.json`、`.codex/harness-runs/20260716-223817-live-retry.ledger.jsonl`、`.codex/harness-runs/20260716-224238-resume.summary.json`。
- 剩余风险 / 后续动作：AC-7 需要 App Server/provider 暴露真实 model/effort 或新的受信任 projection seam；当前不能把请求参数或父自然语言声明当作 runtime 事实。其它 deferred gap 已收敛为 provider projection 与后续 production hardening。

### ER-6

- 记录时间：2026-07-16T22:54:00Z
- Design / Spec / Plan 修订：D1 / S1 / P1
- 检查或命令：执行 `python scripts/run-codex-harness-resume-pilot.py` 的 strict projection probe；随后复跑 package shape/AC/link checks、Impl-Package composition contract、Python `py_compile`、PowerShell `-ValidateOnly` 与 `git diff --check`。
- 结果：AC-7 通过，最新 artifact `20260716-225313-resume.summary.json` 为 `passed`。当前 `thread/read` 的 thread projection 只有 `modelProvider=openai`，但 `config/read(includeLayers=true)` 返回 effective `model=gpt-5.6-terra` 与 `model_reasoning_effort=high`；initial/resumed/fresh 三个 projection 均观察到相同 model/effort，history count 分别为 1/2/1，resume/fork/fresh canary 与故意失配拒绝均通过。该证据证明 POC 所需的有效父 profile 恢复，而不把请求参数或 Parent 自报提升为 authority。
- 证据路径：`.codex/harness-runs/20260716-225313-resume.summary.json`、本 ER-6、[Codex App Server README](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md) 中的 `config/read` effective-config 与 thread lifecycle 说明。
- 结果汇总：结合 ER-3 的 20/20 soak、ER-4 的 adapter write-back、ER-5 的 live kill/统一 retry ledger，以及 AC-10 隔离写入 artifact，AC-1..AC-10 全部有 direct live 或 deterministic fixture evidence；gate 可升级为 `current-G6 · passed`。跨版本兼容、长期驻留清理、MCP 白名单、token/time budget 和 provider-specific settings event 保留为后续 hardening，不阻塞本探索性 package。
