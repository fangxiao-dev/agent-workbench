# Impl-Package 体系设计（Dev-with-Track 体系重构方案）

## 来源与状态

- Created at: 2026-07-10
- Source: `D:\CodeSpace\TaskManager\Dev-with-Track 体系讨论.md`（原始构想稿）
- Status: 方案草案，经多方独立评审收敛，待 owner 批准后按执行基线实施
- 关联设计：`2026-07-09-evergreen-module-spec-and-backfill-design.md`
  （backfill 体系，本方案 stage 7 的既定下游）

## 命名与定位

体系名定为 **Impl-Package 体系**：以 implementation package
（`docs/implementations/<package-id>/`）为持久单位的完整交付工作流。
`dev-with-track` 从此只指 stage 5 的执行 skill，不再兼指整套体系。

体系名作为共享 leading word 写进各成员 skill 的 description
（"Impl-Package 体系的 XX 阶段"），提升互相触发与路由可靠性。

### Package ID 与时间戳命名

把**语义 topic slug** 与目录身份分开：topic slug 是简短的 kebab-case 主题名，
如 `catalog-readiness`；**package-id** 是不可变的目录名，格式为
`YYYYMMDD-HHMMSSZ-<topic-slug>`，如 `20260711-144512Z-catalog-readiness`。
所有**新建** implementation package 必须使用 package-id，因此目录为
`docs/implementations/<package-id>/`。UTC 秒级时间戳让同一主题的独立、短时效
变更事件天然可区分，并保持目录按创建时间排序。

- requirement-alignment 在 Design 开始前生成并记录 package-id，同时记录 topic
  slug；创建后两者均不可改写。若精确目录名已存在，保留同一时间戳和 topic slug
  并追加 `-02`、`-03`…顺序后缀，直到唯一。
- 下游 artifact、ticket ID、truth pointer 与 backfill 记录引用 package-id；不要只
  用 topic slug 作为跨包引用。
- 既有无时间戳目录是 legacy package-id，可被恢复和 post-gate patch 原地复用；不为
  此规则做批量改名。post-gate patch 继续复用其 owning package-id，而不是另建一个
  时间戳目录。

## 按需 composition，不是 sizing

**心智从 sizing（这任务多大→定档）转为 composition（这任务需要哪几种切分
→按需 earn）。** 抛弃 S/M/L 线性档——它把两个正交维度硬压成一条线。分级
决策记录在 `spec.md` 头部 `Composition:` 行，允许中途升级；升级按本方案的
受控迁移契约移动内容、保留 provenance，不重做已确认语义，也不双重维护。

地基恒有：`spec.md` + `plan.md`。之上是两个**正交、可独立 earn**的开关：

| 开关 | earn 条件 | 产出 | 不 earn 时 |
| --- | --- | --- | --- |
| **tickets**（验收切分） | 一次做完才验收太憋，存在 ≥2 个可独立验收的 delivery slice | `tickets/<ticket>.md`（+ 静态 `blocked by` 依赖标注） | 验收标准待在 `spec.md` 的 Acceptance Semantics；单切片不建 ticket 文件 |
| **dag**（执行依赖/协调） | 需要显式表示多 owner 协作、task 间非平凡依赖，或跨 slice seam 协调 | `dag.md` | task checklist 直接待在 `plan.md` 的 T\<n\> 段；跨 session 状态恢复按需使用 progress ledger |

两个开关任意组合合法：都无（spec+plan 直接执行）、只 dag、只 tickets、
两者都有。task 与 ticket 解绑——task 可横切多个 ticket，seam/集成 task
不属于任何单个 ticket。

Review 按独立信号触发，不把 artifact 数量当风险代理：code-review 恒必选；
有 tickets 或 dag 时 module-review 必选，无两者但 spec 声明 interface、状态机、
模块边界或 seam 变化时同样必选；safety-review 永远按信号触发（见 Review 体系）。

- **Design 步骤恒定必过**：调研 + 需求对齐 + readiness 门是 Stage 1 的必经
  步骤，与 composition 无关，不可跳过。`design.md` / `findings.md` 作为文件
  产物可薄可无——调研沉淀少时文件轻，但 readiness 门判定与 owner decisions
  必须留痕。"步骤必过"不等于"文件必建"：沿用"不为形式建空 ledger"约束的是
  文件，不是步骤。
- `tasks/Tn-progress.md` 触发条件维持 dev-with-track 现行规则，不随开关
  自动创建。
- 跨 session 恢复本身不 earn dag：progress ledger 恢复状态，plan/tickets/dag
  恢复拓扑。若执行拓扑无法由 plan/tickets 清晰重建，则因“执行依赖需要
  显式化”earn dag，而不是因“跨 session”earn dag。
- ceremony 守护：tickets 与 dag 都必须由 earn 条件挣得存在；报告/复盘发现
  某 package 的 artifact 空转（如只 1 个 ticket、dag 没有非平凡依赖或协调
  价值）时，视为
  composition 判定错误回记 rubric。

## 七阶段流水线（定稿）

```text
1 对齐与调研  requirement-alignment（通用化后）→ design.md + 首批 findings + owner decisions
2 Spec        requirement-alignment 第二道门 → spec.md（含 Composition 判定）
3 薄 plan     feature-impl-planning → plan.md；earn tickets 时随后 to-tickets(fork, draft) 切 slices
4 Task DAG    create-task-dag ← plan + 相关 approved tickets 子集（有 tickets 时）或 plan（仅 dag 时）
5 执行        dev-with-track：restore → readiness resolution → execute → evidence → findings → gate
6 审查        code-review / module-review / safety-review（映射见下）
7 回刷交接    gate 捕获登记 → backfill 体系（引用 2026-07-09 设计，不再设计）
```

阶段要点（只记与讨论稿差异或收敛修正，正文以讨论稿为底）：

- **Stage 1/2 一个 skill 两道对等必过门**：requirement-alignment 承载
  Design 与 Spec 两个步骤，二者对等且都必过——不是"Design 可选、Spec 必有"。
  调研 readiness 门（Destination 可回答、Open Questions 收敛到不阻塞 spec）
  必过 → 才允许进入 spec 门生成 `spec.md`。不拆成两个 skill：design→spec 是
  紧耦合的顺序交接，拆开徒增一条 handoff seam。前置条件：先解除其
  prj-supplyer-webapp 绑定（见 skill 改造清单）。
- **design.md 护栏**：保留 Design Research 八节结构，但 Decisions
  只记"选择与理由"，行为语义一律进 spec；spec 已有内容 design 不留副本。
  Backfill Candidates 只是其中的**非约束调研提示**小节，供后续参考；durable
  delta 的正式捕获在 gate 关闭时发生（Stage 7），不在 spec 里维护常青 backfill
  map，也不要求执行期归并进 spec（避免与下游 backfill 体系双重登记）。
- **spec.md 模板护栏**：package-id 内的 `spec.md` 按 2026-07-09 设计的模块 spec 八节
  合同结构成型（point-in-time 变更粒度）：Scope/authority/non-goals、术语与
  数据合同、行为/状态机/工作流、模块边界与依赖、**Error Boundaries——失败
  模式与恢复语义**、约束型合同（禁止事项/信任边界/精度/provider 义务/负依赖）、
  Acceptance Semantics 与验证依据、Composition 判定。不得退化为只有
  Composition + Acceptance 两三项的薄壳。
- **Stage 3 顺序**：薄 plan → tickets → 交叉审查；tickets 暴露缺口
  回修 plan，但 plan 不复制 ticket 正文。**earn tickets 时** `plan.md` 完全
  去任务化，收缩为跨 slice 工程契约（策略、seam、migration/rollback、验证
  政策、全局约束）；T\<n\> checklist 只在无 tickets 时留在 plan。
- **Stage 4 两层切分**：ticket 列表（delivery slices + 带阻塞语义的静态
  `blocked by`
  依赖标注）归 to-tickets fork；task DAG（一个 ticket 内 worker tasks，或
  横切多 ticket 的 seam task）归 create-task-dag。输入过宽路由回
  to-tickets draft，不再自带 slicing 规则。create-task-dag 的有效输入是
  package plan + 相关 approved tickets 子集，不能从单个 ticket 猜测跨 ticket
  seam contract。
- **Stage 5 无动态调度器、有 readiness resolution**：删除自动派工、worker
  leasing、并发锁等动态调度——它们服务的是
  多 worker 高并行、主 session 失去全局视野的调度，而实际执行大体串行。
  但每次选择下一执行单元前，必须对静态图做确定性的 readiness resolution，
  处理依赖终态、外部 gate、环、失败/豁免/替代传播及上游返工造成的下游失效；
  多个 actionable 单元按文档顺序稳定选择。单 package 维护完整 ticket 列表；
  ticket 状态按 composition 落到 canonical home（见下节）。patch plan / patch
  DAG 严格保留给 post-gate 生命周期补丁（与 feature-impl-planning
  `patching.md` 互引），不做 per-ticket patch。
  - YAGNI 边界：若未来执行模式真变成多 worker 并行跑不同 ticket，再增加
    动态派工能力；readiness resolution 不是该调度器的降级版，而是串行执行
    与恢复正确性的基础规则。
- **Stage 7**：有 durable delta 时，gate 关闭必须完成 `_pending.md` 捕获登记
  （gate 的 Durable Deltas 表为唯一捕获面）、受影响 module spec 的 truth
  pointer、必要 stub 创建；无 durable delta 时显式记录判定与理由。捕获与路由
  下沉到 gate + `_pending.md` + 下游 backfill report/apply，不在 spec 维护常青
  map。去重键 `<destination>|<delta-id>` 落在 `_pending.md`/report 侧。三源
  对账（`_pending` / gate 漏登 / 无主 commit）引用并同步约束 2026-07-09 设计。

## Artifact Ownership

| Artifact | Canonical Owner | 追加权 | 不应包含 |
| --- | --- | --- | --- |
| `design.md` | requirement-alignment | — | 行为合同副本、worker task、稳定文档改动 |
| `spec.md` | requirement-alignment | feature-impl-planning（Composition 行）、patch 修订 | 调研流水、文件级步骤、长期知识正文、常青 backfill map（捕获在 gate → `_pending.md`） |
| `plan.md` / patch plan | feature-impl-planning | — | earn tickets 时任何 task 细节；ticket 正文；实时状态 |
| Tickets | to-tickets（本地 fork） | dev-with-track（状态） | worker ownership、文件级实现步骤 |
| `dag.md` / patch DAG | create-task-dag 方法 + dev-with-track 持久化 | — | spec/plan/ticket 正文 |
| `tasks/Tn-progress.md` | dev-with-track | worker 汇报 | 迷你 spec、重复计划 |
| `findings.md` | dev-with-track（格式与收口） | **各阶段均可 append** | 普通 task 日志、未证实的长期事实 |
| `gate.md` | dev-with-track | review skills（结论） | 虚构证据、稳定文档直接修改流程 |

## Composition 状态机与跨层契约

本节是各 skill 的共同规范源；skill 可引用、不可各自重定义以下规则。

### 四种组合的 canonical status home

| Composition | 执行状态 | ticket 验收状态 |
| --- | --- | --- |
| 无 tickets、无 dag | `plan.md` checklist；需独立恢复时按规则 earn task progress | 不适用，验收语义与证据在 `spec.md` / `gate.md` |
| 仅 tickets | `plan.md` 只保留跨 slice 契约；各 ticket 文件是自身状态的事实源 | 各 `tickets/<ticket>.md`，不得为状态索引额外创建 `dag.md` |
| 仅 dag | `dag.md` task 状态索引，详细恢复证据按需落 task progress | 不适用，验收语义与证据在 `spec.md` / `gate.md` |
| tickets + dag | `dag.md` 是运行状态索引，task 详细恢复证据按需落 progress | ticket 文件保存验收定义与最终结论；`dag.md` 中 ticket 状态只是投影，不得反向覆盖验收结论 |

同一状态只有一个事实源。索引必须标明是投影；禁止在两个 artifact 中双向维护
同一状态。

### Readiness resolution 与依赖语义

`blocked by` 必须标明阻塞的是 `implementation`、`acceptance` 或 `release`。
“可独立验收的 slice”指值得独立跟踪验收结论、拥有清晰边界、局部 acceptance
和证据，并不承诺独立发布；integration acceptance 与 release readiness 可被
其他 ticket 或 seam 阻塞。

每次选择下一单元时确定性计算：

```text
actionable = 未处于完成/取消/替代终态
             AND 所有 implementation blockers 已进入可释放终态
             AND 自身 owner、外部 gate 与环境前提满足
```

- `DONE` 默认释放依赖；`WAIVED` / `SUPERSEDED` 只有记录替代证据与影响后才
  释放；`FAILED` / `BLOCKED` 不释放。
- publish 前校验无环、无缺失引用。多个 actionable 单元按 ticket/task 文档
  顺序稳定选择，不做自动派工。
- 上游返工或验收重开时，所有依赖其产物且证据可能失效的下游回退为
  `NEEDS-REVALIDATION`；执行者逐项重验证，不自动假定仍有效。
- restore 时先对账 artifact 状态与证据；不一致时以可核实证据为准，并修正
  canonical status home 后再选下一单元。

### Task 到 ticket acceptance 的 many-to-many 追踪

task 与 ticket 不建立包含关系，但必须建立贡献关系。`dag.md`（无 dag 时为
`plan.md`）为每个 task 记录 `contributes-to: <ticket>:<AC-id>`；纯执行基础设施
task 可标 `enables:`，但必须指出最终由哪些 AC 消费其证据。

两个强制 gate：

1. 执行开始前，每个 ticket AC 至少有一个 planned evidence producer 或明确的
   人工验证 owner。
2. ticket 关闭前，每个 AC 逐条记录 evidence；不得由相关 task 全部 DONE
   自动推导验收通过。

### Seam ownership 与 review 边界

- seam contract owner：`plan.md`，描述跨 slice interface、兼容窗口、集成与
  rollback 契约。
- seam execution owner：`dag.md` 中明确指定的 task owner。
- seam acceptance owner：主 session 或显式 integration owner；负责把 seam
  evidence 归入所有受影响 ticket AC。
- 任一 seam acceptance 未通过时，所有依赖该 seam 的 ticket 不得关闭。
- task 级 review 检查局部实现；module-review 检查完整 implementation 的
  contract fidelity，不以某一个 ticket 为审查边界。

### Composition 升级迁移

允许中途升级，不允许无 provenance 的双写。升级不重做已确认语义，但允许一次
受控迁移：更新 `Composition:`、记录变更理由和时间，将旧内容迁入新 canonical
artifact，在原位置留下 relocation pointer，并删除后续双重维护入口。例如从
无 tickets 升级到有 tickets 时，plan 中 T\<n\> checklist 必须迁移/重构为 ticket
与 task 追踪关系，plan 收缩为跨 slice 契约；新增 dag 时同理迁移运行状态索引。
迁移完成后必须运行状态事实源、依赖引用和 AC 覆盖一致性检查。

### Stage 7 完整关闭契约

durable delta 的 canonical 捕获面是 **gate 的 Durable Deltas 表 → `_pending.md`**，
不在 `spec.md` 维护常青 `Stable Doc Backfill Map`（那会与下游 backfill 体系形成
三重登记，违反不双重维护）。`design.md` 的 Backfill Candidates 只是非约束调研
提示，正式捕获在 gate 关闭那一刻发生，不需要在执行期归并进 spec。去重键
`<destination>|<delta-id>` 落在 `_pending.md` 与 report 侧。

- 有 durable delta：在 gate 的 Durable Deltas 表逐条登记 → 写 `_pending.md`、
  为受影响 module spec 写 truth pointer、必要时先创建 stub；三项完成才可关闭
  gate。
- 无 durable delta：在 gate 中显式记录判定与理由。
- 回刷 report 按去重键合并 `_pending.md`、gate 漏登对账与无主 commit 三源；
  任一来源缺失均报告为 capture gap，不猜测为”无变化”。

## Review 体系

两层分类法显式合一：

| 层 | 载体 | 内容 |
| --- | --- | --- |
| Task 级 | create-task-dag worker 协议 | task spec review、task quality review（派发粒度，保持现状） |
| Implementation 级 | 三 review skill | code-review（必选）、module-review（composition/契约信号触发）、safety-review（安全信号触发） |

- create-task-dag 的 "whole-slice review" 改写为**调用 module-review**
  （spec fidelity 轴），不再独立定义检查项。
- module-review 现状即 **Standards + Spec 双轴、两个并行 reviewer**，无需新增
  第三轴或独立 drift skill：
  - **Spec 轴**承担 contract fidelity——"实现的 interface/seam 与 spec/dag
    声明的 contract 是否漂移"是 Spec reviewer 的既有职责，不另设内置检查项。
  - **Standards 轴**的 repository standards 钩子引用 `codebase-design`，
    承载 deep module/interface/seam 基线。
  - 触发规则：有 tickets 或 dag 时必选；无两者但 spec 声明 interface、状态机、
    模块边界或 seam 变化时同样必选。单切片不等于低契约风险。
- safety-review 从 git 历史旧 module-review 精简恢复，范围五类
  （data integrity / security boundary / concurrency / external side
  effects / change map + P0–P2）。触发用可观察信号：diff 触碰
  auth/payment/webhook/migration/外部 mutation 路径，或 `dag.md`
  Verification Gates / `gate.md` Data Safety 声明外部写入 → 自动运行。
  P0 fail-closed：外部 mutation 无幂等/补偿语义；auth/permission 边界
  绕过；可致数据丢失的 migration 无回滚。信号复用 DAG/gate 既有字段，
  不新增登记面。

## Skill 改造清单

| Skill | 改动 |
| --- | --- |
| `requirement-alignment` | 通用化：description/body 解除 prj-supplyer-webapp 绑定，项目细节退回项目 AGENTS/CONTEXT；内置两道对等必过门（Design 步骤与 Spec 步骤都不可跳过，design.md 文件可薄但门必过）；拥有 design.md + spec.md 及其模板（spec 按 2026-07-09 八节合同结构成型，含 Error Boundaries/失败恢复/约束型合同；吸收 to-spec 的模板与 synthesis 方法，不产出第二份 tracker spec）；借用 domain-modeling 分析方法但禁用其 CONTEXT.md 写入（结论进 design/findings + backfill candidate） |
| `to-tickets` | **本地 fork**（保留名，registry 标注"已本地分叉，上游更新人工 diff"）：加 draft/publish 双模式（内部默认 draft）、runner-neutral handoff、删除 /implement 绑定；保留 tracer bullet、带类型的静态 blocking edges、wide-refactor expand–contract；删除自动派工类动态调度，增加 publish 前环/引用校验 |
| `to-spec` | 保留 vendored 只读，不进主流程；其方法已被 requirement-alignment 吸收 |
| `feature-impl-planning` | plan 模板增加"有 tickets"分支（去任务化的跨 slice 契约形态）与"无 tickets"分支（内含 T\<n\> checklist）；识别 `spec.md` 的 Composition 行；拥有受控 composition 升级迁移；patching.md 与 ticket 生命周期互引（patch 仅 post-gate） |
| `create-task-dag` | 收缩到 execution decomposition：删自带 slicing 路由，宽输入改路由 to-tickets draft；全部 to-issues 引用替换为 to-tickets；输入契约 = plan + 相关 approved tickets 子集（有 tickets 时）或 plan（仅 dag 时）；记录 task→AC 与 seam owner；whole-slice review 改为调用 module-review |
| `dev-with-track` | 核心循环增加确定性 readiness resolution（不做自动派工）；按 composition 使用 canonical status home；实现 AC 覆盖 gate、返工失效传播和完整 Stage 7 关闭契约；按 composition 开关决定 scaffold 范围；description 植入体系名 |
| `module-review` | 已换模为 Standards + Spec 双轴双 reviewer：contract-drift 归入 Spec 轴既有职责（不新增内置检查）；Standards 轴 standards 钩子引用 codebase-design；按 composition 或 spec 契约变化信号触发 |
| `safety-review` | 新建（从 git 历史恢复精简）：五类范围 + 信号触发 + P0 fail-closed |
| `orchestrator` | 退休至 `skills-deprecated/`；清理 registry、docs、evals 引用 |

## 执行基线（正式批准）

**实施前置**：先把本方案的“Composition 状态机与跨层契约”编码为共享模板、
字段和验证规则；步骤 3、4、6 不得各自重定义。试点必须刻意覆盖一个
tickets-only package 和一个 tickets+dag+cross-ticket seam package，并采集
ticket/task 数、最大依赖深度、blocked 次数、人工改选下一单元次数、restore
纠错次数与 AC 覆盖缺口，作为 rubric 校准证据。

| 步 | 内容 | 验收 |
| --- | --- | --- |
| 0 | requirement-alignment 通用化（全局前置） | description 无项目绑定；dry-run 一个非 webapp 场景可触发 |
| 1 | requirement-alignment 两道对等必过门 + design/spec ownership + 厚 spec 模板 | 两门都有可检验必过标准（Design 步骤不可跳）；spec 模板含八节含 Error Boundaries；design 护栏语句在位 |
| 2 | to-tickets 本地 fork + registry 标注；to-spec 方法吸收 | fork 后 draft 模式 dry-run 通过；registry 有分叉标注 |
| 3 | create-task-dag 收缩 + to-issues 引用替换 + review 映射 + readiness 契约 | grep 无 to-issues 残留；whole-slice review 指向 module-review；输入支持 plan + tickets 子集；task→AC 与 seam owner 字段在位 |
| 4 | feature-impl-planning plan 双分支（有/无 tickets）+ Composition 协同 | 两个模板分支存在；与 patching.md 互引 |
| 5 | safety-review 恢复 + module-review 触发映射与 standards 钩子 | 触发信号与 P0 清单落文；contract-drift 由 Spec 轴覆盖，Standards 轴引用 codebase-design |
| 6 | dev-with-track gate/scaffold/readiness/canonical status 适配 + 体系名植入全部成员 description | gate 模板含 Durable Deltas 表 + pending + truth pointer + stub 完整关闭契约；核心循环有 readiness resolution 且无自动派工；各 description 含体系名 |
| 7 | orchestrator 退休 + registry/docs/evals 清理 | grep 主链路无 orchestrator 活引用 |
| 8 | 原始讨论稿标注已被本方案取代 + 各 skill evals 更新 | 讨论稿顶部注明"已由本方案取代"；evals 与新行为一致 |

每步一个独立 commit 主题；步 0–2 是其余步骤的前置，3–5 可并行，6–8 收尾。

## Progress 记录的维度：task vs ticket

原则：**progress 跟随"恢复单元"，不跟随命令层级。** 执行单元恒为 task；
引入 ticket 不改变 progress 的写法，而是把 dev-with-track 的 ledger 触发
条件制从 task 层原样上移一层到 ticket 层——earn 才建，不为形式建。

| 记录 | 维度 | 触发 |
| --- | --- | --- |
| `tasks/Tn-progress.md` | task（执行单元） | 现有触发条件不变（独立 owner/subagent、外部 gate、跨 session、独立证据、影响 gate 且挤爆 dag） |
| ticket 验收状态 | ticket（验收单元） | canonical home 恒为 `tickets/<ticket>.md`；有 dag 时可在 `dag.md` 建只读投影索引；**不新增 progress 文件** |
| ticket-level progress | ticket（恢复单元） | 仅当整个 ticket 成为跨 session 独立恢复/交接单元时 earn；记 ticket 局部状态 + 辖下 task 索引，不复制 task progress |

要点：

- ticket 验收 ≠ 辖下 task 全 DONE 的相加，它有独立 acceptance criteria；
  因此 ticket 验收状态以 ticket 文件为事实源；有 dag 时其状态索引只是投影，
  不靠聚合 task progress 得出。
- 两层 progress 可并存，各按自身触发条件，永不强制全建。
- 落点：ticket 文件承载验收状态；`create-task-dag` 的 `dag.md` 可承载明确标为
  投影的 ticket 状态索引。ticket-level progress 触发规则写进 `dev-with-track`（复用其 ledger
  触发条件章节，标注"同规则适用于 ticket 层"）。

## 已定开放决策

1. 体系名：**Impl-Package**（已确认）。
2. composition 判定：tickets ⊥ dag 各自按需 earn（抛弃 S/M/L 线性档），
   earn 条件如上；跑两个真实 package 后按 rubric 校准（已确认路径）。
3. safety-review P0 项目特定项：放各 repo standards，不进 skill 本体（已确认）。
4. 调度：删除自动派工、worker leasing、并发锁；保留静态依赖图上的确定性
   readiness resolution。真多 worker 并行场景出现前不建动态调度器（已确认，
   YAGNI）。
