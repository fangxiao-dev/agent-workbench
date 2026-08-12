---
name: impl-planning
description: 当已有批准的 Decision/Spec，需要创建 initial/patch plan、决定 tickets/DAG Composition、执行策略或验证计划时使用；不维护长期行为合同或运行状态。
---

# Impl Planning

为一个 implementation attempt 创建简洁、可执行的 plan。先读 `../../references/impl-package-composition-contract.md`；需要为 material seam 选择验证层级时再读 `../../references/progressive-system-evidence.md`。

## 输出与规则

- initial：`plan.md`；patch：`<attempt-id>.patch-plan.md`。
- 必填 Attempt ID、`Composition: tickets=..., dag=...`、Coverage & Change Map、执行策略、Planned Verification、集成顺序和下一动作。
- Plan 直接引用当前 `decision.md` / `spec.md` 路径；D/S/P 仅为可选旧别名，不要求因普通编辑升级。
- 所有文件/evidence 引用使用仓库相对路径。
- plan 不复制 Decision/Spec contract ensemble、Ticket、Task 状态或通用 checklist。
- 只有 Ticket/DAG 能减少验收或执行歧义时才 earned。

## 流程

1. 读取已批准 Decision、`spec.md`、其“Spec 设计范围”声明为 earned 的 `contract-design.md`，以及当前代码/测试事实，确认 D/S gate 已通过。
2. 在创建或更新 Plan/state 前执行 admission backstop：若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，停止 planning，明确缺失合同并路由 `/impl-package:req-align` 重新确认当前 Spec。不得创建或更新 Plan/state，也不得在 Plan 中补第二套 DTO/schema。
3. 判断是 initial 还是 patch；patch 只描述相对上次 terminal gate 的实际 delta。
4. 选择四种 Composition 之一，并用一句话解释每个 `true`。
5. 将每个 Decision/Spec 约束映射到实现范围及 Ticket/Task，写执行顺序、修改边界、依赖、集成/回滚方式和足以区分正确/错误实现的验证；每个验证项明确 evidence owner。Coverage Map 可以引用 `spec.md` 或其从属 `contract-design.md` 的稳定章节。
6. `tickets=true` 时调用 `/impl-package:to-tickets`；`dag=true` 时调用 `/impl-package:create-task-dag`。
7. 冻结 plan candidate；调用 `/impl-package:plan-review` 的 `bundle-admission`。返回 `full-review` 时继续同一 skill 的完整审查；处理 material findings，并联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，然后请求一次完整 bundle approval。
8. 获批后运行：

```text
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> init --attempt <id> --plan <repo-relative-plan>
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> validate
```

`<impl-package-plugin-root>` 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。

9. 进入 `/impl-package:execution-preflight`，再交给 `/impl-package:dev-with-track`。

跨 session approval 需要明确当时批准内容所在的 Git commit；同 session 且 candidate 未变化时无需额外 receipt。

## 完成条件

- plan 与 Decision/Spec 语义一致，无 `TBD` blocker；
- Coverage & Change Map 覆盖全部 active 约束，Planned Verification 可执行且有 owner；
- earned Ticket/DAG 均存在并与当前 Attempt 一致；
- bundle review/approval 已完成；
- `state.json` 已初始化并通过 validate；
- owner 能从汇报直接判断能否进入执行。

approval 后的语义变化必须重新打开 plan freeze，并只重审受影响 scope；排版或 projection 修复在实际 diff 不改变合同的前提下无需全量 review。
