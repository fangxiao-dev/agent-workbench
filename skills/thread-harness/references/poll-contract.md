# Thread Harness Poll Contract

本页是 broker 每轮可直接照抄的轮询操作页。契约依据见 `design-notes.md` §3；本页只保留操作事实。

## 固定 JS 片段

五条不可动摇的约束：

1. `timeoutMs` 固定为 `120000`，与当前 `wait_threads` 平台上限一致。
2. `targets` 必须等于脚本按账本机械推导出的 wait 集合：优先为 **runnable watch-set**（`working`、`never_reported`、report 已 stale、controller dispatch 后的 producer 或当前状态 unknown 的 active children）；如果 runnable 集合为空，则回退为全部 active children，保留固定 120 秒 poll。`awaiting_seam`、`awaiting_owner`、`done` 不进入正常阻塞 wait；inactive child 只保留历史，controller 自己也不进入 poll。
3. `text()` 输出**下面这个投影**，字段一个都不能少。`ledger.py sync` 从 controller rollout 里读这个投影——**你不打印的东西，任何地方都不存在**（rollout 记录的是 exec 打印的内容，不是工具原始返回）。
4. `txt` 截断到 500 字符。需要某条线的全文时用 `codex_app__read_thread` 单独取，不要放宽这里。

```js
const ids = [/* runnable watch-set 中各 node 的 current_session_id，内联 */];
const raw = await tools.codex_app__wait_threads({
  targets: ids.map(threadId => ({ threadId })),
  timeoutMs: 120000
});
const r = typeof raw === "string" ? JSON.parse(raw) : raw;
text(JSON.stringify({
  v: 1,
  n: ids.length,
  wake: r.wake || null,
  timedOut: r.timedOut,
  polls: (r.polls || []).map(p => ({
    id: p.thread?.id,
    status: p.thread?.status?.type,
    turn: p.latestTurn?.id,
    turnStatus: p.latestTurn?.status,
    txt: (p.latestAssistantMessage?.text || "").slice(0, 500)
  }))
}));
```

不要"优化"它。这段的每个语法都是实跑验证过的（`?.`、`(x||[])`、`slice`），刻意不用 `??`。缩短它、少打印几个字段、或者只回一个计数——这些都会被 `sync` 的自检当场拦下并作废本轮。若 runnable watch-set 为空，controller 回退到全部 active child，继续执行固定 120 秒 poll。

## 平台约束

- `wait_threads` 单次最多接受 8 个 `targets`。本 harness 当前假设 active children <= 8；超过 8 的分片轮询方案本轮不做，属于已知限制。
- 当前 Desktop bridge 可能把工具结果包装为 JSON 字符串；固定片段必须先做 object/string 双态解包，再输出规定投影。
- 本轮采用 runnable watch-set 兜底：`afterCursor` 只保证已投递 final text 可被抑制，不能把状态级重复唤醒当作已证明消失；HEAD 仍采集全部 active child，阻塞 wait 优先覆盖 runnable 集合，集合为空时回退到全部 active child。
- `create_thread` 不是无条件自授权动作，需要 Owner 在 goal 或对话中明确授权。主控 goal 模板里已包含该授权。
- `create_thread` 无法给子线设置持久 goal，只有初始 prompt。因此子线的 H1 不像主控那样免疫 compaction；缓解手段是主控靠 `last_report_ts` 与 `never_reported` 检测漏报，而不是相信子线记得。子线不直接运行 `ledger.py report/seam/decide`。
- timeout 契约固定为 `120000`。更小会退化为忙等，更大会被当前平台参数校验拒绝。

## wake.reason 语义

| `wake.reason` | 含义 | broker 动作 |
| --- | --- | --- |
| `inactiveStatus` | 有线程闲着，通常是 `notLoaded`。这是“该派活”的信号，不是“没变化”。 | 查看 `ledger.py sync` 摘要里的 `idle_nodes`，给这些 node 派 seam 或任务。 |
| `turnCompleted` | 某条线完成了一个 turn，有新内容可读。 | 查看 `changed_nodes`，必要时读对应 thread 或推进下游。 |
| `actionableStatus` | 有线程需要动作。 | 查看摘要和账本，决定派活、答复或上报。 |
| 无 wake 且 `polls` 为空 | 真的没有变化。 | 进入 `stall-check`，按停滞规则判断是否必须行动。 |

## 一轮动作序列

1. 根据上一轮 ledger 状态计算 runnable watch-set；若集合为空，固定 poll 回退到全部 active child，不取消本轮 120 秒检查。
2. 在 exec JS 中原样敲固定片段，只替换 `ids` 的内联 session id 列表。
3. 执行 `python skills/thread-harness/scripts/ledger.py sync --registry <absolute-registry-json> --round <n>`。
4. 读取 `sync` 的紧凑摘要：
   - `poll_targets`：本轮固定 wait 实际目标；它必须与脚本按 ledger 推导的 runnable 集合完全相等，或在 runnable 为空时等于全部 active child。
   - `idle_nodes`：该派活；只有 active 且最新 ledger state 为 `working` 的 node 才进入。`idle`、`inactive`、`notLoaded`、`not_loaded` 都可作为 idle 信号；`awaiting_seam`、`awaiting_owner`、`done` 和 inactive registry child 排除。
   - `changed_nodes`：有新 head，需要读或推进。
   - `advance_kinds`：本轮 HEAD 推进类型，`docs` 不清零 dispatch 计数，`code` / `unknown` 会清零。
   - `unchanged`：本轮没有变化。
   - `session_age_h`：只测量 active child 的 registry `updated_at` 距当前时间的小时数，按从大到小排列；缺失或不可解析显示为 `?`，不含 controller 和 inactive child。它是主控判断是否触发 session 交接的信号，但不影响退出码、`stall_streak` 或 halt 判定。
   - `timedOut`：`true (timeout, no change)` 表示 wait 超时且没有 poll 内容，区别于被唤醒但无文本。
   - `head_unavailable`：这些 node 的 worktree/git HEAD 取不到；不要把它当成"无变化"。
   - `never_reported`：这些 node 从未通过 controller 验证的 H1 写入 state；用来判断 H1 是否真实遵守。
   - `stale_reports`：这些 node 的最后一次 report 后又出现 git HEAD 变化；不要把旧 report 当成当前阻塞状态。
   - `unknown_status`：这些 node 的 Desktop status 不在已知映射内；不要默认当成 `working`。
   - `pending_decisions`：大于 0 时准备上报 owner。
   - `stall_streak`：默认阈值为 `5/5`；从 `3/5` 起每轮执行一次直接 thread 心跳检查，`5/5` 时必须二选一。
   - `seams_unowned`：第一轮只报数，用来决定后续是否开启阻断校验。
   - `malformed_waiting_on`：历史 report 中不合法的 `waiting_on` 项数量。
   - `dispatches_since_progress`：自最近一次 code 级 git head 推进以来，rollout 中有配对 output 的 `tools.codex_app__send_message_to_thread` 与 `tools.codex_app__create_thread` 调用次数。它只测量，不阻断。
   - `docs_only_advances`：自最近一次 code 级推进以来的 docs-only HEAD 推进次数。
    - `corrupt_ledger_lines`：JSONL 中无法解析的坏行数量；大于 0 时状态摘要只能作诊断，不能视为可信 current state。
5. 执行 `python skills/thread-harness/scripts/ledger.py stall-check --registry <absolute-registry-json>`。
6. 按退出码和输出标记决策。`CHECK_HEARTBEAT` 的退出码也是 `0`，但不能当普通 `OK` 略过。

## Session 路由

交接完成后由当时的 controller 用 `route` 回填 registry，避免手工编辑 JSON：

```powershell
python skills/thread-harness/scripts/ledger.py route --registry <absolute-registry-json> --node <node> --new-session <session-id> [--expect-current <session-id>]
```

`--expect-current`（若提供）必须等于目标 node 当前的 `current_session_id`；`--new-session` 不能等于任何 node 当前的 session id（包括目标自身），两项校验失败都退出 `64` 且不改 registry。成功时只更新目标 node：旧 session 追加到 `previous_session_ids`（不重复）、写入新 `current_session_id`，并刷新 `updated_at`。命令会写回后重新读取，校验目标值及其他 node 的序列化对象均未被改变；未知字段与原有键序保留。`route` 不写四个 JSONL，也不创建或修改 `sync-state.json`。

## 开跑前：preflight

```powershell
python skills/thread-harness/scripts/ledger.py preflight --registry <absolute-registry-json>
```

只读，不写任何 JSONL。`PREFLIGHT OK`（退出码 `0`）才能开始轮询；`PREFLIGHT FAILED`（退出码 `5`）时先修。若发现 JSONL 坏行，先打印 `LEDGER INTEGRITY FAILED: <file>:<line> <reason>` 并返回 `6`。

它拦的全是**会静默扭曲读数**的问题：worktree 路径写错、两个 active node 共用 worktree 或 branch、registry 的 branch 与该 worktree 实际 checkout 的分支不一致、active `children > 8`、active `current_session_id` 重复、controller 的 session id 找不到 rollout、运行时目录未 `init`。inactive child 保留历史，不参与这些 active-child 检查。

`dirty_worktree`（Owner WIP）与 `child_rollout_missing` 只报警告，不阻断——前者是合法状态但派发 prompt 里必须写明不可触碰，后者不影响判定，因为子线状态从 `wait_threads` 投影读、不从 rollout 读。


接手新 session 时先执行：

```powershell
python skills/thread-harness/scripts/ledger.py status --registry <absolute-registry-json>
```

`status` 先读 registry，再只读账本，不读 rollout，也不要求新 session 已经跑过首轮 poll；registry 或 runtime 缺失时报告 `runtime_uninitialized` 或清晰错误，不创建目录、空 JSONL 或 `sync-state.json`。它用于恢复各 node 最新 state/head/turn/最后 H1 时间、pending decisions、未交付 seams、`stall_streak` 和最近一次 `act`。若账本有坏行，仍输出诊断摘要但返回 `6`，并明确 partial rows 不是可信 current state。

`stall-check` 从 `3/5` 起、到 `5/5` 前输出 `CHECK_HEARTBEAT` 时：

1. 若 poll / 当前 report 显示仍有 active / working node，直接对这些 node 的 current session 调 `codex_app__read_thread`，看最新内容；不新增每轮消息缓存。
2. 任一 thread 出现具体且最新的执行心跳（例如新测试正在运行、新 finding 已闭合、正在执行的新命令），执行：

```powershell
python skills/thread-harness/scripts/ledger.py heartbeat --registry <absolute-registry-json> --node <node> --evidence "<一句话具体进展>"
```

3. heartbeat 只允许在 `3/5` 或 `4/5` 时执行，并把全局 `stall_streak` 归零。重复等待文案、旧进展、笼统的“仍在工作”或仅有 active 状态都不算心跳；没有具体新进展时不执行 heartbeat，下一轮继续检查，直到 `5/5`。
4. 若全员 idle，不做 heartbeat；`idle_nodes` 直接按派活信号处理。

该命令只更新 `sync-state.json` 的 reset marker；`--evidence` 只用于迫使 controller 当场说清具体进展，不落盘。它不修改任何 append-only JSONL，也不保存 thread 消息。

`stall-check` 看最近一次 halt 及其记录的 `halt_poll_seq`。若还没有更大的有效 poll seq，输出 `HALTED (ts=<...>, reason=<...>, pending=<...>)` 并返回 `4`；`dispatch` / `escalate` 不会隐式 resume。Owner 在 controller 对话明确恢复后，controller 运行新的有效 poll + sync，新 poll seq 自动使旧 halt 失效；halt 历史保留。

`stall-check` 返回 `MUST_ESCALATE` 时，只列出尚未上报的 pending decision。每次 `decide --raise` 都生成新的 `decision_instance_id`；`act --escalate` 绑定当前 pending instance，旧 instance 的上报不能遮蔽同一 `decision_id` 的新一轮 raise：

```powershell
python skills/thread-harness/scripts/ledger.py act --registry <absolute-registry-json> --escalate --decision-id <d>
```

全部 pending decision 都已上报时，`stall-check` 不再返回 `3`，会继续进入 streak 判定；输出行会带 `pending_escalated: <id...>`，避免这些 pending 从主控视野消失。

`stall-check` 返回 `MUST_ACT` 后，用 `act` 留下本轮选择：

```powershell
python skills/thread-harness/scripts/ledger.py act --registry <absolute-registry-json> --dispatch --seam-id <s> --producer <node> --deliverable "<一句话>"
python skills/thread-harness/scripts/ledger.py act --registry <absolute-registry-json> --halt --reason "<一句话>"
```

`act --dispatch` 的 `--seam-id`、`--producer`、`--deliverable` 都必填，且 producer 必须是 registry node。`act --halt` 的 `--reason` 必填，缺失时退出 `64`；halt 行会记录当时全部 pending decision id 的快照。`stall-check` 会输出 `last_must_act_answered: yes|no`，只报告上一次 `MUST_ACT` 后是否有新 `act` 行，不改变退出码。

## 退出码表（全部子命令通用）

| 码 | 含义 | broker 动作 |
| --- | --- | --- |
| `0` | `OK` 或 `CHECK_HEARTBEAT` | `OK` 按摘要处理；`CHECK_HEARTBEAT` 必须按上方流程直接读 thread，再决定是否 reset |
| `1` | `sync` 自检失败（`ROUND INVALID`）或 rollout 未就绪（`SYNC STALE`） | 见下方「自检失败处理」。**本轮作废，不要当成"无变化"** |
| `2` | `stall-check` 输出 `MUST_ACT` | 二选一：派发新工作，或向 Owner 报告并结束 loop |
| `3` | `stall-check` 输出 `MUST_ESCALATE` | 立即上报尚未上报的 pending decision，并写 `act --escalate`；本轮结束。已上报 pending 不再屏蔽 `2` |
| `4` | `stall-check` 输出 `HALTED` | loop 已由最近一次 halt 终止。**不要继续轮询**，先向 Owner 确认；恢复只能由 Owner 明确恢复后产生新的有效 poll/sync seq 完成 |
| `5` | `preflight` 输出 `PREFLIGHT FAILED` | 修掉列出的每一条再开跑。**不要带着失败开始轮询** |
| `6` | JSONL ledger integrity failed | 立即停止状态推进；保留原账本供诊断，不自动截断、重写或猜测修复 |
| `64` | 命令用法错误（参数拼错、缺必填项） | 修正命令重跑。**这不是业务信号** |

**退出码在语义上必须唯一**——不要复用，理由见 [design-notes.md](design-notes.md) §6。

多值参数（`--blocks` / `--consumers` / `--waiting-on`）**空格分隔和重复传都支持**：`--blocks alpha beta` 与 `--blocks alpha --blocks beta` 等价。

## 回归自检

改动 `ledger.py` 后跑：

```powershell
python skills/thread-harness/scripts/selftest.py
```

它用独立构造的 fixture 覆盖 `sync` 自检判据、`SYNC STALE` 的错误信息完整性、决策与停滞的退出码优先级、已上报 pending 不屏蔽 `MUST_ACT`、同 id 重新 raise 需要重新上报、`act --halt` 直到新的有效 poll seq 才恢复、默认 `5/5` 阈值、从 `3/5` 开始的 `CHECK_HEARTBEAT`、heartbeat reset 不修改 JSONL、`decide --raise/--answer`、多值参数空格分隔、controller 验证 H1 source session 与 HEAD 后代、`report` 状态不被 poll 覆盖、陈旧 report、重复 `round`、docs-only/code 推进分类、active/inactive child 过滤、只读 `status`、`act` 留痕、真实 git HEAD 停滞判断、用法错误退 64。**这份 fixture 刻意不复用 `ledger.py` 自身的解析逻辑**——用被测代码的假设去造测试数据，测不出假设本身是错的。（初版轮询契约就是这样漏掉了"rollout 只记录打印内容"这个事实。）

## 自检失败处理

如果 `ledger.py sync` 输出：

```text
ROUND INVALID: poll snippet altered (<具体原因>)
```

本轮 payload 不会合并进 `progress.jsonl`。broker 应立即停止普通轮询，恢复固定 JS 片段，确认 `timeoutMs == 120000` 且 `targets` 恰好等于 ledger 推导出的 **runnable watch-set**，然后重新发起下一轮。

当前 `sync` 自检只接受固定投影契约。五类失败文案如下：

| 判据 | 不符时的报错 |
| --- | --- |
| 调用 source（legacy `arguments` / modern `input`）里 `timeoutMs == 120000` | `timeoutMs <n> != 120000` |
| 调用 arguments 里能解析出 `const ids = [...]` | `cannot parse ids array from call` |
| 实际 ids 集合等于 ledger 推导的 wait 集合（runnable 非空时为 runnable，否则为全部 active child） | `targets mismatch (missing=<...>, unexpected=<...>)` |
| 输出可解析为 JSON 且 `v == 1` | `projection missing or wrong version` |
| 输出含 `n` 与 `polls` 两个键 | `projection shape altered (missing <key>)` |
| `n` 等于实际 ids 数量 | `projection n=<a> != actual targets <b>` |
| `polls` 每个元素含 `id` / `status` / `turn` / `turnStatus` / `txt` 五个键 | `poll entry shape altered` |
| 输出含 `timedOut` | `projection shape altered (missing timedOut)` |
| `polls[].id` 属于 registry children 且不重复 | `poll id not in registry (<id>)` / `duplicate poll id (<id>)` |

如果 `ledger.py sync` 输出：

```text
SYNC STALE: rollout not flushed (path=<absolute-path>, bytes=<size>, mtime=<mtime>, scanned_lines=<n>)
```

表示 rollout 中还没有本轮 `wait_threads` 输出，或输出 payload 暂不可解析。broker 不得静默复用旧数据；应等待下一轮或重新执行固定片段后再跑 `sync`。

## 已知限制

- BLK-4 decoy 绕过 `validate_call`：rollout 只记录 exec 打印的内容，结构上无法证明实际传给 `wait_threads` 的参数是什么。放一个未使用的正确 `const ids=[...]` 再实际传 `targets: []` 能通过全部校验。这一层封不死。部分缓解是 `polls[].id` 必须属于 registry children。威胁模型上，本 harness 防的是长跑压力下逐步简化，不是主动伪造；decoy 需要写更多代码而非更少，不在退化路径上。
- 坏行不会被自动截断、重写或猜测修复；`status` 的 partial 摘要只用于诊断，返回码 `6` 才是可信信号。
- seam producer 被后续行改写、`artifact` 只是自由文本：第一轮 H4 只登记不校验语义。
- 失败的 dispatch 调用与真实成功与否：当前只统计有配对 output 的调用，并要求 `arguments` 中出现 `tools.codex_app__send_message_to_thread` / `tools.codex_app__create_thread`；不做调用结果追踪。
