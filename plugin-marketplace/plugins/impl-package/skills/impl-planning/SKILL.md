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
   - 常见误判：拿未批准或过期的 D/S 事实开始写 Plan，会把实现候选误写成已冻结的行为合同。
2. 在让 execution-boundaries 创建或更新 Plan/state 前执行 admission backstop：若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，或 contract surface 命中幂等键 / CAS / 版本号、多个来源写同一个目标字段、替换 / 撤回 / 恢复语义、跨存储提交（两个 store 各自提交）或声明值 vs 检测值但 Spec 只有规则没有结果矩阵，停止 planning，明确缺失合同并路由 `/impl-package:req-align` 重新确认当前 Spec；不得创建或更新 Plan/state，也不得在 Plan 中补第二套 DTO/schema。
   - 常见误判：把 Plan 当成补齐 Spec 留白的地方，会产生第二套 DTO/schema，两个实施者随后可以按不同合同实现。
3. 判断是 initial 还是 patch；patch 只描述相对上次 terminal gate 的实际 delta。
   - 常见误判：patch 重述整份历史范围，会把未变化的 evidence 和 gate 重新混入当前 delta，无法判断真正受影响的边界。
4. 新 package 固定选择 `tickets=true, dag=false`；`dag=true` 只允许在旧 package 迁移/恢复计划中出现。
   - 常见误判：为新 package 顺手创建 DAG，会重新引入 Ticket/Task 双层状态和两个 acceptance authority。
5. 将每个 Decision/Spec 约束映射到实现范围及 Ticket，写执行顺序、修改边界、依赖、集成/回滚方式和足以区分正确/错误实现的验证；每个验证项明确 evidence owner。Coverage Map 可以引用 `spec.md` 或其从属 `contract-design.md` 的稳定章节；把 early falsification evidence、remaining completion evidence 和不可延后安全不变量分开写。纵向切片装不下一个 worker 时，回去把该 seam 冻得更细，不要改成横向切分。
   - 常见误判：只列文件或测试名称而不映射约束、owner 和 early/remaining evidence，Ticket 结束时就无法区分局部通过与完整验收。
6. `tickets=true` 时执行本 Skill 的“Ticket 拆分”子流程；新 package 不调用 `create-task-dag`。
   - 常见误判：把 Ticket 拆分交给旧 DAG 入口，会把已经选择的 Ticket-only Composition 偷换成另一套任务结构。
7. 初始 bundle 冻结 plan candidate 后调用 `/impl-package:plan-review` 的 `bundle-admission`；返回 `full-review` 时继续同一 skill 的完整审查，处理 material findings，并联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，然后请求一次完整 bundle approval；后续 patch/update 直接沿用该 approval。
   - 常见误判：只审 Plan 文本、不审跨 Ticket 的 coverage/ownership/order，会让一个局部看似完整的 candidate 直接进入执行。
8. 获批后，主 thread 将 Attempt ID、canonical Plan 路径、bundle approval 和下一动作交给 bound execution-boundaries；由当前已加载插件的 `impl_package_state.py` 语义 CLI 执行 `package init --attempt <id> --plan <repo-relative-plan>` 再执行 `package validate`。插件根目录以当前已加载 skill 所属的插件根目录为准，不假设 workbench 仓库路径或宿主缓存路径。
   - 常见误判：跳过 `package validate` 或先写 state 再确认 Plan，会把不可恢复的 runtime 事实当成已获批的 package 状态。
9. 进入 `/impl-package:execution-boundaries`，再交给 `/impl-package:dev-with-track`。
   - 常见误判：绕过 execution-boundaries 直接执行，会丢掉授权、write-set 和完成前 evidence gate 的边界。

机械操作一律走 typed tools/语义 CLI；状态变更命令的处境与协议尾注由 `situation.py` 按 `situations.yaml` 注入。execution-boundaries 完成写入、state 初始化和 `package validate` 后返回 receipt，主 thread 复核 receipt；初始 bundle approval 在同一 package 内跨 session、patch 和普通更新持续有效，作为唯一 approval receipt。

## Ticket 拆分（仅 `tickets=true`）

仅在当前 plan 声明 `tickets=true` 时使用；Ticket 放在 package 固定的 `tickets/` 目录，文件名可排序且稳定。

本 Skill 拥有 Ticket 的纵向切片、AC、contract references 和 typed dependency 语义；Ticket 文件的物理写入与运行时 state 更新由 bound `/impl-package:execution-boundaries` 执行，主 thread 不直接编辑当前 package 的 Ticket 或 `.impl-package/state.json`。

1. **切分纵向交付**：按可独立验收的纵向交付切片拆分，不按文件、层或 worker 拆分；一个 Ticket 交付恰好一个可验收的用户终态。终态分为权威转换（用户动作成功后产生新的权威记录，下游从此读取）和可验收的展示或编辑终态（用户到达稳定、可当场判定的界面状态，不产生新的权威记录）。
   - 计数判据：建设内容中终态为 0 个时作为层并入其他 Ticket，1 个为正确，2 个及以上拆分；读模型接线、后端算法、UI 只读化、加字段、补测试本身并入其服务的终态。
   - 常见误判：按文件或层切分会得到无法独立验收的半条路径，Ticket 数量看似增加但 acceptance 没有变清楚。
2. **登记 Ticket 合同**：每个 Ticket 写 Ticket ID、Attempt、S/P 别名、`Draft`、建设内容、可观察 AC、evidence owner 和 typed dependency，运行时验收状态只写入 `.impl-package/state.json`。
   - 常见误判：缺少稳定 ID、owner 或 typed dependency，后续 evidence 无法归属，状态也会漂移到文档正文之外。
3. **标记到达路径**：到达路径的中间段先标成 `EXISTS` 或 `NEW`；Plan 的 `Predecessors` 显式写 `None` 或仓库相对路径，供查找与 review 使用。
   - 常见误判：不区分 `EXISTS`/`NEW`，reviewer 会把待建设入口当成已存在，或把已有依赖重复纳入本 Ticket。
4. **单独赚取 UI 形状验收**：当交付面包含实质 UI，且“形状对不对”本身构成独立验收结论时，把“UI 落进目标 app”单独 earn 一个 Ticket，排在接线 Ticket 之前，以 fixture 在真实 app shell 内验收且不依赖后端；这看似与“不按文件、层或 worker 拆分”冲突，但仍符合“只有 Ticket 能减少验收歧义时才 earned”，因为由人观察真实渲染状态而非靠 mock 通过，是独立的纵向验收切片。AC 写可观察的渲染状态与组件复用事实而非“UI 已实现”：目标组件/样式系统在真实 app shell 内渲染，恰好一个 surface 组件同时被 fixture 入口与将来的真实入口引用，状态模型作为目标模块内独立模块并有 focused test，fixture 覆盖正常/缺失/冲突/失败/部分成功且逐状态可达可截图、无后端副作用，Owner 逐状态走查 receipt。
   - 常见误判：只让后端接线 Ticket 通过，会把 UI 形状错误或组件复用错误隐藏在“UI 已实现”的笼统声明里。
5. **限定合同引用**：每个 Ticket 的 contract references 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节，不得裸指整份文档或使用行号；Ticket 只引用其建设内容与 AC 实际依赖的章节。Ticket AC 只写执行所需的 scenario 与 oracle；算法分档、tie-break、状态规则等已有可观察语义从 Decision/Spec 对应章节引用。
   - 常见误判：引用整份文档会让 Ticket 看似有依据，却无法判断实际依赖哪条 authority。
6. **绑定 evidence 与覆盖检查**：evidence 说明验证入口或 owner，不复制通用 checklist；与当前 plan/spec 检查 coverage、重叠、依赖、section-level contract references 和 AC feasibility。Spec 章节发生变化时，扫描引用该章节的全部 Ticket 并标为受影响，覆盖检查以完整集合为准。
   - 常见误判：只写“有测试”而不写入口、owner 和 coverage，会把不可执行或重叠的 AC 留到执行末端才暴露。
7. **发布 Ticket-only Composition**：新 package 使用 `tickets=true, dag=false` Ticket-only 合同，不创建 DAG，也不建立 Ticket/Task 双层 bundle；由 execution-boundaries 发布当前 Attempt 的 Ticket，并通过现有 state CLI 原子推进为 Approved/PENDING。旧 package 的 `dag=true` 只读，不由本 Skill 创建或更新。
   - 常见误判：发布时又创建 Task/DAG 或手写状态，会产生第二个运行时 authority，Ticket 的 Approved/PENDING 也无法回放。
8. **保留 Ticket acceptance 不变量**：Ticket acceptance state 保存在 `.impl-package/state.json`；Ticket AC 使用稳定 claim ID，把 early falsification evidence 与 remaining completion evidence 分开描述，其中只有真实 UI/provider/native tool 才能证伪的可观察结果（如真实入口是否呈现目标状态）标为 `early-falsification`，完整旅程验收仍标为 `remaining-completion`；第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；旧 Task `DONE` 不自动通过 Ticket；P 变化时只将实际受影响 Ticket 设为 `NEEDS-REVALIDATION`。
   - 常见误判：把旧 Task `DONE` 或一次 early falsification 当成 Ticket 满足，会漏掉 remaining evidence 和第一条路径上的安全不变量。
9. **限制发布后的投影**：Ticket 发布后不承载 Phase、Next、worker、implementation progress 或 Runtime Acceptance projection；语义变化使受影响 Ticket 回到 Draft/重验流程；`package refresh-progress` 只重建 `progress.md` 与必要的 Execution Record header。新合同使用 `RETIRED` 统一表示 waived/superseded，并要求记录对应 disposition；3.4 runtime 旧状态只作为迁移输入。
   - 常见误判：把进度或 runtime projection 写回 Ticket，会让接受状态、执行状态和恢复投影形成多个可写来源。

## 完成条件

- plan 与 Decision/Spec 语义一致，无 `TBD` blocker；
- Coverage & Change Map 覆盖全部 active 约束，Planned Verification 可执行且有 owner；
- 新 package 的 Ticket 必须存在并与当前 Attempt 一致；旧 package 迁移计划如需读取 DAG，必须标记为 legacy-only；
- 初始 bundle review/approval 已完成，后续 patch 直接沿用该 approval；
- `state.json` 已初始化并通过 validate；
- owner 能从汇报直接判断能否进入执行。

初始 approval 后，同一 package 的 plan、contract、state、evidence 和 execution 更新直接继续；review 结果写入现有记录并沿用该 approval。
