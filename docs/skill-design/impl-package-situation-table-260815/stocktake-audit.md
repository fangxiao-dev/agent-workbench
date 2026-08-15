# 260815 处境表改动只读盘点

## 审计口径与结论摘要

- 审计日期：2026-08-15；范围：仓库工作区、Git 状态、处境表设计目录、impl-package skill/plugin 目录、相关 tests 与忽略目录。
- “今天”按文件 `LastWriteTime`、`git status` 和最近提交时间交叉判断；当前目录快照为 2026-08-15 16:49:42 之后，`tests/fixtures/situations/` 在连续快照 `219,219,219,219` 后稳定。
- 被审计的本轮产出：**248 个文件**；其中 3 个是已跟踪但未提交的今日修改，14 个是今日核心未跟踪文件，219 个是测试 fixture（含目录 README），1 个是未跟踪测试消费者，9 个是 `.test-tmp` 忽略文件，2 个是忽略的 Python 字节码缓存。
- 本报告是用户指定的唯一新增审计文件，**另计 1 个**，不计入上面的 248 个被审计产出。
- 当前新件接入运行时：**否**。证据链见第 2 节：正式 YAML 只有 `situation.py` 读取；没有 skill 或测试调用该脚本；脚本只是未注册的只读 CLI。
- 文档不一致：**9 条**。候选退休项：**9 条**。这些数字均为本报告第 3、4 节的编号数，不代表已执行任何退休或修复。

## 1. 本轮产出清单

### 1.1 总量与 Git 交叉核对

| 类别 | 文件数 | Git 状态 | 当前判断 |
| --- | ---: | --- | --- |
| 今日已跟踪修改：standing bookkeeper 设计与现役文件 | 3 | `M` | 今日工作区修改，未提交 |
| 今日未跟踪：处境表设计目录 | 12 | `??` | 新增设计/回放文件 |
| 今日未跟踪：正式 YAML 与推导器 | 2 | `??` | 新增核心文件；尚未接入运行时 |
| 今日未跟踪：`tests/fixtures/situations/` | 219 | `??` | 50 个场景目录及目录 README；测试消费者另列 |
| 今日未跟踪：`tests/test_situation_render.py` | 1 | `??` | 直接调用新 CLI 的参数化测试，未纳入 tracked tests |
| 今日忽略：`.test-tmp/replay-timelines/` | 9 | `!! .test-tmp/` | 抽取中间产物，不在普通 `git status` 中 |
| 今日忽略：Python 字节码 | 2 | `!!` | `situation.py` 与测试缓存，残留 |
| **合计（不含本报告）** | **248** |  |  |

`git diff --stat` 只统计已跟踪文件，结果为 10 个文件、175 insertions、72 deletions；未跟踪的 YAML、脚本、12 个设计文档、219 个 fixture 和测试消费者不会出现在该统计中。按日期拆分：今日 3 个已跟踪文件为 126 insertions、0 deletions；此前历史工作区改动的 7 个文件为 49 insertions、72 deletions。最近提交是 `5f299f3`（2026-08-14），没有发现 2026-08-15 已提交的本轮文件。

### 1.2 今日已跟踪修改（3 个）

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `docs/skill-design/impl-package-standing-bookkeeper-skill-design-260814.md` | standing bookkeeper 的试运行说明、§19 bounded write unit 与 receipt 修订设计 | 草稿（§19 明确未实施） | 20,407 B / 350 L |
| `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/SKILL.md` | 现役 standing-bookkeeper skill 的角色与写入边界 | 已定稿（现役；仍是 §19 之前形态） | 3,479 B / 46 L |
| `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/references/role.md` | 现役角色提示、四行回执和越界边界 | 已定稿（现役；receipt 仍为 `done|blocked`） | 4,041 B / 59 L |

依据：三文件 `LastWriteTime` 均为 2026-08-15；`git status --short` 均为 `M`；三文件的 `git diff --stat` 合计 `126 insertions(+), 0 deletions(-)`。

### 1.3 处境表设计目录下的全部 12 个文件

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `docs/skill-design/impl-package-situation-table-260815/README.md` | 处境表、basis、轨迹和落地形式的总设计说明 | 草稿（不授权实施） | 22,633 B / 346 L |
| `docs/skill-design/impl-package-situation-table-260815/situation-table-dev-with-track.md` | 55 行的人读枚举、分组统计和讨论记录 | 草稿（文件第 1、3 行自声明） | 16,727 B / 229 L |
| `docs/skill-design/impl-package-situation-table-260815/trail-schema.md` | `execution/<attempt>/trail.jsonl` 字段与写入分工草案 | 草稿（文件第 1 行自声明） | 5,248 B / 99 L |
| `docs/skill-design/impl-package-situation-table-260815/trial-readout.md` | standing bookkeeper 试运行指标与读数说明 | 中间产物（试运行读数） | 3,518 B / 54 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/case-3.md` | 早期 case 3 的 42 决策点回放 | 残留（合并报告第 5 行明确忽略，后有 `map-case3.md`） | 28,734 B / 216 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/consolidated.md` | 六份 replay 的合并、去重和修表提案 | 中间产物（提案阶段声明未 apply） | 42,567 B / 357 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case1.md` | case 1 时间线到处境的映射 | 中间产物（回放证据） | 20,811 B / 143 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case2a.md` | case 2 分片 a 映射 | 中间产物（回放证据） | 26,264 B / 185 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case2b.md` | case 2 分片 b 映射 | 中间产物（回放证据） | 22,673 B / 179 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case2c.md` | case 2 分片 c 映射 | 中间产物（回放证据） | 28,575 B / 205 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case2d.md` | case 2 分片 d 映射 | 中间产物（回放证据） | 39,260 B / 262 L |
| `docs/skill-design/impl-package-situation-table-260815/replay/map-case3.md` | case 3 完整时间线的新映射 | 中间产物（较新的回放映射） | 26,809 B / 176 L |

### 1.4 正式 YAML 与推导器（2 个）

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml` | `dev-with-track` 的正式机读处境表；55 个 `slug`，6 个优先级组 | 已定稿（机读源，未提交） | 32,407 B / 896 L |
| `plugin-marketplace/plugins/impl-package/scripts/situation.py` | 只读加载 YAML、读取 package facts、执行 `render`/`print-table`/`check` | 草稿（CLI 原型，未接入 skill runtime） | 110,615 B / 2,607 L |

可复核输出：`python -B plugin-marketplace/plugins/impl-package/scripts/situation.py check` 返回：

```text
check: PASS
- stage: dev-with-track
- situations: 55
- implemented when keys: 64
- priority groups: 6
```

这只能证明正式 YAML 通过脚本的静态检查，不能证明脚本已被运行时调用。

### 1.5 `.test-tmp/replay-timelines/` 下的全部 9 个忽略文件

`.gitignore:32` 为 `.test-tmp/`；因此普通 `git status` 不列出它们，`git status --short --ignored` 只显示 `!! .test-tmp/`。

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `.test-tmp/replay-timelines/extract_rollout.py` | 从真实 rollout 抽取时间线的脚本 | 中间产物（忽略） | 29,789 B / 754 L |
| `.test-tmp/replay-timelines/timeline-case1.jsonl` | case 1 原始时间线 | 中间产物（忽略） | 369,264 B / 1,217 L |
| `.test-tmp/replay-timelines/timeline-case2-part1.jsonl` | case 2 分片 1 时间线 | 中间产物（忽略） | 620,291 B / 1,891 L |
| `.test-tmp/replay-timelines/timeline-case2-part2.jsonl` | case 2 分片 2 时间线 | 中间产物（忽略） | 620,604 B / 2,183 L |
| `.test-tmp/replay-timelines/timeline-case2-part3.jsonl` | case 2 分片 3 时间线 | 中间产物（忽略） | 620,704 B / 2,117 L |
| `.test-tmp/replay-timelines/timeline-case2-part4.jsonl` | case 2 分片 4 时间线 | 中间产物（忽略） | 619,913 B / 2,054 L |
| `.test-tmp/replay-timelines/timeline-case2.jsonl` | case 2 合并时间线 | 中间产物（忽略） | 2,473,267 B / 8,245 L |
| `.test-tmp/replay-timelines/timeline-case3.jsonl` | case 3 时间线 | 中间产物（忽略） | 649,744 B / 1,991 L |
| `.test-tmp/replay-timelines/timeline-summary.md` | 时间线抽取摘要 | 中间产物（忽略） | 26,659 B / 141 L |

### 1.6 今日生成的忽略字节码（2 个）

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `plugin-marketplace/plugins/impl-package/scripts/__pycache__/situation.cpython-310.pyc` | Python import/执行缓存；不是源文件或 runtime 注册物 | 残留 | 93,422 B；二进制，不计文本行 |
| `tests/__pycache__/test_situation_render.cpython-310-pytest-9.0.2.pyc` | `test_situation_render.py` 的 pytest 字节码缓存 | 残留 | 5,185 B；二进制，不计文本行 |

依据：`git check-ignore -v` 命中 `.gitignore:1:__pycache__/`；两个文件 `LastWriteTime` 均为 2026-08-15。

### 1.7 `tests/fixtures/situations/` 当前全部 219 个文件

下表每个分号项都是一个完整文件路径；场景项的路径前缀统一为 `tests/fixtures/situations/<场景>/`。当前快照为 **50 个场景目录、219 个文件**。这些文件均为 `??`，状态统一记为“中间产物（快照）”：包含 `.impl-package/state.json`、trail/findings、Ticket、gate 和 `expected.json` 等输入/期望数据。当前 tracked tests 没有消费者；但新增的未跟踪 `tests/test_situation_render.py:12-13,27-31` 直接调用脚本并读取这些目录。目录生成在审计期间变化过，以下是稳定快照，不把它们误称为已定稿测试合同。

| 场景目录 | 文件（大小） |
| --- | --- |
| `tests/fixtures/situations/README.md`（根目录文件） | fixture 来源、50 个场景覆盖与字段还原说明；20,962 B/102 L |
| `p0-anchor-mismatch`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (76 B/2 L); `expected.json` (553 B/14 L); `gate.md` (26 B/2 L) |
| `p0-checkpoint-missing`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (83 B/2 L); `expected.json` (571 B/14 L); `gate.md` (26 B/2 L) |
| `p0-checkpoint-refresh`（4） | `.impl-package/state.json` (330 B/20 L); `execution/fixture-attempt/trail.jsonl` (86 B/2 L); `expected.json` (524 B/14 L); `gate.md` (26 B/2 L) |
| `p0-evidence-unfiled`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (174 B/1 L); `expected.json` (491 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p0-handoff-in-flight`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (78 B/2 L); `expected.json` (530 B/14 L); `gate.md` (26 B/2 L) |
| `p0-handoff-recovery-needed`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (84 B/2 L); `expected.json` (529 B/14 L); `gate.md` (26 B/2 L) |
| `p0-handoff-target-corrected`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (85 B/2 L); `expected.json` (521 B/14 L); `gate.md` (26 B/2 L) |
| `p0-judgment-unfiled`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (102 B/1 L); `expected.json` (504 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p0-projection-drift`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (88 B/2 L); `expected.json` (562 B/14 L); `gate.md` (26 B/2 L) |
| `p0-session-resumed`（4） | `.impl-package/state.json` (335 B/20 L); `execution/fixture-attempt/trail.jsonl` (91 B/2 L); `expected.json` (522 B/14 L); `gate.md` (26 B/2 L) |
| `p0-state-missing`（2） | `expected.json` (522 B/13 L); `gate.md` (26 B/2 L) |
| `p0-terminal-frozen`（4） | `.impl-package/state.json` (378 B/20 L); `expected.json` (474 B/12 L); `gate.md` (86 B/4 L); `tickets/01.md` (132 B/8 L) |
| `p1-all-edges-held`（5） | `.impl-package/state.json` (330 B/20 L); `expected.json` (550 B/14 L); `gate.md` (26 B/2 L); `tickets/tkt-base.md` (136 B/8 L); `tickets/tkt-child.md` (191 B/11 L) |
| `p1-blocker-maybe-resolved`（5） | `.impl-package/state.json` (277 B/17 L); `execution/fixture-attempt/trail.jsonl` (90 B/2 L); `expected.json` (538 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (132 B/8 L) |
| `p1-integration-carrier-unavailable`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (93 B/2 L); `expected.json` (574 B/14 L); `gate.md` (26 B/2 L) |
| `p1-multiple-ready`（6） | `.impl-package/state.json` (290 B/19 L); `execution/fixture-attempt/trail.jsonl` (153 B/3 L); `expected.json` (534 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (132 B/8 L); `tickets/02.md` (132 B/8 L) |
| `p1-worker-still-running`（4） | `.impl-package/state.json` (192 B/12 L); `execution/fixture-attempt/trail.jsonl` (91 B/2 L); `expected.json` (520 B/14 L); `gate.md` (26 B/2 L) |
| `p2-awaiting-reviewer`（5） | `.impl-package/state.json` (537 B/28 L); `execution/fixture-attempt/trail.jsonl` (93 B/1 L); `expected.json` (559 B/16 L); `gate.md` (26 B/2 L); `tickets/01.md` (149 B/9 L) |
| `p2-closure-awaiting`（4） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (118 B/7 L); `expected.json` (575 B/16 L); `gate.md` (26 B/2 L) |
| `p2-envelope-invalid`（5） | `.impl-package/state.json` (192 B/12 L); `execution-findings.md` (89 B/7 L); `execution/fixture-attempt/trail.jsonl` (89 B/2 L); `expected.json` (584 B/15 L); `gate.md` (26 B/2 L) |
| `p2-incomplete-first`（5） | `.impl-package/state.json` (242 B/16 L); `execution/fixture-attempt/trail.jsonl` (170 B/3 L); `expected.json` (543 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (132 B/8 L) |
| `p2-incomplete-second`（5） | `.impl-package/state.json` (242 B/16 L); `execution/fixture-attempt/trail.jsonl` (263 B/4 L); `expected.json` (542 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (132 B/8 L) |
| `p2-investigate-evidence-gap`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (119 B/1 L); `expected.json` (529 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p2-investigate-no-carrier`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (103 B/1 L); `expected.json` (533 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p2-main-session-finding`（5） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (92 B/6 L); `execution/fixture-attempt/trail.jsonl` (139 B/1 L); `expected.json` (642 B/16 L); `gate.md` (26 B/2 L) |
| `p2-review-required-trigger`（4） | `.impl-package/state.json` (241 B/15 L); `expected.json` (508 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (160 B/9 L) |
| `p2-reviewer-returned`（5） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (88 B/6 L); `execution/fixture-attempt/trail.jsonl` (138 B/1 L); `expected.json` (602 B/16 L); `gate.md` (26 B/2 L) |
| `p2-reviewer-unavailable`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (113 B/1 L); `expected.json` (501 B/13 L); `gate.md` (26 B/2 L) |
| `p2-source-recheck`（4） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (144 B/8 L); `expected.json` (581 B/16 L); `gate.md` (26 B/2 L) |
| `p2-worker-blocked`（5） | `.impl-package/state.json` (289 B/16 L); `execution/fixture-attempt/trail.jsonl` (156 B/1 L); `expected.json` (633 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (132 B/8 L) |
| `p3-comparison-head-unfixed`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (86 B/1 L); `expected.json` (515 B/13 L); `gate.md` (26 B/2 L) |
| `p3-contradictory`（4） | `.impl-package/state.json` (862 B/38 L); `expected.json` (684 B/18 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p3-integration-evidence-unavailable`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (99 B/1 L); `expected.json` (554 B/13 L); `gate.md` (26 B/2 L) |
| `p3-retire-undecided`（4） | `.impl-package/state.json` (241 B/15 L); `expected.json` (503 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (157 B/9 L) |
| `p3-revalidation-pending`（4） | `.impl-package/state.json` (309 B/16 L); `expected.json` (490 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p3-revision-diverged`（5） | `.impl-package/state.json` (344 B/19 L); `execution/fixture-attempt/trail.jsonl` (78 B/1 L); `expected.json` (660 B/16 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p3-safety-invariant`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (121 B/1 L); `expected.json` (560 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (183 B/10 L) |
| `p3-sources-unique`（5） | `.impl-package/state.json` (241 B/15 L); `execution/fixture-attempt/trail.jsonl` (126 B/1 L); `expected.json` (556 B/13 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p4-acceptance-edge-held`（6） | `.impl-package/state.json` (676 B/32 L); `execution/fixture-attempt/trail.jsonl` (61 B/1 L); `expected.json` (560 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (180 B/10 L); `tickets/base.md` (140 B/7 L) |
| `p4-all-terminal-durable-missing`（4） | `.impl-package/state.json` (344 B/19 L); `expected.json` (571 B/14 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p4-comparison-mismatch`（4） | `.impl-package/state.json` (344 B/19 L); `expected.json` (577 B/15 L); `gate.md` (52 B/3 L); `tickets/01.md` (131 B/7 L) |
| `p4-completion-claim-unaudited`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (92 B/1 L); `expected.json` (544 B/13 L); `gate.md` (26 B/2 L) |
| `p4-findings-triage-pending`（4） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (100 B/7 L); `expected.json` (586 B/14 L); `gate.md` (26 B/2 L) |
| `p4-gate-verdict-undecided`（2） | `.impl-package/state.json` (191 B/11 L); `expected.json` (562 B/13 L) |
| `p4-grading-undecided`（4） | `.impl-package/state.json` (191 B/11 L); `execution-findings.md` (105 B/7 L); `expected.json` (555 B/14 L); `gate.md` (26 B/2 L) |
| `p4-manual-result-missing`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (144 B/1 L); `expected.json` (546 B/13 L); `gate.md` (26 B/2 L) |
| `p4-release-edge-unchecked`（5） | `.impl-package/state.json` (521 B/27 L); `execution/fixture-attempt/trail.jsonl` (109 B/1 L); `expected.json` (614 B/15 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p4-satisfiable`（5） | `.impl-package/state.json` (521 B/27 L); `execution/fixture-attempt/trail.jsonl` (108 B/1 L); `expected.json` (600 B/15 L); `gate.md` (26 B/2 L); `tickets/01.md` (131 B/7 L) |
| `p4-terminal-coverage-incomplete`（4） | `.impl-package/state.json` (191 B/11 L); `execution/fixture-attempt/trail.jsonl` (95 B/1 L); `expected.json` (545 B/13 L); `gate.md` (26 B/2 L) |
| `p5-intake-backlog`（4） | `.impl-package/intake.jsonl` (55 B/1 L); `.impl-package/state.json` (191 B/11 L); `expected.json` (479 B/13 L); `gate.md` (26 B/2 L) |

### 1.8 今日未跟踪测试消费者（1 个）

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `tests/test_situation_render.py` | 对 50 个 fixture 目录参数化执行 `situation.py render --json`，校验 primary/secondary、layer 与 forbidden hit | 中间产物（未跟踪测试） | 2,692 B / 71 L |

依据：文件第 12 行指向 `plugin-marketplace/plugins/impl-package/scripts/situation.py`，第 13、17、27 行读取 fixture 目录，第 30-31 行通过 subprocess 调用 `render`。

### 1.9 本轮之前已存在的未提交修改（7 个）

这些文件出现在 `git status` 和 `git diff --stat`，但文件时间为 2026-08-14，不能归入今天的产出。

| 路径 | 作用 | 状态 | 大小 |
| --- | --- | --- | ---: |
| `skills/architecture-review/SKILL.md` | 通用 architecture-review skill | 历史遗留未提交 | 8,394 B / 107 L |
| `skills/thread-harness/SKILL.md` | 通用 thread-harness skill | 历史遗留未提交 | 3,976 B / 47 L |
| `skills/thread-harness/goal-prompt.md` | thread-harness 目标提示 | 历史遗留未提交 | 8,076 B / 148 L |
| `skills/thread-harness/references/run-procedure.md` | thread-harness 执行流程 | 历史遗留未提交 | 4,640 B / 60 L |
| `skills/thread-harness/references/session-dispatch.md` | thread-harness session 派发规则 | 历史遗留未提交 | 12,461 B / 172 L |
| `tests/test_handoff_to_new_session_contract.py` | handoff contract 测试 | 历史遗留未提交 | 4,304 B / 88 L |
| `tests/test_thread_harness_contract.py` | thread-harness contract 测试 | 历史遗留未提交 | 17,824 B / 378 L |

## 2. 引用关系与运行时接入证据

### 2.1 正式 YAML、推导器和 skill 的引用树

```text
plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml
└── plugin-marketplace/plugins/impl-package/scripts/situation.py
    ├── TABLE_PATH = PLUGIN_ROOT / "skills" / "dev-with-track" / "situations.yaml"  (situation.py:28-30)
    ├── _yaml_text() 读取 TABLE_PATH.read_text(...)                         (situation.py:1971-1977)
    ├── check：校验正式表并打印 55/64/6                                 (situation.py:2524-2545)
    ├── print-table：打印正式表                                     (situation.py:2562-2564, 2586-2589)
    └── render：由显式 CLI 参数读取 package facts 并渲染 projection       (situation.py:2557-2577)
        └── 若 package 有 situations.yaml，仍由同一脚本 PackageReader.read() 合并 (situation.py:2129-2170)

plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md
└── 未发现 situation.py / situations.yaml 的引用或调用

其他 impl-package skill / plugin manifest / tracked tests
└── 未发现 situation.py / situations.yaml 的调用注册

tests/test_situation_render.py（未跟踪）
├── 读取 tests/fixtures/situations/ 下的 fixture 目录（第 13、17、27-29 行）
└── subprocess 调用 situation.py render --json（第 12、30-31 行）
```

可核对的搜索结果：

```text
Get-ChildItem plugin-marketplace/plugins/impl-package/skills -Recurse -File |
  Select-String -SimpleMatch -Pattern 'situation.py','situations.yaml'
# 无输出

git grep -n -F -e 'situation.py' -e 'situations.yaml' --
  plugin-marketplace/plugins/impl-package/skills tests
# 无输出（tracked 范围）

Get-Content tests/test_situation_render.py |
  Select-String -SimpleMatch -Pattern 'situation.py','fixtures/situations','subprocess.run'
# 命中未跟踪测试第 12、13、30-31 行；这是 CLI 测试消费者，不是 skill/runtime caller

Get-ChildItem plugin-marketplace/plugins/impl-package/scripts -Recurse -File |
  Select-String -SimpleMatch -Pattern 'situation.py'
# 只命中 situation.py 自身/其缓存，不命中其它调用者
```

`situation.py` 的 docstring（第 1–6 行）明确写着只读、从表读取、从不写 package 或 working tree；parser（第 2548–2565 行）只注册 `render`、`print-table`、`check` 三个命令。当前没有 host link、skill body、runtime engine 或 plugin manifest 对它做 dispatch；有一个新出现但仍未跟踪的测试文件直接调用 CLI，这不等于运行时接入。`.codex-plugin/plugin.json` 与 `.claude-plugin/plugin.json` 只写 `"skills": "./skills/"`，没有脚本入口。

结论：**新件目前没有接入运行时，答案为“否”。** `check: PASS` 只说明脚本可以独立读取并校验 55 行 YAML；未跟踪的 `tests/test_situation_render.py` 证明 CLI 有测试消费者，但不是被 `dev-with-track` 或其它 skill 调用的证据。

### 2.2 设计文档之间的链接

| 来源 | 指向 | 证据与状态 |
| --- | --- | --- |
| `README.md:95` | `situation-table-dev-with-track.md` | 文件存在；同时 `README.md:269` 将其降级为设计草稿 |
| `README.md:123` | `trail-schema.md` | 文件存在；轨迹字段草案通过相对链接引用 |
| `README.md:339` | `../impl-package-standing-bookkeeper-skill-design-260814.md` | 文件存在；说明第一轮试运行关系 |
| `situation-table-dev-with-track.md:5` | `README.md#9-命名空间` | 文件存在，锚点文本可由标题推得；未执行渲染器级 anchor 验证 |
| `trail-schema.md:98` | `README.md#102-首版不改动-impl_package_statepy` | 文件存在，锚点文本可由标题推得 |
| `trial-readout.md:17,45,48` | `README.md` 相关章节 | 文件存在；主要为回指说明 |
| `replay/consolidated.md:4` | `map-case1.md`、`map-case2a.md`、`map-case2b.md`、`map-case2c.md`、`map-case2d.md`、`map-case3.md` | 6 个文件都存在；第 5 行明确忽略同目录较早的 `case-3.md` |

路径链接检查未发现不存在的文件路径；不能仅凭文本检查确认所有 Markdown anchor 在渲染器中可点击。

### 2.3 “现役 12 个 skill”的核对结果

仓库当前 `plugin-marketplace/plugins/impl-package/skills/` 实际有 **19 个目录**：

```text
backfill-stable-docs, create-task-dag, dev-with-track, do-review,
execution-preflight, grill-me-smartly, grilling, impl-package,
impl-planning, plan-review, req-align, review-code,
review-code-by-spec, review-code-by-standards, safety-review,
standing-bookkeeper, subagent-driven-development, to-tickets,
verification-before-completion
```

两个 plugin manifest 都只声明 `skills: ./skills/`，没有找到规范性“现役 12 个”清单。因此下面的 12 个是本审计为回答问题采用的主流程分组：去掉入口 router、3.4 legacy `create-task-dag`、grilling 辅助对和三个 reviewer leaf；这不是仓库声明的权威名单。若 Owner 所说的 12 个是另一组，当前材料未能确认其定义。

| 本审计采用的 12 个 | 55 行中的覆盖情况 | YAML/文档证据 |
| --- | --- | --- |
| `dev-with-track` | 直接覆盖；整张 55 行表属于该 stage | YAML `stage: dev-with-track`；README:7-8 |
| `subagent-driven-development` | 直接覆盖 investigate/implement/fix/review/verify worker 路由及 worker mode 条件 | YAML 的 C1/C10-C12/E1/E3/N15/N21 action 与 `trail.last_worker_mode` |
| `do-review` | 直接覆盖 closure、review required、source recheck、fresh review、immutable head | YAML 的 C6/C7/E2/F3/N13/N18/N21 action |
| `req-align` | 直接覆盖多个业务结果、来源冲突、durable delta 的决策路径 | YAML 的 C3/C5/E5 action |
| `impl-planning` | 有局部覆盖：terminal 后 patch、contract-change 相关规划 | YAML A4、D4 action；不是全量 planning 生命周期 |
| `verification-before-completion` | 直接覆盖 terminal/accept/rework 前的验证 | YAML B3/F2/D2/N15 action |
| `standing-bookkeeper` | 覆盖 record/intake backlog 的簿记语义；不等于已实现 §19 bounded receipt | YAML G2、README:337-344 |
| `backfill-stable-docs` | 只覆盖 durable delta 的一条 disposition 路径 | YAML E5 action |
| `execution-preflight` | 仅有 readiness/carrier 语义邻接；未出现直接 action 或 skill 调用 | `situations.yaml` 中无 `execution-preflight` 字符串 |
| `safety-review` | 仅以安全/数据/并发触发条件间接出现；未出现直接 action | `situations.yaml` 中无 `safety-review` 字符串 |
| `plan-review` | 未覆盖为处境 action | `situations.yaml` 中无 `plan-review` 字符串 |
| `to-tickets` | 未覆盖为处境 action | `situations.yaml` 中无 `to-tickets` 字符串 |

因此“55 行覆盖了现役 12 个 skill”不能作为整体事实使用：其中 8 个有直接或局部动作映射，4 个没有直接调用证据；且 12 的名单本身未在仓库中定稿。

### 2.4 3.4 / DAG / Task 兼容物的现存依赖

当前没有在 `docs/implementations/` 下找到活动的 3.4 package：该目录只有 `retired.json` 和 4 个现行 Decision/Spec 文件；没有 `formatVersion: 3.4`、`dag.md`、`patch-dag` 或 Task Handoff 文件。可核对的 `git grep` 命中却显示兼容链仍被保留：

| 兼容物 | 现存证据 | 结论 |
| --- | --- | --- |
| `create-task-dag` skill | `SKILL.md:8` 明确“新 package 不调用”，只读已有 3.4；`impl-package/SKILL.md:33,66` 仍提供 legacy 路由；`tests/test_impl_package_step8_evals.py:24`、`tests/test_ticket_first_contract.py:416` 仍读取它 | 没有活动新 package 依赖，但测试、旧包恢复/迁移合同仍依赖存在性 |
| Composition Contract 的 `dag=false` | `references/impl-package-composition-contract.md:23,26` 明确是 3.4 state engine 兼容占位；runtime `engine.py:158` 拒绝非 `tickets=true, dag=false` | 新 3.5 package 依赖其 Ticket-only 合同文字/状态形状；不能据“没有 DAG”推出无依赖 |
| `validate_ticket_first_migration.py` | Current State:5 声明一次性显式迁移脚本；`ticket-first-migration-runbook.md:3,12` 调用；`tests/test_impl_package_migration.py:14,164` 导入/运行；plugin test:70,95 断言它位于 scripts 且只由 runbook 使用 | 没有普通 runtime 依赖，但迁移 admission、测试和 runbook 仍依赖 |
| 真实 3.4 package | `docs/implementations` 当前未发现；migration fixture 在 `tests/fixtures/impl-package-ticket-first/migration/`，且 `tests/test_impl_package_migration.py` 会构造 3.4 legacy state | 只确认有迁移测试输入，未确认有待迁移生产 package |

## 3. 文档间不一致（9 条）

每条都给出当前内容与机械核对后的应有口径；没有执行修复。

### 1. `trail-schema.md` 的 42 行统计过时

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `docs/skill-design/impl-package-situation-table-260815/trail-schema.md:76,98` |
| 当前内容 | `42 行中约 15 行自动、15 至 20 行显式`；“首版……**42 行**的轨迹全部显式写入”。 |
| 对照证据 | `README.md:97,101-102` 为 55/44/11；人读表:155、173 为 55/11、55/13/42；YAML check 输出 `situations: 55`。 |
| 正确内容应为 | 明确区分：正式处境表 **55 行**，其中 13 条 `cli`、42 条 `prose`；首版若全部显式写，应写“55 行全部显式”，而 15–20 是后续自动化目标，不能写成当前 42 行总数。 |

### 2. 多份 replay 把历史 42 行写成“当前”

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/case-3.md:5,202-208`；`replay/map-case3.md:173-175`；`replay/map-case2a.md:166,173`；`replay/map-case2d.md:248` |
| 当前内容 | 分别写“42 个主控决策点/当前 42-row design”“当前 42 行”“当前 42-row table”。其中 map-case3 自己的统计已是 45 个决策点、38 命中、5 unmatched、2 insufficient（:7-11）。 |
| 正确内容应为 | 若这些文件保留历史回放数字，应统一标为“针对 42 行旧快照的历史 replay”；若描述当前正式表，应改为 55 行，并把 42 解释为旧基线或 prose 子集。 |

### 3. consolidated 的“未修改/未 apply”状态声明已陈旧

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/consolidated.md:9` |
| 当前内容 | “没有修改 `situations.yaml`、README、人读枚举……提案阶段完成不等于修表已 apply”。 |
| 对照证据 | 当前 YAML、README、人读枚举均存在且更新时间晚于 consolidated；当前 YAML 已有 55 行，README 已写 55/42/13，人读表已写正式路径和 55 行。consolidated:306-319 的若干提案已被部分吸收。 |
| 正确内容应为 | 加时间边界：“截至本合并报告生成时尚未 apply；之后发生了部分 apply/重写”；同时保留 proposal 与 current snapshot 的差异表。 |

### 4. 正式 YAML 路径写法不一致

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/consolidated.md:307`；对照 `situation-table-dev-with-track.md:3`、`README.md:263-264` |
| 当前内容 | consolidated 提案仍把头部写法称为 `situations/dev-with-track.yaml`，并建议改为 `skills/dev-with-track/situations.yaml`。 |
| 正确内容应为 | 当前正式相对路径是 `skills/dev-with-track/situations.yaml`，仓库实际路径是 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`；`situations/dev-with-track.yaml` 应标为已废弃提案写法。 |

### 5. consolidated 对 README 状态的判断过时

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/consolidated.md:308`；对照 `README.md:5-6` |
| 当前内容 | 提案说 README §1 仍写“命名空间与落地形式待定”。 |
| 正确内容应为 | README 当前写“方向讨论完成”、命名空间固定、正式机读来源固定；consolidated 该行应标成“已 apply/不再是当前差异”。 |

### 6. consolidated 对 `when` grammar 的判断过时

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/consolidated.md:310`；对照 `README.md:240-249`、`situation.py:2552-2554` |
| 当前内容 | 说 `>1`、`>0` 没有定义，建议补 grammar。 |
| 正确内容应为 | 当前 README 已定义布尔、标量 equality、数值比较、`manual` sentinel 与 `unknown`；脚本 parser epilog 也写出比较规则。该提案应标为已处理，若仍有语义缺口应另列，不应继续描述为“未定义”。 |

### 7. consolidated 的新增行/轨迹字段提案与当前 YAML/轨迹草案未对账

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `replay/consolidated.md:311,313-315`；对照人读表:19-24、YAML 55 个 slug、`trail-schema.md:1-99` |
| 当前内容 | 提案称应增加 N13、N19、N20、N21、N05–N12、N17、worker mode/evidence timing 等。 |
| 对照证据 | 当前表已包含 N05–N10、N13、N15、N18–N21，并已在若干 `when` 使用 `trail.last_worker_mode`；但 N01–N04、N11、N12、N14、N16、N17、N22 未在当前 55 行中发现，trail-schema 也没有完整的 `worker_mode`、`envelope_valid`、`outcome_count` 和 evidence timing 字段契约。 |
| 正确内容应为 | consolidated 必须区分“已吸收”“未吸收”“只改 YAML 尚未改 schema”三种状态；不能继续用一张“待增加”表描述已经部分落地的提案。 |

### 8. standing bookkeeper 设计文档把 proposed receipt 当成现行 receipt

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `docs/skill-design/impl-package-standing-bookkeeper-skill-design-260814.md:208-211`；对照 `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/references/role.md:33-41` |
| 当前内容 | 设计文档称现有 §19.5 回执状态已区分 `DONE / BLOCKED / NEEDS_SPLIT`；现役 role.md 实际 JSON 是 `status:"done|blocked"`，现役 SKILL.md 没有 §19.5 的 bounded receipt 字段。 |
| 正确内容应为 | §15.1 写当前试运行 receipt 只有 `done|blocked`；把 `NEEDS_SPLIT`、`VALIDATION_FAILED`、`artifact/section/operation` 和 `unexpected paths` 明确标为 §19 proposed contract，直至现役文件改变。 |

### 9. README 对人读表的“完整枚举”与“降级草稿”定位不够一致

| 项目 | 内容 |
| --- | --- |
| 文件/行号 | `README.md:95`、`README.md:269`；对照 `situation-table-dev-with-track.md:1,3` |
| 当前内容 | README §6 说“完整枚举见”人读表；§10.1 又说该文件在 YAML 落地后“降级为设计草稿、不是事实源”。 |
| 正确内容应为 | 链接可以保留，但第 95 行应明确“完整的历史/设计期人读枚举见……；事实源见 YAML”，以免“完整枚举”被理解为当前 source of truth。 |

补充：文件路径级交叉链接未发现断链；上述第 9 条是状态/权威性口径不清，不是文件不存在。

## 4. 候选退休项（只列，不执行）

以下 9 项是可能已经没有持续价值的对象或文档片段；每项同时列出保留它的风险。这里的“候选”不等于批准退休。

| # | 候选 | 可能没有价值的理由 | 退休/保留风险 |
| ---: | --- | --- | --- |
| 1 | `docs/skill-design/impl-package-situation-table-260815/replay/case-3.md` | `consolidated.md:5` 明确忽略；`map-case3.md` 是较新的完整 case 3 映射，统计也从 42 个决策点变为 45 个 | 删除会损失早期超时/中断产物、时间线解释和旧版表的 provenance；新映射不一定能重现早期结论 |
| 2 | `docs/skill-design/impl-package-situation-table-260815/situation-table-dev-with-track.md` | 文件第 1、3 行自称设计草稿；README:269 已把 YAML 定为正式机读来源 | 删除会损失人读 55 行的枚举过程、分组统计、basis 解释和与回放的阅读索引；YAML 本身不替代这些历史说明 |
| 3 | `docs/skill-design/impl-package-standing-bookkeeper-skill-design-260814.md` 第 19 节 | §19 是 2026-08-15 修订设计；第 348 行明确说未视为 SKILL.md、缓存或 runtime CLI 的完成实现，现役 role 仍是 §19 之前的 receipt | 删除会损失 bounded write unit、receipt contract、eval 修订依据；保留它又会继续被误读为现役行为 |
| 4 | `.test-tmp/replay-timelines/` 整个目录 | `.gitignore:32` 忽略；包含抽取脚本、原始 JSONL 和摘要，属于回放中间物 | 删除会损失从真实 rollout 重建 replay 的可复核输入；保留会让工作区看起来像有一套未登记的第二事实源 |
| 5 | `docs/skill-design/impl-package-situation-table-260815/replay/consolidated.md` | 文件第 9 行声明只是提案且未 apply；第 302–319 行有多处已被当前 YAML/README 部分吸收的旧建议 | 删除会损失六份映射的合并、去重、候选行和决策 provenance；保留会放大“当前仍未 apply”的陈旧状态 |
| 6 | `plugin-marketplace/plugins/impl-package/skills/create-task-dag/` | 新 package 明确不调用；`docs/implementations` 未发现活动 3.4 package，故新流程没有运行时收益 | 删除可能破坏 legacy 3.4 审计/迁移路由、plugin contract 测试及旧 package 恢复说明 |
| 7 | `plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md` 中 `dag=false` 的 3.4 兼容占位 | 现行 3.5 语义是 Ticket-only，`dag=false` 不再表示创建 DAG | 删除/退休可能破坏 runtime 的 composition 校验、plan 模板、migration validator 和“旧 3.4 只读”的边界说明 |
| 8 | `plugin-marketplace/plugins/impl-package/scripts/validate_ticket_first_migration.py` | Current State 明确它是一次性、显式、只读迁移脚本；当前 `docs/implementations` 没有待迁移 package 的证据 | 退休可能破坏 ticket-first migration admission、runbook 以及 `tests/test_impl_package_migration.py` 的导入和 subprocess 断言 |
| 9 | 两个今日 Python 缓存：`plugin-marketplace/plugins/impl-package/scripts/__pycache__/situation.cpython-310.pyc` 与 `tests/__pycache__/test_situation_render.cpython-310-pytest-9.0.2.pyc` | `.gitignore:1` 忽略；只是可重新生成的本地 Python 缓存，没有源代码或合同价值 | 删除只会损失本地缓存，不会损失源文件；但在没有确认生成进程结束前处理它们，可能造成无意义的并发噪声 |

未把 `tests/fixtures/situations/` 计入退休候选：它是新生成的 219 文件快照；tracked tests 尚无消费者，但未跟踪的 `tests/test_situation_render.py` 已直接读取它们。由于测试本身尚未纳入 tracked suite，仍不能把这些输入自动归入正式测试合同，也不能断言无价值。

## 5. 工作区状态完整分类

### 5.1 `git status --short` 的 tracked 与 untracked 分类

| 分类 | 数量 | 路径范围 | 是否属于今天 |
| --- | ---: | --- | --- |
| `M`：今日 standing bookkeeper 变更 | 3 | 第 1.2 节 3 个路径 | 是 |
| `M`：历史未提交变更 | 7 | 第 1.9 节 7 个路径 | 否，文件时间为 2026-08-14 |
| `??`：处境表目录 | 12 | 第 1.3 节全部路径 | 是 |
| `??`：YAML/推导器 | 2 | 第 1.4 节全部路径 | 是 |
| `??`：situations fixture | 219 | 第 1.7 节全部路径 | 是；生成过程曾在审计期间变化 |
| `??`：CLI 测试消费者 | 1 | 第 1.8 节路径 | 是；未跟踪 |
| `!!`：忽略的 timeline | 9 | 第 1.5 节全部路径，顶层显示 `!! .test-tmp/` | 是 |
| `!!`：忽略的 pyc | 2 | 第 1.6 节路径 | 是 |

普通 `git status --short --untracked-files=all` 的核心输出可归纳为：

```text
M  3 个今日 standing bookkeeper 文件
M  7 个 2026-08-14 的历史文件
?? 12 个 situation-table 文档
?? situation.py
?? situations.yaml
?? tests/fixtures/situations/ 下 219 个文件
?? tests/test_situation_render.py
```

忽略输出由以下证据确认：

```text
.gitignore:32:.test-tmp/       .test-tmp/replay-timelines/extract_rollout.py
.gitignore:1:__pycache__/      plugin-marketplace/plugins/impl-package/scripts/__pycache__/situation.cpython-310.pyc
.gitignore:1:__pycache__/      tests/__pycache__/test_situation_render.cpython-310-pytest-9.0.2.pyc
```

### 5.2 提交分批所需的状态事实（仅盘点）

- 今日没有已提交本轮文件：最新提交为 2026-08-14 的 `5f299f3`；今日 3 个 tracked 文件仍为 `M`，其余今日源文件与 fixture 为 `??` 或 `!!`。
- 今日核心变更与历史遗留混在同一工作区：3 个今日 tracked 文件应与 7 个旧的 architecture/thread-harness/test 改动区分；`git diff --stat` 已能按两组分别得到 `126/0` 与 `49/72`。
- `.test-tmp` 与 pyc 不在普通 diff 中；如果只依据 `git diff --stat`，会漏掉本轮回放输入、抽取脚本和本地缓存。
- `tests/fixtures/situations/` 尚没有 tracked 测试消费者证据；未跟踪的 `tests/test_situation_render.py` 已直接调用 CLI 并读取它们。当前 219 个文件只能以未跟踪 fixture 快照报告，不能把它们自动归入正式测试合同。
- `git status` 同时报告 `warning: could not open directory '.pytest_cache/': Permission denied`。该目录内容未能读取，故不对其是否有今日文件作结论。

## 6. 机械审计的最终计数

| 项目 | 结果 |
| --- | ---: |
| 被审计的本轮产出文件数（不含本报告） | **248** |
| 本报告新增文件 | **1**，即本文件 |
| 文档不一致条数 | **9** |
| 候选退休项条数 | **9** |
| 新件是否已接入运行时 | **否** |

运行时“否”的最短证据：`situations.yaml` 的正式读取点只有 `situation.py:28-30,1971-1977,2129-2170`；对 `plugin-marketplace/plugins/impl-package/skills`、tracked `tests` 和脚本目录的调用者搜索没有找到 skill/runtime caller。新出现的 `tests/test_situation_render.py:12,30-31` 只是未跟踪的 CLI 测试消费者；脚本 parser 只提供显式 `check`/`print-table`/`render` CLI。因此当前产物是独立设计源与只读 CLI 原型，不是现役 `dev-with-track` 执行链的一部分。
