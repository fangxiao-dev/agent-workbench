---
name: impl-package
description: Impl-Package 体系的入口地图与路由：判断从需求对齐、计划、Ticket/DAG、执行、验证或稳定文档回刷的哪个阶段进入；并承载交互质询（grilling）与旧 DAG 只读审计的入口判断。只导航，不代替阶段 skill 执行。
---

# Impl-Package

链路：Decision/Spec contract ensemble → Plan → 可选 Ticket → execution state → verification → Gate → stable-doc backfill；DAG/Task 只为旧 package 恢复与迁移保留。核心原则：只保存会改变下一动作/阻止 false PASS/约束危险 mutation 的状态；只有 Git commit ID 可作为版本点；路径一律仓库相对 POSIX，拒绝绝对路径与 `..`；正式规则见 [Composition Contract](../../references/impl-package-composition-contract.md) 与 [Current State](../../references/impl-package-current-state.md)。路由统一使用 `/plugin:skill` 调用形式；仅询问体系时停在本页，已明确阶段则直达对应 skill。

## 入口：阶段命令

| 命令 | 用途 | 命令 | 用途 |
| --- | --- | --- | --- |
| impl-req-align | 需求/Decision/Spec 对齐 | impl-grill-me-smartly | 高风险 Spec gate ledger 审问 |
| impl-grilling | 交互式深入质询 | impl-impl-planning | 建 initial/patch plan、定 Composition |
| impl-plan-review | 审查 plan 或 bundle | impl-to-tickets | 创建独立验收切片 |
| impl-create-task-dag | 旧 Task/DAG 只读审计/迁移 | impl-execution-preflight | 执行前确认授权与工作区 |
| impl-standing-bookkeeper | 绑定/恢复、更新与回执 | impl-subagent-driven-development | 调查/实现/修复/验证与分工 |
| impl-dev-with-track | 恢复执行、推进、写 Gate | impl-do-review | 多 reviewer 编排与收敛 |
| impl-review-code | 实现正确性与可维护性 | impl-review-code-by-standards | 按规范/interface/depth/locality 审查 |
| impl-review-code-by-spec | 按需求/Spec/Plan 审查忠实度 | impl-safety-review | 安全/数据完整性/并发/副作用 |
| impl-verification-before-completion | complete/merge-ready 前审计证据 | impl-backfill-stable-docs | 回刷稳定知识/退休 package |

最小 package（人类参考）：`spec.md`（可选 `decision.md`）、从属 `contract-design.md`（默认 detailed；spec 完整承担语义时 not-required 并写明理由）、`plan.md`、`tickets/`（Ticket-only 合同时）、`progress.md`、`execution/<attempt>/execution-record.md`、`.impl-package/state.json`、`gate.md`（首次 gate 时创建）。新 package 统一 `tickets=true, dag=false`；`dag=true` 只读旧 package，不为审计完整感增加 artifact。

## 交互质询（grilling）

设计树 rounds 质询：每轮先列完整 frontier（可读则一批，过大则连续分批且保留全部 material decisions、稳定 ID 不遗漏），逐题编号并给推荐答案，等用户整批回复；聚焦随材料成熟度变化，真实缺口或用户请求可重开选项空间。事实自己查（可派 subagent，不阻塞其余 frontier），决策留给用户。frontier 空即收敛：呈现汇总，确认后才写回目标文档；写回后简报改动文档/吸收的决策组/未决与延期项/未运行的阶段。记录边界：无 ledger，已确认项/非目标/延期/开放项留在工作记忆或用户既有 notes 面，mid-grill 不编辑目标文档。细节按需读 `../grilling/rubric.md`。

## Legacy（create-task-dag，只读）

新 package 一律不创建 Task DAG；仅在 owner 明确授权恢复/迁移已有 3.4 package 且 artifact 已存在时读取 `dag.md`/`<attempt-id>.patch-dag.md`。只审计 primary ownership、确定依赖、贡献 Ticket、seam/risk 与 section-level contract refs；迁移时把 Task 真实产物映射回 Ticket claim，不把 Task handoff 或 `DONE` 当 acceptance proof；Task 状态只存 `.impl-package/state.json`；发现新 DAG 需求回 `impl-planning`。细节按需读 `../create-task-dag/references/`（dag-and-ownership、worker-prompts、review-and-verification、slice-to-dag）。
