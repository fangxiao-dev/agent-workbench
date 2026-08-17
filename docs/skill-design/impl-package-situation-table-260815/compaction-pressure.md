# Compaction pressure handoff checkpoint

## 阶段 1：阈值口径与脚本（已落盘）

本阶段只负责从宿主 rollout 计算压力投影；不写 `trail.jsonl`，不新增 fact key，也不启动常驻进程。

### `high` 判据

对匹配 rollout 的 `compacted` 时间戳计算相邻间隔（分钟）。令第一段间隔为 baseline，令最近三段间隔（不足三段则取已有段）的中位数为 recent median：

- `shrinking = true`：至少有两段间隔，且 recent median 严格小于 baseline。
- `high = true`：至少有三段间隔、baseline 大于 0，且 recent median 不超过 baseline 的 80%（即至少缩短 20%）。
- `high` 不由 compaction 次数单独触发；次数门槛只保证有足够的 cadence 样本。

选择相对第一段的最近中位数，是为了检测持续的工作集增长而不是单个异常短间隔；最近三段也允许最后一次出现轻微反弹。脚本先按 rollout 文件最后写入时间找最新候选，再读取候选的 `session_meta.cwd`，避免每轮渲染打开全部 sessions 文件。

样本表现：

- `56/40/15/12`：recent median=`15`，`15 <= 56*0.8`，所以 `shrinking=true`、`high=true`。
- `50/50/50/50`：recent median=`50`，没有缩短，所以 `shrinking=false`、`high=false`。

找不到 sessions root、找不到 cwd 匹配 rollout、rollout 零次压缩或时间戳无法形成间隔时，脚本返回 `high=false` 和 `explanation`，不抛异常。

### 阶段 1 证据

- `tests/test_compaction_pressure.py`：4 passed。
- `python -m py_compile scripts/rollout_pulse.py scripts/compaction_pressure.py`：通过。
- 真实 `01a00deb` rollout（当前文件已追加到 6 次压缩）实际输出：

  ```json
  {"compactions":6,"last_interval_min":12.55,"shrinking":true,"high":true,"explanation":"recent median interval 12.55 min is at most 80% of the first interval 56.15 min"}
  ```

阶段 1 已完成；阶段 2 尚未开始。现有 fixture 未改动。

## 阶段 2：renderer、when-key 与表行（已落盘）

- `situation.py` 新增可选 `--compaction-pressure JSON_OR_FILE`，接受脚本输出的结构化 object；renderer 不读取宿主 sessions root。
- 新 `attempt.compaction_pressure_high` 只从该参数的 `high` 布尔值推导，不进入 `FACT_KEYS` 或 trail fact 通道。
- 缺少参数返回 U，理由为“缺少结构化 compaction pressure”；非法 JSON/字段形状沿用 validation-result 的硬失败边界。
- 表行 `attempt.record.handoff-due` 放在 P1。P0 仍先处理 state、projection、anchor、checkpoint 等完整性问题；压力提示不阻断当前单元，只要求下一个主控判断的 checkpoint 后交接，因此不应排到 P0，也不需要进入 fact/gate。
- 正式表检查：`57` 行、`67` 个 implemented when key、`6` 个 priority group，`check: PASS`。

### 现有期望的必要变化（先记录，再修改）

新行在缺参时必须是 U，所以所有已有 attempt fixture 的 `undetermined` 观测会多 1 行；这不是改变任何既有 row 的判据语义。当前测试明确暴露了两处依赖总数的期望：

- `tests/fixtures/situations/p4-satisfiable-no-trail/expected.json`：`33 → 34`。
- `tests/test_situation_render.py` 的 human 输出断言：`无法判定 30 行 → 31 行`。

这两处只反映新增 key 的 U 计数；主选、优先层、secondary 和 suppressed 期望均保持不变。阶段 2 将在本段已落盘后更新这两个计数，并增加显式 high/low/missing 参数的 renderer 回归。

### 阶段 2 证据

- `python plugin-marketplace/plugins/impl-package/scripts/situation.py check`：`check: PASS`，57 rows / 67 implemented keys / 6 priority groups。
- `python -m pytest tests/test_situation_render.py -q`：54 passed；仅保留 pytest cache 目录权限 warning。
- 新回归确认：缺参数的 `attempt.compaction_pressure_high` 是 `status=unknown` 并进入 `undetermined`；传 `high=true` 命中 `attempt.record.handoff-due`；传 `high=false` 不命中该行并继续原有 P4 结果。
- 已按本报告前一段记录的必要变化更新一个 fixture JSON 计数和两个 human 计数断言；没有修改其它 fixture 的判据期望或 situations 表其它行。

阶段 2 已完成；阶段 3 尚未开始。

## 阶段 3：SKILL 接线与实测（已落盘）

Restore 现在按 `package validate` → `$compactionPressure = python scripts/compaction_pressure.py` → `--compaction-pressure $compactionPressure` → `situation.py render` 执行；原有 `$previousDigest`、`--since` 和 `--explain-undetermined` 说明保留。`references/situation-inputs.md` 在既有 2.1、9.2 表中补了 CP 输入行、when-key 行和 P1 slug 行，没有另起章节。

最终实测：

- `python plugin-marketplace/plugins/impl-package/scripts/situation.py check`：PASS，57 rows / 67 keys / 6 priority groups。
- `python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py -q`：61 passed；1 个既有 pytest cache 权限 warning，不影响测试结果。
- `python -m pytest tests/test_compaction_pressure.py -q`：4 passed；同一 cache 权限 warning。
- `python scripts/compaction_pressure.py`（仓库根）：`{"compactions":0,"last_interval_min":null,"shrinking":false,"high":false,"explanation":"matched rollout has zero compactions"}`。
- 从 `01a00deb` rollout 所在 worktree 正常 CLI 运行：`{"compactions":6,"last_interval_min":12.55,"shrinking":true,"high":true,"explanation":"recent median interval 12.55 min is at most 80% of the first interval 56.15 min"}`。该文件当前比背景时点多了第 6 次压缩；仍保留原先 56/40/15/12 的恶化结论。

本任务没有 commit；未启动 daemon，没有向 `trail.jsonl` 写入，没有修改 `dispatch_audit.py`、`impl_package_state.py` 或四个 leaf agent。阶段 3 已完成，整个本次改动范围已验证但工作树仍包含 Owner 原有的其它 dirty/untracked 改动，不能把整棵工作树称为 closed。
