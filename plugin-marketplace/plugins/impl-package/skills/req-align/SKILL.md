---
name: req-align
description: 当新增或变更 requirement 需要判断 contract impact，或需要创建、审查、修订、更新 Decision/Spec 时使用；在 implementation planning 前路由 no-contract fast path、Decision/Spec gates 及其 decision.md/spec.md artifacts。
---

# Requirement Alignment

把 contract-impacting change 路由为 Decision、Spec 或两者，保持 package 与 artifact 单一 owner。内容工作由内部 SUB-SKILL 执行，按需读取，不进主 session 默认上下文。

## 路由判定

- full：Decision PASSED 后进入 Spec；decision-only：Decision 得出 PASSED/BLOCKED 后停止；spec-only：验证现有 Decision 前置后直接进入 Spec。初始 bundle 仍做前置验证；同一 package 的 follow-up 沿用初始 approval，输入默认视为当前文档 delta，只有 owner 明确声明才整体替换。

- contract impact 分类：implementation-only 沿用当前文档进入当前 plan 或新 patch plan；behavior-contract 更新当前 Spec；decision-direction 更新 Decision 与 Spec；只使真正受影响的下游范围失效。business result、Acceptance Semantics、security/data constraints 与 mutation authority 均未变化时走 no-contract fast path：复用仍有效的 D/S 并说明为何继续成立，直接路由 owning skill；删除只要改变 promise 或 acceptance boundary，就仍是 contract-impacting。

## 机制与边界

- 机械操作一律走现有语义 CLI；formal artifact 的物理写入与 focused validation 由 bound bookkeeper 执行，本 Skill 不直接写 package artifact，不创建 tracker spec、plan 或 runtime state。

- 生命周期、影响路由细节与 module-knowledge baseline 按需读 references/package-lifecycle.md；初始 bundle 的 Gate 判据按需读 decision-gate.md / spec-gate.md；汇报前读 references/handoff.md 输出最具体的可恢复状态。

- 完成条件：fast path 已证明现行合同继续成立，或所选 route 的全部 Gate 已通过；Decision、Spec 与从属 contract-design 无平行 authority；blocked 状态说明 exact missing contract 与下一有效动作；ready 只在 planning 不再需要发明行为或数据合同后成立。
