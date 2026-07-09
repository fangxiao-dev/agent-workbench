# 常青 Module-Spec 体系与回刷机制设计

## 来源与状态

- Created at: 2026-07-09
- Source: brainstorming session（agent-workbench，基于
  `D:\CodeSpace\TaskManager\20_Sources\2026-06-17-func-design-directory-repositioning.md` 定稿的落地设计）
- Status: 设计已批准，待实施规划
- 首个实例项目: prj-supplyer-webapp

## 目标

把项目文档体系从「一次变更一份文档」演进为「常青真相 + 事件流 + 定期压实」：

1. 建立全项目长期的模块清单与模块级常青 spec（`module-specs/`）。
2. 存量文档按「骨架 + 归档 + 碰到才刷」处理，不做批量蒸馏。
3. 以 dev-with-track 任务包为默认工作形态，配套「回刷」机制把 ad-hoc
   任务产物定期压实回全部常青文档层。

## 心智模型

事件溯源 + 快照：

- slug 的 temporary spec / design.md = append-only 事件流（事实源）；
- 常青文档（module-spec、PRD、ARD、ubiquitous-language、tech-stack、
  hands-on）= 物化读模型；
- 回刷 = compaction / checkpoint。

该模式唯一的死法：压实掉链子 → 读模型陈旧 → 没人信常青文档。本设计的全部
加固都针对这一点。

## 已定决策

| 决策点 | 结论 |
| --- | --- |
| 存量 83 个旧 func-design | 维持定稿：建骨架 → 整体归档 `_archive/` → 碰到才刷惰性回填，不批量蒸馏 |
| 机制层级 | 通用 workbench skill + 项目实例（模块清单、README、Pending 约定属于各项目 repo） |
| 常青层命名 | `module-specs/`（弃 func-design；design 一词保留给变更时意图，即 slug 内 design.md） |
| 目录结构 | 按模块平铺；单文件过大才升级为子目录，切分维度是子域，永远不按 feature 切 |
| 粒度控制 | 模块清单是封闭集：新模块须先过清单准入（owner 决策），README 写死目标区间与准入规则 |
| `_pending.md` 定位 | 仅为加速索引，不是事实源；事实源永远是 slug 目录 |
| 回刷范围 | 全部常青层（module-spec、PRD、ARD、ubiquitous-language、tech-stack、hands-on），不只 spec |
| 合入方式 | 定时 routine 只产报告（report 模式）；合入是独立的人工触发步骤（apply 模式） |
| 机制自优化 | 每轮压实报告作为 `/improve-skill` 的 rubric 证据，回刷 skill 进偏好闭环 |

## 项目实例结构（以 prj-supplyer-webapp 为例）

```text
docs/module-specs/
  README.md            # 三层定位、模块清单与准入规则、Pending deltas 约定、回刷机制说明
  _archive/            # 旧 func-design 整体归档，保留 provenance
  _pending.md          # promotion candidate 索引队列
  _compaction/         # 回刷报告与压实日志（含 watermark）
    YYYY-MM-DD-report.md
  <module>.md          # 一个模块 = 一个文件（默认）
  <big-module>/        # 例外：单文件过大时升级
    README.md          # 模块内索引
    <sub-domain>.md
```

三层常青定位（altitude 不同，都常青）：

| 层 | 回答什么 | Home |
| --- | --- | --- |
| 产品级意图 | why / 用户得到什么 | `top-level-knowledge/`（prd-*、ard、ubiquitous-language） |
| 模块级契约 | how-it-behaves / 接口·状态机·边界·失败模式·验收 | `module-specs/` |
| 变更时设计（point-in-time） | 这次怎么改 | `docs/implementations/<slug>/`（dev-with-track） |

模块 PRD 与模块 spec 的边界：PRD-* = 产品意图/受众价值；module-spec =
系统行为契约。两者都常青、都模块级，必须保持锐利。

## 模块清单（封闭集）

- 来源：从 `ard.md` + `ubiquitous-language.md` 抽取，单一 owner。
- 清单即准入闸门：spec 文件只能对应清单内模块；新增模块 = 清单变更 =
  owner 决策。
- README 写死目标区间（首版建议 10~25 个模块）。目标区间 = 清单允许的
  模块数量带宽，是粒度的双向护栏：过少说明 spec 会变成大杂烩，过多说明
  实际在按 feature 切。抽清单时结果落在区间外，先合并或拆分粒度再定稿；
  接近上限时的正确动作是合并或升级子目录，不是继续铺。

## 捕获（capture）

落点：dev-with-track `gate.md` 模板的 Spec Backfill 节升级。

- gate 关闭时，实施者把「本 slug 改了哪些常青层持久事实」追加进项目
  `_pending.md`，一行一条：

  ```text
  | 目的地 | slug | 一句话 delta | 登记日期 |
  ```

  目的地枚举：`module-spec/<module>` | `prd-*` | `ard` |
  `ubiquitous-language` | `tech-stack` | `hands-on`。
- 同时在受影响的模块 spec 顶部维护真相指针：
  `Pending deltas: <slug-a>, <slug-b>`（未压实期间读者以这些 slug 为准；
  压实后清空）。目标文件是空 stub 时先建 stub 再挂行。
- 阈值：无 durable delta 的任务显式勾选跳过，不给琐碎任务加税。
- 捕获是必过闸门但按「尽力」设计：漏登由回刷的对账兜底，不由纪律兜底。

## 回刷 skill：`backfill-stable-docs`

通用 workbench skill，两个模式：

### report 模式（默认，定时 routine 跑它，只读）

1. **双源收集**：
   - 快路径：读 `_pending.md`；
   - 兜底路径：watermark 对账——读 `_compaction/` 压实日志中上次水位，
     扫描 `docs/implementations/` 中此后 gate 已关闭的 slug，与
     `_pending` 比对；漏登 slug 从其 `spec.md` Backfill Candidates /
     `design.md` Stable Doc Backfill Map 补收。
2. **路由**：目的地判定复用 `project-knowledge-manager` 的
   routing-taxonomy，不另造一套。
3. **产出报告** `_compaction/YYYY-MM-DD-report.md`：
   - 按目的地分组的待归并 delta；
   - 冲突点（同一模块被多个 slug 改动）与建议的归并方案；
   - 建议作废的旧结论；
   - 漏登对账结果（登记率）；
   - 建议的常青文档 diff（提案形式，不执行）；
   - **全量模块体检**：每个模块 spec 的行数与 Pending 行堆积数，超过
     README 阈值（如 400 行）时给出「升级子目录 / 合并模块」建议。
     单文件过大的守护靠这一项，不靠纪律。

### apply 模式（人工审完报告后触发）

1. 按报告执行合入：更新 module-spec / PRD / ARD 等目标文档；
2. 清空对应 Pending deltas 行与 `_pending.md` 条目；
3. 推进压实日志 watermark；
4. 报告归档。

### 触发

- 主：定时 routine（首版每周一次，report 模式，跑在项目 repo）；
- 辅：gate 关闭时若某目的地 pending ≥ 3 条，提示可顺手压实；
- 人工随时可跑。

## 机制自优化闭环

每轮报告中的漏登率、冲突类型、路由误判是回刷机制自身的质量信号。用
`/improve-skill` 对回刷 skill 做定期优化，报告即 rubric 证据来源。

## 机制编码落点（防失传）

| 规则 | 落点 |
| --- | --- |
| 捕获步 + 跳过阈值 | dev-with-track `assets/templates/gate.md` |
| 三层定位、清单准入、Pending 约定、回刷说明 | 项目 `module-specs/README.md` |
| func-design → module-spec 定义改写 | `project-knowledge-manager` routing-taxonomy |
| 回刷流程本身 | 新 skill `backfill-stable-docs`（workbench） |

## 存量迁移策略

- 建模块骨架后，83 个旧 func-design 整体移入 `_archive/`；
- 模块 spec 用「碰到才刷」填充：下次动到某模块时把相关旧设计 + 新变更
  一起蒸馏进去；
- 空模块放 stub + 「尚未回填」标记；
- `docs/impl-plans/` 存量按同策略归档（后续任务归 dev-with-track 任务包）。

## 推进顺序

| Phase | 内容 | 产出地 |
| --- | --- | --- |
| 1 | prj-supplyer-webapp 内一个 dev-with-track 任务包：抽模块清单（定 owner、粒度、目标区间）→ 建 `module-specs/` 骨架 + README → 存量归档 | webapp repo |
| 2 | gate.md 模板捕获步升级；project-knowledge-manager routing-taxonomy 改写 | workbench + 全局 skill |
| 3 | 回刷 skill + 定时 report routine；跑一次首压实（report → 人工审 → apply）当试金石 | workbench + webapp repo |

## 风险与守护

| 风险 | 守护 |
| --- | --- |
| 压实掉链子 → spec 陈旧失信 | 定时 report + gate 阈值提示双触发；Pending deltas 真相指针保证陈旧期不误导 |
| 捕获漏登 | watermark 对账兜底，事实源在 slug 目录，索引丢条目不丢事实 |
| 粒度失控 | 封闭模块清单 + 准入规则 + 目标区间；单文件过大由报告体检项发现并建议拆分 |
| 自动合入污染常青文档 | report/apply 分离，合入必经人工审 |
| 机制本身退化 | improve-skill 闭环，报告即证据 |

## 开放问题

- 模块清单目标区间的具体数字（首版按 10~25，Phase 1 抽清单时定）。
- 定时频率（首版每周；跑两轮后按报告体量调整）。
- 报告与已 apply 报告的保留策略（建议保留全部，`_compaction/` 本身就是
  压实历史）。
