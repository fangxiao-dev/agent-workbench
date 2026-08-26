# Spec Gate: Contract Completeness and Conditional Scrutiny

只在 initial Decision PASSED 后读取。Spec 阶段先完成 Spec Design Preflight 与 contract design，Gate 最后验证已经声明的范围；同一 package 的 follow-up 更新直接使用 initial approval。Gate 聚焦已声明范围的完整性；DTO、persistence boundary 与 CAS 由 Spec Design Preflight 形成。

## Gate inputs

Gate 读取当前 `spec.md`、其“Spec 设计范围”、从属 `contract-design.md`、Decision outcomes、repository facts 与 Acceptance Semantics。`contract-design.md` 与 `spec.md` 共用 Status、approval 和 Gate，不形成第二套 behavior contract；`not-required` 必须说明 `spec.md` 如何完整承担精确语义。未触及的 legacy Spec 只在下次 req-align 时补齐。

## Pass criteria

Spec 只有同时满足以下条件才可 PASSED：

- 设计范围列出当前全部具体 API operations、persistence models、cross-module seams 与 public read models，并为每项指向唯一规范 owner；
- 每个 declared surface 满足 [Contract Surface Design](contract-surface-design.md) 的适用下限；
- contract coherence 已闭合：required input 可取得；有副作用、并发或重试风险的 operation 已逐项定义 identity、重复/stale 结果与恢复；每个可观察字段，以及行为/状态机/工作流表与错误边界表中每一个用户可见结果，都有唯一 authority，并能指到承载它的 read-model 字段与实际 producer；
- 八个 behavior-contract 章节 substantive，behavior、state/workflow、permission/boundary、error/recovery 与 canonical model 内部一致；
- 每个 promise/constraint 映射到 observable evidence，并为 manual evidence 指定 owner；
- 每条 AC 恰好覆盖一个权威转换：用户完成一个动作、成功后系统产生一份新的权威记录，下游从此读取它；
- blocking owner decision、contract ambiguity 与 artifact authority conflict 为零；
- 两个独立实施者可以选择不同内部实现，但不会产生不同 API、data identity、permission、concurrency、recovery 或 public shape。
- initial artifact 已记录当前合同，所需 owner approval 已记录，Status、Gate result 与 handoff readiness 一致；正式阶段迁移以该 bundle 记录为依据。

Gate 可以发现设计范围与正文之间的明显漏项；发现后返回 Preflight 修正范围与设计。若 Plan 仍需决定可观察语义或 canonical contract，记录 exact missing contract 并 `BLOCKED`，不交给 planning。

完整交互中存在无法取得的 required input、未裁决的重复 authority、未闭合的 retry/concurrency/recovery 语义，或没有 authoritative producer 的承诺输出时，Gate 必须 `BLOCKED`。先报告最小断点；不要求为无相关风险的 operation 发明幂等、恢复或额外持久化机制。

`spec.md`/`contract-design.md` 不得包含 stable-doc backfill maps、durable-delta queues、Composition、worker steps、verification command logs 或 tracker publication metadata。

## Blocked persistence

能在当前对话中关闭的 Preflight blocker 只留在 working output，关闭后再写 formal Spec。只有阻断使本轮必须暂停、跨 session 或等待 owner/外部条件时，才持久化简短的 `Spec Gate Blocked` 与恢复入口；不为当场可回答的问题制造额外状态。

## Conditional evidence-integrity contract

仅当 acceptance 依赖可能造成 false PASS 的 evidence authority、comparison、publication、compatibility 或 consumption 时评估，例如 external-provider proof、durable current pointer、atomic publish/archive、external mutation、projected schema 或 state-varying public payload。

信号出现时，在现有 contract owner 中定义 authoritative sources、comparison units/normalization、trusted inputs 与 commit-point revalidation、post-side-effect failure 与 compensation/invalidation、完整 compatibility admission、safe observable failure surface 与 stable public shape。false-PASS counterexamples 必须可测试；不要增加第九个 behavior section，也不要把该流程施加到普通变化。

## Risk-driven Grill

只有用户明确要求，或存在 unresolved material ambiguity、cross-module/external interface、migration/compatibility、security/data authority、destructive external mutation、evidence-integrity false-PASS risk 等高风险信号时，运行 `/impl-package:grill-me-smartly`。它不能静默应用 clarification。

Ledger 位于 OS temp，不进入 package。向用户汇总 converged decisions 与 owner decisions；initial bundle 的 owner decision 是规划入口的必要输入。initial bundle 完成 owner approval；Spec PASSED 后的同一 package clarification 可直接更新 current Spec，`/impl-package:grilling` 仍只是可选 deeper review。
