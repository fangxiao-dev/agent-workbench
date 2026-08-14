---
name: plan-review
description: Review an implementation plan or complete plan/Ticket/DAG bundle for feasibility, scope, architecture, tests, risk, and decision readiness; optionally verify a focused closure batch.
---

# Plan Review

Review the actual candidate and return decisions, not audit machinery. The review is read-only unless the owner separately asks to apply edits; approved package edits are physically applied by the bound `/impl-package:standing-bookkeeper`.

初始 Decision/Spec/Plan bundle 的 review 产出最终 owner approval；同一 package 的后续 patch、closure 或记录更新均沿用该 approval。

## Modes

- `full-review`: inspect the whole candidate and discover material findings.
- `bundle-admission`: decide whether a low-risk complete bundle can proceed without full review.
- `focused-closure-verification`: verify a previously agreed finite finding/decision batch without reopening general discovery unless scope expanded.

If mode is omitted, use `full-review`.

`bundle-admission` 只在 bundle 完整、低风险、无跨模块 material seam、无安全/数据/外部 mutation 信号且 Planned Verification 足以裁决时返回 `admitted`；否则路由 `full-review`，不能用 admission 降低审查强度。

## Inputs

- candidate plan and, when earned, its Ticket/DAG bundle;
- Decision/Spec and relevant repository facts;
- target branch/worktree and current Git commit;
- optional prior closure brief or owner decisions.

Paths persisted in review artifacts must be repository-relative. D/S/P aliases are readable labels only. 初始 bundle 的 approval 记录其 Git commit；同一 package 的后续 review 直接沿用该 approval。

Review outcome 可由 current Attempt 的 Execution Record judgment 引用。不要创建 review ledger、manifest、preimage receipt 或内容绑定。

## Review

1. Fix the candidate Git commit（或 same-session unchanged working-tree candidate）。`full-review` 至少派发一个 fresh independent reviewer；只给 candidate 与 source contracts，不喂先前结论。
2. Confirm the candidate is complete for its declared Composition and matches Decision/Spec.
3. Check Coverage & Change Map、scope、sequencing、architecture/seams、Planned Verification、rollback、ownership/dependencies、Ticket AC 和 integration authorization。
4. Separate material findings from editorial improvements. A material finding changes behavior, safety, feasibility, acceptance, authority or execution order.
5. For each material item give evidence, impact, recommendation and the exact owner decision only when multiple valid product choices remain.
6. 初始 bundle 使用有限 decision waves 收敛：形成一个完整 material batch，取得 owner decision，应用一个 closure batch，只重审 affected scope。初始 approval 后的更新可直接应用；review 只报告 affected scope 和 findings，并沿用该 approval。

Useful checklists live in `references/scope-review.md`, `architecture-review.md`, `test-review.md`, `performance-review.md`, and `code-quality-review.md`.

## Verdicts

- `cleared`: no unresolved material finding.
- `revise`: actionable material changes are required.
- `owner-decision`: one or more genuine choices need owner input.
- `blocked`: required source material is missing or contradictory.
- Admission only: `full-review` or `admitted`.
- Focused closure only: `closure-verified` or `reopen-full-review`.

`focused-closure-verification` 只能核对预先列明的 finding/decision 集合及其受影响范围；不得无限重新发现普通改进项，也不得在 candidate 扩大时假装 closure 仍有限。

## Apply boundary

初始 bundle approval 前，按 owner 要求形成 review edits，由 bound bookkeeper 写入显式 repository-relative 文件并验证；approval 后，同一 package 的 review edits 仍沿用该 bookkeeper。Git supplies history and rollback；review outcome 继续写入现有记录。

## Output

Lead with verdict, material finding count and whether an owner decision remains. Then list findings and the smallest next action. State the reviewed Git commit only when it matters for cross-session reuse.
