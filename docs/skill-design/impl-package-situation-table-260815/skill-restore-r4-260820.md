# SKILL 降载减法审计（r4）

本记录按文件完成顺序追加。删除台账只登记从 `4e53faa^` 来源底稿中不再出现在入口正文的内容；压缩不登记。承接者必须是宿主无关的入口、references 或 runtime/CLI 机制，不使用 DSH、evals 或 tests 夹具。

## execution-boundaries

来源：`execution-preflight/SKILL.md`、`standing-bookkeeper/SKILL.md`、`verification-before-completion/SKILL.md`。

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| `execution-preflight` 的独立 frontmatter/name 与 `# Execution Preflight` 入口载体 | `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:1-10,53`（三边界合并后的统一路由） |
| `standing-bookkeeper` 的独立 frontmatter/name 与独立入口载体 | `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:2-3,55-68`；详细角色继续由 `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/references/role.md:1-16,38-54` 承接 |
| `verification-before-completion` 的独立 frontmatter/name 与独立入口载体 | `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:2-3,93-105`（统一 completion-claim evidence gate） |
| Standing Bookkeeper「返回短回执」的四字段示例与 `bookkeeper-receipts.jsonl` 的完整 JSON 行格式 | `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/references/role.md:17-36`（专项 slow-path 回执 checklist） |

### 行数

- 降载前：197 行（60 + 59 + 78）
- 降载后：34 行
- 本次结果：122 行

## impl-package

来源：`impl-package/SKILL.md`、`grilling/SKILL.md`、`create-task-dag/SKILL.md`。

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| 原路由表中把执行前、standing bookkeeper、completion verification 分别作为 `/impl-package:execution-preflight`、`/impl-package:standing-bookkeeper`、`/impl-package:verification-before-completion` 的三条独立入口 | `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md:28,38`；统一由 `/impl-package:execution-boundaries` 承接 |
| `grilling` 的独立 frontmatter/name 与 standalone 入口载体 | `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md:60-79`；实际 ledger 生命周期另由 `plugin-marketplace/plugins/impl-package/skills/grill-me-smartly/SKILL.md:7-18,20-43` 承接 |
| `create-task-dag` 的独立 frontmatter/name 与 standalone 入口载体 | `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md:81-88`（旧 Task/DAG 只读章节与 references 指针） |
| 原路由表中将 `grilling`、`create-task-dag` 暴露为可独立调用的 route | `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md:38,60-88`（内嵌方法/legacy 章节；不重新创建已撤销 SKILL） |

### 行数

- 降载前：145 行（68 + 58 + 19）
- 降载后：32 行
- 本次结果：88 行

## backfill-stable-docs

来源：`backfill-stable-docs/SKILL.md`。

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| 无。降载前配置、工作区基准、Audit、Gate/gap-catching、item ID、Apply、Verify、Retirement 与阶段收口语义均在本次结果中保留或压缩。 | — |

### 行数

- 降载前：42 行
- 降载后：16 行
- 本次结果：40 行

## grill-me-smartly

来源：`grill-me-smartly/SKILL.md`。

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| 无。降载前的 ledger source-of-truth、Review/Apply 门槛、角色边界、临时路径、命令、Questioner loop、frontier 完整性、stop proof、中文摘要、问题质量和常见错误均在本次结果中保留或压缩。 | — |

### 行数

- 降载前：216 行
- 降载后：43 行
- 本次结果：89 行
