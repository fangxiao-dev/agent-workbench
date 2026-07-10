# 常青 Module-Spec 体系与回刷机制设计

## 来源与状态

- Created at: 2026-07-09
- Revised at: 2026-07-10
- Source: brainstorming session（agent-workbench，基于
  `D:\CodeSpace\TaskManager\20_Sources\2026-06-17-func-design-directory-repositioning.md`
  定稿，并由 owner 于 2026-07-10 改为全量迁移）
- Status: 设计已批准，Phase 1/2 待按修订计划完成
- 首个实例项目: prj-supplyer-webapp

## 目标

把项目文档体系从「一次变更一份文档」演进为「常青真相 + 事件流 + 定期压实」：

1. 建立全项目长期的模块清单与模块级常青 spec（`module-specs/`）。
2. 将旧 `func-design` 全量蒸馏为当前模块合同；审核通过后删除旧文档树，
   provenance 由 Git 历史与迁移台账承担。
3. 以 dev-with-track 任务包为默认工作形态；任务关闭时登记长期规则，定期把
   implementation 产物压实回常青文档。

## 心智模型

事件溯源 + 快照：

- slug 内 `spec.md` / `design.md` = 变更事件与事实来源；
- 常青文档（module-spec、PRD、ARD、项目语言、tech-stack、hands-on）=
  可直接阅读的当前快照；
- 回刷 = 对新事件做 compaction / checkpoint；
- Git 历史 + 迁移台账 = 已删除旧设计层的 provenance。

常青文档必须可以独立承载当前真相。旧专题设计不在最终仓库保留副本，也不能
成为现行文档或工具的运行依赖。

## 已定决策

| 决策点 | 结论 |
| --- | --- |
| 存量 func-design | 全量蒸馏；逐文件登记处置；五轮审核后删除整个旧树 |
| provenance | Git 历史 + task-local 迁移台账；不保留新的 archive/evidence 副本 |
| 常青层命名 | `module-specs/`；design 一词只用于变更时意图 |
| 模块清单 | 18 个封闭模块；新增模块需 owner 决策 |
| 大模块结构 | notifications、product-catalog-pricing、erp-order-documents 预先升级为子域目录 |
| 真相裁决 | 当前代码/测试 → PRD/ARD/CONTEXT 边界 → 较新设计；仍冲突则 owner gate |
| Phase 1 引用排除 | 只排除 `docs/exchange/**` 与 `docs/implementations/**` |
| Phase 2 范围 | gate 模板 + dev-with-track 主说明 + project-knowledge-manager 主说明 + routing taxonomy；不新增自动测试 |
| Phase 3 首轮 | 用明确的 5 个遗留 implementation slug 做 bootstrap，不无界扫描历史 |
| report/apply | report 只提案；apply 经 owner 审核后执行，并修复 bootstrap 包旧引用 |
| worktree | webapp 与 agent-workbench 均在隔离 worktree 开发；未合入 skill 不影响全局 junction |

## 最终项目结构

```text
docs/module-specs/
  README.md
  _pending.md
  _compaction/
    README.md
    bootstrap-2026-07.md       # Phase 3 创建；固定首轮 slug 清单
    YYYY-MM-DD-report.md
  <15 个低密度模块>.md
  notifications/
    README.md
    email-event-matrix.md
    _generated/
      email-event-matrix.lark.md
      email-event-matrix.lark.json
  product-catalog-pricing/
    README.md
    product-definition.md
    pricing-and-effective-configuration.md
    catalog-and-master-data.md
  erp-order-documents/
    README.md
    delivery-notes.md
    invoices.md
    shared-lines-sync-and-evidence.md
```

最终不存在 `docs/module-specs/_archive/func-design/`。

## 三层常青定位

| 层 | 回答什么 | Home |
| --- | --- | --- |
| 产品级意图 | why / 用户得到什么 | `docs/top-level-knowledge/` 与根 `CONTEXT.md` |
| 模块级契约 | how-it-behaves / 接口、状态、边界、失败与验收 | `docs/module-specs/` |
| 变更时设计 | 这次为什么、怎么改 | `docs/implementations/<slug>/` |

PRD 描述产品意图和受众价值；module-spec 描述当前系统行为合同；implementation
任务包记录 point-in-time 变更。三者不得互相替代。

## Phase 1：全量迁移

### 输入基线与处置台账

prj-supplyer-webapp 旧树实测共 99 个文件：95 Markdown、2 HTML、2 JSON。
此前 `module-mapping-dryrun.md` 的「94/94」不能作为覆盖验收：其模块清单映射
91 个 Markdown，未映射项实际是 `README.md`、`customer-poc-demo-design.md`、
`2026-06-02-email-event-matrix.lark.md`，但报告误写成 `.lark.json`。

实施时创建 `migration-ledger.md`，每个旧文件恰好一行：

```text
| 源文件 | 目标 module-spec/小节 | 处置 | 当前性 | 事实依据 | 起草 | 审核 |
```

处置枚举：

- `distill`：当前有效规则写入指定 module-spec 小节；
- `relocate-generated`：生成物改到新路径并验证可重复生成；
- `superseded-no-copy`：被替代规则不进入当前合同，台账记录替代依据；
- `presentation-no-copy`：纯展示附件确认无独有规则后删除。

“全量”表示全部 99 个文件都有可审计处置，不表示把废弃结论原样复制进当前
module-spec。

### Module-spec 合同结构

每个模块入口包含：

1. Scope、authority、non-goals；
2. 核心术语与数据合同；
3. 当前行为、状态和工作流；
4. 模块边界与依赖；
5. 失败模式与恢复语义；
6. 验收与验证依据；
7. `Pending deltas`。

正文不得链接即将删除的旧设计。来源到目标小节的追踪只保留在迁移台账和
Git 历史。

### 特殊文件处置

- 旧目录 `README.md`：由新 module-spec README 和迁移台账取代；
- `customer-poc-demo-design.md`：有效规则分散到对应模块，不保留 demo 副本；
- `archive/customer-type-base-pricing.md`：当前规则进入 pricing 子域，旧规则
  标为 superseded；
- UOM HTML 看板、SKU truth HTML/JSON：用于语义核对，确认无独有当前规则后
  删除，不建立 evidence 目录；
- Email Matrix：权威 Markdown 与两个生成物迁到 notifications 子域，脚本改
  新路径，重复生成一致后删除旧文件。

### 引用处理边界

Phase 1 只允许以下目录保留旧引用：

- `docs/exchange/**`：临时对齐记录；
- `docs/implementations/**`：交给 Phase 3 bootstrap。

其余保留文件全部改到新 module-spec，包括 top-level 文档、impl-plans 及其
archive、project-progress、reviews、test-cases、hands-on、项目内 skills、
脚本与配置。引用应尽量指向具体子域文件或小节。

KaiSpan 删除 `previousContextPath`，保留 `contextPath: docs/kaispan-ui-design`，
不创建替代路径。

### 五轮审核

1. **覆盖审核**：99 行、源文件唯一、无遗漏、无 `unmapped`；
2. **语义审核**：对照代码/测试/顶层文档，正确处理当前、废弃与冲突结论；
3. **模块审核**：检查跨模块归属和重复定义；
4. **引用审核**：在明确排除范围外，两种旧路径引用均为零；
5. **删除后审核**：删除旧树后，只读 module-spec、当前代码、测试与顶层文档，
   仍能回答模块合同、状态、失败与边界问题。

任一轮失败，都不得删除旧树或合入本地 `develop`。

## Phase 2：任务结束时登记长期规则

Phase 2 与 Phase 1 并行在 agent-workbench 隔离 worktree 开发，修改：

- `skills/dev-with-track/assets/templates/gate.md`；
- `skills/dev-with-track/SKILL.md`；
- `skills/project-knowledge-manager/SKILL.md`；
- `skills/project-knowledge-manager/references/routing-taxonomy.md`。

gate 关闭时：

- 有长期规则：登记一句话 delta、目标长期文档和受影响模块；
- 没有长期规则：明确记录“没有”及原因；
- 登记不要求当场改完长期文档；后续由 backfill report/apply 压实。

本阶段不新增自动测试。实施必须保留当前 workbench `dev-with-track/SKILL.md`
中尚未提交的 patch-mode 修订。skill worktree 合入前，全局 junction 继续使用
当前 `main`。

## Phase 3：有界 bootstrap 与稳态回刷

### Bootstrap

首轮只扫描以下 5 个 slug：

1. `inventory-item-default-replenishment-unit`；
2. `manufacture-recipe-inventory-granularity`；
3. `order-snapshot-reuse`；
4. `product-external-spec-field-cleanup`；
5. `products-inventory-link-cleanup`。

report 读取全部 5 个并分类 gate 状态。只有 gate/owner 已确认的长期规则可进入
module-spec；旧链接迁移与规则采纳分开判断。apply 在当前 webapp worktree 中
把 5 个包的旧设计引用改到新 module-spec，即使任务未完成也可修复链接，但不得
把其未确认设计写成当前合同。

### 稳态 watermark

稳态 watermark 使用 Phase 2 实际合入并启用的 commit，不再以 2026-07-09
日期无界扫描历史。bootstrap 完成后，后续 report 才按 watermark 扫描新关闭
任务和无主 commit。

### Report / apply

- `report`：只读，收集 pending、gate 后漏登和无主 commit，生成建议报告；
- `apply`：人工审阅报告后触发，更新长期文档、清理 pending、修复获批引用并
  推进 watermark；
- 首轮从 agent-workbench Phase 3 worktree 显式调用，不修改全局 junction；
- owner 审阅首次 report/apply 后，才合入新 skill；每周 routine 最后创建。

## 两仓库交付顺序

1. webapp Phase 1 与 agent-workbench Phase 2 并行完成；
2. Phase 1 五轮审核全部通过；
3. webapp 分支先合入本地 `develop`；
4. agent-workbench 分支随后立即合入 `main`，全局 skill 启用新规则；
5. 用新 gate 继续真实开发；
6. Phase 3 skill 在独立 worktree 完成 bootstrap report/apply 试金石；
7. 审核通过后合入 Phase 3 skill，并最后创建每周 report routine。

## 风险与守护

| 风险 | 守护 |
| --- | --- |
| 全量蒸馏漏文件 | 99 行唯一处置台账 + task-local verifier |
| 废弃规则污染当前合同 | 固定真相裁决顺序 + owner conflict gate |
| 模块边界重叠 | 独立模块审核与跨模块组合复核 |
| 删除后文档不可用 | clean-room 删除后审核；失败即阻塞合入 |
| 工具依赖旧路径 | 正式引用全量扫描 + Email Matrix 重复生成验证 |
| 新 gate 早于新目录启用 | webapp 先合，agent-workbench 随后合 |
| 首轮 backfill 报告失控 | 固定 5 个 bootstrap slug；稳态 watermark 从 Phase 2 activation commit 起 |
| worktree 修改影响现用 skill | junction 保持指向当前 `main`；新 skill 从 worktree 显式试跑 |
