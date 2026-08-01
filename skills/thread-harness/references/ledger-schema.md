# Thread Harness Ledger Schema

本页是账本文件的字段参考。运行时目录固定为 `%TEMP%\codex-thread-broker\<coordination_id>\`；routing registry 固定为同级 `%TEMP%\codex-thread-broker\<coordination_id>.json`，由 broker 维护，账本脚本只读。

三个账本文件都是 JSON Lines，均为 append-only：只能追加新行，不重写旧行，不删除旧行。字段依据见 `design-notes.md` §5。

## progress.jsonl

记录每个 node 的最新可观测进度。写入者包括 `ledger.py sync` 和各子线通过 `ledger.py report` 主动上报。

字段按来源合成当前状态：

- `src=="poll"` 是 broker 从 rollout 与 registry worktree 读到的地面真相，负责 `head` / `turn` / `status`。
- `src=="report"` 是子线自报，负责 `state` / `waiting_on` / `last_report_ts`。
- 某 node 从未 `report` 时，`state` 回落到 poll 推导值，`waiting_on` 视为空；`sync` 摘要会在 `never_reported` 中列出该 node。
- `head` 只表示 git commit SHA，来源是 `git -C <worktree> rev-parse HEAD` 或 `report --head` 显式传入的 git SHA。Desktop `latestTurn.id` 存在 `turn`，不参与停滞判断。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `sync` / `report` | 本行写入账本的时间。 |
| `src` | string | 是 | `poll` / `report` | `sync` / `report` | 本行事实来源；读取当前状态时按字段分源合成。 |
| `round` | number | 是 | 整数 | `sync` / `report` | broker 轮询轮次；手动 report 不知道轮次时可写 `0`。 |
| `node` | string | 是 | registry node 名称 | `sync` / `report` | 进度所属 node。 |
| `head` | string 或 null | poll 必填；report 可选 | 40 位 git SHA 或 `null` | `sync` / `report` | git HEAD。`sync` 取不到 worktree/git 仓库/git 命令时写 `null`，并在摘要 `head_unavailable` 列出。 |
| `turn` | string 或 null | poll 必填 | Desktop `latestTurn.id` | `sync` | 最近一次 poll 看到的 turn id；不参与 `stall_streak`。 |
| `status` | string 或 null | poll 必填 | Desktop thread status | `sync` | 最近一次 poll 看到的 thread status。 |
| `turn_status` | string 或 null | poll 必填 | Desktop `latestTurn.status` | `sync` | 最近一次 poll 看到的 turn status。 |
| `state` | string | 是 | `working` / `awaiting_seam` / `awaiting_owner` / `done` | `sync` / `report` | node 当前状态；有 report 时以最近 report 为准。 |
| `waiting_on` | array[string] | report 必填；poll 不写 | seam 引用必须写成 `seam:<id>` | `report` | 当前阻塞依赖。poll 行不得伪造空数组来覆盖自报依赖。 |
| `last_report_ts` | string | report 必填；poll 不写 | 本地时区 ISO 8601，带偏移 | `report` | node 最近一次主动上报时间。 |
| `note` | string | 是 | 自由短文本 | `sync` / `report` | 面向 broker 的简短状态说明。 |

示例：

```jsonl
{"ts":"2026-08-01T04:48:07+02:00","src":"report","round":412,"node":"catalog","head":"f69a8b73f69a8b73f69a8b73f69a8b73f69a8b73","state":"awaiting_seam","waiting_on":["seam:order_core_writer"],"last_report_ts":"2026-08-01T04:48:07+02:00","note":"T1/T2/T3/T5 BLOCKED"}
{"ts":"2026-08-01T04:48:10+02:00","src":"poll","round":412,"node":"checkout","head":"71f19b7471f19b7471f19b7471f19b7471f19b74","turn":"turn-200","status":"notLoaded","turn_status":"completed","state":"working","note":"turnCompleted"}
{"ts":"2026-08-01T04:50:10+02:00","src":"poll","round":413,"node":"foundation","head":null,"turn":"turn-201","status":"notLoaded","turn_status":"completed","state":"working","note":"inactiveStatus"}
```

## seams.jsonl

记录 seam 的生产者、消费者与交付状态。写入者是 broker 或 Foundation 子线通过 `ledger.py seam` 登记。

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
| `status` | string | 是 | `pending` / `answered` | `decide` | `pending` 会让 `stall-check` 优先返回 `MUST_ESCALATE`。 |
| `answer` | string 或 null | 是 | 自由短文本 | `decide --answer` | owner 或 broker 的回答。待决策时为 `null`。 |

示例：

```jsonl
{"ts":"2026-08-01T04:49:02+02:00","decision_id":"freeze_order_core_ownership","raised_by":"f6_order_core","blocks":["inventory","checkout","f6_order_core"],"question":"Should order core ownership freeze before checkout consumes it?","status":"pending","answer":null}
{"ts":"2026-08-01T04:55:18+02:00","decision_id":"freeze_order_core_ownership","raised_by":null,"blocks":[],"question":null,"status":"answered","answer":"Freeze ownership now; checkout consumes commit:800521e8."}
{"ts":"2026-08-01T05:02:11+02:00","decision_id":"split_catalog_foundation","raised_by":"catalog","blocks":["catalog"],"question":"Create a separate Foundation line for catalog pricing seam?","status":"pending","answer":null}
```

## 常见错误

- `waiting_on` 写成 `"order core writer"` 这类自由文本。跨线 seam 依赖必须写成 `seam:<id>`，例如 `seam:order_core_writer`。
- `state` 使用枚举外的值，例如 `idle`、`blocked`、`waiting`。必须映射到 `working`、`awaiting_seam`、`awaiting_owner`、`done`。
- 把 `inactiveStatus` 当成没有变化。它表示有 node 闲置，该 node 应进入 `idle_nodes`，语义是该派活。
- 更新账本时重写旧 JSONL。三个账本只能追加新事实；状态变更通过新行表达。
- 在 `seams.jsonl` 里只写消费者，不写 `producer`。第一轮脚本只报 `seams_unowned` 数量，后续阶段会把无 producer 的 seam 作为阻断。
- 在 `decisions.jsonl` 留下 `pending` 后继续普通轮询。`stall-check` 会优先返回 `MUST_ESCALATE`，broker 应上报 owner。

## 实测记录

行为的权威记录是可重跑的回归自检，不是贴在文档里会过期的输出：

```powershell
python skills/thread-harness/scripts/selftest.py
```

覆盖：`sync` 自检判据各自的失败路径（含 `text({pollCount:0})` 这种退化输出）、实际 ids 集合与 registry children 不一致的失败路径、投影 `n` 与实际 ids 数量不一致、poll 字段完整性、正常投影合并、`inactiveStatus` 归入 `idle_nodes` 且与 `unchanged` 分开、`SYNC STALE` 错误信息含 path/bytes/mtime/scanned_lines、`report` 后 `state` / `waiting_on` 不被下一轮 `sync` 覆盖、真实 git fixture 下 turn 变化不重置 `stall_streak`、`stall-check` 的 0/2/3 优先级、`decide --raise/--answer`、多值参数空格分隔、`seam` producer/consumer registry 校验、用法错误退 64。

自检用 `THREAD_HARNESS_BROKER_ROOT` 与 `THREAD_HARNESS_SESSIONS_ROOT` 指向隔离目录，**不会碰生产运行时**。

fixture 刻意手写、不复用 `ledger.py` 的解析逻辑——用被测代码自己的假设去造测试数据，测不出假设本身是错的。
