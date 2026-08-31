---
name: req-align
description: 当新增或变更 requirement 需要判断 contract impact，或需要创建、审查、修订、更新 Decision/Spec 时使用；在 implementation planning 前路由 no-contract fast path、Decision/Spec gates 及其 decision.md/spec.md artifacts。
---

# Requirement Alignment

把一次 contract-impacting change 路由为 Decision、Spec 或两者，并保持 package、artifact 与下游 handoff 只有一个 owner；本 Skill 是公共入口，内容工作由 [Decision SUB-SKILL](sub-skills/decision/SUB-SKILL.md) 与 [Spec SUB-SKILL](sub-skills/spec/SUB-SKILL.md) 执行，按需读取，不进主 session 默认上下文。

## 路由

| 用户意图 | 路由 |
| --- | --- |
| 未显式限定阶段 | full：Decision PASSED 后进入 Spec |
| 明确“仅 Decision” | decision-only：Decision 得出 PASSED/BLOCKED 后停止 |
| 明确“仅 Spec / 只做 Spec 设计” | spec-only：验证现有 Decision 前置后直接进入 Spec |

spec-only 可以使用当前 passed `decision.md`、当前 `spec.md` 的 Passed Decision Gate Record，或同 session 已确认且满足 lightweight Decision Gate 的完整方向；初始 bundle 仍做前置验证，同一 package 的 follow-up 直接沿用初始 approval。

## Ownership 与 fast path

本 Skill 拥有 configured implementations root（默认 `docs/implementations/`）下 package 的 Decision、Spec、从属 `contract-design.md` 与可读 D/S aliases 的语义和内容；每个新建或被修订的 Spec 都生成该从属文件，未触及的 legacy Spec 到下次 req-align 再补齐。当前 package artifact 的物理写入和 focused validation 由绑定的 `/impl-package:execution-boundaries` 执行；本 Skill 不创建 tracker spec、第二套 behavior contract、plan 或 runtime state。

当需要创建或更新 Decision/Spec contract ensemble 时，主 thread 先把已确认的结论、必要依据和依赖性发送给 bound execution-boundaries；由其按本 Skill 与对应 sub-skill 定位并写入 canonical artifact，主 thread 保留 contract 语义、Gate 和最终采信权。机械操作一律走现有 typed tools/语义 CLI；状态变更命令的当前处境与协议尾注由 `situation.py` 按 `situations.yaml` 注入。

当 business result、Acceptance Semantics、security/data constraints 与 mutation authority 均未变化时，走 no-contract fast path：复用仍有效的 D/S，说明现有合同为何继续成立，并直接路由 owning skill；删除只要改变 promise 或 acceptance boundary，就仍是 contract-impacting。
   - 常见误判：只因为改动看起来像删除或普通实现变化就跳过合同判断，会把已经改变的 promise 或 acceptance boundary 隐藏在 fast path 后面。

## 主路径

1. 分类 contract impact；需要 D/S 时先查找相关 package。没有相关 package，或相关 package 不适合 patch 时，按 initial 新建 package；存在可 patch 的相关 package 时，必须先询问 Owner 是否进入 patch 模式，获得显式确认前保持旧 package 只读，不得把本次输入当作 follow-up 或修改其 artifact。确认路由后识别 initial、follow-up 或 package closure，并读取 [Package Lifecycle](references/package-lifecycle.md)。
   - 常见误判：把 behavior-contract 或 decision-direction 变化当成 implementation-only，或仅因找到相关 package 就静默进入 follow-up，会分别让下游消费失效 D/S，或改写尚未获准 patch 的旧 package。
2. 解析 canonical package 与当前 Decision/Spec；已确认 patch 的 follow-up 默认把输入视为当前文档的 delta，只有 owner 明确声明 full replacement 才整体替换。
   - 常见误判：把普通 delta 当 full replacement，会静默丢掉未重复提及但仍需 carry forward 的 promise。
3. initial 的 full 或 decision-only 读取并执行 [Decision SUB-SKILL](sub-skills/decision/SUB-SKILL.md)；同一 package 的 follow-up 直接更新当前 Decision 并沿用初始 approval。
   - 常见误判：没有先经过 Decision 就让 Spec 或 Plan 决定方向，会把 implementation candidate 提升成 product promise。
4. initial 的 full 在 Decision `PASSED` 后、或 spec-only 前置验证通过后，读取并执行 [Spec SUB-SKILL](sub-skills/spec/SUB-SKILL.md)；同一 package 的 follow-up 直接更新当前 Spec 并沿用初始 approval。
   - 常见误判：Decision 尚未 PASSED 就进入 Spec，会让行为合同建立在未闭合的方向和 blocking uncertainty 上。
5. initial bundle 的两个 Gate 均通过且 lifecycle registration 有效时，把同一 Spec contract ensemble 交给 `/impl-package:impl-planning`；follow-up 沿用该 bundle approval 进入后续工作。
   - 常见误判：只看到一个 Gate 通过就开始 planning，会把未完成的 contract surface 留给 Plan 临时发明。
6. 直接引用当前 Decision/Spec 路径，记录用于 module-knowledge/code 比较的 Git commit；implementation attempt 获批前不创建 runtime state，formal artifact 的物理写入交给 bound execution-boundaries。
   - 常见误判：在 attempt 获批前先创建 runtime state，会留下没有 approval provenance 的孤儿状态，也让 artifact 出现第二个写入 owner。
7. 汇报任何 Gate 结果前读取 [Handoff](references/handoff.md)，输出最具体的可恢复状态。
   - 常见误判：只报 PASSED/BLOCKED 而不带恢复入口，下一 session 无法判断缺口、owner decision 和下一动作。

Package ID 创建后不得改名；后续 requirement delta 先按 implementation-only / behavior-contract / decision-direction 分类，只使真正受影响的下游范围失效。

## 完成条件

- fast path 已证明现行合同继续成立，或 initial bundle 已完成所选 route 的全部 Gate；follow-up 已更新 current artifact 并沿用 initial bundle approval；
- Decision、Spec 与从属 contract-design 没有平行 authority，且 contract-design 已记录 `detailed | not-required` disposition；
- blocked 状态说明 exact missing decision/contract 与下一有效动作；ready 状态只在 planning 不再需要发明行为或数据合同后成立。

## 输出

用业务语言说明 focused requirement、selected direction、route、Gate results、blockers/owner decisions 与下一有效步骤；发生 Spec artifact 写入时，由 execution-boundaries 返回 canonical package、Decision/Spec evidence 与 `contract-design.md` disposition，主 thread 复核后汇报，不粘贴完整 artifact。
