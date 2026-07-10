---
name: dev-with-track
description: >
  当用户想要 tracked implementation（追踪式实现）、implementation workspace
  执行账本、DAG/cohort 调度板、gate 决策、findings 更新、证据留存，或需要
  implementation-local design/spec/plan/账本角色划分时使用；也用于中途接入
  已有 spec/plan 并继续追踪执行。本 skill 只拥有追踪结构，不负责撰写
  spec/plan 本身。
---

# Dev With Track

创建或维护一个能在上下文丢失后恢复、支持并行执行的 implementation
workspace。持久单位是 implementation，不是一次聊天轮次，也不是单个 slice
文件。

核心循环：

```text
restore implementation -> update DAG -> execute task -> capture evidence -> promote findings -> decide gate
```

本 skill 只拥有追踪结构。产品语言、安全规则、命令和验收细节仍归 domain
skills、repo `AGENTS.md`、implementation plan 和验证文档所有。

## 配套 Skill

- `feature-impl-planning` 负责规划输入的撰写规则：`spec.md`、`plan.md` 和
  根目录 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`。本 skill 消费这些文件
  来刷新执行账本，不重定义它们的撰写规则。
- 需要 worker cohort、并行安全的任务分解、ownership 边界、seam 处理或
  whole-slice review 时，用 `create-task-dag` 提供调度方法。本 skill 提供
  持久容器，把它的输出落进下方文件角色；不在这里重实现 DAG 方法。

## Implementation Workspace

新的追踪工作创建一个 implementation slug 目录：

```text
docs/implementations/<implementation-slug>/
├── [design.md]
├── spec.md
├── plan.md
├── [YYYYMMDD-HHMM-<patch-topic>.patch-plan.md]
├── dag.md
├── [YYYYMMDD-HHMM-<patch-topic>.patch-dag.md]
├── findings.md
├── gate.md
└── tasks/
    ├── Tn-progress.md
    └── Tn-handoff.md
```

仓库已有不同约定的根目录时沿用它，但保持角色不变；按角色追踪，不按文件名。

## 文件角色

- `design.md`（可选）：implementation-local top design 和稳定文档回写来源：
  产品/PRD 笔记、架构/ARD 笔记、技术栈/运行时笔记、稳定文档回写地图。仅当
  本次实现产生了应回写 top-level/module PRD、module spec、ARD、Tech Stack 或 hands-on
  knowledge 的上层知识时创建；它本身不是稳定文档目的地。不要把它的内容复制
  进 `spec.md`；由 `spec.md` 引用它。
- `spec.md`（必须）：本 slug 的临时任务级 Func Design / implementation
  spec——功能合同、引用的稳定 spec、任务局部 delta、非目标、验收语义、待定
  决策。可厚可薄，但必须存在，作为 workspace 的功能合同入口。
- `plan.md`：初始实现计划和工程执行主控：实现策略、文件范围、任务概要、
  验证计划、验收清单。`spec.md` 存在时不要把功能行为主要写在这里。Patch
  模式不覆盖、不重命名 `plan.md`；如果初始计划已完成或不再是当前执行入口，
  在文件开头标记 `Deprecated / Superseded by <patch-plan-file>`，保留它作为
  历史实施证据。
- `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`：同一 slug 的 patch/follow-up
  执行输入。视为叠在 `spec.md` / `plan.md` 之上的计划 delta，映射进
  当前 DAG 和 task ledger，不覆盖初始 plan。
- `dag.md`：执行控制板：cohort、任务 ownership、seam、状态、gate 和验证
  证据。它是主 session 的实时调度面，不是详细日志。Patch 模式下，如果旧
  `dag.md` 已经 gate passed 或明确完成，可在文件开头标记
  `Retired / gate passed`，保留为上一批执行账本。
- `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`（可选）：当 patch/follow-up 的
  task graph materially changes，或旧 `dag.md` 已 retired 时使用。它是当前
  patch 的调度面，任务编号继续从 slug 内最高 `T<number>` 之后递增，不重排
  旧 DAG 任务。
- `tasks/Tn-progress.md`：需要独立记录的任务的局部进度账本。保持薄：恢复
  任务现场即可，不要变成迷你实现计划。
- `tasks/Tn-handoff.md`（可选）：仅当该任务需要跨 session 或跨 agent 的
  独立交接时创建。
- `findings.md`：跨任务的发现、风险、决策、后续项和可复用经验；不收普通
  任务局部日志。
- `gate.md`：implementation 级别的关闭档案。仅在关闭、阻塞或明确延期
  implementation 级验收时更新。

新实现不要用根 `process.md`；它会与 `plan.md` 和 `dag.md` 重复。遗留 slice
已有 `process.md` 时只把当前事实映射进上述角色。

## 中途接入

已有 ad-hoc spec / Func Design / 实现计划 / 旧 `process.md` 时，把它采纳进
slug workspace：移动为 `spec.md` / `plan.md` 并原地调整链接与追踪元数据。
不复制、不建 wrapper plan——重复的 plan 来源会迅速漂移。仅当用户明确要求
保留原路径、或移动会破坏已被接受的项目索引时，才让 `spec.md` / `plan.md`
作为短指针 wrapper 指向原路径。具体接入流程读
[references/control-flow.md](./references/control-flow.md)。

完成标准：implementation 有唯一清晰入口，`spec.md` 和 `plan.md` 都存在，
旧的 ad-hoc spec/plan 路径要么已移动要么被明确保留，仓库索引指向活跃的
implementation workspace。

## Task Ledger 触发条件

简单任务保持为 `dag.md` 一行。仅当满足至少一个触发条件时创建
`tasks/Tn-progress.md`：

- 独立 owner 或 subagent；
- 独立外部 gate（浏览器、IM、邮件、ERP、公共 smoke、production-like 验证等）；
- `NEEDS_SEAM`、blocker、reviewer finding 或未决决策；
- 预期跨 session 继续；
- 有必须保存的独立证据（record ID、smoke marker、截图、清理结果、目标身份等）；
- 影响最终 gate 但细节会挤爆 `dag.md`。

完成标准：每个有持久状态的任务都有 ledger；琐碎 seam 修改和一次性测试留在
`dag.md`。

不要默认发明其他任务级文档；证据、reviewer finding、局部笔记先进
`Tn-progress.md`。`Tn-handoff.md` 只在需要独立交接时创建。

任务编号在 slug 内稳定递增：新增任务前检查 `dag.md`、
`tasks/T*-progress.md`、`tasks/T*-handoff.md`、`plan.md` 和根目录
`*.patch-plan.md` / `*.patch-dag.md`，从最高 `T<number>` 之后继续编号。
不复用、不重排已有编号。

## Patch 模式

当用户明确要求 patch、follow-up、补丁计划，或该 implementation 已经被 owner
接受并开始执行/完成后出现新增需求、回归修复或增量范围时，进入 patch 模式。
已有 slug 只说明应复用 implementation workspace；如果当前仍处于需求理解、
spec/plan/DAG 规划阶段，需求纠正应原地更新现有规划文件，不得仅因 slug 已存在
就创建 patch plan。

```text
patch mode = same slug + updated spec + new patch-plan + retired old plan if completed + retired old dag if completed + new patch-dag when task graph materially changes + continued task numbering
```

具体规则：

- 规划期修订：implementation 尚未开始执行时，更新同一 slug 的 `spec.md`、
  `plan.md`、`dag.md`、`findings.md` 或 `gate.md` 的当前规划状态；不新增
  `*.patch-plan.md`、`*.patch-dag.md`，也不递增 task ID。
- 执行期增量：只有明确满足上面的 patch 触发条件时，才创建新的 patch plan；
  patch 必须说明它相对当前 spec/plan 的 delta，并继续使用该 slug 的 task
  numbering。

- 复用同一 implementation slug，不为 patch 另建第二个 slug。
- 原地更新 `spec.md`，使最新合同无歧义。
- 新增 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`，不覆盖 `plan.md`。
- `plan.md` 仍代表初始实施计划；如果已完成或不再是当前执行入口，在开头标记
  `Deprecated / Superseded by <patch-plan-file>`。
- `dag.md` 如果已经 gate passed 或只记录上一批执行账本，在开头标记
  `Retired / gate passed`。
- 当 patch 需要新的任务图、cohort、ownership 或 seam 调度时，新建
  `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`，并把它作为当前 patch 的执行
  控制板。
- patch task id 从 slug 内最高 `T<number>` 继续编号，不复用、不重排旧编号。

## 长期知识登记

implementation 关闭、阻塞或明确延期时，在 `gate.md` 登记本次产生的 durable
delta；登记不要求当场修改长期文档，后续 compaction/backfill 再执行压实。

对每条候选陈述先用两问 litmus 分类：

1. 若完全替换实现，只要用户价值不变，该陈述是否仍必须成立？是则属于意图。
2. 能否由测试、接口、状态查询或故障演练直接验证？是则属于行为合同。

一句陈述同时含 why 与 how 时拆成两条 delta，不在 PRD 与 spec 原样复制。每条
登记必须包含 destination、source、statement、受影响模块、authority 和 evidence；没有长期规则时
登记 `none` 并说明原因。四层目的地为：

- journey/产品级意图 -> `top-level-prd`；顶层 PRD journey 重构完成前写入
  `docs/module-knowledge/_pending.md`，记录 destination=`top-level-prd`、source、
  statement 与 authority，不继续扩写现有巨型 PRD；
- 模块级意图 -> `module-prd`，即
  `docs/module-knowledge/<module>/prd.md`；
- 模块行为合同 -> `module-spec`，即
  `docs/module-knowledge/<module>/spec.md` 或子域契约；
- 项目语言 -> `context-language`，即根 `CONTEXT.md`。

module PRD 惰性创建。普通 gate 遇到尚不存在的 `prd.md` 时只登记到
`docs/module-knowledge/_pending.md`，不得首建文件；只有 owner 审阅后的
backfill apply 才能首次创建。已有 `prd.md` 可由正常维护流程更新。首建 evidence
必须来自顶层 PRD、已批准 design、owner 决策或已确认 gate，不得只从代码反推
意图；内容还必须形成 Purpose、用户或 journey、Outcomes、Scope/Non-goals，
以及到顶层 PRD/module spec 的链接。

## 首读

1. 先读仓库指令：根 `AGENTS.md`、应用/工作区指令和相关验证文档。
2. 定位既有的 ad-hoc spec / Func Design、实现计划、根目录
   `*.patch-plan.md`、扁平 impl-plan、roadmap、handoff、process 账本、
   findings、gate 和证据。
3. 中途接入既有 spec/plan/patch plan、或判定 implementation 结束状态时读
   [references/control-flow.md](./references/control-flow.md)。
4. 需要脚手架时用 `assets/templates/` 下的模板。

## 操作规则

- 临时 `spec.md` 与稳定 module-knowledge / top-level PRD / ARD 文档保持区分。
  稳定文档回写是后续文档维护任务，除非用户明确把它纳入本次实现。
- 只提升跨任务结论到 `findings.md`。
- 证据诚实：记录实际运行了什么、跳过了什么、为什么。
- 验证命令用本仓库文档里的；不要从其他项目搬命令。

## 最小执行清单

1. 恢复或创建 implementation workspace。
2. 判断是否需要 `design.md` 承载 PRD/ARD/技术栈回写知识；需要时创建或更新。
3. 确认活跃的临时任务 spec 已体现为 `spec.md`，含中途采纳既有 ad-hoc
   spec / Func Design。
4. 确认活跃 plan 已体现为 `plan.md`，含中途采纳既有 plan。
5. 更新 `dag.md`：任务/cohort 状态、owner、gate/证据、seam 备注。
6. 按触发条件判断哪些任务需要 `tasks/Tn-progress.md`。
7. 执行或调度下一个受控任务。
8. 把任务证据写进 task ledger 或 `dag.md`。
9. 把跨任务发现提升到 `findings.md`。
10. implementation 级关闭、阻塞或延期决策变化时更新 `gate.md`，登记 durable
    delta（或 `none` + 原因）、destination、source、statement、受影响模块、
    authority 与 evidence。
11. 按角色汇报实现状态：design 状态（如存在）、spec 状态、plan 状态、
    DAG/cohort 状态、触碰的 task ledger、提升的 findings、gate 状态。

## 模板

仓库缺少对应账本时使用：

- `assets/templates/design.md`
- `assets/templates/dag.md`
- `assets/templates/progress.md`
- `assets/templates/handoff.md`
- `assets/templates/findings.md`
- `assets/templates/gate.md`

`spec.md` 与 `plan.md` 的 canonical 模板由 `feature-impl-planning` 维护
（`../feature-impl-planning/assets/templates/`）；本 skill 需要脚手架这两个
文件时使用那里的模板，不维护第二份。
