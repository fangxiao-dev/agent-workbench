---
name: impl-planning
description: 当已有批准的 Decision/Spec，需要创建 initial/patch plan、决定 Ticket-only Composition、执行策略或验证计划时使用；不维护长期行为合同或运行状态。
---

# Impl Planning

为一个 implementation attempt 创建简洁、可执行的 plan。先读 `../../references/impl-package-composition-contract.md`；需要为 material seam 选择验证层级时再读 `../../references/progressive-system-evidence.md`。

## 输出与规则

- initial：`plan.md`；patch：`<attempt-id>.patch-plan.md`。
- 必填 Attempt ID、阶段 A 兼容写法 `Composition: tickets=true, dag=false`、Coverage & Change Map、执行策略、Planned Verification、集成顺序和下一动作。
- Plan 直接引用当前 `decision.md` / `spec.md` 路径；D/S/P 仅为可选旧别名，不要求因普通编辑升级。
- 所有文件/evidence 引用使用仓库相对路径。
- plan 不复制 Decision/Spec contract ensemble、Ticket 状态或通用 checklist；新 plan 不建立 Task 状态轴。
- 只有 Ticket 能减少验收歧义时才 earned；DAG/Task 只在旧 package 迁移/恢复计划中作为只读输入。

Plan 的语义、Coverage、执行策略和 Planned Verification 仍由本 Skill 与主 thread 拥有；Plan artifact 的物理写入、state 初始化和 Progress 投影由绑定的 `/impl-package:standing-bookkeeper` 执行。主 thread 不直接编辑当前 package 的 Plan 或 runtime state。

## 流程

1. initial 读取已批准 Decision、`spec.md`、从属 `contract-design.md` disposition，以及当前代码/测试事实，确认 D/S gate 已通过；未触及的 legacy Spec 可暂缺该文件，同一 package 的 patch/update 沿用 initial bundle approval。
2. 在让 bookkeeper 创建或更新 Plan/state 前执行 admission backstop：若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，停止 planning，明确缺失合同并路由 `/impl-package:req-align` 重新确认当前 Spec。不得创建或更新 Plan/state，也不得在 Plan 中补第二套 DTO/schema。
3. 判断是 initial 还是 patch；patch 只描述相对上次 terminal gate 的实际 delta。
4. 新 package 固定选择 `tickets=true, dag=false`；`dag=true` 只允许在旧 package 迁移/恢复计划中出现。
5. 将每个 Decision/Spec 约束映射到实现范围及 Ticket，写执行顺序、修改边界、依赖、集成/回滚方式和足以区分正确/错误实现的验证；每个验证项明确 evidence owner。Coverage Map 可以引用 `spec.md` 或其从属 `contract-design.md` 的稳定章节。把 early falsification evidence、remaining completion evidence 和不可延后安全不变量分开写。
6. `tickets=true` 时调用 `/impl-package:to-tickets`；新 package 不调用 `create-task-dag`。
7. 初始 bundle 冻结 plan candidate；调用 `/impl-package:plan-review` 的 `bundle-admission`。返回 `full-review` 时继续同一 skill 的完整审查；处理 material findings，并联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，然后请求一次完整 bundle approval。后续 patch/update 直接沿用该 approval。
8. 获批后，主 thread 将 Attempt ID、canonical Plan 路径、bundle approval 和下一动作交给 bound bookkeeper；由 bookkeeper 运行：

```text
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> package init --attempt <id> --plan <repo-relative-plan>
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> package validate
```

`<impl-package-plugin-root>` 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。

9. 进入 `/impl-package:execution-preflight`，再交给 `/impl-package:dev-with-track`。

bookkeeper 完成写入、state 初始化和 `package validate` 后返回 receipt；主 thread 复核 receipt。初始 bundle approval 在同一 package 内跨 session、patch 和普通更新持续有效，作为唯一 approval receipt。

## 完成条件

- plan 与 Decision/Spec 语义一致，无 `TBD` blocker；
- Coverage & Change Map 覆盖全部 active 约束，Planned Verification 可执行且有 owner；
- 新 package 的 Ticket 必须存在并与当前 Attempt 一致；旧 package 迁移计划如需读取 DAG，必须标记为 legacy-only；
- 初始 bundle review/approval 已完成；后续 patch 直接沿用该 approval；
- `state.json` 已初始化并通过 validate；
- owner 能从汇报直接判断能否进入执行。

初始 approval 后，同一 package 的 plan、contract、state、evidence 和 execution 更新直接继续；review 结果写入现有记录并沿用该 approval。
