---
name: req-align
description: 当新增或变更 requirement 需要判断 contract impact，或需要创建、审查、修订、更新 Decision/Spec 时使用；在 implementation planning 前路由 no-contract fast path、Decision/Spec gates 及其 decision.md/spec.md artifacts。
---

# Requirement Alignment

把一次 contract-impacting change 路由为 Decision、Spec 或两者，并保持 package、artifact 与下游 handoff 只有一个 owner。本 Skill 是公共入口；Decision 与 Spec 的内容工作由内部 SUB-SKILL 执行。

## 路由

| 用户意图 | 路由 |
| --- | --- |
| 未显式限定阶段 | full：Decision PASSED 后进入 Spec |
| 明确“仅 Decision” | decision-only：Decision 得出 PASSED/BLOCKED 后停止 |
| 明确“仅 Spec / 只做 Spec 设计” | spec-only：验证现有 Decision 前置后直接进入 Spec |

spec-only 可以使用当前 passed `decision.md`、当前 `spec.md` 的 Passed Decision Gate Record，或同 session 已确认且满足 lightweight Decision Gate 的完整方向。它只跳过 Decision 的产出过程，不跳过前置验证；前置缺失或已被 delta 失效时返回阻断，不静默改跑 full。

## Ownership 与 fast path

本 Skill 拥有 configured implementations root（默认 `docs/implementations/`）下 package 的 current `decision.md`、`spec.md`、earned `contract-design.md` 与可读 D/S aliases。它不创建 tracker spec、第二套 behavior contract、plan 或 runtime state。

当 business result、Acceptance Semantics、security/data constraints 与 mutation authority 均未变化时，走 no-contract fast path：复用仍有效的 D/S，说明现有合同为何继续成立，并直接路由 owning skill。删除只要改变 promise 或 acceptance boundary，就仍是 contract-impacting。

## 主路径

1. 分类 contract impact；需要 D/S 时识别 initial、follow-up 或 package closure，并读取 [Package Lifecycle](references/package-lifecycle.md)。
2. 解析 canonical package 与当前 Decision/Spec。follow-up 默认把输入视为当前文档的 delta；只有 owner 明确声明 full replacement 才整体替换。
3. full 或 decision-only 读取并执行 [Decision SUB-SKILL](sub-skills/decision/SUB-SKILL.md)。Decision `BLOCKED` 时停止，不创建 Spec。
4. full 在 Decision `PASSED` 后、或 spec-only 前置验证通过后，读取并执行 [Spec SUB-SKILL](sub-skills/spec/SUB-SKILL.md)。Spec `BLOCKED` 时不进入 planning。
5. 两个 Gate 均通过且 lifecycle registration 有效时，把同一 Spec contract ensemble 交给 `/impl-package:impl-planning`。
6. 直接引用当前 Decision/Spec 路径，记录用于 module-knowledge/code 比较的 Git commit；implementation attempt 获批前不创建 runtime state。
7. 汇报任何 Gate 结果前读取 [Handoff](references/handoff.md)，输出最具体的可恢复状态。

Package ID 创建后不得改名。后续 requirement delta 先按 implementation-only / behavior-contract / decision-direction 分类，只使真正受影响的下游范围失效。

## 完成条件

- fast path 已证明现行合同继续成立，或请求已完成所选 route 的全部 Gate；
- Decision、Spec 与 optional detailed contract 没有平行 authority；
- blocked 状态说明 exact missing decision/contract 与下一有效动作；
- ready 状态只在 planning 不再需要发明行为或数据合同后成立。

## 输出

用业务语言说明 focused requirement、selected direction、route、Gate results、blockers/owner decisions 与下一有效步骤。发生 artifact 写入时，报告 canonical package、Decision/Spec evidence，以及存在时的 `contract-design.md`；不要粘贴完整 artifact。
