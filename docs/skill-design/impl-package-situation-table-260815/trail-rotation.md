# Trail rotation：交接时重新基线化

状态：阶段 1（轮换形态定稿）已落盘；阶段 2、阶段 3 尚未开始。

本次设计只处理 `dev-with-track` 的 attempt trail。目标是让交接后的当前处境不再消费交接前文件里的旧 fact，同时保留旧轨迹供回放和审计；不改变 fact key 集合、state writer、gate 或 leaf agent。

## 阶段 1：形态定稿

### 1. 命名与位置：保留活动名，序号归档

采用第一种形态：

```text
execution/<attempt>/trail.jsonl       # 当前活动轨迹
execution/<attempt>/trail.001.jsonl   # 第一次轮换的旧轨迹
execution/<attempt>/trail.002.jsonl   # 更早的下一次旧轨迹
```

交接轮换时，把现有 `trail.jsonl` 原样移为下一个三位序号的归档文件，再创建新的空 `trail.jsonl`；归档序号取该 attempt 目录中已有 `trail.NNN.jsonl` 的最大值加一。当前活动文件始终使用不带序号的名字。

选择这个形态的理由：

- renderer 现有读取入口是固定的 `execution/<attempt>/trail.jsonl`，活动文件名不变，绝大多数只有一份 trail 的 package 不需要迁移或兼容分支。
- writer 仍然只向活动路径 append；轮换只是文件生命周期操作，不改写任何 JSON 行。把文件移动到归档名不破坏 append-only 的内容语义，旧文件仍可原样回放。
- 序号是可枚举且可排序的 provenance；不会把多个 attempt 混在一起，也不会把任意相似命名文件误当作 trail。

### 2. renderer：当前活动文件

renderer 只读取当前 `trail.jsonl`，不读取、不合并 `trail.001.jsonl` 及更早归档。当前 situation 的事实基线必须是当前文件：旧文件里的 `trail.handoff_target_corrected=true` 在新文件没有重新声明时不再命中，因此原问题确实被解决；仍然为真的 fact 必须在交接后的文件重新写入。

归档文件缺失、损坏或不存在都不参与 renderer，也不应使 renderer 报错；当前 `trail.jsonl` 的缺失/损坏行为保持原样。renderer 的 JSON source 仍报告活动路径 `execution/<attempt>/trail.jsonl`，不把归档序列伪装成当前输入。

#### 跨轮换扫描 key 逐项结论

扫描 key 也按当前文件重新建立基线，不读取归档；这不是把历史合并后再覆盖 fact，而是交接边界明确结束上一份当前轨迹。

| key | 轮换后的行为 | 是否误判 | 处理 |
| --- | --- | --- | --- |
| `trail.actions_since_checkpoint` | 只数当前文件中最后一个 checkpoint marker 之后的 rows；无 active checkpoint 仍为 `0`；当前文件为空仍沿用现有 empty-trail 的 `unknown`。 | 不会把归档动作带入“刚恢复”；空文件的 `unknown` 也不是伪造的 `0`。 | 保持现有算法，只让它看到当前 rows。交接后需要表达当前 checkpoint/动作时，在新文件写当前 marker/事件。 |
| `trail.incomplete_count` | 只从当前文件末尾连续扫描 `result`/`worker-return`；轮换本身是新的计数边界。新文件的第一条 `INCOMPLETE` 是当前基线的第 1 次。 | 不会把旧的 incomplete 重新变成当前处境；跨文件“全局连续第二次”不再被当前 projection 声称为第二次。 | 保持现有算法，并把“连续”口径明确为当前活动 trail 内连续；需要继续表达的当前 retry 必须在新文件形成当前事件。 |
| `trail.last_outcome` | 只取当前文件最后一个 result-like outcome（无 result-like 时沿用普通 outcome fallback）。 | 旧的 `DONE`/`INCOMPLETE` 不会在交接后继续驱动 review/fallback 建议。 | 保持现有算法，按当前 baseline 重算。 |
| `trail.last_worker_mode` | 只从当前文件取最后一个可解析 mode。 | 不会把旧 worker 的 mode 误套到新交接上下文。 | 保持现有算法；新返回/派发在当前文件记录 mode。 |
| `trail.decision_without_result` | 只配对当前文件的 decision、dispatch 与 result-like rows。 | 归档中的 open dispatch 不会被伪装成当前仍 open；如果交接后仍需要等待/重派，当前文件必须有对应当前事件。 | 保持现有配对算法。 |
| `trail.direct_evidence_returned`、`trail.finding_source`、`trail.envelope_valid` | 只扫描当前 subject 的当前文件 rows；持久化 `evidenceIndex`/state 仍按原入口读取。 | 不会用旧返回重新制造当前未归档/返回状态；当前待处理返回须在当前文件表达。 | 不新增 summary fact 或 state 字段，沿用当前扫描算法。 |
| `trail.has_investigate` / `trail.investigation_carrier_present` | 只看当前 trail 的调查 dispatch/result；既有 evidenceIndex 仍是独立持久化输入。 | 不会因旧 session 做过调查而阻止当前基线重新判断。 | 保持现有 subject 过滤和 evidence 读取。 |

因此本轮不增加“跨归档连续性摘要”或新的 fact key：那会把旧状态重新带回当前 projection，并扩大 writer/schema 范围。交接是新的可观察边界；当前文件必须承载交接后仍有效的声明和动作。

### 3. `dispatch_audit.py`：完整序列

审计与 renderer 的职责不同。`dispatch_audit.py` 读选定 attempt 目录内的完整序列：所有匹配 `trail.NNN.jsonl` 的归档按数字升序，然后读取当前 `trail.jsonl`；没有归档时仍只读当前文件。它把各文件的 rows 按这个顺序拼成一条只读审计流，因此：

- 旧 dispatch、digest、reason 和 schema violation 仍可回放；
- 审计不会因为找不到任何归档文件报错；
- `state.json` 指向的 attempt 仍是首选，fallback 仍保持“唯一 execution trail”规则；
- 报告保留当前 `trail` 字段，并额外列出实际读到的 `trails` 序列，方便知道审计覆盖范围。

审计发现文件的规则是严格文件名匹配：`trail.jsonl` 加 `trail.` 后三位十进制序号再加 `.jsonl`；其它文件不纳入。它不把 archive 内容送入 renderer 的当前处境计算，只把全序列用于历史 dispatch 审计和回放。

## 阶段 1 的 bounded scope

实施只涉及：renderer 的活动 trail 读取边界、`dispatch_audit.py` 的序列发现与读取、dev-with-track 交接一句话、现有 `situation-inputs.md` 表格口径、trail schema 轮换说明，以及一个归档 fact 不再命中的 fixture。不会修改 `compaction_pressure.py`、`impl_package_state.py`、四个 leaf agent 或外部 package。

## 阶段 2：实施

状态：阶段 2 已落盘；阶段 3 尚未开始。

已实施：

- renderer 使用明确的活动路径 helper，仍只读 `execution/<attempt>/trail.jsonl`；归档文件不会进入 `TrailView` 或 `FactContext`。
- `dispatch_audit.py` 识别严格格式 `trail.NNN.jsonl`，按序读取归档后再读活动文件；单文件时保留原有读取顺序和报告的当前 `trail` 字段，同时增加 `trails` 覆盖清单。
- `dev-with-track/SKILL.md` 的交接段落增加一句轮换与重新声明义务；`situation-inputs.md` 现有 R 表格和 trail event/fact 表格明确 renderer 与 audit 的不同读取范围；`trail-schema.md` 写入命名、序号、只读边界和 fact 基线规则。
- 新增 `p0-handoff-target-corrected-rotated` fixture：`trail.001.jsonl` 只有旧的 `trail.handoff_target_corrected=true`，当前 `trail.jsonl` 没有该 fact；参数化 fixture 测试和专门测试都要求当前 P0 不命中。
- fact 仍保持当前 schema 的 latest-wins 语义；没有新增 fact key、state 字段或 gate。

阶段 2 局部验证：

```text
python -m py_compile plugin-marketplace/plugins/impl-package/scripts/situation.py plugin-marketplace/plugins/impl-package/scripts/dispatch_audit.py
→ exit 0

python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py -q
→ 64 passed, 1 warning
```

唯一 warning 是既有 `.pytest_cache` 无法写入的 Windows 权限 warning；不影响测试结果。指定的全量 check、四组 pytest 和真实 package 只读渲染留到阶段 3。

## 阶段 3：实测

状态：阶段 3 已落盘；本任务的三阶段交付已完成，工作树仍保留 Owner 原有的其它 dirty/untracked 改动，未 commit。

### 指定 check

```text
PS> python plugin-marketplace/plugins/impl-package/scripts/situation.py check
check: PASS
- stage: dev-with-track
- situations: 57
- implemented when keys: 67
- priority groups: 6
```

### 指定 pytest

```text
PS> python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py tests/test_compaction_pressure.py tests/test_impl_package_plugin.py -q
........................................................................ [ 93%]
.....                                                                    [100%]
77 passed, 1 warning in 32.33s
```

warning 仍是 pytest 无法写入既有 `.pytest_cache` 的 Windows 权限 warning。

### 轮换 fixture 实测

fixture：`tests/fixtures/situations/p0-handoff-target-corrected-rotated`。
`trail.001.jsonl` 含 `trail.handoff_target_corrected=true`，当前 `trail.jsonl` 没有该 fact。

```text
PS> python plugin-marketplace/plugins/impl-package/scripts/situation.py render --package tests/fixtures/situations/p0-handoff-target-corrected-rotated
处境: attempt.record.unmatched
需要主控自行判断是否进入: ticket.route.multiple-business-outcomes, ticket.route.sources-conflicting
无法判定 39 行
digest: 8c69fef68f93
```

没有选中旧的 `attempt.record.handoff-target-corrected`，证明归档 fact 未进入 renderer 当前投影；参数化 fixture 与专门断言均通过。

### 真实 package 只读渲染

只读检查确认该 package 当前只有一份活动文件：

```text
execution/initial/trail.jsonl
```

实际渲染输出：

```text
PS> python D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\scripts\situation.py render --package D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning\docs\domains\finance-assistant\implementations\2026-08-15-datev-tax-advisor-import-workbench
处境: attempt.record.handoff-target-corrected  (attempt)
可选: a) resend-corrected-handoff  b) cancel-corrected-handoff
判断点: 机械条件命中，优先执行默认动作
需要主控自行判断是否进入: ticket.route.multiple-business-outcomes, ticket.route.sources-conflicting
无法判定 47 行
读取提示: 1 条（JSON 模式含详情）
digest: cd8a924f8cf0
```

因为它尚未轮换，当前文件里的 fact 仍按原 latest-wins 语义命中 P0；如果在交接时把这份文件原样归档为 `trail.001.jsonl` 并新建当前 `trail.jsonl`，而新文件没有重新声明该 fact，则这次 P0 不再命中，处境会回到当前文件能证明的状态（例如本 fixture 的 `attempt.record.unmatched`，或新的当前事件/声明所对应的 row）。真实 package 没有被修改。

### Closure recheck

随后将 audit 的单文件人类输出恢复为原形（仅多文件时显示 `trail-files`）后，重跑结果仍为：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py check
→ check: PASS

python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py tests/test_compaction_pressure.py tests/test_impl_package_plugin.py -q
→ 77 passed, 1 warning in 36.27s

python -m py_compile plugin-marketplace/plugins/impl-package/scripts/situation.py plugin-marketplace/plugins/impl-package/scripts/dispatch_audit.py
→ exit 0

git diff --check
→ exit 0（仅报告既有 CRLF line-ending warning）
```
