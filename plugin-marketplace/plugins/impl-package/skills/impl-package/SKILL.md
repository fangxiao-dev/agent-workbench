---
name: impl-package
description: Impl-Package 体系的入口地图与路由：判断从需求对齐、计划、Ticket、执行、验证、进度监控或稳定文档回刷的哪个阶段进入；并承载高风险审问与旧 package 迁移的入口判断。只导航，不代替阶段 skill 执行。
---

# Impl-Package

Impl-Package 把一次变更组织为可裁剪的链路：Decision/Spec contract ensemble → Plan → Ticket-only Composition → execution state → verification → Gate → stable-doc backfill；旧 package 的 Task/DAG 只经迁移 Runbook 处理。

## 核心原则

- 只保存会改变下一动作、阻止 false PASS 或约束危险 mutation 的状态；D/S/P 只作为可选的人类可读别名，不是新 package 的必填字段，也不绑定文件内容。
- 机械操作（状态、Ticket、evidence、Gate、trail 的写入）一律走 `../../scripts/impl_package_state.py` 的语义 CLI；被拒就按错误信息处理。正式规则见 [Composition Contract](../../references/impl-package-composition-contract.md) 与 [Current State](../../references/impl-package-current-state.md)；Codex hook 见 [Codex Hooks](../../references/codex-hooks.md)。

## 入口：阶段命令

路由统一使用 `/plugin:skill` 调用形式；下表同时保留宿主 native command index（`impl-*`）与跨宿主路由。宿主内部 registry/discovery 显示的无 `/` skill key 不是第二种文档写法。

| native entry | 跨宿主 route | 用途 |
| --- | --- | --- |
| `impl-req-align` | `/impl-package:req-align` | 需求/Decision/Spec 对齐 |
| `impl-grill-me-smartly` | `/impl-package:grill-me-smartly` | 高风险 Spec gate 的审问：Answerer 代答可查事实，判断题回 Owner |
| `impl-impl-planning` | `/impl-package:impl-planning` | 创建 initial/patch plan、决定 Composition |
| `impl-plan-review` | `/impl-package:plan-review` | 审查 plan 或完整 Plan/Ticket/DAG bundle |
| `impl-to-tickets` | `/impl-package:impl-planning` 的 Ticket-split | 创建独立验收切片 |
| `impl-dispatcher` | `$dispatcher` | 候选选择、bounded brief、dependency/resource admission、dispatch/return/review 与 idle；进入执行阶段先读其「执行原则」四行 |
| `impl-dev-with-track` | `/impl-package:dev-with-track` | 恢复执行、确定业务重点与候选范围、消费 Dispatcher 结果、推进 Ticket 与写 Gate |
| `impl-monitor-progress` | `/impl-package:monitor-progress` | 打开实时进度页面，并可选创建只读主控监控 automation |
| `impl-do-review` | `/impl-package:do-review` | 多 reviewer 编排、fail-closed 聚合 findings 并判断收敛 |
| `impl-review-code` | `/impl-package:review-code` | 审查实现正确性、仓库规范与可维护性 |
| `impl-review-code-by-spec` | `/impl-package:review-code-by-spec` | 按需求、Spec、Plan 审查实现忠实度 |
| `impl-safety-review` | `/impl-package:safety-review` | 审查安全、数据完整性、并发和外部副作用 |
| `impl-backfill-stable-docs` | `/impl-package:backfill-stable-docs` | 回刷稳定知识或退休 package |

仅询问体系时停在本页；用户已明确阶段和动作时直达对应 skill。执行前授权、异常对账和 completion claim 不再有 standalone 入口，统一在 `dev-with-track`（Verify and Gate）；旧 Task/DAG 只由下面的“旧 package”章节承接。

## 最小 package

```text
<package>/
  decision.md            # 可选；轻量 Decision 也可在 spec.md
  spec.md
  contract-design.md     # 从属 spec.md；detailed | not-required
  plan.md
  tickets/               # Ticket-only Composition earned 时
  progress.md             # active Attempt 的 machine-owned 恢复投影
  execution/
    <attempt>/
      execution-record.md
  .impl-package/state.json
  gate.md                 # 首次 gate evaluation 时创建
```

新 package 统一使用 `tickets=true, dag=false` Ticket-only 合同；`dag=false` 是 3.4 兼容占位，不表示创建 Task/DAG。不要为审计完整感增加 artifact。每个新建或被修订的 Spec 都有从属 `contract-design.md`；默认 `Disposition: detailed`，精确语义已由 `spec.md` 完整承担时使用 `Disposition: not-required` 并写明理由。未触及的 legacy Spec 到下次 req-align 再补齐；该文件没有独立 alias、revision、状态、审批或生命周期。

## 旧 package

新 package 一律不创建 Task DAG。仅当 owner 明确授权恢复/迁移已有 3.4 package（`dag=true` 或带 Task/DAG）时，按 [Ticket-first 迁移 Runbook](../../references/ticket-first-migration-runbook.md) 迁移：把真实产物映射回 Ticket claim，不把 Task handoff 或 `DONE` 当 acceptance proof。
