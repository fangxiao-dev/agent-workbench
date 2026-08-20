---
name: req-align-decision
description: req-align 内部的 Decision 阶段；对齐 requirement inputs、Focused PRD、blocking uncertainty 与 Core/Capability，并产出 Decision Gate 结果。
---

# Decision Alignment

只在 `req-align` 路由到 full 或 decision-only 时执行。本 SUB-SKILL 拥有 Decision 内容与 initial bundle Gate；package 路径、Spec 与 Plan 由各自 owning skill 管理，同一 package 的 follow-up 只更新 current Decision。

## 输入

- 用户确认的 requirement 与当前 route；canonical package、当前 Decision/Spec 与 initial/follow-up 分类；
- repository instructions、authority sources、相关 code/tests 与允许的只读调查结果。

## 流程

1. 读取 [Requirement Inputs](../../references/requirement-inputs.md)、[Decision Gate](../../references/decision-gate.md)；earned Focused PRD 再读取 [Focused PRD](../../references/focused-prd.md)。
2. 发现 repository instructions、product/architecture authority、相关 code/tests 与预期但缺失的知识；durable project knowledge 需要变化时，针对已发现的 authoritative source 提案并等待 owner 批准，不发明长期落点。
3. initial 从已确认的对话、截图、文档和 repository facts 捕获全部 material promises；follow-up 先读当前 Decision/Spec，再把 delta 分类为 carry forward、add、modify、explicit remove 或 blocker，未重复提及等于 carry forward。
4. 对 Core/Capability、repository fit、delivery path、material choices 与每个 unknown 做 blocking-decision triage；普通 task-scoped read-only investigation 直接执行，需新权限、副作用、实质成本、code spike、环境变化或 scope expansion 时持久化 `Decision Gate: BLOCKED`。
5. 用 [Alignment Proposal](../../assets/templates/alignment-proposal.md) 形成 working output；只有 discovery 与允许调查都无法关闭 intent、scope、trade-off 或 owner decision 时才问一个 focused question，proposal 不是 durable artifact。
6. earned Decision 使用 [Decision Template](../../assets/templates/decision.md)；主 thread 把已确定内容交给 bound `/impl-package:execution-boundaries` 写入并验证 `decision.md`，lightweight correction 在 Decision PASSED 后把最小 evidence 交给 Spec 的 Decision Gate Record，Decision BLOCKED 一律使用 `decision.md` 且不创建 Spec。机械写入走 typed/语义 CLI，回执可带当前处境协议。
7. 仅 initial bundle 运行 Decision Gate；目标落点、Focused PRD（适用时）、input reconciliation、Core/Capability、repository fit、material choices 与所有 blocking uncertainty 全部闭合后才可 PASSED，follow-up 更新直接沿用 initial approval。

## 完成条件

- 每个 material confirmed promise 都有当前 home、明确变更/排除或 blocker；
- 没有把 implementation candidate 提升为 product promise，也没有把 Spec/Plan 细节写入 Decision；
- initial PASSED 输出给出 selected direction、Spec contract boundary 与 evidence；
- BLOCKED 输出给出 exact investigation/owner decision 与恢复入口。

## 返回 router

返回 initial Decision Gate result，或 follow-up 更新后的 standalone `decision.md` / lightweight record、Spec 可消费的 boundary，以及 comparison evidence；artifact 的物理写入和 focused validation 由 bound `/impl-package:execution-boundaries` 完成，主 thread 负责采信结果。initial 的 decision-only 到此停止；initial full 只有 PASSED 才能进入 Spec。
