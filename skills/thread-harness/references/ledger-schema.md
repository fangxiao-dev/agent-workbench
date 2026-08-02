# Thread Harness Ledger Schema

本页是账本文件的字段参考。运行时目录固定为 `%TEMP%\codex-thread-broker\<coordination_id>\`；routing registry 固定为同级 `%TEMP%\codex-thread-broker\<coordination_id>.json`，由 broker 维护，账本脚本只读。

四个账本文件都是 JSON Lines，均为 append-only：只能追加新行，不重写旧行，不删除旧行。字段依据见 `design-notes.md` §5。

## progress.jsonl

记录每个 node 的最新可观测进度。写入者包括 `ledger.py sync` 和各子线通过 `ledger.py report` 主动上报。

字段按来源合成当前状态：

- `src=="poll"` 是 broker 从 rollout 与 registry worktree 读到的地面真相，负责 `head` / `turn` / `status`。
- `src=="report"` 是子线自报，负责 `state` / `waiting_on` / `last_report_ts`。
- 某 node 从未 `report` 时，`state` 回落到 poll 推导值，`waiting_on` 视为空；`sync` 摘要会在 `never_reported` 中列出该 node。
- `head` 只表示 git commit SHA，来源是 `git -C <worktree> rev-parse HEAD` 或 `report --head` 显式传入的 git SHA。Desktop `latestTurn.id` 存在 `turn`，不参与停滞判断。
- `round` 只是模型自述标签，不参与计算；`sync` 写入的 poll 行使用 `sync-state.json` 中的 `seq` 按追加顺序分组，`stall_streak` 只按 `seq` 判断。
- 如果某 node 的 git HEAD 在最后一条 report 之后发生变化，合成状态会显示为 `<state>(stale)`，摘要会在 `stale_reports` 中列出该 node。脚本只暴露陈旧，不自动改写 child state。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `sync` / `report` | 本行写入账本的时间。 |
| `src` | string | 是 | `poll` / `report` | `sync` / `report` | 本行事实来源；读取当前状态时按字段分源合成。 |
| `seq` | number | poll 必填；report 不写 | 单调递增整数 | `sync` | poll 追加批次序号，来自 `sync-state.json`；停滞判断按它分组。 |
| `round` | number | 是 | 整数 | `sync` / `report` | broker 轮询轮次标签；手动 report 不知道轮次时可写 `0`。不参与计算。 |
| `node` | string | 是 | registry node 名称 | `sync` / `report` | 进度所属 node。 |
| `head` | string 或 null | poll 必填；report 可选 | 40 位 git SHA 或 `null` | `sync` / `report` | git HEAD。`sync` 取不到 worktree/git 仓库/git 命令时写 `null`，并在摘要 `head_unavailable` 列出。 |
| `turn` | string 或 null | poll 必填 | Desktop `latestTurn.id` | `sync` | 最近一次 poll 看到的 turn id；不参与 `stall_streak`。 |
| `status` | string 或 null | poll 必填 | Desktop thread status | `sync` | 最近一次 poll 看到的 thread status。 |
| `turn_status` | string 或 null | poll 必填 | Desktop `latestTurn.status` | `sync` | 最近一次 poll 看到的 turn status。 |
| `state` | string | 是 | report 只允许 `working` / `awaiting_seam` / `awaiting_owner` / `done`；poll 可推导为 `unknown` | `sync` / `report` | node 当前状态；有非陈旧 report 时以最近 report 为准。陈旧 report 在合成状态中显示为 `<state>(stale)`。 |
| `waiting_on` | array[string] | report 必填；poll 不写 | seam 引用必须写成 `seam:<id>` | `report` | 当前阻塞依赖。poll 行不得伪造空数组来覆盖自报依赖。 |
| `last_report_ts` | string | report 必填；poll 不写 | 本地时区 ISO 8601，带偏移 | `report` | node 最近一次主动上报时间。 |
| `note` | string | 是 | 自由短文本 | `sync` / `report` | 面向 broker 的简短状态说明。 |

示例：

```jsonl
{"ts":"2026-08-01T04:48:07+02:00","src":"report","round":412,"node":"catalog","head":"f69a8b73f69a8b73f69a8b73f69a8b73f69a8b73","state":"awaiting_seam","waiting_on":["seam:order_core_writer"],"last_report_ts":"2026-08-01T04:48:07+02:00","note":"T1/T2/T3/T5 BLOCKED"}
{"ts":"2026-08-01T04:48:10+02:00","src":"poll","seq":41,"round":412,"node":"checkout","head":"71f19b7471f19b7471f19b7471f19b7471f19b74","turn":"turn-200","status":"notLoaded","turn_status":"completed","state":"working","note":"turnCompleted"}
{"ts":"2026-08-01T04:50:10+02:00","src":"poll","seq":42,"round":413,"node":"foundation","head":null,"turn":"turn-201","status":"notLoaded","turn_status":"completed","state":"working","note":"inactiveStatus"}
```

## seams.jsonl

记录 seam 的生产者、消费者与交付状态。写入者是 broker 或 Foundation 子线通过 `ledger.py seam` 登记；broker 使用 `ledger.py act --dispatch` 派活时，也会同步追加一条 `status=assigned` 的 ownership 行。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `seam` | 本行写入时间。 |
| `seam_id` | string | 是 | 不带 `seam:` 前缀的稳定 id | `seam` | seam 的唯一业务标识。 |
| `producer` | string | 是 | registry node 名称 | `seam` | 负责产出该 seam 的 node。 |
| `consumers` | array[string] | 是 | registry node 名称列表 | `seam` | 依赖该 seam 的 node。 |
| `status` | string | 是 | `assigned` / `delivered` | `seam` | seam 已指派或已交付。 |
| `artifact` | string 或 null | 是 | 例如 `commit:800521e8` | `seam` | 交付物指针；未交付时为 `null`。 |

示例：

```jsonl
{"ts":"2026-08-01T04:45:00+02:00","seam_id":"order_core_writer","producer":"f6_order_core","consumers":["inventory","checkout"],"status":"assigned","artifact":null}
{"ts":"2026-08-01T05:10:31+02:00","seam_id":"order_core_writer","producer":"f6_order_core","consumers":["inventory","checkout"],"status":"delivered","artifact":"commit:800521e8"}
{"ts":"2026-08-01T05:12:02+02:00","seam_id":"customer_tax_contract","producer":"foundation_customer","consumers":["customer","checkout"],"status":"assigned","artifact":null}
```

## decisions.jsonl

记录 owner 级决策队列。写入者是 broker 或需要 owner 裁决的子线通过 `ledger.py decide` 发起，owner/broker 通过同一命令追加回答行。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `decide` | 本行写入时间。 |
| `decision_id` | string | 是 | 稳定 id | `decide` | 决策项唯一标识。后续回答使用同一 id。 |
| `raised_by` | string 或 null | 是 | registry node 名称 | `decide --raise` | 发起决策的 node。回答行可为 `null`。 |
| `blocks` | array[string] | 是 | registry node 名称列表 | `decide --raise` | 被该决策阻塞的 node。 |
| `question` | string 或 null | 是 | 自由短文本 | `decide --raise` | 需要 owner 回答的问题。 |
| `status` | string | 是 | `pending` / `answered` | `decide` | 尚未通过 `act --escalate` 上报的 `pending` 会让 `stall-check` 优先返回 `MUST_ESCALATE`。 |
| `answer` | string 或 null | 是 | 自由短文本 | `decide --answer` | owner 或 broker 的回答。待决策时为 `null`。 |

示例：

```jsonl
{"ts":"2026-08-01T04:49:02+02:00","decision_id":"freeze_order_core_ownership","raised_by":"f6_order_core","blocks":["inventory","checkout","f6_order_core"],"question":"Should order core ownership freeze before checkout consumes it?","status":"pending","answer":null}
{"ts":"2026-08-01T04:55:18+02:00","decision_id":"freeze_order_core_ownership","raised_by":null,"blocks":[],"question":null,"status":"answered","answer":"Freeze ownership now; checkout consumes commit:800521e8."}
{"ts":"2026-08-01T05:02:11+02:00","decision_id":"split_catalog_foundation","raised_by":"catalog","blocks":["catalog"],"question":"Create a separate Foundation line for catalog pricing seam?","status":"pending","answer":null}
```

## acts.jsonl

记录 broker 在 `MUST_ESCALATE` / `MUST_ACT` 后选择了哪类动作。它只让选择可观测，不验证派发语义是否充分。

`act --dispatch` 成功时还会向 `seams.jsonl` 追加同一 `seam_id` 的 `status=assigned` 行，`consumers=[]`、`artifact=null`；如果该 seam 最新 producer 与本次不同，命令会提示 producer 变更并继续追加，最新行代表当前 ownership。

halted 状态只由 `acts.jsonl` 判定：最后一行 `kind=="halt"` 表示 loop 已终止；追加任何 `dispatch` / `escalate` 行都会自动解除。`act --halt` 必须带 `--reason`，并记录 halt 当时全部 pending decision id 的快照。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `act` | 本行写入时间。 |
| `seq` | number | 是 | 单调递增整数 | `act` | action 追加序号，来自 `sync-state.json`。 |
| `kind` | string | 是 | `dispatch` / `escalate` / `halt` | `act` | `dispatch` 表示派活，`escalate` 表示 pending decision 已上报，`halt` 表示向 Owner 报告并结束 loop。 |
| `seam_id` | string 或 null | dispatch 必填 | 不带 `seam:` 前缀 | `act --dispatch` | 本次派发要生产的 seam。 |
| `producer` | string 或 null | dispatch 必填 | registry node 名称 | `act --dispatch` | seam 生产者；必须是 registry node。 |
| `deliverable` | string 或 null | dispatch 必填 | 一句话 | `act --dispatch` | 本次派发要求交付的内容。 |
| `decision_id` | string 或 null | escalate 必填 | 稳定 id | `act --escalate` | 本次升级关联的决策项。 |
| `reason` | string 或 null | halt 必填 | 一句话 | `act --halt` | 结束整个 loop 的原因。 |
| `pending_decision_ids` | array[string] | halt 必填 | decision id 列表 | `act --halt` | halt 当时全部 pending decision id 的快照。 |

示例：

```jsonl
{"ts":"2026-08-01T05:20:00+02:00","seq":1,"kind":"dispatch","seam_id":"order_core_writer","producer":"f6_order_core","deliverable":"Publish the writer seam contract and commit pointer.","decision_id":null}
{"ts":"2026-08-01T05:25:00+02:00","seq":2,"kind":"escalate","seam_id":null,"producer":null,"deliverable":null,"decision_id":"freeze_order_core_ownership"}
{"ts":"2026-08-01T05:30:00+02:00","seq":3,"kind":"halt","seam_id":null,"producer":null,"deliverable":null,"decision_id":null,"reason":"Owner report sent; loop intentionally stopped.","pending_decision_ids":["freeze_order_core_ownership"]}
```

## sync-state.json

`sync-state.json` 不是 append-only 账本；它是本地运行状态。当前字段包括 rollout offset、`next_poll_seq`、`next_act_seq`、`dispatches_since_progress`、`docs_only_advances`、`last_must_act_seq`、invalid round 计数，以及 heartbeat reset 的 `stall_reset_seq`。

`dispatches_since_progress` 只在 code 级 git HEAD 推进后清零；docs-only 推进只增加 `docs_only_advances`。推进分类按上一条已知 head 到当前 head 的 git 区间计算：区间内任一 commit 触及非 Markdown / `docs/` 路径即为 code，区间内全部 commit 都是文档才计 docs-only。首次观测没有旧 head 时退回单 commit 判断；区间不可判定时按 `unknown`，并保守视为 code 推进。

`heartbeat` 仅允许在默认阈值的 `3/5` 或 `4/5` 执行。controller 直接读取 thread 并确认具体、最新的工作心跳后，它把当前 poll seq 写入 `stall_reset_seq`，使该轮成为新的 streak baseline；不追加或改写 `progress.jsonl`、`seams.jsonl`、`decisions.jsonl`、`acts.jsonl`，也不保存 thread 消息。

`seams_unowned` 只统计当前合成状态为 `awaiting_seam` 且 report 未陈旧的 `waiting_on` seam；因 report 陈旧而被排除的条目数显示为 `stale_waiting_on`。

## 常见错误

- `waiting_on` 写成 `"order core writer"` 这类自由文本。跨线 seam 依赖必须写成 `seam:<id>`，例如 `seam:order_core_writer`。
- `state` 使用枚举外的值，例如 `idle`、`blocked`、`waiting`。必须映射到 `working`、`awaiting_seam`、`awaiting_owner`、`done`。
- 把 `inactiveStatus` 当成没有变化。它表示有 node 闲置，该 node 应进入 `idle_nodes`，语义是该派活。
- 把 `round` 当成权威轮次。它只是模型自述标签，compaction 后可能重复；停滞判断以 `seq` 为准。
- `state=awaiting_seam` 但不写合法 `seam:<id>`。该命令会退出 `64`；摘要里的 `malformed_waiting_on` 用来暴露历史坏行。
- 更新账本时重写旧 JSONL。四个 JSONL 账本只能追加新事实；状态变更通过新行表达。
- 在 `seams.jsonl` 里只写消费者，不写 `producer`。第一轮脚本只报 `seams_unowned` 数量，后续阶段会把无 producer 的 seam 作为阻断。
- 在 `decisions.jsonl` 留下尚未上报的 `pending` 后继续普通轮询。`stall-check` 会优先返回 `MUST_ESCALATE`，broker 应上报 owner 并写 `act --escalate`。已上报但仍 pending 的决策会继续显示为 `pending_escalated`，但不再屏蔽停滞判定。

## 实测记录

行为的权威记录是可重跑的回归自检，不是贴在文档里会过期的输出：

```powershell
python skills/thread-harness/scripts/selftest.py
```

覆盖：`sync` 自检判据各自的失败路径（含 `text({pollCount:0})` 这种退化输出）、实际 ids 集合与 registry children 不一致的失败路径、投影 `n` 与实际 ids 数量不一致、`timedOut` 与 poll 字段完整性、陌生/重复 poll id、正常投影合并、`inactiveStatus` 归入 `idle_nodes` 且与 `unchanged` 分开、`polls[]` 缺 child 时仍为该 child 写 progress 并读取 head、`SYNC STALE` 错误信息含 path/bytes/mtime/scanned_lines、`report` 后 `state` / `waiting_on` 不被下一轮 `sync` 覆盖、陈旧 report 暴露为 `stale_reports` 且 stale waiting_on 不计入无主 seam、重复 `round` 时按追加顺序累计 `stall_streak`、默认 `5/5` 阈值与从 `3/5` 开始的 heartbeat reset、heartbeat 不修改 JSONL、多 commit 区间内 docs-only 与 code 推进区分、首次观测单 commit 推进分类、`act --dispatch` 留痕并同步形成 seam ownership、`act --halt` 留痕、halted 状态暴露与自动解除、`status` 无 sync 时可读、真实 git fixture 下 turn 变化不重置 `stall_streak`、`stall-check` 的 0/2/3 优先级、已上报 pending 不屏蔽 `MUST_ACT`、同 id 重新 raise 需要重新上报、`decide --raise/--answer`、多值参数空格分隔、`seam` producer/consumer registry 校验、用法错误退 64。

自检用 `THREAD_HARNESS_BROKER_ROOT` 与 `THREAD_HARNESS_SESSIONS_ROOT` 指向隔离目录，**不会碰生产运行时**。

fixture 刻意手写、不复用 `ledger.py` 的解析逻辑——用被测代码自己的假设去造测试数据，测不出假设本身是错的。
