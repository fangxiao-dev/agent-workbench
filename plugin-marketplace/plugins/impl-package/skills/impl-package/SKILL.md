---
name: impl-package
description: Impl-Package 体系的入口地图与路由；当需要判断从需求对齐、计划、Ticket/DAG、执行、验证或稳定文档回刷的哪个阶段进入时使用。只导航，不代替阶段 skill 执行。
---

# Impl-Package

Impl-Package 把一次变更组织为可裁剪的链路：Decision/Spec contract ensemble → Plan → 可选 Tickets/DAG → execution state → verification → Gate → stable-doc backfill。

## 核心原则

- 只保存会改变下一动作、阻止 false PASS 或约束危险 mutation 的状态。
- D/S/P 是人类可读别名，不绑定文件内容。
- 只有 Git commit ID 可作为版本/比较点。
- 外部文件和 evidence 一律使用仓库相对 POSIX 路径；拒绝绝对路径和 `..`。
- 已知 artifact 使用固定目录或显式路径，不保存扫描结果副本。
- Git 负责历史审计；现役格式不维护 contract/schema 版本、迁移账本或兼容层。

正式规则见 [Composition Contract](../../references/impl-package-composition-contract.md)，状态格式和 CLI 见 [Current State](../../references/impl-package-current-state.md)。

## 路由

面向用户和 agent 的路由统一使用 `/plugin:skill` 调用形式；宿主内部 registry/discovery 显示的无 `/` skill key 不是第二种文档写法。

| 当前需要 | 使用 |
| --- | --- |
| 对齐需求、Decision、Spec | `/impl-package:req-align` |
| 在高风险 Spec gate 做 ledger 驱动审问 | `/impl-package:grill-me-smartly` |
| 对计划、Decision 或 Spec 做交互式深入质询 | `/impl-package:grilling` |
| 创建 initial/patch plan、决定 Composition | `/impl-package:impl-planning` |
| 审查 plan 或完整 Plan/Ticket/DAG bundle | `/impl-package:plan-review` |
| 创建独立验收切片 | `/impl-package:to-tickets` |
| 创建横向执行依赖图 | `/impl-package:create-task-dag` |
| 执行前确认授权与工作区 | `/impl-package:execution-preflight` |
| 调查原因、影响面或既有实现后再写入 | `/impl-package:investigate-before-implement` |
| 安排主 session 与 subagent 的通用调度 | `/impl-package:subagent-driven-development` |
| 恢复执行、推进 Task/Ticket、写 Gate | `/impl-package:dev-with-track` |
| 派发边界明确的局部 Task | `/impl-package:dispatch-bounded-task` |
| 编排多 reviewer、聚合 findings 并判断收敛 | `/impl-package:do-review` |
| 审查实现正确性和可维护性 | `/impl-package:code-review` |
| 审查仓库规范和模块 interface/depth/locality | `/impl-package:standards-review` |
| 审查需求、Spec、Plan 与实现忠实度 | `/impl-package:spec-review` |
| 审查安全、数据完整性、并发和外部副作用 | `/impl-package:safety-review` |
| 声称 complete/merge-ready 前审计证据 | `/impl-package:verification-before-completion` |
| 回刷稳定知识或退休 package | `/impl-package:backfill-stable-docs` |

当用户只是询问体系时停在本页；当用户已明确阶段和动作，直接进入对应 skill。

## 最小 package

```text
<package>/
  decision.md            # 可选；轻量 Decision 也可在 spec.md
  spec.md
  contract-design.md     # 可选；从属 spec.md，共用同一 S revision/Status/Gate
  plan.md
  tickets/               # Composition earned 时
  dag.md                  # Composition earned 时
  progress.md             # active Attempt 的 machine-owned 恢复投影
  execution/
    <attempt>/
      execution-record.md
      task-handoffs/      # 仅实际发生 handoff 时创建
  .impl-package/state.json
  gate.md                 # 首次 gate evaluation 时创建
```

小型个人/团队改动可以 `tickets=false, dag=false`；不要为审计完整感增加 artifact。

`contract-design.md` 只有在精确结构会遮蔽 `spec.md` 的行为/验收主线，或同一 canonical model 被多个 operation/module 消费时才 earned。它没有独立 alias、revision、状态、审批或生命周期。
