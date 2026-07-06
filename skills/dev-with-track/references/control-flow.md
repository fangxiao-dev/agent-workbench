# Dev With Track Control Flow

状态：通用参考
用途：指导 implementation workspace 如何用 `spec.md` / `plan.md` / `dag.md` / `tasks/Tn-progress.md` / optional `tasks/Tn-handoff.md` / `findings.md` / `gate.md` 记录临时功能合同、计划、调度、证据、发现和关闭状态。

## 角色优先

先判断文档角色，再判断文件名：

- `spec`：本次 implementation 的临时 Func Design / implementation spec，记录任务局部功能合同、引用的长期 spec、本次 delta、非目标和验收语义。
- `plan`：怎么做、文件范围、执行策略、验证计划和执行 checklist。
- `patch plan`：同一 implementation slug 的后续 patch/follow-up 执行计划，文件名为 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`，作为 `spec.md` / `plan.md` 之上的计划 delta 输入。
- `dag`：谁在做、能否并行、当前状态、seam 在哪里、gate 证据是什么。
- `task progress`：某个任务自己的局部状态、证据、blocker、seam request。
- `task handoff`：某个任务需要单独交接时的最小移交文档。
- `findings`：跨 task 的发现、风险、后续动作、可复用经验。
- `gate`：implementation 是否可以关闭、阻塞、延期或交给人工判断。

文件名只是默认承载。项目已有约定时，可以使用等价文件名，但不要混淆角色。

## 新建 Implementation

新工作默认创建：

```text
docs/implementations/<implementation-slug>/
├── spec.md
├── plan.md
├── [YYYYMMDD-HHMM-<patch-topic>.patch-plan.md]
├── dag.md
├── findings.md
├── gate.md
└── tasks/
```

`spec.md` 必须存在。即使已有长期 `docs/func-design/...`，也要在 slug 内创建薄 `spec.md`，引用长期设计并说明本任务 delta。开始时只需要足够支撑当前执行的文件；不要为了形式创建很多空 task ledger。

## 中途接入已有 Spec / Func Design

如果已有 ad-hoc spec、临时 Func Design、handoff 中的功能合同、或旧需求说明：

1. 创建 implementation slug 目录。
2. 建立 `spec.md` 入口。
3. 如果该文档本质是本任务临时 spec，且用户允许重组，把内容迁入 `spec.md`，并在旧位置留索引/指针或按项目规则处理旧路径。
4. 如果该文档已经是长期稳定 spec，保留原文档；`spec.md` 写 adoption wrapper：链接长期 spec，说明本 implementation 只实现哪些 delta、非目标、验收语义和临时决策。
5. 如果没有现成 spec，也要创建最小 `spec.md`：背景、引用、in/out scope、功能 slice、验收、待回写候选。

完成标准：新 workspace 能通过 `spec.md` 恢复本任务要实现什么；长期 spec 不被误当成临时执行账本；临时 spec 后续是否沉淀回长期文档交给文档维护任务。

## 中途接入已有 Plan

如果已有 `docs/impl-plans/*.md`、handoff、roadmap 段落或旧 `process.md`：

1. 创建 implementation slug 目录。
2. 建立 `plan.md` 入口。
3. 如果用户允许重组，把原 plan 内容迁入 `plan.md`，并在原位置留索引或不动旧文档，取决于项目规则。
4. 如果用户只要求开始跟踪，不迁移旧文档，`plan.md` 写 adoption wrapper：链接原 plan、说明原 plan 仍是内容来源、列出本 workspace 负责承载 DAG/findings/gate/tasks。
5. 从旧 process/handoff 中抽取当前状态到 `dag.md`，不要逐字搬运流水账。

完成标准：新 workspace 能恢复执行现场；旧 plan 没有被误删或孤立。

## 接入 Patch Plan

如果同一 slug 下已有 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`：

1. 读取 `spec.md`、`plan.md`、目标 patch plan、`dag.md` 和已有 task ledgers。
2. 把 patch plan 视为计划 delta，更新 `dag.md`、必要的 `tasks/Tn-progress.md`、`findings.md` 或 `gate.md`，不要覆盖 `plan.md`。
3. 如果 patch plan 暴露出功能合同变化，确认该变化已经进入 `spec.md`；缺失时先补 spec 或标记 blocker。
4. 新增 task 时从当前 slug 的最高 `T<number>` 之后继续编号。

完成标准：patch 进入执行调度，但初始 plan、patch plan、DAG 三者角色不互相覆盖。

## DAG Board

`dag.md` 是主 session 的调度面板。推荐最小表格：

```md
| Task | Owner | Status | Gate / Evidence | Seam / Notes |
| --- | --- | --- | --- | --- |
```

状态词保持少量：

- `Planned`
- `Ready`
- `Running`
- `Needs seam`
- `Blocked`
- `Integrated`
- `Verified local`
- `Verified external`
- `Deferred`

高并行任务可以加 cohort：

```md
| Cohort | Task | Owner | Status | Gate / Evidence | Seam / Notes |
```

不要把 `dag.md` 写成详细日志。它应该让后来者一眼知道下一步调度。

## Task Ledger Trigger

只有满足触发条件时才创建 `tasks/Tn-progress.md`：

- 独立 owner / subagent；
- 独立外部 gate；
- `NEEDS_SEAM`、blocker、review finding；
- 跨 session 继续；
- 有独立证据要保存；
- 会影响最终 gate 且 `dag.md` 一行放不下。

不满足触发条件的任务留在 `dag.md` 一行内。

`tasks/Tn-handoff.md` 只在该 task 需要单独交接、跨 session 移交、或交给另一个 agent/worker 接手时创建。不要提前引入 `Tn-evidence.md`、`Tn-review.md`、`Tn-notes.md`；这些内容先放进 `Tn-progress.md`。

## Task Numbering

任务编号在一个 implementation slug 内稳定递增。新增任务前扫描：

- `dag.md`
- `tasks/T*-progress.md`
- `tasks/T*-handoff.md`
- `plan.md`
- 根目录 `*.patch-plan.md`

取最高 `T<number>` 后的下一个编号。不要复用、重排或压缩已有编号；patch plan 追加任务也遵循同一序列。

## Findings Promotion

不要把每个 task 的局部日志都推到 `findings.md`。只提升这些内容：

- 跨 task 的风险；
- 改变 plan、DAG 或 gate 的发现；
- 后续 issue/backlog 候选；
- 可复用到后续 implementation 的经验。

## Gate Control

`gate.md` 只回答 implementation 级别是否能关闭：

- `spec.md` 的功能合同是否覆盖本次实现；
- acceptance 是否覆盖；
- required local/browser/external verification 是否完成或明确 defer；
- seams 是否集成；
- review findings 是否处理；
- residue / cleanup / skipped checks 是否有解释；
- follow-up 是否进入 findings、issue 或 backlog。
- task-local `spec.md` 中哪些结论已回写到长期 spec，哪些明确延期，哪些只是本任务上下文。

不要用 task 局部通过代替 implementation gate 通过。

## 结束语义

保持这些状态不同：

- `planned`：implementation 入口和边界已建立；
- `running`：至少一个 task 正在执行；
- `integrated`：seam 已合并但验证未全过；
- `verified local`：本地自动化证据完成；
- `verified external`：需要的浏览器/外部 smoke 完成；
- `gate passed`：implementation 关闭条件满足；
- `deferred`：用户接受未完成项后延。
