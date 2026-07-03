# Dev With Track Control Flow

状态：通用参考
用途：指导 implementation workspace 如何用 `plan.md` / `dag.md` / `tasks/Tn-progress.md` / optional `tasks/Tn-handoff.md` / `findings.md` / `gate.md` 记录计划、调度、证据、发现和关闭状态。

## 角色优先

先判断文档角色，再判断文件名：

- `plan`：为什么做、做什么、验收什么、有什么边界。
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
├── plan.md
├── dag.md
├── findings.md
├── gate.md
└── tasks/
```

开始时只需要足够支撑当前执行的文件。不要为了形式创建很多空 task ledger。

## 中途接入已有 Plan

如果已有 `docs/impl-plans/*.md`、handoff、roadmap 段落或旧 `process.md`：

1. 创建 implementation slug 目录。
2. 建立 `plan.md` 入口。
3. 如果用户允许重组，把原 plan 内容迁入 `plan.md`，并在原位置留索引或不动旧文档，取决于项目规则。
4. 如果用户只要求开始跟踪，不迁移旧文档，`plan.md` 写 adoption wrapper：链接原 plan、说明原 plan 仍是内容来源、列出本 workspace 负责承载 DAG/findings/gate/tasks。
5. 从旧 process/handoff 中抽取当前状态到 `dag.md`，不要逐字搬运流水账。

完成标准：新 workspace 能恢复执行现场；旧 plan 没有被误删或孤立。

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

## Findings Promotion

不要把每个 task 的局部日志都推到 `findings.md`。只提升这些内容：

- 跨 task 的风险；
- 改变 plan、DAG 或 gate 的发现；
- 后续 issue/backlog 候选；
- 可复用到后续 implementation 的经验。

## Gate Control

`gate.md` 只回答 implementation 级别是否能关闭：

- acceptance 是否覆盖；
- required local/browser/external verification 是否完成或明确 defer；
- seams 是否集成；
- review findings 是否处理；
- residue / cleanup / skipped checks 是否有解释；
- follow-up 是否进入 findings、issue 或 backlog。

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
