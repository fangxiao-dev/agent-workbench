---
name: impl-planning
description: 当已有批准的 Decision/Spec，需要创建 initial/patch plan、决定 Ticket-only Composition、执行策略或验证计划时使用；当已批准 plan 判定需要至少两个独立跟踪 acceptance 结论的交付切片时也使用（合并原 to-tickets）；只创建 Plan/Ticket 合同，不维护长期行为合同、Task 或运行状态。
---

# Impl Planning（含 Ticket 拆分）

为一个 implementation attempt 创建简洁、可执行的 plan，并把验收拆成可独立验收的 Ticket 合同；先读 `../../references/impl-package-composition-contract.md`，需要为 material seam 选择验证层级时再读 `../../references/progressive-system-evidence.md`。Plan 的语义、Coverage、执行策略、Planned Verification 与 Ticket 语义由本 Skill 与主 thread 拥有，主 thread 不直接编辑当前 package 的 Plan 或 runtime state；物理写入、state 初始化和 Progress 投影由 bound `/impl-package:execution-boundaries` 执行。D/S gate 已通过才继续，未触及的 legacy Spec 可暂缺。

## 输出与规则

- initial 写 `plan.md`，patch 写 `<attempt-id>.patch-plan.md`；必填 Attempt ID、阶段 A 兼容写法 `Composition: tickets=true, dag=false`、Coverage & Change Map、执行策略、Planned Verification、集成顺序和下一动作。
- Plan 直接引用当前 `decision.md` / `spec.md` 路径；D/S/P 仅为可选旧别名，不要求因普通编辑升级；所有文件/evidence 引用使用仓库相对路径。
- Plan 不复制 Decision/Spec contract ensemble、Ticket 状态或通用 checklist，新 plan 不建立 Task 状态轴；只有 Ticket 能减少验收歧义时才 earned，DAG/Task 只在旧 package 迁移/恢复计划中作为只读输入。

## 流程

1. initial 读取已批准 Decision、`spec.md`、从属 `contract-design.md` disposition 及当前代码/测试事实，确认 D/S gate 已通过；未触及的 legacy Spec 可暂缺该文件，同一 package 的 patch/update 沿用 initial bundle approval。
2. 在让 execution-boundaries 创建或更新 Plan/state 前执行 admission backstop：若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，或 contract surface 命中幂等键 / CAS / 版本号、多个来源写同一个目标字段、替换 / 撤回 / 恢复语义、跨存储提交（两个 store 各自提交）或声明值 vs 检测值但 Spec 只有规则没有结果矩阵，停止 planning，明确缺失合同并路由 `/impl-package:req-align` 重新确认当前 Spec；不得创建或更新 Plan/state，也不得在 Plan 中补第二套 DTO/schema。
3. 判断是 initial 还是 patch；patch 只描述相对上次 terminal gate 的实际 delta。
4. 新 package 固定选择 `tickets=true, dag=false`；`dag=true` 只允许在旧 package 迁移/恢复计划中出现。
5. 将每个 Decision/Spec 约束映射到实现范围及 Ticket，写执行顺序、修改边界、依赖、集成/回滚方式和足以区分正确/错误实现的验证；每个验证项明确 evidence owner。Coverage Map 可以引用 `spec.md` 或其从属 `contract-design.md` 的稳定章节；把 early falsification evidence、remaining completion evidence 和不可延后安全不变量分开写。纵向切片装不下一个 worker 时，回去把该 seam 冻得更细，不要改成横向切分。
6. `tickets=true` 时执行本 Skill 的“Ticket 拆分”子流程；新 package 不调用 `create-task-dag`。
7. 初始 bundle 冻结 plan candidate 后调用 `/impl-package:plan-review` 的 `bundle-admission`；返回 `full-review` 时继续同一 skill 的完整审查，处理 material findings，并联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，然后请求一次完整 bundle approval；后续 patch/update 直接沿用该 approval。
8. 获批后，主 thread 将 Attempt ID、canonical Plan 路径、bundle approval 和下一动作交给 bound execution-boundaries；由当前已加载插件的 `impl_package_state.py` 语义 CLI 执行 `package init --attempt <id> --plan <repo-relative-plan>` 再执行 `package validate`。插件根目录以当前已加载 skill 所属的插件根目录为准，不假设 workbench 仓库路径或宿主缓存路径。
9. 进入 `/impl-package:execution-boundaries`，再交给 `/impl-package:dev-with-track`。

机械操作一律走 typed tools/语义 CLI；状态变更命令的处境与协议尾注由 `situation.py` 按 `situations.yaml` 注入。execution-boundaries 完成写入、state 初始化和 `package validate` 后返回 receipt，主 thread 复核 receipt；初始 bundle approval 在同一 package 内跨 session、patch 和普通更新持续有效，作为唯一 approval receipt。

## Ticket 拆分（仅 `tickets=true`）

仅在当前 plan 声明 `tickets=true` 时使用；Ticket 放在 package 固定的 `tickets/` 目录，文件名可排序且稳定。

本 Skill 拥有 Ticket 的纵向切片、AC、contract references 和 typed dependency 语义；Ticket 文件的物理写入与运行时 state 更新由 bound `/impl-package:execution-boundaries` 执行，主 thread 不直接编辑当前 package 的 Ticket 或 `.impl-package/state.json`。

- 按可独立验收的纵向交付切片拆分，不按文件、层或 worker 拆分；每个 Ticket 写 Ticket ID、Attempt、S/P 别名、`Draft`、建设内容、可观察 AC、evidence owner 和 typed dependency，运行时验收状态只写入 `.impl-package/state.json`。
- 每个 Ticket 的 contract references 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节，不得裸指整份文档或使用行号；Ticket 只引用其建设内容与 AC 实际依赖的章节。
- evidence 说明验证入口或 owner，不复制通用 checklist；与当前 plan/spec 检查 coverage、重叠、依赖、section-level contract references 和 AC feasibility。
- 新 package 使用 `tickets=true, dag=false` Ticket-only 合同，不创建 DAG，也不建立 Ticket/Task 双层 bundle；由 execution-boundaries 发布当前 Attempt 的 Ticket，并通过现有 state CLI 原子推进为 Approved/PENDING。旧 package 的 `dag=true` 只读，不由本 Skill 创建或更新。
- Ticket acceptance state 保存在 `.impl-package/state.json`；Ticket AC 使用稳定 claim ID，把 early falsification evidence 与 remaining completion evidence 分开描述；第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；旧 Task `DONE` 不自动通过 Ticket；P 变化时只将实际受影响 Ticket 设为 `NEEDS-REVALIDATION`。
- Ticket 发布后不承载 Phase、Next、worker、implementation progress 或 Runtime Acceptance projection；语义变化使受影响 Ticket 回到 Draft/重验流程；`package refresh-progress` 只重建 `progress.md` 与必要的 Execution Record header。新合同使用 `RETIRED` 统一表示 waived/superseded，并要求记录对应 disposition；3.4 runtime 旧状态只作为迁移输入。

## 完成条件

- plan 与 Decision/Spec 语义一致，无 `TBD` blocker；
- Coverage & Change Map 覆盖全部 active 约束，Planned Verification 可执行且有 owner；
- 新 package 的 Ticket 必须存在并与当前 Attempt 一致；旧 package 迁移计划如需读取 DAG，必须标记为 legacy-only；
- 初始 bundle review/approval 已完成，后续 patch 直接沿用该 approval；
- `state.json` 已初始化并通过 validate；
- owner 能从汇报直接判断能否进入执行。

初始 approval 后，同一 package 的 plan、contract、state、evidence 和 execution 更新直接继续；review 结果写入现有记录并沿用该 approval。
