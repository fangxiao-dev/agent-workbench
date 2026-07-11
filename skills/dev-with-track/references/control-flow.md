# Dev With Track Control Flow

状态：通用参考
用途：中途接入既有 spec / plan / patch plan 的具体流程，以及 implementation
的结束语义。Composition、canonical status home、readiness、迁移和 Stage 7 以
`docs/skill-design/references/impl-package-composition-contract.md` 为准；文件角色、
账本触发条件和任务编号规则见 `SKILL.md`。

## 中途接入已有 Spec / Func Design

如果已有 ad-hoc spec、临时 Func Design、handoff 中的功能合同、或旧需求说明：

1. 路由 `requirement-alignment`，先完成其必过 Design / Spec gates；本 skill 不
   自行创建、裁剪或采纳 spec。
2. 如有 ad-hoc 文档，作为 requirement-alignment 的输入；由该 skill 决定迁入
   canonical `spec.md`、保留指针，或把稳定文档作为权威引用。
3. Spec gate 通过后，读取它的唯一 Composition 声明，只 scaffold earned artifacts。

完成标准：新 workspace 能通过已过门 `spec.md` 恢复本任务要实现什么；长期 spec
不被误当成执行账本；durable delta 仅在 Stage 7 的 gate capture 中进入 backfill 路径。

## 中途接入已有 Plan

如果已有 `docs/impl-plans/*.md`、handoff、roadmap 段落或旧 `process.md`：

1. 创建带时间戳的 implementation package-id 目录；新包格式为
   `YYYYMMDD-HHMMSSZ-<topic-slug>`，已有 legacy package 不改名。
2. 建立 `plan.md` 入口。
3. 如果用户允许重组，把原 plan 内容迁入 `plan.md`，并在原位置留索引或不动
   旧文档，取决于项目规则。
4. 如果用户只要求开始跟踪，不迁移旧文档，`plan.md` 写 adoption wrapper：
   链接原 plan、说明原 plan 仍是内容来源、列出本 workspace 负责承载
   DAG/findings/gate/tasks。
5. 从旧 process/handoff 中抽取当前状态到 composition 的 canonical state home：
   earned `dag.md`、ticket 文件或 no-DAG plan checklist；不要逐字搬运流水账。

完成标准：新 workspace 能恢复执行现场；旧 plan 没有被误删或孤立。

## 接入 Patch Plan

如果同一 package-id 下已有 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`：

1. 读取 `spec.md`、`plan.md`、目标 patch plan、composition 所 earn 的 DAG/tickets
   和已有 ledger。
2. 把 patch plan 视为计划 delta，更新 composition 的 canonical execution state、
   必要的 `tasks/Tn-progress.md`、`findings.md` 或 `gate.md`，不要覆盖 `plan.md`。
3. 如果 patch plan 暴露出功能合同变化，确认该变化已经进入 `spec.md`；缺失
   时先补 spec 或标记 blocker。
4. 新增 task 时从当前 package-id 的最高 `T<number>` 之后继续编号。

完成标准：patch 进入有序执行，但初始 plan、patch plan、earned DAG/tickets 三者
角色不互相覆盖；不得仅因 ticket 而创建 per-ticket patch plan。

## 结束语义

保持这些 implementation 级状态彼此不同：

- `planned`：implementation 入口和边界已建立；
- `running`：至少一个 task 正在执行；
- `integrated`：seam 已合并但验证未全过；
- `verified local`：本地自动化证据完成；
- `verified external`：需要的浏览器/外部 smoke 完成；
- `gate passed`：implementation 关闭条件满足；
- `deferred`：用户接受未完成项后延。

不要用单个 task 的通过代替 implementation gate 的通过。
