# 常青 Module-Knowledge 体系与回刷机制设计

## 来源与状态

- Created at: 2026-07-09
- Revised at: 2026-07-12（补充稳态使用与 backfill 授权边界）
- Source: brainstorming session（agent-workbench，基于 `D:\CodeSpace\TaskManager\20_Sources\2026-06-17-func-design-directory-repositioning.md` 定稿；owner 于 2026-07-10 先改为全量迁移，再确认常青层合并为 `docs/module-knowledge/` 并新增模块级 PRD）
- Status: 设计已批准并进入稳态使用；历史 Phase 1–3 仅记录首次项目的迁移和激活过程，不是当前调用步骤
- 首个实例项目: prj-supplyer-webapp

## 目标

把项目文档体系从「一次变更一份文档」演进为「常青真相 + 事件流 + 定期压实」：

1. 建立全项目长期的模块清单与模块级常青知识目录（`docs/module-knowledge/`）： 每个模块一个目录，`spec.md` 承载行为合同，`prd.md` 承载模块级意图。
2. 将旧 `func-design` 的当前行为规则全量蒸馏为模块合同，将当前纯模块意图延期 登记到 pending；审核通过后删除旧文档树，provenance 由 Git 历史与迁移台账 承担。
3. 以 dev-with-track 任务包为默认工作形态；任务关闭时登记长期规则，定期把 implementation 产物压实回常青文档。

## 当前稳态用法

1. 任意 terminal gate（pass/fail/defer）entry 写入前，`dev-with-track` 必须完成 durable delta 或 `none + reason` capture、`_pending.md` 注册、受影响 module truth pointer 与必要 stub。这是 gate 内关闭合同，不能延期给 backfill。
2. gate 关闭后只提示可按需通过 Codex 调用 `$stable-docs-backfill:backfill-stable-docs`。未运行 backfill 不影响 gate、交付或任务 closed；可以延期、批量或按周期维护。
3. `audit-stable-docs` 只有在用户明确要求、已有维护计划或周期任务上下文中才运行；它对 source 只读，只生成带 item ID 的 compaction report。`apply-stable-docs` 必须绑定 owner 明确批准的 report item ID；`verify-stable-docs` 独立检查 apply 结果。提示不构成 audit/apply/verify 授权，任一阶段完成也不得替代其他阶段的状态结论。
4. backfill 消费已 capture 的 delta，并通过 gate 漏登对账和无主 commit 扫描发现 capture gap；它不替 terminal gate 履行 Stage 7 capture，也不重新打开已关闭 gate。

## 心智模型

事件溯源 + 快照：

- implementation package-id 内 `spec.md` / `design.md` = 变更事件与事实来源；
- 常青文档（module-knowledge 的 prd/spec、顶层 PRD、ARD、项目语言、 tech-stack、hands-on）= 可直接阅读的当前快照；
- 回刷 = gate 后异步执行的 compaction / checkpoint；capture 已在 gate 内完成，回刷可以延期、批量和周期执行；
- Git 历史 + 迁移台账 = 已删除旧设计层的 provenance。

常青文档必须可以独立承载当前真相。旧专题设计不在最终仓库保留副本，也不能 成为现行文档或工具的运行依赖。

### 顶层当前知识纪律

`CONTEXT.md` 与 `docs/top-level-knowledge/**` 是当前产品知识，不是历史兼容层：只能陈述当前语言、意图、架构和行为。退役能力、历史字段和“历史只读”解释必须留在 Git 历史、migration ledger、implementation package 或 compaction record，不能保留在顶层当前合同中。

只有 owner 明确批准的 future capability 才能在顶层登记 TODO；该 TODO 必须标为 future / non-current，并写明目标与前提。没有此批准时，删除退役概念，不创建推测性的 TODO。

## 已定决策

| 决策点 | 结论 |
| --- | --- |
| 存量 func-design | 全量蒸馏；逐文件登记处置；五轮审核后删除整个旧树 |
| provenance | Git 历史 + task-local 迁移台账；不保留新的 archive/evidence 副本 |
| 常青层根目录 | `docs/module-knowledge/`（由 `module-specs/` 更名）；与 `top-level-knowledge/`、`implementations/` 构成同族三层命名；design 一词仍只用于变更时意图 |
| 模块目录形态 | 18 个模块全部为目录：`spec.md`（行为合同入口）+ `prd.md`（模块级意图，惰性创建）+ 按需 `_generated/`；不再有平铺单文件与升级协议 |
| module PRD | 惰性创建：首个意图类 durable delta 出现时才建 `prd.md`，不预建 18 个 stub；Phase 1 不创建任何 prd.md |
| journey 级意图 | 留在 `docs/top-level-knowledge/` 顶层 PRD；顶层 PRD 可继续粗粒度拆分（现有 2 份不敷使用），不新建中间层 |
| 模块清单 | 18 个封闭模块；新增模块需 owner 决策 |
| 大模块结构 | notifications、product-catalog-pricing、erp-order-documents 预先带子域契约文件；`spec.md` 为模块入口 |
| cross-module 规则 | 规则归属主模块 `spec.md`；其他模块在「边界与依赖」小节放指针，不复制 |
| 真相裁决 | 当前代码/测试 → PRD/ARD/CONTEXT 边界 → 较新设计；仍冲突则 owner gate |
| Phase 1 引用排除 | 只排除 `docs/exchange/**` 与 `docs/implementations/**` |
| Phase 2 范围 | gate 模板 + dev-with-track 主说明 + project-knowledge-manager 主说明 + routing taxonomy（目的地枚举含 module-prd）；不新增自动测试 |
| Phase 3 首轮 | 用明确的 5 个遗留 implementation package-id（旧称 slug）做 bootstrap，不无界扫描历史 |
| audit/apply/verify | audit 只提案；apply 经 owner 审核后执行并修复 bootstrap 包旧引用；verify 独立检查结果 |
| worktree | webapp 与 agent-workbench 均在隔离 worktree 开发；未合入 skill 不影响全局 junction |

## 最终项目结构

```text
docs/module-knowledge/
  README.md                    # 机制文档：清单、角色、准入、压实约定
  _pending.md
  _compaction/
    README.md
    bootstrap-2026-07.md       # Phase 3 创建；固定首轮 legacy package-id 清单
    YYYY-MM-DD-report.md
  <15 个低密度模块>/
    spec.md                    # 行为合同（模块入口）
    prd.md                     # 模块级意图；惰性创建，初始不存在
  notifications/
    spec.md
    email-event-matrix.md
    _generated/
      email-event-matrix.lark.md
      email-event-matrix.lark.json
  product-catalog-pricing/
    spec.md
    product-definition.md
    pricing-and-effective-configuration.md
    catalog-and-master-data.md
  erp-order-documents/
    spec.md
    delivery-notes.md
    invoices.md
    shared-lines-sync-and-evidence.md
```

最终不存在 `docs/module-knowledge/_archive/func-design/`，也不存在旧根 `docs/module-specs/`。

## 四层常青定位

| 层 | 回答什么 | Home |
| --- | --- | --- |
| 产品级意图 | why / journey 级用户价值 | `docs/top-level-knowledge/`（顶层 PRD，可继续粗粒度拆分）与根 `CONTEXT.md` |
| 模块级意图 | 该模块为何存在、承载什么价值切片 | `docs/module-knowledge/<module>/prd.md`（惰性创建） |
| 模块级契约 | how-it-behaves / 接口、状态、边界、失败与验收 | `docs/module-knowledge/<module>/spec.md` 及子域契约文件 |
| 变更时设计 | 这次为什么、怎么改 | `docs/implementations/<package-id>/` |

顶层 PRD 描述产品全貌与 journey 级叙事，下钻引用各模块 `prd.md`；模块 `prd.md` 描述该模块承载的意图切片；`spec.md` 描述当前系统行为合同； implementation 任务包记录 point-in-time 变更。四者不得互相替代。层间纪律 靠固定文件角色（`prd.md` / `spec.md`）保障，不靠目录分离。

### 跨模块 journey 与引用纪律

一个 journey 可以跨多个模块，但端到端 intent 只有一个 owner：

1. 顶层 PRD 的 journey anchor 拥有端到端用户目标、参与者/阶段、跨模块 outcome 与 journey-level invariant；persona 只是适用标签，不按 Customer/Supplier surface 复制 journey。
2. 每个受影响 module `prd.md` 只写本模块对该 journey 的价值贡献、责任边界与 non-goals，并反向链接 journey anchor，不复制完整 journey。
3. 可验证行为、接口和状态由 module `spec.md` 拥有。真正跨模块的 rule/seam 选择一个 primary contract owner（最能执行和裁决规则的模块），其他 module spec 在“边界与依赖”引用该 anchor；若无法合理确定 owner，升级为 ARD/top-level contract owner decision，不能多模块双写。
4. `docs/implementations/<package-id>/design.md` 只记录本次跨模块变化的选择、影响图、迁移/rollout、seam 协调和 expected canonical deltas；package `spec.md` 保存本次批准的 acceptance/contract delta。二者引用 journey/module anchors，不复制常青全文。gate capture 为每个 durable delta 指定唯一 destination；backfill 后 package 保留事件 provenance，不成为长期 SoT。

引用链固定为：`journey anchor → module PRD contribution → primary module spec contract（dependent specs 只引用）→ implementation package change delta`。

### 方法论归属

| Owner | 拥有内容 |
| --- | --- |
| `dev-with-track` | terminal gate entry 写入前完成 Stage 7 durable-delta capture；blocked 的 capture gap 只由后续 entry 补齐；保留两问 litmus 本体 |
| `project-knowledge-manager` | hands-on knowledge 维护与跨文档层的入口分流；不复制 module 层压实方法 |
| `backfill-stable-docs` | gate 后按明确授权路由 `audit-stable-docs`、`apply-stable-docs`、`verify-stable-docs`；入口不执行具体阶段，也不替 gate 履行 capture |
| 项目 `docs/module-knowledge/` | 当前模块意图与行为合同快照；项目路径和 module 清单留在项目侧 README |

module `prd.md` 超过 250 行时触发 owner 内容审查；首建内容不足以形成 Purpose、 用户或 journey、Outcomes、Scope/Non-goals 以及到顶层 PRD/module spec 的链接时， 继续保留在 `_pending.md`，不创建薄弱文件。

## 附录：首次迁移与激活历史

以下 Phase 1–3、bootstrap、worktree 与两仓库交付顺序只记录首个实例项目的迁移 provenance，不得作为当前 agent 的执行路由。当前用法以上文“当前稳态用法”为准。

### 历史 Phase 1：全量迁移

### 根更名与模块目录化（蒸馏前的机械步）

蒸馏动工前先完成一次独立的机械结构 commit：

1. `docs/module-specs/` 整体更名为 `docs/module-knowledge/`（含 `_archive/`）；
2. 18 个平铺 `<module>.md` stub 改为 `<module>/spec.md`；
3. 重跑正式引用扫描，把仓库内 `docs/module-specs/` 旧字符串全部改到新路径 （即重做一轮先前骨架引用修复的工作）。

本步只做 archive 路径随根目录的机械迁移，不把旧专题语义猜测性重定向到尚未 蒸馏完成的 module spec；从旧专题到新合同具体小节的语义重定向留到蒸馏和正式 引用更新完成后执行。

此后迁移台账、审核记录与全部后续工作只使用新路径。Phase 1 不创建任何 `prd.md`：真正约束模块 authority 的 scope/non-goals 可按 `distill` 进入 `spec.md`；当前仍有效的纯意图不得塞入 spec 或丢弃，按 `defer-module-prd` 登记到 `_pending.md`，由 Phase 2 后的 backfill 在具备最小内容时惰性建档。

### 输入基线与处置台账

prj-supplyer-webapp 旧树实测共 99 个文件：95 Markdown、2 HTML、2 JSON。 此前 `module-mapping-dryrun.md` 的「94/94」不能作为覆盖验收：其模块清单映射 91 个 Markdown，未映射项实际是 `README.md`、`customer-poc-demo-design.md`、 `2026-06-02-email-event-matrix.lark.md`，但报告误写成 `.lark.json`。

实施时创建 `migration-ledger.md`，每个旧文件恰好一行：

```text
| 源文件 | 目标文件/小节 | 处置 | 当前性 | 事实依据 | 起草 | 审核 |
```

删除旧树后，verifier 使用 `git ls-tree -r HEAD --name-only -- docs/module-knowledge/_archive/func-design` 从删除前的 HEAD tree 重放 99 文件覆盖 检查并与台账对账；无需另建 manifest。该命令必须在旧树已从工作区删除、删除 commit 尚未提交时运行。

verifier 只提供一个无参数命令，每次全量执行：旧树存在时从工作区枚举，旧树 不存在时从上述 HEAD tree 枚举，并自动应用对应的删除前/删除后断言。

处置枚举：

- `distill`：当前有效规则写入指定模块 `spec.md`（或子域契约文件）小节；
- `relocate-generated`：生成物改到新路径并验证可重复生成；
- `superseded-no-copy`：被替代规则不进入当前合同，台账记录替代依据；
- `presentation-no-copy`：纯展示附件确认无独有规则后删除。
- `defer-module-prd`：当前有效的纯模块意图不进入 spec；写入 `_pending.md`， 记录目标模块、原始来源与意图 authority，等待后续 backfill 创建或更新 `prd.md`。

“全量”表示全部 99 个文件都有可审计处置，不表示把废弃结论原样复制进当前 模块合同。每条 `defer-module-prd` 必须在 `_pending.md` 中恰好有一条对应记录。

### 模块 spec 合同结构

每个模块的 `spec.md` 入口包含：

1. Scope、authority、non-goals；
2. 核心术语与数据合同；
3. 当前行为、状态和工作流；
4. 模块边界与依赖；
5. 失败模式与恢复语义；
6. 约束型合同：禁止事项、信任边界、数值精度与归一化、外部 provider 义务、负依赖；
7. 验收与验证依据；
8. `Pending deltas`。

正文不得链接即将删除的旧设计。来源到目标小节的追踪只保留在迁移台账和 Git 历史。

### 特殊文件处置

- 旧目录 `README.md`：由新 module-knowledge README 和迁移台账取代；
- `customer-poc-demo-design.md`：有效规则分散到对应模块，不保留 demo 副本；
- `archive/customer-type-base-pricing.md`：当前规则进入 pricing 子域，旧规则 标为 superseded；
- UOM HTML 看板、SKU truth HTML/JSON：用于语义核对，确认无独有当前规则后 删除，不建立 evidence 目录；
- Email Matrix：权威 Markdown 与两个生成物迁到 notifications 子域，脚本改 新路径，重复生成一致后删除旧文件。

### 引用处理边界

Phase 1 只允许以下目录保留旧引用：

- `docs/exchange/**`：临时对齐记录；
- `docs/implementations/**`：交给 Phase 3 bootstrap。

其余保留文件全部改到新 module-knowledge 路径，包括 top-level 文档、impl-plans 及其 archive、project-progress、reviews、test-cases、hands-on、项目内 skills、 脚本与配置。引用应尽量指向具体模块 `spec.md`、子域文件或小节。旧路径共三种： `docs/func-design/`、`docs/module-specs/_archive/func-design/`，以及更名后残留 的 `docs/module-specs/` 本身。

KaiSpan 删除 `previousContextPath`，保留 `contextPath: docs/kaispan-ui-design`， 不创建替代路径。

除三种旧路径字符串扫描外，对本次修改过的 Markdown 链接按源文件解析相对 路径，验证目标文件与 anchor 存在。外部 Lark 文档、routine prompt 和用户级 junction 使用人工 checklist，不扩展为全仓链接图。

### 五轮审核

1. **覆盖审核**：99 行、源文件唯一、无遗漏、无 `unmapped`；
2. **语义审核**：对照代码/测试/顶层文档，正确处理当前、废弃与冲突结论； 按模块 cohort 分批由隔离 subagent 执行，逐行给出证据；cohort reviewer 的 证据即 Gate 2 分片，最终只汇总核对完整性并确认 owner conflict 清零，不重跑 语义审核；
3. **模块审核**：检查跨模块归属和重复定义；此轮需要合并视图，不得用隔离 subagent 分批；
4. **引用审核**：在明确排除范围外，三种旧路径引用均为零；
5. **删除后审核**：删除旧树后，只读 module-knowledge、当前代码、测试与顶层 文档，填写 18×6 链接表；每格只允许“文件#anchor + 一行结论”，回答模块 拥有/不拥有什么、核心行为或状态流程、主要失败与恢复语义、跨模块规则由谁 拥有、哪些代码或测试验证当前合同，以及本模块承诺不做、不信任或不依赖 什么。任一格答不出或缺少具体引用即失败。

Gate 5 禁止读取 Git 旧版本只约束语义 reviewer；verifier 使用 `git ls-tree` 仅做机械覆盖对账，不属于语义输入。

任一轮失败，都不得删除旧树或合入本地 `develop`。

### 历史 Phase 2：建立 gate 内 capture 合同

Phase 2 与 Phase 1 并行在 agent-workbench 隔离 worktree 开发，修改：

- `skills/impl-package/dev-with-track/assets/templates/gate.md`；
- `skills/impl-package/dev-with-track/SKILL.md`；
- `skills/project-knowledge-manager/SKILL.md`；
- `skills/project-knowledge-manager/references/routing-taxonomy.md`。

terminal gate entry 写入前（延期的是后续压实，不是本次 capture）：

- 有长期规则：登记一句话 delta、目标长期文档和受影响模块；
- 没有长期规则：明确记录“没有”及原因；
- 登记不要求当场改完长期文档；后续由 backfill audit、approved apply 和 independent verify 压实并验收。

当前 attempt 先保留下一个 gate entry id，并以该 id 完成 `_pending.md` 注册、受影响 module spec truth pointer 与必要 stub；随后一次性把不可变 entry 插入单一 `gate.md` 顶部。blocked entry 的 capture gap 由后续 entry 补齐，不回改旧 entry。

长期规则分流使用两问 litmus：

1. 若完全替换实现，只要用户价值不变，该陈述是否仍必须成立？是则属于意图；
2. 能否由测试、接口、状态查询或故障演练直接验证？是则属于行为合同。

一句陈述同时包含 why 与 how 时拆成两个 delta，不在 prd/spec 两处原样复制。 gate 保持轻量，只要求 durable delta（或 `none` + 原因）、destination、statement 与 evidence。创建首份 module PRD 的 evidence 必须来自顶层 PRD、已批准 design、 owner 决策或已确认 gate，不得仅从代码反推意图；内容不足以形成 Purpose、用户或 journey、Outcomes、Scope/Non-goals 以及到顶层 PRD/module spec 的链接时，继续 保留在 `_pending.md`。

routing taxonomy 与 `_pending.md` 的目的地枚举按四层定位改写：

- 模块行为合同 → `docs/module-knowledge/<module>/spec.md`（或子域文件）；
- 模块级意图 → `docs/module-knowledge/<module>/prd.md`（`module-prd`； 文件不存在时由 apply 首次创建）；
- journey 级 / 产品级意图 → 顶层 PRD；
- 项目语言 → 根 `CONTEXT.md`（`context-language`）。

本阶段不新增自动测试。实施必须保留当前 workbench `dev-with-track/SKILL.md` 中尚未提交的 patch-mode 修订。在 routing taxonomy 末尾加入一张轻量人工 fixture 表，覆盖 module-spec、module-prd、top-level-prd、context-language、变更时 design 与无 durable delta 六类输入，列出预期目的地和是否建档，并纳入人工验收。 在顶层 PRD journey 重构完成前，新增 `top-level-prd` delta 只登记 pending， 不继续扩写现有两份巨型 PRD。skill worktree 合入前，全局 junction 继续使用当前 `main`。

### 历史 Phase 3：有界 bootstrap 与稳态回刷激活

Phase 3 skill 的创建时机提前到 Phase 1/2 完成后、两仓库合入前，以便先做首次 真实 report 试金石。激活门不变：不修改全局 junction，不在 owner 审阅首次 真实运行前合入 `main`；正式启用仍遵守两仓库交付顺序。

### Bootstrap

首轮只扫描以下 5 个 legacy package-id：

1. `inventory-item-default-replenishment-unit`；
2. `manufacture-recipe-inventory-granularity`；
3. `order-snapshot-reuse`；
4. `product-external-spec-field-cleanup`；
5. `products-inventory-link-cleanup`。

report 读取全部 5 个并分类 gate 状态。只有 gate/owner 已确认的长期规则可进入 module-knowledge（合同进 `spec.md`，意图进 `prd.md`）；旧链接迁移与规则采纳 分开判断。apply 在当前 webapp worktree 中把 5 个包的旧设计引用改到新 module-knowledge 路径，即使任务未完成也可修复链接，但不得把其未确认设计写成 当前合同。

### 稳态 watermark

稳态 watermark 使用 Phase 2 实际合入并启用的 commit，不再以 2026-07-09 日期无界扫描历史。bootstrap 完成后，后续 audit 才按 watermark 扫描新关闭任务和无主 commit。

### Audit / apply / verify

- gate 后不自动调用；`audit-stable-docs` 只在用户明确要求、已有维护计划或周期任务上下文中运行，对 source 只读，收集 pending、gate 后漏登和无主 commit，生成带 item ID 的建议报告；
- `apply-stable-docs` 只有在 owner 明确批准具体 report item ID 后触发，更新长期文档、清理 pending、修复获批引用并推进 watermark；
- `verify-stable-docs` 独立检查 authority、链接、覆盖率、pending、watermark 和残留，不以 audit 或 apply 状态替代；
- audit/apply/verify 均可延期且不回开已关闭 gate，也不影响当前交付或任务 closed；
- 首轮通过 Codex Plugin 显式调用，不修改全局根 Skill；
- owner 审阅首次 audit/apply/verify 后，才启用 Plugin；每周 Automation 最后创建。

### 历史两仓库交付顺序

1. webapp Phase 1 与 agent-workbench Phase 2 并行完成；
2. Phase 1 五轮审核全部通过；
3. webapp 分支先合入本地 `develop`；
4. agent-workbench 分支随后立即合入 `main`，全局 skill 启用新规则；
5. 用新 gate 继续真实开发；
6. Phase 3 Plugin 已在独立 worktree 提前创建；此处审阅其首次 audit/apply/verify 试金石并确认激活门；
7. 审核通过后合入 Phase 3 Plugin，并最后创建每周 audit Automation。

Phase 1 保持整分支一次合入，不采用结构 checkpoint 或 cohort 分批合入。迁移 开始前同步一次本地 `develop`，最终五轮审核开始前再同步一次；若第二次同步触及 代码、测试、PRD、ARD 或 CONTEXT，Gate 2 必须确认相关事实依据仍有效。

Phase 1 完成后立即为顶层 PRD 按 journey 粗粒度重构单独立项；persona 作为适用 范围标签，不再继续按 Customer/Supplier surface 扩张。该后继任务不属于本次 迁移，也不在本设计中预先锁定最终文件名。

## 风险与守护

| 风险 | 守护 |
| --- | --- |
| 全量蒸馏漏文件 | 99 行唯一处置台账 + task-local verifier |
| 废弃规则污染当前合同 | 固定真相裁决顺序 + owner conflict gate |
| 根更名造成引用断链 | 更名为独立机械 commit；verifier 把 `docs/module-specs/` 列入旧路径清单 |
| prd/spec 层混淆 | 固定文件角色命名 + routing taxonomy 明确目的地；prd 惰性创建避免空壳 |
| 模块边界重叠 | 独立模块审核与跨模块组合复核 |
| 删除后文档不可用 | clean-room 删除后审核；失败即阻塞合入 |
| 工具依赖旧路径 | 正式引用全量扫描 + Email Matrix 重复生成验证 |
| 新 gate 早于新目录启用 | webapp 先合，agent-workbench 随后合 |
| 首轮 backfill 报告失控 | 固定 5 个 bootstrap legacy package-id；稳态 watermark 从 Phase 2 activation commit 起 |
| worktree 修改影响现用 skill | junction 保持指向当前 `main`；新 skill 从 worktree 显式试跑 |
| 把 backfill 当作 gate 前置条件 | 明确 gate 内 capture 与 gate 后 compaction 分层；backfill 可延期且不阻塞 terminal gate |
| 把提示误当执行授权 | report 需要明确维护上下文；apply 还需 owner 批准具体 report item ID |
