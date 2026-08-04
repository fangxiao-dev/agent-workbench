# Impl-Package Execution Record 与 Progress 模型优化提案

- 日期：2026-08-03
- 状态：owner 已批准，v1 implementation in progress
- 范围：`skills/impl-package/` 的 Ticket/Task runtime、ER、Progress projection、CLI、validation 与 eval
- 首版边界：只支持 fresh contract package；不迁移或兼容解析现有 package

## 1. 要解决的问题

当前体系把几种不同信息都称为或当作 “Progress”：

- Task/Ticket 当前状态；
- `plan.md` 中持续增长的 Execution Record（ER）；
- Ticket 的 `Phase / Next / Progress`；
- 条件化的 `tasks/Tn-progress.md`；
- gate、review 与 artifact evidence。

结果是 Ticket 逐渐从“可独立验收纵切”变成准 Task，Task progress 又并非真正的连续进度；同时没有一个清晰的 package 恢复入口。仅把 ER 从 `plan.md` 搬出去不能解决这些概念问题。

首版目标：

1. 明确 Ticket 状态在哪里记录并提供可读总览。
2. 将状态、历史、当前进度视图和局部交接分层。
3. 恢复 Ticket 的验收职责，恢复 Task 的执行职责。
4. 将 ER 从 plan 独立出来，但保持写入主路径足够简单。
5. 先运行数轮验证模型，再依据真实摩擦扩展。

## 2. 四层模型

| 层 | 回答的问题 | 唯一事实源或承载面 |
| --- | --- | --- |
| Current State | 现在处于什么状态？ | runtime state、revision registry、gate resolver |
| Execution History | 为什么走到这里？ | sealed ER ledger |
| Attempt Progress | 当前执行周期推进到哪里？ | machine-owned `progress.md` projection |
| Local Handoff | 某个 Task 交给别人时从哪里继续？ | 条件化 `tasks/Tn-handoff.md` |

`progress.md`、Ticket marker、DAG table 与 ER index 都是 projection 或 pointer surface，不得成为第二个可写状态源。

## 3. 领域边界

### 3.1 Attempt

Attempt 是 package 内的一次完整执行周期，不是 agent session 或命令 retry：

- 由 `impl-planning` 建立，绑定 current D/S/P 与 Composition；
- 可以跨 session、worker、commit 和多个 P revision；
- `blocked` gate 不终结 Attempt；
- `pass / fail / defer` 终结并冻结 Attempt；
- terminal 后的新工作进入新的 Attempt，例如 `initial`、`patch-a`。

### 3.2 Ticket

Ticket 是可独立验收的纵向交付切片。它只拥有 delivery boundary、AC、typed acceptance/release dependency、publication status、Runtime Acceptance Status 投影和 acceptance evidence pointer。

fresh contract Ticket 删除 `Phase / Next / Progress`，不创建 `ticket-progress.md`，也不承载 worker、Task、implementation phase 或 machine dispatch checkpoint。

Ticket runtime acceptance state 的唯一事实源是 `.impl-package/runtime-state.json`：

```text
PENDING
BLOCKED
NEEDS-REVALIDATION
SATISFIED
WAIVED
SUPERSEDED
```

Draft Ticket 不建立 runtime record；其文档 marker 使用非 runtime 的 `UNRECORDED` sentinel。Approved 发布时原子创建唯一 `PENDING` runtime record 并刷新 projection。删除 runtime `IN_PROGRESS`，避免用 Ticket 状态表达实施进度。

### 3.3 Task 与 Task Handoff

Task 是 `dag=true` 时存在的可分派执行单元；current state 继续由 runtime state 拥有，并投影到 DAG。

现有 `tasks/Tn-progress.md` 改为 `tasks/Tn-handoff.md`。它只在 Task 实际 BLOCKED、retry、跨 session/owner handoff 或并行委派时创建，内容限于 blocker、已做 evidence、下一动作、影响 Ticket 与接手边界。

Task Handoff 是可更新的局部恢复材料，不是状态或审计记录。具有长期价值的判断、failure learning 或 checkpoint 由主 session 提炼进 ER；worker 不直接写 ER。

### 3.4 Execution Record

ER 保存不能从 runtime state、artifact chain、review ledger、gate 或 Git 可靠推导的执行判断。它位于 package/Attempt 公共层，不被 Ticket、Task、AC 或 seam 拥有；相关实体只是 subject 或脚本派生关系。

ER 是 human-readable、machine-validated 的公共叙事账本，不是内部 sidecar。写入 owner 是 `dev-with-track` 主 session。

## 4. 目标布局

```text
<package>/
├─ plan.md
├─ progress.md
├─ execution-records/
│  ├─ index.md
│  ├─ initial.md
│  └─ patch-a.md
├─ tickets/
├─ tasks/
│  └─ T3-handoff.md
├─ gate.md
└─ .impl-package/
   ├─ revision-bindings.json
   └─ runtime-state.json
```

- `plan.md` 保留执行策略、Composition、Planned Verification，以及到 progress/ER index 的稳定链接；不再包含 ER 正文。
- ER 按 Attempt 分区，不按 Ticket、Task 或 owning stage 分区。
- 首版每个 Attempt 只有一个 ER 文件，不做 segment rollover。
- terminal gate 后对应 Attempt ER 冻结。
- `index.md` 与 `progress.md` 都是 machine-owned projection。

## 5. Attempt Progress

`progress.md` 是 current Attempt 的统一恢复入口，不是历史日志，也不能手改。它显示：

1. Attempt、D/S/P、Composition、derived lifecycle 与 latest gate；
2. 当前 blockers；
3. Ticket acceptance table（仅 `tickets=true`）；
4. Task execution table 与 Handoff 链接（仅 `dag=true`）；
5. 当前有效 checkpoint；
6. 最新有效 checkpoint 的 next action 与相关 pointer。

Ticket acceptance 与 Task execution 永远分轴展示，不互相聚合，也不计算完成百分比。`progress.md` 只展示 canonical 状态、显式 blocker 和指针，不推导或授权 dispatch readiness。

四种 Composition 使用同一个 projection：

| Composition | Progress 内容 |
| --- | --- |
| 无 Ticket、无 DAG | Attempt、Spec acceptance pointer、checkpoint、gate |
| 有 Ticket、无 DAG | Ticket acceptance、checkpoint、gate；不造 Task |
| 无 Ticket、有 DAG | Task execution、Spec acceptance pointer、checkpoint、gate |
| 有 Ticket、有 DAG | Ticket acceptance 与 Task execution 两张表，加 checkpoint、gate |

## 6. ER 首版模型

### 6.1 Identity

ER 使用 Attempt-local ID：

```text
initial-ER-001
initial-ER-002
patch-a-ER-001
```

每个 Attempt 从 `ER-001` 开始；package index 使用完整 ID。首版不使用 package-global ordinal、global/stage hash chain 或 segment ownership。

### 6.2 Purpose：2

只保留：

- `checkpoint`：可恢复执行边界，也是唯一进入 progress Active Checkpoints 的 purpose。
- `judgment`：统一承载 execution-time decision、finding disposition、failure learning 与 external evidence interpretation。

`judgment` 不能绕过上游 authority：若内容实质改变 D/S/P contract、Acceptance Semantics、Composition、计划策略、安全边界或外部 mutation authority，必须路由对应 owning stage，而不是写成 ER。

routine state transition、普通 validation PASS、artifact/hash/revision 注册、无信息增量重跑，以及能从其他 canonical source 推导的事实不得进入 ER。

checkpoint 只支持恢复上下文，不推导 implementation readiness，也不释放 dependency。

### 6.3 Subject 与关系派生

每条 ER 只有一个主语：

```text
attempt          # 默认
ticket:<id>
task:<id>
```

agent 不维护任意 `refs[]`。脚本只校验 subject 属于 current Attempt，并读取 current D/S/P 与 subject runtime state 以判断 checkpoint 是否明确失效。

AC 继续通过 Ticket evidence pointer 表达；seam 写在 checkpoint 的 stable boundary 中。dependency、contribution 与 dispatch 仍由各自 canonical contract 和主 session 判断，不进入 checkpoint schema。

### 6.4 Supersede 与 freshness

正常 checkpoint 更新不要求 agent 查找旧 ER：

- recovery checkpoint 按 `subject` 自动 supersede；
- judgment 默认追加，低频 correction 才显式引用旧 record。

D/S/P 不匹配，或 subject 明确进入 `NEEDS-REVALIDATION`/`SUPERSEDED` 时，相关 checkpoint 在 progress 中显示 stale。v1 不承诺推导 dependency、contribution 或 evidence drift。

## 7. 单命令写入

首版只提供一个主命令：

```text
er-add
```

agent 通过 stdin 提交 `purpose=checkpoint|judgment`、可选 subject、title、content，以及 checkpoint 的 `nextAction`。脚本一次性：

1. 推导唯一 Active Attempt；
2. 校验 subject 与 freshness inputs；
3. 分配 ER ID；
4. 校验 admission 与必填内容；
5. 渲染完整 Markdown record并计算 content hash；
6. 原子更新当前 Attempt ledger；
7. 重建 ER index 与 `progress.md`；
8. 返回 record ID、path 与 anchor。

agent 不查找或编辑 Attempt、ER ID、旧 checkpoint、文件名、ledger、index 或 progress。

不实现 reserve/write/seal、reservation、token、open slot、abort/recover 或专用 ER 状态机。相同 payload 重试返回同一 ER，但幂等命中仍重建并校验 index/progress，使 ledger 已写而 projection 刷新中断的状态可恢复。写入前执行 committed 与 working-tree validation；成功写入并重建 projection 后再次执行 working-tree validation。

## 8. Restore 与 ownership

正常恢复：

1. 运行 committed validation。
2. 打开 `progress.md` 确认 current Attempt、两条状态轴、显式 blockers、checkpoint 与 handoff/ER 指针。
3. 只沿 progress pointer 读取相关 Ticket、Task、Handoff、ER、review 或 evidence。
4. 用 current revision 与实际 diff 校准，发现 stale 时只 reconcile 受影响 scope。

主要 owner：

| Surface | Owner |
| --- | --- |
| Plan/P/Composition/Planned Verification | `impl-planning` |
| Ticket contract/publication | `to-tickets` |
| DAG Task/contribution | `create-task-dag` |
| Task/Ticket runtime state | `dev-with-track` through state CLI |
| Task Handoff | Task worker/main session，按条件维护 |
| ER admission/body | `dev-with-track` 主 session |
| ER identity/render/append/index 与 progress | state CLI |
| Gate verdict/Stage 7 | 现有 gate owner；ER/progress 不接管 |

## 9. 首版实施与验证范围

首版只做：

1. 3.3 contract revision 与 fresh layout；3.2 package 只返回 `upgradeRequired`，不提供 migration command。
2. Ticket state vocabulary 与模板收敛。
3. Task Progress 改为 Task Handoff。
4. Attempt-local 单文件 ER、package index 与 `er-add`。
5. machine-owned `progress.md`。
6. working-tree/committed validation 与 projection rebuild。
7. fresh fixture unit、skill eval 和一条完整 integration flow。

最小验证场景：

- 四种 Composition 都可从 progress 恢复，且不创建未 earned artifact。
- Task `DONE` 不自动改变 Ticket state。
- routine validation 不能创建 ER。
- checkpoint 自动派生 subject 关系并按 key supersede。
- checkpoint payload 不接受 downstream/readiness 字段，也不释放 dependency。
- revision 或 subject state 明确失效时 checkpoint stale；不承诺 dependency/evidence drift 推导。
- 相同 payload 重试幂等；projection 可重建；sealed ER 被修改时 validate fail closed。
- terminal Attempt 冻结，新 Attempt 从自己的 `ER-001` 开始。
- agent 无需查找 ID、路径、旧 checkpoint 或编辑 machine-owned 文件。

## 10. 明确延期

- segment rollover；
- reserve/write/seal 与 reservation recovery；
- multi-writer 或 worker 直接写 ER；
- package-global ordinal/hash chain；
- AC-level runtime state；
- seam registry；
- 旧 package migration、legacy parser 与 anchor redirect；
- 新 purpose、配置项或扩展性抽象。

## 11. 试运行与停止条件

首版在 fresh package 上运行数轮，观察：

- 新 session 能否从 progress 快速恢复；
- owner 能否直接找到 Ticket acceptance state；
- Task Handoff 与 ER 是否出现重复；
- 单 Attempt ER 体量是否真的需要分段；
- progress 是否包含无法可靠派生的字段；
- checkpoint supersede/freshness 是否符合实际执行。

首版在 state、ER、progress、Task Handoff 与 gate 的完整路径通过验证，且没有为了假设中的体量、并发或历史兼容加入延期项后停止。后续优化只根据试运行事实另行立项。
