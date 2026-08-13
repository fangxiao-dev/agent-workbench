# Thread Harness Ledger Schema

本页是账本文件的字段参考。正式调用显式传入 `<absolute-registry-json>`；运行时目录由 registry sibling 与其中的 `coordination_id` 推导，即 `<registry-parent>\<coordination_id>\`。旧的 `THREAD_HARNESS_BROKER_ROOT` + `--coordination-id` 仍兼容，routing registry 由 broker 维护，账本脚本不重写。

未显式传 registry 时，兼容路径默认使用 `ledger.py` 所在仓库中已忽略的 `.progress-record`；`THREAD_HARNESS_BROKER_ROOT` 仍可覆盖该兼容路径。`coordination_id` 用 `<YYMMDDHH>-<slug>`，时间戳取该 coordination 的起始小时。**不要放在 `%TEMP%`**——账本是接手与复盘唯一的事实来源。

四个账本文件都是 JSON Lines，均为 append-only：只能追加新行，不重写旧行，不删除旧行。**controller 是指定 ledger writer**；child 只发送 H1 JSON payload，controller 验证后使用现有命令追加。CLI 不提供可信调用者鉴权；`act --halt --source-session` 只用于防误操作与来源一致性校验。所有 mutation 在 coordination 级跨进程写锁内完成；追加使用完整 UTF-8 bytes、flush 与 fsync。坏行会 fail-closed，不能自动修复。

## registry broker contract

registry 根部必须包含：

```json
{
  "broker": {
    "profile": "solo",
    "budget": {
      "smart_zone_tokens": 150000,
      "tail_requests": 20,
      "tail_p75_increment_tokens": 1720
    }
  }
}
```

`profile` 只能是 `solo` 或 `swarm`；三项 budget 必须是正整数，并且脚本机械计算出正的 `handoff_at`。缺失或非法配置由 `preflight` fail-closed，不自动迁移旧 registry。计算规则为 `tail_reserve_tokens = tail_requests × tail_p75_increment_tokens`、`handoff_at = smart_zone_tokens − tail_reserve_tokens`，默认结果为 `115600`。

child 可声明绝对 `package_entry`，指向任务包 `progress.md`。`solo` 需要唯一 active task child 且 entry 有效；`swarm` 对声明 entry 的 task child 做 adapter 校验，Platform child 可省略 entry。adapter 优先读取 3.5 的 `attempt.id`、`activeCheckpoints.attempt.next`、`attemptHistory.executionRecord` 与 Git revision；package schema 缺失或不一致只进入 `package_schema_warning`，无法确认的 checkpoint/next action 置空，不阻断 preflight。adapter 不读取或写入 Ticket、Task、evidence、acceptance 或 package state writer。

## budget observer

`sync-state.json` 的 `compaction_observers` 按 current session id 保存 rollout 增量 offset、compaction count、最近 `last_token_usage.input_tokens`、`model_context_window` 与可用性。首次观察从 rollout EOF 建 baseline；部分 JSONL 行不推进 offset；新 session 使用新 id 建 baseline。预算只覆盖 controller 与 active task session，Platform 不进入 task handoff budget。

`budget_states` 按 current session id 保存 `tracking` 或 sticky `handoff_due`。token observer 优先使用最近 `last_token_usage.input_tokens`，不使用累计 `total_token_usage`；token observer 不可用时只保留已有 compaction-count fallback，不把缺失值猜成 0。`handoff_due` 后 controller 通过 `act --handoff` 只追加一次 handoff action；route 到新 session 后下一轮 sync 建立新 baseline。

## route：registry 路由回填

`route --registry <absolute-json> --node <node> --new-session <session-id> [--expect-current <session-id>]` 只修改 registry，不写任何账本 JSONL，也不创建或修改 `sync-state.json`。它要求 `--expect-current`（若提供）匹配目标 node 当前的 `current_session_id`，并拒绝与任一 node 当前 session id 重复的新值；这两类校验失败都退出 `64` 且 registry 一字不改。

成功时仅更新目标 node：把旧 `current_session_id` 追加进 `previous_session_ids`（若尚未存在），设置新的 `current_session_id`，并刷新 `updated_at`。写回后命令会重新读取 registry，确认目标值已生效且其他 node 对象未变；未知字段与原有键序保留。controller 可用自己的 node 名或字面量 `controller` 定位。

## progress.jsonl

记录每个 node 的最新可观测进度。写入者包括 `ledger.py sync` 和 controller 验证 H1 后通过 `ledger.py report` 追加。

字段按来源合成当前状态：

- `src=="poll"` 是 broker 从 rollout 与 registry worktree 读到的地面真相，负责 `head` / `turn` / `status`。
- `src=="report"` 是 controller 验证 H1 后写入的 state，负责 `state` / `waiting_on` / `last_report_ts`。
- 某 node 从未有 controller 验证的 H1 report 时，`state` 回落到 poll 推导值，`waiting_on` 视为空；`sync` 摘要会在 `never_reported` 中列出该 node。
- `head` 只表示 git commit SHA，来源是 registry worktree 的 `git rev-parse HEAD` 或经过 source session 与后代校验的 H1 head。Desktop `latestTurn.id` 存在 `turn`，不参与停滞判断。
- `round` 只是模型自述标签，不参与计算；`sync` 写入的 poll 行使用 `sync-state.json` 中的 `seq` 按追加顺序分组，`stall_streak` 只按 `seq` 判断。
- 如果某 node 的 git HEAD 在最后一条 report 之后发生变化，合成状态会显示为 `<state>(stale)`，摘要会在 `stale_reports` 中列出该 node。脚本只暴露陈旧，不自动改写 child state。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `sync` / `report` | 本行写入账本的时间。 |
| `src` | string | 是 | `poll` / `report` | `sync` / `report` | 本行事实来源；读取当前状态时按字段分源合成。 |
| `seq` | number | poll 必填；report 不写 | 单调递增整数 | `sync` | poll 追加批次序号，来自 `sync-state.json`；停滞判断按它分组。 |
| `ledger_seq` | number | 新 row 必填；legacy 可缺省 | coordination 内单调递增批次序号 | `sync` / `report` | 用于跨 `progress.jsonl` / `acts.jsonl` 判断 report 与 dispatch 的真实追加顺序；同一 sync 批次的 poll rows 可共享一个值。 |
| `round` | number | 是 | 整数 | `sync` / `report` | broker 轮询轮次标签；手动 report 不知道轮次时可写 `0`。不参与计算。 |
| `node` | string | 是 | registry node 名称 | `sync` / `report` | 进度所属 node。 |
| `head` | string 或 null | poll 必填；report 可选 | 40 位 git SHA 或 `null` | `sync` / `report` | git HEAD。`sync` 取不到 worktree/git 仓库/git 命令时写 `null`，并在摘要 `head_unavailable` 列出。 |
| `turn` | string 或 null | poll 必填 | Desktop `latestTurn.id` | `sync` | 最近一次 poll 看到的 turn id；不参与 `stall_streak`。 |
| `status` | string 或 null | poll 必填 | Desktop thread status | `sync` | 最近一次 poll 看到的 thread status。 |
| `turn_status` | string 或 null | poll 必填 | Desktop `latestTurn.status` | `sync` | 最近一次 poll 看到的 turn status。 |
| `state` | string | 是 | report 允许 `working` / `awaiting_seam` / `awaiting_owner` / `ready_for_assignment`；历史 `done` 仅兼容读取；poll 可推导为 `unknown` | `sync` / `report` | node 当前 assignment 状态；有非陈旧 report 时以最近 report 为准。`ready_for_assignment` 只结束当前 assignment，不代表 package/node terminal。陈旧 report 在合成状态中显示为 `<state>(stale)`。 |
| `waiting_on` | array[string] | report 必填；poll 不写 | seam 引用必须写成 `seam:<id>` | `report` | 当前阻塞依赖。poll 行不得伪造空数组来覆盖自报依赖。 |
| `last_report_ts` | string | report 必填；poll 不写 | 本地时区 ISO 8601，带偏移 | `report` | node 最近一次主动上报时间。 |
| `note` | string | 是 | 自由短文本 | `sync` / `report` | 面向 broker 的简短状态说明。 |
| `source_session_id` | string | controller 接受 H1 后的 report 必填；legacy report 可缺省 | registry 当前 child session id | controller | controller 从消息来源绑定并验证。 |
| `source_registry` | string | controller 接受 H1 后的 report 必填；legacy report 可缺省 | absolute registry JSON path | controller | 记录 controller 实际使用并验证的 registry。 |

示例：

```jsonl
{"ts":"2026-08-01T04:48:07+02:00","src":"report","ledger_seq":40,"round":412,"node":"catalog","head":"f69a8b73f69a8b73f69a8b73f69a8b73f69a8b73","state":"awaiting_seam","waiting_on":["seam:order_core_writer"],"last_report_ts":"2026-08-01T04:48:07+02:00","note":"T1/T2/T3/T5 BLOCKED"}
{"ts":"2026-08-01T04:48:10+02:00","src":"poll","ledger_seq":41,"seq":41,"round":412,"node":"checkout","head":"71f19b7471f19b7471f19b7471f19b7471f19b74","turn":"turn-200","status":"notLoaded","turn_status":"completed","state":"working","note":"turnCompleted"}
{"ts":"2026-08-01T04:50:10+02:00","src":"poll","ledger_seq":43,"seq":42,"round":413,"node":"foundation","head":null,"turn":"turn-201","status":"notLoaded","turn_status":"completed","state":"working","note":"inactiveStatus"}
```

### H1 JSON payload（消息格式，不是新 API）

子线只发送以下最小 JSON 给当前 controller；它不运行 `ledger.py report`、`seam` 或 `decide`：

```json
{"v":1,"event":"state_changed","state":"awaiting_seam","head":"0123456789012345678901234567890123456789","waiting_on":["seam:order_core_writer"],"artifact":null,"details":null,"note":"waiting for writer contract"}
```

controller 必须从消息来源唯一绑定 node 与 source session，再重新读取自己持有的 registry，确认来源等于该 node 的 current session；无法唯一绑定就停止，不猜测。若已有 ledger HEAD，H1 head 必须是其 git 后代，且必须位于该 node 当前 worktree HEAD 的历史上，才允许写入 progress。`event` 用于说明触发原因，`artifact` 无交付物时为 `null`。`details` 是事件特有的最小对象：`seam_delivered` 带 `seam_id/consumers`，`owner_blocked` 带 `decision_id/blocks/question`，`handed_off` 带 `new_session_id`（child 自建继任者后上报，controller 据此回填 registry），其他事件为 `null`。seam ownership 与 Owner decision 同样由 controller 写入。

bounded assignment 结束时 child 报 `ready_for_assignment`。`sync` 对仍为 active 的该状态输出 `reassignment_required`；controller 只有在核验 terminal acceptance 后才把 registry `active=false`。历史 `done` 行继续可读，但按 `ready_for_assignment` 的动作语义处理，不能静默解释为 package terminal。

## seams.jsonl

记录 seam 的生产者、消费者与交付状态。写入者是 controller；Platform child 在 H1 中报告交付事实，controller 通过 `ledger.py seam` 登记；controller 使用 `ledger.py act --dispatch` 派活时，也会同步追加一条 `status=assigned` 的 ownership 行。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `seam` | 本行写入时间。 |
| `ledger_seq` | number | 新 row 必填；legacy 可缺省 | coordination 内单调递增批次序号 | `seam` | 账本 mutation 的追加顺序标记。 |
| `seam_id` | string | 是 | 不带 `seam:` 前缀的稳定 id | `seam` | seam 的唯一业务标识。 |
| `producer` | string | 是 | registry node 名称 | `seam` | 负责产出该 seam 的 node。 |
| `consumers` | array[string] | 是 | registry node 名称列表 | `seam` | 依赖该 seam 的 node。 |
| `status` | string | 是 | `assigned` / `delivered` | `seam` | seam 已指派或已交付。 |
| `artifact` | string 或 null | 是 | 例如 `commit:800521e8` | `seam` | 交付物指针；未交付时为 `null`。 |

示例：

```jsonl
{"ts":"2026-08-01T04:45:00+02:00","ledger_seq":38,"seam_id":"order_core_writer","producer":"f6_order_core","consumers":["inventory","checkout"],"status":"assigned","artifact":null}
{"ts":"2026-08-01T05:10:31+02:00","ledger_seq":46,"seam_id":"order_core_writer","producer":"f6_order_core","consumers":["inventory","checkout"],"status":"delivered","artifact":"commit:800521e8"}
{"ts":"2026-08-01T05:12:02+02:00","ledger_seq":47,"seam_id":"customer_tax_contract","producer":"foundation_customer","consumers":["customer","checkout"],"status":"assigned","artifact":null}
```

## decisions.jsonl

记录 owner 级决策队列。child 在 H1 中报告 Owner 级阻塞，controller 通过 `ledger.py decide` 发起；owner/controller 通过同一命令追加回答行。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `decide` | 本行写入时间。 |
| `ledger_seq` | number | 新 row 必填；legacy 可缺省 | coordination 内单调递增批次序号 | `decide` | 账本 mutation 的追加顺序标记。 |
| `decision_id` | string | 是 | 稳定 id | `decide` | 决策项唯一标识。后续回答使用同一 id。 |
| `decision_instance_id` | string | 新 raise 必填；legacy 可缺省 | UUID | `decide` / `act --escalate` | 一次 `raise` 的不可复用实例；answer/escalate 必须绑定当前 pending instance。缺失时按 legacy timestamp fallback。 |
| `raised_by` | string 或 null | 是 | registry node 名称 | `decide --raise` | 发起决策的 node。回答行可为 `null`。 |
| `blocks` | array[string] | 是 | registry node 名称列表 | `decide --raise` | 被该决策阻塞的 node。 |
| `question` | string 或 null | 是 | 自由短文本 | `decide --raise` | 需要 owner 回答的问题。 |
| `status` | string | 是 | `pending` / `answered` | `decide` | 尚未通过 `act --escalate` 上报的 `pending` 会让 `stall-check` 优先返回 `MUST_ESCALATE`。 |
| `answer` | string 或 null | 是 | 自由短文本 | `decide --answer` | owner 或 broker 的回答。待决策时为 `null`。 |

示例：

```jsonl
{"ts":"2026-08-01T04:49:02+02:00","ledger_seq":42,"decision_id":"freeze_order_core_ownership","decision_instance_id":"2e8f8c5d-8c6a-4c6b-bb13-7c3eabf7b4b1","raised_by":"f6_order_core","blocks":["inventory","checkout","f6_order_core"],"question":"Should order core ownership freeze before checkout consumes it?","status":"pending","answer":null}
{"ts":"2026-08-01T04:55:18+02:00","ledger_seq":44,"decision_id":"freeze_order_core_ownership","decision_instance_id":"2e8f8c5d-8c6a-4c6b-bb13-7c3eabf7b4b1","raised_by":null,"blocks":[],"question":null,"status":"answered","answer":"Freeze ownership now; checkout consumes commit:800521e8."}
{"ts":"2026-08-01T05:02:11+02:00","ledger_seq":45,"decision_id":"split_catalog_foundation","decision_instance_id":"b1f4f77d-43d2-4b31-a6af-6dd12ca77c9a","raised_by":"catalog","blocks":["catalog"],"question":"Create a separate Platform line for catalog pricing seam?","status":"pending","answer":null}
```

## acts.jsonl

记录 broker 在 `MUST_ESCALATE` / `MUST_ACT` 或预算交接后选择了哪类动作。它只让选择可观测，不验证派发语义是否充分。

`act --dispatch` 成功时还会向 `seams.jsonl` 追加同一 `seam_id` 的 `status=assigned` 行，`consumers=[]`、`artifact=null`；如果该 seam 最新 producer 与本次不同，命令会提示 producer 变更并继续追加，最新行代表当前 ownership。

halted 状态由 `acts.jsonl` 的最近 halt 与其 `halt_poll_seq` 判定：没有更大的有效 poll seq 时 loop 已终止；追加 `dispatch` / `escalate` 行不会自动解除。controller 执行 `act --halt` 前必须重新读取 registry，并同时传入当前 `controller.current_session_id` 作为 `--source-session` 与一句话 `--reason`；任一缺失都退出 `64`。该 session 参数不是可信鉴权。成功后记录 halt 当时全部 pending decision id 的快照。

| 字段 | 类型 | 必填 | 枚举 / 格式 | 写入者 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `ts` | string | 是 | 本地时区 ISO 8601，带偏移 | `act` | 本行写入时间。 |
| `seq` | number | 是 | 单调递增整数 | `act` | action 追加序号，来自 `sync-state.json`。 |
| `ledger_seq` | number | 新 row 必填；legacy 可缺省 | coordination 内单调递增批次序号 | `act` | 用于判断 dispatch 与 report 的真实追加顺序；同一 `act --dispatch` 写入的 ownership seam row 共享该值。 |
| `kind` | string | 是 | `dispatch` / `escalate` / `halt` / `handoff` | `act` | `dispatch` 表示 swarm 派活，`escalate` 表示 pending decision 已上报，`halt` 表示向 Owner 报告并结束 loop，`handoff` 表示 current session 已达到 sticky `handoff_due`。 |
| `seam_id` | string 或 null | dispatch 必填 | 不带 `seam:` 前缀 | `act --dispatch` | 本次派发要生产的 seam。 |
| `producer` | string 或 null | dispatch 必填 | registry node 名称 | `act --dispatch` | seam 生产者；必须是 registry node。 |
| `deliverable` | string 或 null | dispatch 必填 | 一句话 | `act --dispatch` | 本次派发要求交付的内容。 |
| `decision_id` | string 或 null | escalate 必填 | 稳定 id | `act --escalate` | 本次升级关联的决策项。 |
| `decision_instance_id` | string 或 null | 新 instance escalate 必填；legacy 可缺省 | UUID | `act --escalate` | 精确绑定本次 pending decision instance；旧行缺失时保留 timestamp fallback。 |
| `reason` | string 或 null | halt 必填 | 一句话 | `act --halt` | 结束整个 loop 的原因。 |
| `pending_decision_ids` | array[string] | halt 必填 | decision id 列表 | `act --halt` | halt 当时全部 pending decision id 的快照。 |
| `halt_poll_seq` | number | halt 必填 | 当前有效 poll seq | `act --halt` | 只有 Owner 明确恢复后产生更大的有效 poll seq，旧 halt 才失效。 |
| `node` | string | handoff 必填 | active registry node 名称 | `act --handoff` | 需要交接的 current node。 |
| `node_session_id` | string | handoff 必填 | node 当前 session id | `act --handoff` | 交接 action 的 session 身份；route 后新 session 不复用旧 action。 |
| `source_session` | string | handoff 必填 | 当前 controller session id | `act --handoff` | 来源一致性护栏，不是可信鉴权。 |
| `budget_stage` | string | handoff 必填 | `handoff_due` | `act --handoff` | ledger 重新确认的预算阶段。 |
| `handoff_requested` | boolean | handoff 必填 | `true` | `act --handoff` | 幂等 action 标记；同 node/current session 重复调用不追加新行。 |

示例：

```jsonl
{"ts":"2026-08-01T05:20:00+02:00","ledger_seq":48,"seq":1,"kind":"dispatch","seam_id":"order_core_writer","producer":"f6_order_core","deliverable":"Publish the writer seam contract and commit pointer.","decision_id":null}
{"ts":"2026-08-01T05:25:00+02:00","ledger_seq":49,"seq":2,"kind":"escalate","seam_id":null,"producer":null,"deliverable":null,"decision_id":"freeze_order_core_ownership"}
{"ts":"2026-08-01T05:30:00+02:00","ledger_seq":50,"seq":3,"kind":"halt","seam_id":null,"producer":null,"deliverable":null,"decision_id":null,"reason":"Owner report sent; loop intentionally stopped.","pending_decision_ids":["freeze_order_core_ownership"]}
```

## sync-state.json

`sync-state.json` 不是 append-only 账本；它是本地运行状态。当前字段包括 controller rollout offset、按 controller 与 active task session id 保存的 `compaction_observers`、按 current session 保存的 `budget_states`、`next_poll_seq`、`next_act_seq`、`next_ledger_seq`、`dispatches_since_progress`、`docs_only_advances`、`last_must_act_seq`、invalid round 计数，以及 heartbeat reset 的 `stall_reset_seq`。每个 observer 保存 rollout path、byte offset、`observed_count`、最后一次 `window_number/window_id`、最近 `last_token_usage.input_tokens`、`model_context_window` 与 token 可用性；首次观测在 EOF 建基线，后续只读取新增完整行，不递归扫描全量 sessions，也不修改四个 append-only JSONL。`compaction_count` 因而是 observer 建立后的可靠观测下界，不是平台历史总数。

本轮采用 runnable watch-set 兜底，不把未经证明的 cursor 当作状态级去重依据；HEAD 仍覆盖全部 active child。`ledger_seq` 用于消除同秒 report/dispatch 的顺序歧义；legacy 行缺失该字段时回退到时间戳判断。halt 行记录当时的 `halt_poll_seq`；`dispatch` / `escalate` 不会清除 halt。`handoff` action 由 controller 对当前 active node 幂等追加，重复调用不追加新行。

`dispatches_since_progress` 只在 code 级 git HEAD 推进后清零；docs-only 推进只增加 `docs_only_advances`。推进分类按上一条已知 head 到当前 head 的 git 区间计算：区间内任一 commit 触及非 Markdown / `docs/` 路径即为 code，区间内全部 commit 都是文档才计 docs-only。首次观测没有旧 head 时退回单 commit 判断；区间不可判定时按 `unknown`，并保守视为 code 推进。

`heartbeat` 仅允许在默认阈值的 `3/5` 或 `4/5` 执行。controller 直接读取 thread 并确认具体、最新的工作心跳后，它把当前 poll seq 写入 `stall_reset_seq`，使该轮成为新的 streak baseline；不追加或改写 `progress.jsonl`、`seams.jsonl`、`decisions.jsonl`、`acts.jsonl`，也不保存 thread 消息。

`seams_unowned` 只统计当前合成状态为 `awaiting_seam` 且 report 未陈旧的 `waiting_on` seam；因 report 陈旧而被排除的条目数显示为 `stale_waiting_on`。

## 常见错误

- `waiting_on` 写成 `"order core writer"` 这类自由文本。跨线 seam 依赖必须写成 `seam:<id>`，例如 `seam:order_core_writer`。
- `state` 使用枚举外的值，例如 `idle`、`blocked`、`waiting`。必须映射到 `working`、`awaiting_seam`、`awaiting_owner`、`ready_for_assignment`。不要新写 `done`；它只为历史 ledger 兼容保留。
- 把 bounded assignment 的 `ready_for_assignment` 当成 package 或 node terminal。active node 必须进入 `reassignment_required`，只有 registry `active=false` 才表示该 node 已退出 coordination。
- 把 `inactiveStatus` 当成没有变化。它表示有 node 闲置，该 node 应进入 `idle_nodes`，语义是该派活。
- 把 `round` 当成权威轮次。它只是模型自述标签，compaction 后可能重复；停滞判断以 `seq` 为准。
- `state=awaiting_seam` 但不写合法 `seam:<id>`。该命令会退出 `64`；摘要里的 `malformed_waiting_on` 用来暴露历史坏行。
- 新 ledger row 的 `ledger_seq` 缺失可以按 legacy 处理；字段存在但不是正整数必须按账本完整性错误处理，不能静默回退到时间戳。
- 更新账本时重写旧 JSONL。四个 JSONL 账本只能追加新事实；状态变更通过新行表达。
- 把坏行当成普通摘要尾项。任何坏行都必须先打印 `LEDGER INTEGRITY FAILED: <file>:<line> <reason>` 并返回 `6`；不能继续追加事实。
- 在 `seams.jsonl` 里只写消费者，不写 `producer`。第一轮脚本只报 `seams_unowned` 数量，后续阶段会把无 producer 的 seam 作为阻断。
- 在 `decisions.jsonl` 留下尚未上报的 `pending` 后继续普通轮询。`stall-check` 会优先返回 `MUST_ESCALATE`，broker 应上报 owner 并写 `act --escalate`。已上报但仍 pending 的决策会继续显示为 `pending_escalated`，但不再屏蔽停滞判定。
