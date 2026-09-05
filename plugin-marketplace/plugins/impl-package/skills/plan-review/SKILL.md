---
name: plan-review
description: Review an implementation plan or complete plan/Ticket/DAG bundle for feasibility, scope, architecture, tests, risk, and decision readiness; optionally verify a focused closure batch.
---

# Plan Review

审查实际 candidate 并返回判决，不做审计机械；review 只读，批准后的业务文档由 owning-stage 主 thread 直接更新，运行状态交给 `/impl-package:execution-boundaries` 记账 subagent。初始 Decision/Spec/Plan bundle 的 review 产出最终 owner approval；同一 package 的后续 patch、closure 或记录更新沿用该 approval。

审查包含 Ticket 的 bundle 时先读 `../../references/impl-package-composition-contract.md`，用其中的 Ticket、typed dependency 与 stable claim acceptance atom 合同判断 candidate。

## Modes

- `full-review`：审查整个 candidate 并发现 material findings。
- `bundle-admission`：判断低风险且完整 bundle 是否可免 full review。
- `focused-closure-verification`：核对预先同意的有限 finding/decision batch；除非 scope 扩大，不重开一般发现。

mode 省略时使用 `full-review`。`bundle-admission` 只有在 bundle 完整、低风险、无跨模块 material seam、无安全/数据/外部 mutation 信号且 Planned Verification 足以裁决时返回 `admitted`；否则路由 `full-review`，不能用 admission 降低审查强度。

## Inputs

输入是 candidate plan 及（earned 时）Ticket/DAG bundle、Decision/Spec 与相关 repository facts、target branch/worktree/current Git commit，以及可选的 prior closure brief 或 owner decisions。持久化到 review artifact 的路径必须是 repository-relative；D/S/P 只是可读别名。初始 bundle approval 记录其 Git commit，同 package 后续 review 直接沿用该 approval；review outcome 可由 current Attempt 的 Execution Record judgment 引用，不创建 review ledger、manifest、preimage receipt 或内容绑定。

## Review

1. **锚定 candidate**：Fix the candidate Git commit，或在 same-session unchanged working-tree candidate 上明确保持不变；`full-review` 至少派发一个 fresh independent reviewer，只给 candidate 与 source contracts，不喂先前结论。
2. **确认前置完整性**：确认 candidate 对其声明的 Composition 完整，并与 Decision/Spec 一致。
   - 对每个声明的前置包，检查本包的 `NEW` 声明是否覆盖该前置包已经建好的能力。
3. **审查维度**：按以下顺序逐项检查：
   1. **完整性**：对照 Decision/Spec 结构与全部 Ticket 的 Contract references 与 AC，确认 candidate 对其声明的 Composition 完整；Plan 不再维护独立 Coverage & Change Map 表格，完整性核对直接读 Ticket 集合。否则可能只实现 happy path，留下无法验收的半套接线。
   2. **范围**：scope，检查真实消费者、跨平台镜像、旧布局/旧 contract 入口以及 `NOT in scope`；否则遗漏或静默扩大的范围会在实施时才暴露。
   3. **顺序**：sequencing，检查前置依赖、迁移窗口、integration point 和 release gate 的先后；否则依赖未释放或迁移窗口错位会让计划不可执行。
   4. **结构**：architecture/seams，检查组件责任、依赖方向、数据流、失败隔离和跨边界耦合；否则 ownership 与真实生产失败场景会被推迟到实施阶段才发现。
   5. **验证**：Planned Verification，确认每个 material behavior 有入口、测试层级、可观察 oracle 和 evidence owner；否则“增加测试”不能区分正确实现与常见错误实现。
   6. **回退**：rollback，检查兼容、迁移、拒绝、归档或 compensation 语义；否则破坏性变化会把恢复方案留给实施者猜测。
   7. **归属**：ownership/dependencies，确认 owner、handoff、依赖释放和真实消费者边界；否则没有明确责任人承接失败、迁移或发布协调。
   8. **验收**：Ticket AC，检查验收条件是否能落到可验证行为与 evidence，并按 Composition Contract 确认 stable claim 已原子化；可独立失败或依赖不同 oracle/evidence lane 的子句共用一个 claim 时返回 `revise`，同一不可分割 oracle 裁决的一组场景不强拆。否则 runtime 可能用部分 evidence 错误满足整个 Ticket。
   9. **授权**：integration authorization，确认 bundle approval、owner decision 和 integration gate；否则执行可能先于授权改变方案结果或产生不可逆影响。
4. **区分问题类型**：material finding 会改变 behavior、safety、feasibility、acceptance、authority 或 execution order；editorial improvement 单独归类。
5. **形成可执行结论**：每个 material item 给 evidence、impact、recommendation；仅当证据支持两个以上 material 不同有效结果时才请求 exact owner decision。
6. **有限 decision waves**：初始 bundle 形成完整 material batch，取得 owner decision，应用一个 closure batch，只重审 affected scope；初始 approval 后的更新可直接应用，review 只报告 affected scope/findings 并沿用既有 approval。

专项清单按需读 `references/scope-review.md`、`architecture-review.md`、`test-review.md`、`performance-review.md`、`code-quality-review.md` 和 `decision-policy.md`；独立 reviewer prompts 见 `references/subagent-prompts.md`，输出模板见 `references/final-report.md`。

## Verdicts

- `cleared`：无 unresolved material finding。
- `revise`：需要 actionable material changes。
- `owner-decision`：存在一个或多个 genuine choices 需要 owner input。
- `blocked`：required source material 缺失或矛盾。
- Admission 只返回 `full-review` 或 `admitted`；focused closure 只返回 `closure-verified` 或 `reopen-full-review`。

`focused-closure-verification` 只能核对预先列明的 finding/decision 及受影响范围；不得无限重新发现普通改进项，也不得在 candidate 扩大时假装 closure 仍有限。

## Apply boundary

初始 bundle approval 前，按 owner 要求形成 review edits，由 owning-stage 主 thread 写入显式 repository-relative 业务文档并验证；approval 后，同一 package 的 review edits 沿用该初始授权。Git 提供 history 与 rollback，review outcome 继续写入现有记录。

## Output

先给 verdict、material finding 数和是否仍有 owner decision，再列 findings 与最小下一动作；只有跨 session 复用有意义时才说明 reviewed Git commit。
