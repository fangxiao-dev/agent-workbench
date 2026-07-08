# Dev With Track Control Flow

状态：通用参考
用途：中途接入既有 spec / plan / patch plan 的具体流程，以及 implementation
的结束语义。文件角色、账本触发条件和任务编号规则见 `SKILL.md`。

## 中途接入已有 Spec / Func Design

如果已有 ad-hoc spec、临时 Func Design、handoff 中的功能合同、或旧需求说明：

1. 创建 implementation slug 目录。
2. 建立 `spec.md` 入口。
3. 如果该文档本质是本任务临时 spec，且用户允许重组，把内容迁入 `spec.md`，
   并在旧位置留索引/指针或按项目规则处理旧路径。
4. 如果该文档已经是长期稳定 spec，保留原文档；`spec.md` 写 adoption
   wrapper：链接长期 spec，说明本 implementation 只实现哪些 delta、非目标、
   验收语义和临时决策。
5. 如果没有现成 spec，也要创建最小 `spec.md`：背景、引用、in/out scope、
   功能 slice、验收、待回写候选。

完成标准：新 workspace 能通过 `spec.md` 恢复本任务要实现什么；长期 spec 不
被误当成临时执行账本；临时 spec 后续是否沉淀回长期文档交给文档维护任务。

## 中途接入已有 Plan

如果已有 `docs/impl-plans/*.md`、handoff、roadmap 段落或旧 `process.md`：

1. 创建 implementation slug 目录。
2. 建立 `plan.md` 入口。
3. 如果用户允许重组，把原 plan 内容迁入 `plan.md`，并在原位置留索引或不动
   旧文档，取决于项目规则。
4. 如果用户只要求开始跟踪，不迁移旧文档，`plan.md` 写 adoption wrapper：
   链接原 plan、说明原 plan 仍是内容来源、列出本 workspace 负责承载
   DAG/findings/gate/tasks。
5. 从旧 process/handoff 中抽取当前状态到 `dag.md`，不要逐字搬运流水账。

完成标准：新 workspace 能恢复执行现场；旧 plan 没有被误删或孤立。

## 接入 Patch Plan

如果同一 slug 下已有 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`：

1. 读取 `spec.md`、`plan.md`、目标 patch plan、`dag.md` 和已有 task ledger。
2. 把 patch plan 视为计划 delta，更新 `dag.md`、必要的
   `tasks/Tn-progress.md`、`findings.md` 或 `gate.md`，不要覆盖 `plan.md`。
3. 如果 patch plan 暴露出功能合同变化，确认该变化已经进入 `spec.md`；缺失
   时先补 spec 或标记 blocker。
4. 新增 task 时从当前 slug 的最高 `T<number>` 之后继续编号。

完成标准：patch 进入执行调度，但初始 plan、patch plan、DAG 三者角色不互相
覆盖。

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
