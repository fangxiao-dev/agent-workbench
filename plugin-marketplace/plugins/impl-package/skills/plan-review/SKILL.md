---
name: plan-review
description: Review an implementation plan or complete plan/Ticket/DAG bundle for feasibility, scope, architecture, tests, risk, and decision readiness; optionally verify a focused closure batch.
---

# Plan Review

审查实际 candidate 并返回判决，不做审计机械；review 只读，approved edits 由 bound bookkeeper 写入。初始 bundle 的 review 产出最终 owner approval，同 package 后续沿用。

## 判定
- mode 省略时 full-review；bundle-admission 仅当 bundle 完整、低风险、无跨模块 material seam、无安全/数据/外部 mutation 信号且 Planned Verification 足以裁决时返回 admitted，否则路由 full-review，不得以 admission 降强度。
- material finding：改变行为、安全、可行性、验收、权限或执行顺序；editorial 不算。每项给 evidence→impact→recommendation；仅当证据支持两个以上 material 不同有效结果时才请求 owner decision。
- verdict：cleared | revise | owner-decision | blocked；admission 只出 full-review/admitted；focused closure 只出 closure-verified/reopen-full-review 且只核对预先列明的集合。
- full-review 至少一个 fresh independent reviewer，只给 candidate 与 source contracts；有限 decision waves 收敛：完整 material batch → owner decision → 一个 closure batch → 只重审 affected scope。不建 review ledger/manifest/内容绑定。

## 机制
- 专项清单按需读 references/（scope/architecture/test/performance/code-quality、decision-policy）；独立 reviewer prompts 见 subagent-prompts.md；输出模板见 final-report.md（先 verdict、material finding 数、是否剩 owner decision，再 findings 与最小下一动作）。
