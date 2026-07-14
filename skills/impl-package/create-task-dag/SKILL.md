---
name: create-task-dag
description: >
  当已批准 implementation plan 与相关 ticket subset 需要转为 task DAG、分配 ownership、
  协调 worker 或 integration seam 时使用。消费已冻结 contract；task 实现与即时 review
  交由 `subagent-driven-development`，ticket acceptance review 交由 `dev-with-track`。
---

# Create Task DAG

把已批准的 implementation package 输入变成可执行的 worker task DAG：明确 ownership、稳定的契约、集成 seam 和验证交接。它只做 **execution decomposition**；delivery slice / ticket 的验收切分归 `to-tickets`。

本 skill 的共享语义唯一引用 `skills/impl-package/references/impl-package-composition-contract.md`。不得在本 skill 重定义 canonical status、readiness resolution、composition migration、Stage 7 或 seam 关闭规则。

## 输入与路由边界

可开始 DAG execution decomposition 的有效输入只有当前 attempt plan 声明 `dag=true` 的两种 Composition：

1. `tickets=true, dag=true`：当前 attempt plan + **属于同一 Attempt ID 且相关、Approved 的 ticket 子集**；该子集必须足以读取其受影响的 acceptance target，seam contract 从当前 spec revision 读取。
2. `tickets=false, dag=true`：当前 attempt plan；其 acceptance target 由 package 的 `spec.md` 提供。

Impl-Package 中 `dag=true` 的 DAG 必须持久化为当前 attempt 的 `dag.md` 或 patch DAG；不得只留在对话/handoff，也不得把 task contract、ownership 或状态写入 plan。若只有单一 ticket，不能据此猜测跨 ticket seam context，必须要求 plan + 相关 Approved ticket 子集，并从 spec 解析 contract。

按当前 attempt plan 的 Composition 与 artifact 状态路由，不能从 spec 或历史 attempt 猜测：

- 当前 plan 明确为 `tickets=false, dag=true`，且有 gated spec 与稳定 `spec:AC-n`：直接使用 plan 创建 DAG；不进入 `to-tickets`。
- 当前 plan 明确为 `tickets=true, dag=true`、尚无 Approved ticket、且没有 Draft ticket：才路由 `to-tickets mode=draft`。
- 同一组合已有 Draft ticket：等待明确 owner approval，然后路由 `to-tickets mode=publish`；本 skill 不把 Draft 标为 Approved。
- 当前 plan 明确为 `tickets=true, dag=true`，已有同 Attempt ID 的相关 Approved ticket 子集：开始 DAG 输入校验。
- `tickets=true, dag=false` 或 `tickets=false, dag=false`：不调用本 skill 创建 task-decomposition artifact；no-DAG 状态与 seam 限制只引用共享 contract，不在本 skill 重定义。
- Composition 未决，或当前 plan Composition 与现有 artifact 不一致：路由 `impl-planning` 升级 P revision并完成 artifact relocation；不重跑 D/S gate。
- S/M/L/D shorthand 不是创建或删除 DAG 的授权；只有当前 plan 的 canonical Composition 可以 earn DAG。口令、实际依赖信号与 plan 不一致时回 `impl-planning`，在 owner 决议前不改变 artifact。
- gated spec、D/S revision、AC 或 seam contract 缺失/漂移：路由 `req-align` 修复所需 Design/Spec gate。
- gated spec 已就绪但缺 `plan.md`：路由 `impl-planning` 生成 plan；宽泛或未成 package 的输入同样先走 `req-align`，不得跳到 `to-tickets`。
- 只有单一 Approved ticket，且需要跨 ticket seam：请求 package plan + 相关 Approved ticket 子集；不得自行推断 seam。

本 skill 不切 slice、不发布 tracker，也不把 draft 变成 Approved ticket。只有完成相应上游输入后，才继续画 task DAG。

## 持久化映射

本 skill 的 canonical 输出是 package 内当前 attempt DAG。缺 package-id、当前 plan 或可写 package workspace 时停止并路由上游；对话中的草图不算 Impl-Package DAG 产物。本节是唯一的映射来源：

- 功能合同、seam contract 或验收语义的变化 -> `spec.md`。DAG 工作暴露出合同变化时，先补 spec 或标记 blocker，不要只改 plan。
- 当前 attempt 的执行顺序、具体集成动作与验证选择变化 -> 当前 plan 的新 P revision。
- 任务契约、cohort、ownership、状态、seam、验证 gate -> `dag.md`；patch 模式下旧 `dag.md` 已标记 `Retired / terminal gate` 时，写入当前的 `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`。
- 持久的任务局部状态 -> `tasks/Tn-progress.md`。
- 任务交接 -> `tasks/Tn-handoff.md`。
- 跨任务风险与后续项 -> `findings.md`。
- 完整 review/verification 证据 -> 当前 plan Execution Record；关闭判决摘要 -> `gate.md` 新 entry。

## 运行原则

- **Ticket**：delivery slice 与验收单元；它不是 worker task 的包含容器。
- **Task DAG**：执行依赖与 worker 协调图；task 可贡献给多个 ticket AC，seam task 不属于单一 ticket。
- **Main session**：协调者、集成验证者、外部把关者；它只有在 spec seam contract 被明确指定时才是 contract/acceptance owner，或在 DAG task 被指定时才是 seam execution owner。
- **Worker**：单任务或窄 cohort 的有界实现者。
- **Task review carrier**：`subagent-driven-development` 组织独立 reviewer subagent 完成 task spec-compliance / code-quality review。
- **Ticket acceptance reviewers**：由 `dev-with-track` 在固定 review point 路由 code-review、适用的 module-review 和 safety-review。

不要因为存在共享文件就串行化实现。给共享文件明确 ownership，让 worker 上报 seam 需求，而不是越界编辑。

用 **ownership lanes** 代替扁平的文件清单。每个 worker prompt 和 DAG 任务都区分 primary owned（正常写入范围）、conditional seam（仅在点名条件下可改）、forbidden（禁改）三类文件。这让 plan ownership 与 worker prompt 保持一致，也让有意的 seam 编辑可审查，而不是变成意外的 scope creep。

**Seam status** 用词精确：并行任务之间计划内的依赖是 `NEEDS_SEAM`，不是 `BLOCKED`。`BLOCKED` 只留给缺上下文、缺权限、数据不可用、计划错误或需要人类决策的情况。

## 工作流

### 1. 校验已批准输入

读当前 attempt plan、同 Attempt ID 的相关 Approved tickets（若 tickets=true）、spec 的 D/S revision、AC 与 seam contract、仓库指令和相关验证文档。plan 和 spec 通常由 `impl-planning` / `req-align` 产出在 `docs/implementations/<package-id>/`。来源不满足输入契约时，读 `references/slice-to-dag.md` 并按缺失原因路由。识别：

- 所有将被 task 贡献或启用的 acceptance target；
- 每个 acceptance target 的必需 evidence producer，以及尚未在 ticket 阶段解析的 producer obligation；
- 当前分支与脏状态；
- 外部 mutation 权限与红线；
- 可能的共享 seam 文件；
- 需要的本地、浏览器和外部验证。

完成标准：main session 能说出受影响 acceptance target、必须交付什么、不能碰什么、哪些 decisions 仍真正属于 owner；未批准或缺失的 ticket 不得作为 DAG 输入。

### 2. 校验共享契约

派发 worker 前，从当前 spec revision 校验它们独立工作所需的契约：

- DTO / 类型 / API 字段；
- fallback 与兼容规则；
- route / page prop 命名；
- i18n namespace / key 约定；
- worker 所属数据支撑的 UI 状态；
- 外部 smoke 的 marker 与清理协议。

完成标准：worker 不用发明形状、不用碰非属地文件，就能消费或产出其契约。

### 3. 画 DAG 与 Ownership Map

用 `references/dag-and-ownership.md`：任务记录、ownership 模式、cohort 规则和任务编号续编。

把 DAG 按上方映射持久化到当前 attempt 的 `dag.md` 或 patch DAG；不得写入 plan、只留对话或改写历史 DAG。

完成标准：每个任务都有依赖、可并行邻居、ownership lanes、聚焦测试、完成标准、acceptance contribution/enablement 与 seam execution owner；每个 acceptance target 的证据生产者或人工验证 owner 可被追溯。

在持久化 DAG 前，把 ticket acceptance、typed implementation edges、task Depends on 与 task-to-AC evidence contribution 组成一个联合 readiness 图并检查 satisfiability。若某项 AC 的必需 producer task 直接或传递依赖该 AC 所属 ticket 先通过 acceptance，则这是 semantic cycle；ticket 图和 task 图各自无环也不能放行。

semantic cycle 若只需重分类 typed edge、调整 task 顺序或修正 evidence producer 投影，且不改变 D/S、AC、Composition、安全规则或外部 mutation authority，则返回对应 owning skill 做机械修正并继续，不请求 owner 重新批准业务范围。只有修正产生不同业务结果或改变授权事实时才升级 owner decision。

### 4. 派发并行 Worker Cohort

用 `references/worker-prompts.md` 生成 worker prompt 和处理返回状态。

同一 cohort 中契约已稳定、primary 写入集不重叠的任务一起派发。worker prompt 从 DAG ownership lanes 生成；不要手写比 DAG 更窄或更宽的 ownership 清单。共享 seam 文件留给 main session 或一个明确点名的 seam worker。

完成标准：每个 worker 拿到有界 prompt，不可能把自己的任务误当成整个 implementation。

### 5. 集成 Seam

main session 处理跨任务 seam：

- route / page 接线；
- 共享类型导出；
- 词典合并；
- prop 形状不匹配；
- 测试矩阵缺口；
- worker 产出之间的冲突。

完成标准：集成后的 worktree 是一个连贯 implementation，不是相邻的任务孤岛。

### 6. 交回执行与验收

用 `references/review-and-verification.md`：task review、验证 gate 和 ticket acceptance review 的调用方式。

任务级 review 不够。集成后，把固定 comparison point、package spec、plan、相关 tickets、DAG 和验证证据交回 `dev-with-track`；由它自动路由完整的 ticket acceptance review。本 skill 不另行定义正式 reviewer 检查项。

完成标准：本地集成测试、必要的浏览器检查、外部 smoke gate，以及正式 review 的固定点结论都被诚实记录。

## 输出契约

用于规划或执行准备时，输出或记录：

```markdown
## Task DAG
| Task | Depends on | Can run with | Primary owned | Conditional seam | Forbidden | Acceptance target | Seam | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Shared Contracts
- ...

## Parallel Cohorts
- Cohort 1:
- Cohort 2:
- Final:

## Integration Seams
- ...

## Verification Gates
- ...
```

用于执行期时，最终汇报必须包含：

向 owner 汇报时使用 `talk-to-boss`，说明总执行范围、已完成/待执行的功能工作线数量、集成是否完成、剩余 blocker 和能否进入 gate。以下 cohort、task、seam 与命令属于 canonical evidence，不作为 owner 汇报开场：

- 派发的 worker cohort；
- main session 处理的 seam；
- 实际运行的测试和浏览器/外部检查；
- ticket acceptance review 的固定点结果；
- 剩余风险或被阻塞的 gate。
