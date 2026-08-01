# Thread Harness Poll Contract

本页是 broker 每轮可直接照抄的轮询操作页。契约依据见 `design-notes.md` §3；本页只保留操作事实。

## 固定 JS 片段

四条不可动摇的约束：

1. `timeoutMs` 不得低于 `180000`，推荐固定为 `180000`。
2. `targets` 必须覆盖 registry 中**全部 children，不含 controller 自己**。主控轮询自身没有意义，且会让 `n` 多算一个而每轮判 `ROUND INVALID`。
3. `text()` 输出**下面这个投影**，字段一个都不能少。`ledger.py sync` 从 controller rollout 里读这个投影——**你不打印的东西，任何地方都不存在**（rollout 记录的是 exec 打印的内容，不是工具原始返回）。
4. `txt` 截断到 500 字符。需要某条线的全文时用 `codex_app__read_thread` 单独取，不要放宽这里。

```js
const ids = [/* registry 中各 node 的 current_session_id，内联 */];
const r = await tools.codex_app__wait_threads({
  targets: ids.map(threadId => ({ threadId })),
  timeoutMs: 180000
});
text(JSON.stringify({
  v: 1,
  n: ids.length,
  wake: r.wake || null,
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
- `create_thread` 不是无条件自授权动作，需要 Owner 在 goal 或对话中明确授权。主控 goal 模板里已包含该授权。
- `create_thread` 无法给子线设置持久 goal，只有初始 prompt。因此子线的 H1/H2 不像主控那样免疫 compaction；缓解手段是主控靠 `last_report_ts` 与 `never_reported` 检测漏报，而不是相信子线记得。
- timeout 契约是不得低于 `180000`，推荐固定 `180000`。实现接受 `>= 180000`，避免把更保守的等待误判成无效轮次。

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
   - `unchanged`：本轮没有变化。
   - `head_unavailable`：这些 node 的 worktree/git HEAD 取不到；不要把它当成"无变化"。
   - `never_reported`：这些 node 从未通过 `ledger.py report` 自报；用来判断 H1 是否真实遵守。
   - `pending_decisions`：大于 0 时准备上报 owner。
   - `stall_streak`：接近 `3/3` 时必须准备二选一。
   - `seams_unowned`：第一轮只报数，用来决定后续是否开启阻断校验。
   - `dispatches_since_progress`：自最近一次 git head 推进以来，rollout 中 `send_message_to_thread` 与 `create_thread` 调用次数。它只测量，不阻断。
4. 执行 `python skills/thread-harness/scripts/ledger.py stall-check --coordination-id <id>`。
5. 按退出码决策。

## 退出码表（全部子命令通用）

| 码 | 含义 | broker 动作 |
| --- | --- | --- |
| `0` | 正常 | 按 `sync` 摘要处理普通事项，进入下一轮 |
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

它用独立构造的 fixture 覆盖 `sync` 自检判据、`SYNC STALE` 的错误信息完整性、决策与停滞的退出码优先级、`decide --raise/--answer`、多值参数空格分隔、`report` 状态不被 poll 覆盖、真实 git HEAD 停滞判断、用法错误退 64。**这份 fixture 刻意不复用 `ledger.py` 自身的解析逻辑**——用被测代码的假设去造测试数据，测不出假设本身是错的。（初版轮询契约就是这样漏掉了"rollout 只记录打印内容"这个事实。）

## 自检失败处理

如果 `ledger.py sync` 输出：

```text
ROUND INVALID: poll snippet altered (<具体原因>)
```

本轮 payload 不会合并进 `progress.jsonl`。broker 应立即停止普通轮询，恢复固定 JS 片段，确认 `timeoutMs >= 180000` 且 `targets` 数量等于 registry 的 children 总数，然后重新发起下一轮。

当前 `sync` 自检只接受固定投影契约。五类失败文案如下：

| 判据 | 不符时的报错 |
| --- | --- |
| 调用 arguments 里 `timeoutMs >= 180000` | `timeoutMs <n> < 180000` |
| 调用 arguments 里能解析出 `const ids = [...]` | `cannot parse ids array from call` |
| 实际 ids 集合等于 registry 中全部 children 的 `current_session_id` 集合 | `targets mismatch (missing=<...>, unexpected=<...>)` |
| 输出可解析为 JSON 且 `v == 1` | `projection missing or wrong version` |
| 输出含 `n` 与 `polls` 两个键 | `projection shape altered (missing <key>)` |
| `n` 等于实际 ids 数量 | `projection n=<a> != actual targets <b>` |
| `polls` 每个元素含 `id` / `status` / `turn` / `turnStatus` / `txt` 五个键 | `poll entry shape altered` |

如果 `ledger.py sync` 输出：

```text
SYNC STALE: rollout not flushed (path=<absolute-path>, bytes=<size>, mtime=<mtime>, scanned_lines=<n>)
```

表示 rollout 中还没有本轮 `wait_threads` 输出，或输出 payload 暂不可解析。broker 不得静默复用旧数据；应等待下一轮或重新执行固定片段后再跑 `sync`。
