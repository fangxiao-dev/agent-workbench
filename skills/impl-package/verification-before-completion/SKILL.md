---
name: verification-before-completion
description: 在宣称工作 complete、closed、fixed、passing、merge-ready 或 release-ready 前使用；把每项 claim 与同 revision、同 environment 的直接 evidence 对齐，并准确报告 verification gap。
---

# Verification Before Completion

Completion claim 不能宽于 evidence。Verification 是 claim-to-evidence contract，不要求在当前消息里机械重跑所有可能的检查。

## Impl-Package orchestration

本 skill 是 Impl-Package 的 completion-claim evidence gate。它不是 DAG task，也不按 ticket 或 implementation unit 重复运行。

局部进度、单个文件已修改、某个定向 validator 通过或“完成了第 N 步”属于 scoped status，不是 terminal completion claim。此类陈述只需引用对应直接 evidence，不运行完整 Impl-Package terminal audit、Stage 7 或全量 gate 对账。只有准备写 terminal pass，或声称整个约定范围 complete/closed/fixed/merge-ready/release-ready 时才进入本节完整 orchestration。

- `dev-with-track` 在适用 implementation review、package 级 execution findings closure 和拟 pass 的 Stage 7 artifact 准备完成后、写入 terminal `pass` gate entry 前调用本 skill。
- terminal metadata commit、目标分支合入或相关 environment 变化后，在宣称 `complete`、`closed`、`merge-ready` 或 `release-ready` 前再次调用。复用未受影响的 evidence，只验证 delta 与 claim-specific gate。
- 已合入目标分支但尚无 terminal gate 时，真实状态是 `Integrated, gate open`；只能报告 integration 阶段，不能把 merge 当成 closed evidence。
- 默认 `gate-before-merge` 下，current attempt 的 finalized `pass` 是 merge 前提；`blocked`、`fail`、`defer`、没有 gate.md 都不能支持 merge-ready claim。若已经 pre-gate integration，必须从 plan 核对该 integration 前已记录的 owner authorization。没有该证据时报告 process violation；不得事后把授权或 terminal pass 倒灌到已发生的 merge。
- 若当前 diff 只实现了 spec 的一部分 AC，completion claim 只能覆盖该明确边界的子切片。除非 Decision/Spec/Plan 已同步将 attempt 收窄或分拆，否则不得把局部 merge、测试或 schema rollout 说成完整 package / issue closure。
- proof 缺失或 stale 时，阻止的是 completion claim，不一定否定 implementation。应报告 `implemented, not verified` 或具体 pending gate，不能写入或重复 pass claim。
- 本 skill 审计 evidence，不替代 `code-review`、`module-review`、`safety-review`、planned test、smoke 或项目特定 acceptance。

## 定义 claim

报告成功前先说明 claim 的范围：

- 某个具体 behavior 可用；
- 某项定向检查 passing；
- 某个 implementation phase complete；
- 某个 merge、release 或 production gate 已满足。

定向 claim 可以使用定向 evidence；宽泛 readiness claim 必须覆盖所有相关 gate。

## Evidence contract

Evidence 同时满足以下条件时才可使用：

- 直接执行或检查被 claim 的 behavior；
- 来自同一 worktree、revision 与相关 environment；
- 晚于最后一次可能影响结果的变化；
- 包含 command/procedure、exit status、failure count 和决定性 artifact；
- 覆盖 repository 对该 claim 要求的 gate。

不要用相邻 evidence 替代：lint 不能证明 build，unit test 不能证明 integration，passing regression test 本身也不能证明原始 symptom 已解决。

## 复用与独立 verification

当 provenance 清楚且相关 revision/environment 未变化时，可以复用 subagent、Execution Record、CI run 或较早 turn 的完整 evidence。必须检查 evidence 与实际 diff，不能只相信 success label。

出现以下情况时运行独立或更宽的 verification：

- evidence 不完整、stale、相互冲突或来自不同 revision/environment；
- evidence 之后的变化可能影响结果；
- claim 属于高风险 merge、release、migration、security、data-integrity 或 external-side-effect gate；
- project policy 明确要求当前 owner fresh run。

不要为了制造 RED evidence 而临时回退 fix，尤其当该操作不安全时。使用已有 failing run、受控 worktree、test fixture mutation，或明确记录没有独立证明 RED。

## 报告真实状态

- Evidence 覆盖 claim：陈述 claim 并引用 evidence。
- Implementation 已存在但 verification 缺失：报告 `implemented, not verified`。
- Verification 已运行但失败：报告 failure 与剩余工作。
- 部分 gate 通过、其余仍待处理：明确已完成阶段与 outstanding gate，不得称整个任务 closed。

不得把 confidence、agent report 或局部相邻检查转化为 completion claim。
