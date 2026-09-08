---
name: impl-planning
description: 当已有批准的 Decision/Spec，需要创建 initial/patch plan、决定 Ticket-only Composition、执行策略或验证计划时使用；当已批准 plan 判定需要至少两个独立跟踪 acceptance 结论的交付切片时也使用（合并原 to-tickets）；只创建 Plan/Ticket 合同，不维护长期行为合同、Task 或运行状态。
---

# Impl Planning（含 Ticket 拆分）

为一个 implementation attempt 创建简洁、可执行的 plan，并把验收拆成可独立验收的 Ticket 合同；先读 `../../references/impl-package-composition-contract.md`，需要为 material seam 选择验证层级时再读 `../../references/progressive-system-evidence.md`。Plan 的语义、Coverage、执行策略、Planned Verification 与 Ticket 语义由本 Skill 与主 thread 拥有，主 thread 直接写入并验证 Plan/Ticket；runtime state 通过现有语义 CLI 更新。D/S gate 已通过才继续，未触及的 legacy Spec 可暂缺。

## 输出与规则

- initial 写 `plan.md`，patch 写 `<attempt-id>.patch-plan.md`；必填 Attempt ID、阶段 A 兼容写法 `Composition: tickets=true, dag=false`、全局调度（Ticket 顺序/依赖/共享资源）、全局执行边界、Planned Verification（跨 Ticket 范围）、集成顺序、Final Gate 判据和下一动作。
- Plan 直接引用当前 `decision.md` / `spec.md` 路径；D/S/P 仅为可选旧别名，不要求因普通编辑升级；所有文件/evidence 引用使用仓库相对路径。
- Plan 不复制 Decision/Spec contract ensemble、Ticket 状态或通用 checklist，新 plan 不建立 Task 状态轴；只有 Ticket 能减少验收歧义时才 earned，DAG/Task 只在旧 package 迁移/恢复计划中作为只读输入；Plan 不复制 Decision/Spec 约束到 Ticket 的映射、Ticket 的建设内容或逐项验证细节——这些属于 Ticket；Plan 只保留跨 Ticket 才存在的调度、共享资源、全局边界与 Final Gate 判据。

## 流程

1. initial 读取已批准 Decision、`spec.md`、从属 `contract-design.md` disposition 及当前代码/测试事实，确认 D/S gate 已通过；未触及的 legacy Spec 可暂缺该文件，同一 package 的 patch/update 沿用 initial bundle approval。
2. 在创建或更新 Plan，或更新 state 前执行 admission backstop：若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，或 contract surface 命中幂等键 / CAS / 版本号、多个来源写同一个目标字段、替换 / 撤回 / 恢复语义、跨存储提交（两个 store 各自提交）或声明值 vs 检测值但 Spec 只有规则没有结果矩阵，停止 planning，明确缺失合同并路由 `/impl-package:req-align` 重新确认当前 Spec；不得创建或更新 Plan/state，也不得在 Plan 中补第二套 DTO/schema。误判提醒见 [Admission 与计划](references/common-misjudgments.md#admission-与计划)。
3. 判断是 initial 还是 patch；patch 只描述相对上次 terminal gate 的实际 delta。
4. 新 package 固定选择 `tickets=true, dag=false`；`dag=true` 只允许在旧 package 迁移/恢复计划中出现。
5. 在 Ticket 拆分子流程中，把每个 Decision/Spec 约束映射到具体 Ticket 的 Contract references 与 AC，并按 Composition Contract 编译为 stable claim acceptance atoms；Ticket 自身承载建设内容、逐项 evidence、early-falsification、remaining-completion 和安全不变量。Plan 只提炼跨 Ticket 的实施与接线安排、typed dependency、共享资源、全局执行边界与 Planned Verification。
   - 并行判断：先核实真实 caller、复用入口、依赖产物、接线条件和验证可行性；结合冻结合同与当前资源，只提前开展能独立实施并验证的工作。
   - 按整票真实阻塞选择 `implementation / acceptance / release`，票内等待写成接线条件；只记录会改变安排的交接产物及其验证，不预列完整 baby-step 队列，派发和步骤大小交给 `$dispatcher` 与 `/impl-package:subagent-driven-development`。误判提醒见 [并行与调度安排](references/common-misjudgments.md#并行与调度安排)。
6. `tickets=true` 时执行本 Skill 的“Ticket 拆分”子流程；新 package 不调用 `create-task-dag`。
7. 初始 bundle 冻结 plan candidate 后调用 `/impl-package:plan-review` 的 `bundle-admission`；返回 `full-review` 时继续同一 skill 的完整审查，处理 material findings，并联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，然后请求一次完整 bundle approval；后续 patch/update 直接沿用该 approval。
8. 获批后，主 thread 使用当前已加载插件的 `impl_package_state.py` 语义 CLI 执行 `package init --attempt <id> --plan <repo-relative-plan>`，再执行 `package validate`；同时确认 execution-boundaries 的授权范围。插件根目录以当前已加载 skill 所属的插件根目录为准，不假设 workbench 仓库路径或宿主缓存路径。误判提醒见 [State 与发布边界](references/common-misjudgments.md#state-与发布边界)。
9. 进入 `/impl-package:execution-boundaries`，再交给 `/impl-package:dev-with-track`。

机械操作一律走 typed tools/语义 CLI；状态变更命令的处境与协议尾注由 `situation.py` 按 `situations.yaml` 注入。主 thread 完成 Plan/Ticket 写入与 `package init`/`package validate`；execution-boundaries 负责授权与 completion evidence audit。初始 bundle approval 在同一 package 内跨 session、patch 和普通更新持续有效，作为唯一 approval receipt。

## Ticket 拆分（仅 `tickets=true`）

仅在当前 plan 声明 `tickets=true` 时使用；Ticket 放在 package 固定的 `tickets/` 目录，文件名可排序且稳定。

本 Skill 拥有 Ticket 的纵向切片、AC、contract references 和 typed dependency 语义；主 thread 直接写入并验证 Ticket 正文，运行时 state 由主 thread 直接通过语义 CLI 更新。以下 9 步的误判提醒见 [Ticket 合同与证据](references/common-misjudgments.md#ticket-合同与证据)。

1. **切分纵向交付**：按可独立验收的纵向交付切片拆分，不按文件、层或 worker 拆分；一个 Ticket 交付恰好一个可验收的用户终态。终态分为权威转换（用户动作成功后产生新的权威记录，下游从此读取）和可验收的展示或编辑终态（用户到达稳定、可当场判定的界面状态，不产生新的权威记录）。
   - 计数判据：建设内容中终态为 0 个时作为层并入其他 Ticket，1 个为正确，2 个及以上拆分；读模型接线、后端算法、UI 只读化、加字段、补测试本身并入其服务的终态。
2. **登记 Ticket 合同**：每个 Ticket 写 Ticket ID、Attempt、S/P 别名、`Draft`、建设内容、可观察 AC、evidence owner 和 typed dependency，运行时验收状态只写入 `.impl-package/state.json`。
3. **标记到达路径**：到达路径的中间段先标成 `EXISTS` 或 `NEW`；Plan 的 `Predecessors` 显式写 `None` 或仓库相对路径，供查找与 review 使用。
4. **单独赚取 UI 形状验收**：当交付面包含实质 UI，且“形状对不对”本身构成独立验收结论时，把“UI 落进目标 app”单独 earn 一个 Ticket，排在接线 Ticket 之前，以 fixture 在真实 app shell 内验收且不依赖后端；这看似与“不按文件、层或 worker 拆分”冲突，但仍符合“只有 Ticket 能减少验收歧义时才 earned”，因为由人观察真实渲染状态而非靠 mock 通过，是独立的纵向验收切片。AC 写可观察的渲染状态与组件复用事实而非“UI 已实现”：目标组件/样式系统在真实 app shell 内渲染，恰好一个 surface 组件同时被 fixture 入口与将来的真实入口引用，状态模型作为目标模块内独立模块并有 focused test，fixture 覆盖正常/缺失/冲突/失败/部分成功且逐状态可达可截图、无后端副作用，Owner 逐状态走查 receipt。
5. **限定合同引用**：每个 Ticket 的 contract references 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节，不得裸指整份文档或使用行号；引用 `contract-design.md` 时，因其体量大，必须在章节定位之外命名具体 entry point（Operation/Aggregate/DTO/Seam/Projection 名，或函数/类名），格式为 `path#section-anchor · <entry point 名>`，不得只停在章节级。Ticket 只引用其建设内容与 AC 实际依赖的章节。Ticket AC 只写执行所需的 scenario 与 oracle；算法分档、tie-break、状态规则等已有可观察语义从 Decision/Spec 对应章节引用。
6. **绑定 evidence 与覆盖检查**：evidence 说明验证入口或 owner，不复制通用 checklist；与当前 plan/spec 检查 coverage、重叠、依赖、section-level contract references、stable claim atomization 和 AC feasibility。Spec 章节发生变化时，扫描引用该章节的全部 Ticket 并标为受影响，覆盖检查以完整集合为准。
 7. **发布 Ticket-only Composition**：新 package 使用 `tickets=true, dag=false` Ticket-only 合同，不创建 DAG，也不建立 Ticket/Task 双层 bundle；主 thread 发布当前 Attempt 的 Ticket，并通过现有 state CLI 原子推进为 Approved/PENDING。旧 package 的 `dag=true` 只读，不由本 Skill 创建或更新。
8. **保留 Ticket acceptance 不变量**：Ticket acceptance state 保存在 `.impl-package/state.json`；Ticket AC 按 Composition Contract 使用稳定 claim ID，一个 AC 可包含多个原子 claim；把 early falsification evidence 与 remaining completion evidence 分开描述，其中只有真实 UI/provider/native tool 才能证伪的可观察结果（如真实入口是否呈现目标状态）标为 `early-falsification`，完整旅程验收仍标为 `remaining-completion`；第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；旧 Task `DONE` 不自动通过 Ticket；P 变化时只将实际受影响 Ticket 设为 `NEEDS-REVALIDATION`。
9. **限制发布后的投影**：Ticket 发布后不承载 Phase、Next、worker、implementation progress 或 Runtime Acceptance projection；语义变化使受影响 Ticket 回到 Draft/重验流程；`package refresh-progress` 只重建 `progress.md` 与必要的 Execution Record header。新合同使用 `RETIRED` 统一表示 waived/superseded，并要求记录对应 disposition；3.4 runtime 旧状态只作为迁移输入。

## 完成条件

- plan 与 Decision/Spec 语义一致，无 `TBD` blocker；
- 全部 active 约束都能在某个 Ticket 的 Contract references 与 AC 中定位（无遗漏、无重复认领）；跨 Ticket 的 Planned Verification 可执行且有 owner；
- 新 package 的 Ticket 必须存在并与当前 Attempt 一致；旧 package 迁移计划如需读取 DAG，必须标记为 legacy-only；
- 初始 bundle review/approval 已完成，后续 patch 直接沿用该 approval；
- `state.json` 已初始化并通过 validate；
- owner 能从汇报直接判断能否进入执行。

初始 approval 后，同一 package 的 plan、contract、state、evidence 和 execution 更新直接继续；review 结果写入现有记录并沿用该 approval。
