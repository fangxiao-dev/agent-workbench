# Thread Harness Poll Contract

本页是 broker 每轮可直接照抄的轮询操作页。契约依据见 `design-notes.md` §3；本页只保留操作事实。

## 固定 JS 片段

四条不可动摇的约束：

1. `timeoutMs` 固定为 `120000`，与当前 `wait_threads` 平台上限一致。
2. `targets` 必须覆盖 registry 中**全部 children，不含 controller 自己**。主控轮询自身没有意义，且会让 `n` 多算一个而每轮判 `ROUND INVALID`。
3. `text()` 输出**下面这个投影**，字段一个都不能少。`ledger.py sync` 从 controller rollout 里读这个投影——**你不打印的东西，任何地方都不存在**（rollout 记录的是 exec 打印的内容，不是工具原始返回）。
4. `txt` 截断到 500 字符。需要某条线的全文时用 `codex_app__read_thread` 单独取，不要放宽这里。

```js
const ids = [/* registry 中各 node 的 current_session_id，内联 */];
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

不要"优化"它。这段的每个语法都是实跑验证过的（`?.`、`(x||[])`、`slice`），刻意不用 `??`。缩短它、少打印几个字段、或者只回一个计数——这些都会被 `sync` 的自检当场拦下并作废本轮。

## 平台约束

- `wait_threads` 单次最多接受 8 个 `targets`。本 harness 当前假设 children <= 8；超过 8 的分片轮询方案本轮不做，属于已知限制。
- 当前 Desktop bridge 可能把工具结果包装为 JSON 字符串；固定片段必须先做 object/string 双态解包，再输出规定投影。
- `create_thread` 不是无条件自授权动作，需要 Owner 在 goal 或对话中明确授权。主控 goal 模板里已包含该授权。
- `create_thread` 无法给子线设置持久 goal，只有初始 prompt。因此子线的 H1/H2 不像主控那样免疫 compaction；缓解手段是主控靠 `last_report_ts` 与 `never_reported` 检测漏报，而不是相信子线记得。
- timeout 契约固定为 `120000`。更小会退化为忙等，更大会被当前平台参数校验拒绝。

## wake.reason 语义

| `wake.reason` | 含义 | broker 动作 |
| --- | --- | --- |
| `inactiveStatus` | 有线程闲着，通常是 `notLoaded`。这是“该派活”的信号，不是“没变化”。 | 查看 `ledger.py sync` 摘要里的 `idle_nodes`，给这些 node 派 seam 或任务。 |
| `turnCompleted` | 某条线完成了一个 turn，有新内容可读。 | 查看 `changed_nodes`，必要时读对应 thread 或推进下游。 |
| `actionableStatus` | 有线程需要动作。 | 查看摘要和账本，决定派活、答复或上报。 |
| 无 wake 且 `polls` 为空 | 真的没有变化。 | 进入 `stall-check`，按停滞规则判断是否必须行动。 |

## 一轮动作序列

1. 在 exec JS 中原样敲固定片段，只替换 `ids` 的内联 session id 列表。
2. 执行 `python skills/thread-harness/scripts/ledger.py sync --coordination-id <id> --round <n>`。
3. 读取 `sync` 的紧凑摘要：
   - `idle_nodes`：该派活。
   - `changed_nodes`：有新 head，需要读或推进。
   - `advance_kinds`：本轮 HEAD 推进类型，`docs` 不清零 dispatch 计数，`code` / `unknown` 会清零。
   - `unchanged`：本轮没有变化。
   - `timedOut`：`true (timeout, no change)` 表示 wait 超时且没有 poll 内容，区别于被唤醒但无文本。
   - `head_unavailable`：这些 node 的 worktree/git HEAD 取不到；不要把它当成"无变化"。
   - `never_reported`：这些 node 从未通过 `ledger.py report` 自报；用来判断 H1 是否真实遵守。
   - `stale_reports`：这些 node 的最后一次 report 后又出现 git HEAD 变化；不要把旧 report 当成当前阻塞状态。
   - `unknown_status`：这些 node 的 Desktop status 不在已知映射内；不要默认当成 `working`。
   - `pending_decisions`：大于 0 时准备上报 owner。
   - `stall_streak`：默认阈值为 `5/5`；从 `3/5` 起每轮执行一次直接 thread 心跳检查，`5/5` 时必须二选一。
   - `seams_unowned`：第一轮只报数，用来决定后续是否开启阻断校验。
   - `malformed_waiting_on`：历史 report 中不合法的 `waiting_on` 项数量。
   - `dispatches_since_progress`：自最近一次 code 级 git head 推进以来，rollout 中有配对 output 的 `tools.codex_app__send_message_to_thread` 与 `tools.codex_app__create_thread` 调用次数。它只测量，不阻断。
   - `docs_only_advances`：自最近一次 code 级推进以来的 docs-only HEAD 推进次数。
   - `corrupt_ledger_lines`：JSONL 中无法解析的坏行数量。
4. 执行 `python skills/thread-harness/scripts/ledger.py stall-check --coordination-id <id>`。
5. 按退出码和输出标记决策。`CHECK_HEARTBEAT` 的退出码也是 `0`，但不能当普通 `OK` 略过。

接手新 session 时先执行：

```powershell
python skills/thread-harness/scripts/ledger.py status --coordination-id <id>
```

`status` 只读账本和 registry，不读 rollout，也不要求新 session 已经跑过首轮 poll。它用于恢复各 node 最新 state/head/turn/最后 report 时间、pending decisions、未交付 seams、`stall_streak` 和最近一次 `act`。

`stall-check` 从 `3/5` 起、到 `5/5` 前输出 `CHECK_HEARTBEAT` 时：

1. 若 poll / 当前 report 显示仍有 active / working node，直接对这些 node 的 current session 调 `codex_app__read_thread`，看最新内容；不新增每轮消息缓存。
2. 任一 thread 出现具体且最新的执行心跳（例如新测试正在运行、新 finding 已闭合、正在执行的新命令），执行：

```powershell
python skills/thread-harness/scripts/ledger.py heartbeat --coordination-id <id> --node <node> --evidence "<一句话具体进展>"
```

3. heartbeat 只允许在 `3/5` 或 `4/5` 时执行，并把全局 `stall_streak` 归零。重复等待文案、旧进展、笼统的“仍在工作”或仅有 active 状态都不算心跳；没有具体新进展时不执行 heartbeat，下一轮继续检查，直到 `5/5`。
4. 若全员 idle，不做 heartbeat；`idle_nodes` 直接按派活信号处理。

该命令只更新 `sync-state.json` 的 reset marker；`--evidence` 只用于迫使 controller 当场说清具体进展，不落盘。它不修改任何 append-only JSONL，也不保存 thread 消息。

`stall-check` 返回 `MUST_ACT` 后，用 `act` 留下本轮选择：

```powershell
python skills/thread-harness/scripts/ledger.py act --coordination-id <id> --dispatch --seam-id <s> --producer <node> --deliverable "<一句话>"
python skills/thread-harness/scripts/ledger.py act --coordination-id <id> --escalate --decision-id <d>
```

`act --dispatch` 的 `--seam-id`、`--producer`、`--deliverable` 都必填，且 producer 必须是 registry node。`stall-check` 会输出 `last_must_act_answered: yes|no`，只报告上一次 `MUST_ACT` 后是否有新 `act` 行，不改变退出码。

## 退出码表（全部子命令通用）

| 码 | 含义 | broker 动作 |
| --- | --- | --- |
| `0` | `OK` 或 `CHECK_HEARTBEAT` | `OK` 按摘要处理；`CHECK_HEARTBEAT` 必须按上方流程直接读 thread，再决定是否 reset |
| `1` | `sync` 自检失败（`ROUND INVALID`）或 rollout 未就绪（`SYNC STALE`） | 见下方「自检失败处理」。**本轮作废，不要当成"无变化"** |
| `2` | `stall-check` 输出 `MUST_ACT` | 二选一：派发新工作，或向 Owner 报告并结束 loop |
| `3` | `stall-check` 输出 `MUST_ESCALATE` | 立即上报 pending decision，不进入下一轮。**优先级高于 `2`** |
| `64` | 命令用法错误（参数拼错、缺必填项） | 修正命令重跑。**这不是业务信号** |

`64` 是刻意选的，不用 argparse 默认的 `2`：如果用法错误也退 `2`，一次拼错的命令会被读成 `MUST_ACT`，或者反过来让真正的 `MUST_ACT` 被当成拼写问题忽略掉。**退出码在语义上必须唯一。**

多值参数（`--blocks` / `--consumers` / `--waiting-on`）**空格分隔和重复传都支持**：`--blocks alpha beta` 与 `--blocks alpha --blocks beta` 等价。

## 回归自检

改动 `ledger.py` 后跑：

```powershell
python skills/thread-harness/scripts/selftest.py
```

它用独立构造的 fixture 覆盖 `sync` 自检判据、`SYNC STALE` 的错误信息完整性、决策与停滞的退出码优先级、默认 `5/5` 阈值、从 `3/5` 开始的 `CHECK_HEARTBEAT`、heartbeat reset 不修改 JSONL、`decide --raise/--answer`、多值参数空格分隔、`report` 状态不被 poll 覆盖、陈旧 report、重复 `round`、docs-only/code 推进分类、`act` 留痕、`status` 接手路径、真实 git HEAD 停滞判断、用法错误退 64。**这份 fixture 刻意不复用 `ledger.py` 自身的解析逻辑**——用被测代码的假设去造测试数据，测不出假设本身是错的。（初版轮询契约就是这样漏掉了"rollout 只记录打印内容"这个事实。）

## 自检失败处理

如果 `ledger.py sync` 输出：

```text
ROUND INVALID: poll snippet altered (<具体原因>)
```

本轮 payload 不会合并进 `progress.jsonl`。broker 应立即停止普通轮询，恢复固定 JS 片段，确认 `timeoutMs == 120000` 且 `targets` 数量等于 registry 的 children 总数，然后重新发起下一轮。

当前 `sync` 自检只接受固定投影契约。五类失败文案如下：

| 判据 | 不符时的报错 |
| --- | --- |
| 调用 source（legacy `arguments` / modern `input`）里 `timeoutMs == 120000` | `timeoutMs <n> != 120000` |
| 调用 arguments 里能解析出 `const ids = [...]` | `cannot parse ids array from call` |
| 实际 ids 集合等于 registry 中全部 children 的 `current_session_id` 集合 | `targets mismatch (missing=<...>, unexpected=<...>)` |
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
- seam producer 被后续行改写、`artifact` 只是自由文本：第一轮 H4 只登记不校验语义。
- 失败的 dispatch 调用与真实成功与否：当前只统计有配对 output 的调用，并要求 `arguments` 中出现 `tools.codex_app__send_message_to_thread` / `tools.codex_app__create_thread`；不做调用结果追踪。
