# Thread Harness · 设计依据与实现契约

本文件是 `thread-harness` 的**设计说明与实现契约**。SKILL.md 只写"怎么用"，本文件写"为什么这样、必须满足什么"。实现者（人或 agent）以本文件为准。

证据来源：2026-08-01 对 coordination_id `remove-lark-runtime` 的调度复盘（1 主控 + 7 子线，13.75 小时，全线死锁）。完整报告见 `D:\CodeSpace\agent-eval-20260801\REPORT.md`，findings 编号 F1–F10 在下文被直接引用。

---

## 1. 要解决的问题（一句话）

上一轮失败**不是**模型犯糊涂、不是额度耗尽、不是缺授权、不是崩溃。是**没有任何组件对"整体是否在推进"负责**：broker 把自己定义成不写代码的调度者，子线把自己定义成"没有 exact artifact 就待命"，于是产出契约的责任落进缝隙；唯一能发现这件事的人（Owner）睡着了 8 小时。

所以本 harness 的设计目标不是"让它跑得更久"，而是**让它卡住时会叫人，且尽量少地卡住**。

## 2. 四条硬规则（第一轮强制）

其余一切都是启发式与意图偏置。硬的只有这四条，且每条都对应一个已发生的失效。

| # | 硬规则 | 对应 finding |
| --- | --- | --- |
| H1 | **回报触发条件**：任一 thread 在 turn 结束前，若 ①`head` 变了 ②状态从 working 转为 waiting ③产生 owner 级阻塞——三者之一成立，必须写账本并 `send_message_to_thread` 回 broker | F3：7 条线里 5 条从不主动回报，F6 唯一能解环的 Owner 请求因此永远没送达 |
| H2 | **账本字段与写入时机**：状态变更即 append，字段按 §5 schema | F9：全局进度只活在 context 里，末期每 12 分钟被 compaction 清洗一次 |
| H3 | **停滞上限 + 二选一**：连续 3 轮所有 node 的 `head` 无变化，broker 必须二选一——(a) 派发新工作（含 create_thread 开新 Foundation 线），(b) 向 Owner 报告并结束 loop。**禁止第三种输出。** 另：`decisions.jsonl` 有 `pending` 项时立即上报，不进入下一轮 | F1：Owner 是唯一解卡装置；F7：broker 把自己的待办归类成外部阻塞。上一轮它输出了 104 次"本轮 loop 检查完成" |
| H4 | **seam 必须登记生产者**：任何 `awaiting_seam` 都要指向一个 `seam_id`，该 seam 必须在 `seams.jsonl` 里有一条带 `producer` 的记录 | F2/F7：环的成因是"跨域上游契约"是个没有归属的名词 |

H4 的分阶段：**第一轮只登记不校验**；阶段 2 打开校验（`waiting_on` 指向的 seam 查不到 producer → broker 必须立即指派，否则报错阻断）。schema 一次写全，不迁移。

## 3. 轮询契约（poll contract）

### 3.1 已核实的运行时约束

对上一轮 4016 次 exec 调用的解析结论，实现时不要挑战这些：

- exec 是沙箱 JS，**无模块加载**：`require` / `eval` / `import` / `new Function` 出现次数均为 **0**。
- `tools.codex_app__*` 绑定**只存在于 exec 的 JS 里**，不是一等 function_call 工具，`tools.shell_command` 够不着。
- 可用绑定全集（观测到的）：`shell_command`、`apply_patch`、`update_plan`、`web__run`、`codex_app__{wait_threads, send_message_to_thread, read_thread, read_thread_terminal, list_threads, create_thread, set_thread_title, list_projects, load_workspace_dependencies, fork_thread}`。
- **结论：无法让模型"执行一个文件"。那段 JS 必须由模型每轮亲手敲出来。**

`fork_thread` 本 harness 不使用。

### 3.1.1 rollout 写入行为（已探针验证，2026-08-01）

完整探针记录见 `D:\CodeSpace\agent-eval-20260801\probe-rollout-flush.md`。

- **同 turn 内前一个工具调用的输出，在下一个工具调用启动时已可从磁盘读到**（Desktop 主控 thread 与非 ephemeral CLI 会话均在 attempt 0 命中）。按事件追加并及时 flush，不是 turn 结束批量写。
- **`--ephemeral` 的 CLI 会话不写 rollout 文件**。因此 broker 绝不能跑在 ephemeral 模式下——`ledger.py sync` 会读不到任何东西。
- 未验证：非零延迟的分布（无 p95/p99 样本）、并发多 thread 写入时的定位、Windows 以外平台、进程崩溃时的部分写入。

对实现的约束：`sync` 用**有界重试 20 次 × 100ms（上限 2 秒）**，每次重新 stat 文件；超时后必须打印候选文件路径、大小、mtime、已扫描行数，**不得静默当作"无输出"**。定位 rollout **必须用 session id**，不要按 LastWriteTime 猜——并发场景会选错。

### 3.2 设计取向：把可被简化的部分挪出模型的书写范围

上一轮的退化路径是：模型每轮现写 JS → 每写一次简化一点 → 最后简化成 `text({pollCount})`，返回 `{"pollCount":0}`，**主动丢弃 payload**（F5）。

对策不是"要求它别简化"，而是让简化**无物可吃**：JS 半边短到没有简化空间，解释逻辑全部住在磁盘脚本里。

### 3.3 一个曾经写错的设计（保留记录，避免重犯）

初版设计写的是「JS 只回一行短确认，完整 payload 由 `ledger.py` 从 rollout 读取」。**这是错的。**

实测证据：rollout 的 `response_item/custom_tool_call_output` 记录的是 **exec cell 打印出来的内容**，不是工具的原始返回。

- 04:40 脚本是 `text(r)` → 输出里有完整 payload。
- 06:30 脚本是 `text({pollCount:..., wake:...})` → 输出就只有 `{"pollCount":0}`。

而 `codex_app__wait_threads` 不是一等 function_call 工具，**没有独立的记录行**。所以：**脚本不打印的东西，任何地方都不存在。**

推论：payload 必须经由 `text()` 输出，才可能被 `ledger.py` 读到。省 context 的正确做法不是"不打印"，而是"**打印一个固定的、有界的投影**"。

### 3.4 固定 JS 片段（模型每轮原样敲）

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

四条不可动摇：`timeoutMs` 固定 `180000`；`targets` 覆盖 registry 的**全部 children，不含 controller 自己**（主控轮询自身没有意义）；输出是**这个投影**，字段一个不能少；`txt` 截断到 500 字符。

**所有语法都是实跑验证过的**：可选链 `?.`、`(x||[])`、`String.slice` 在上一轮主控 06:30 的真实片段里都出现过。刻意不用 `??`（未见证据）。

**为什么是投影而不是全量**：全量 payload 里的 `latestAssistantMessage.text` 是不设上限的（子线回报常达 800–1500 字），7 条线一轮就能吃掉几 KB 到几十 KB，正是 F9 的燃料。投影把每轮成本压到约 3.5KB 上限且**可预测**。broker 需要某条线的全文时，用 `codex_app__read_thread` 单独取——**默认有界、按需全量**。

### 3.5 自检：静默退化 → 响亮报错

`ledger.py sync` 必须校验最近一次 `wait_threads` 的调用与输出：

| 判据 | 不符时的报错 |
| --- | --- |
| 调用 arguments 里 `timeoutMs >= 180000` | `timeoutMs <n> < 180000` |
| 输出可解析为 JSON 且 `v == 1` | `projection missing or wrong version` |
| 输出含 `n` 与 `polls` 两个键 | `projection shape altered (missing <key>)` |
| `n` == registry 中 **children** 数量 | `targets <n> != registry children <m>` |
| `polls` 每个元素含 `id` / `status` / `turn` 四个键中至少 `id` 与 `status` | `poll entry shape altered` |

任一不符 → 打印 `ROUND INVALID: poll snippet altered (<原因>)`，拒绝本轮合并，`invalid_rounds` 计数 +1，退出码 1。

> 这条是整个设计里最重要的单点。上一轮最贵的地方不是它退化了，是**它退化得毫无声音**，烧了 3 小时没人知道。
>
> 注意校验判据的选择：**校验"你有没有把数据给我"，而不是校验"你的源码长得像不像"**。源码形态可以有无数种等价写法，而投影的 shape 是唯一的、可判定的。上一轮的退化终点 `text({pollCount:0})` 会被第 2、3 条判据当场拦下。

### 3.5.1 payload 从哪读

`ledger.py sync` 读主控自己的 rollout jsonl，抽取最近一次 `wait_threads` exec 的输出（即上面那个投影）。

- 主控的 session id 来自 registry 的 `controller.current_session_id`。
- 路径：`~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<ISO时间戳>-<session-id>.jsonl`，按 session id 递归搜索定位。
- **按 byte offset 增量读**，offset 持久化在运行时目录。

保留的收益（初版设计里唯一站得住的那条）：**解释逻辑住在磁盘文件里，模型改不了**——对冲 F5。停滞计数、状态合并、seam 归属检查全部在 `ledger.py`，模型只读它输出的紧凑摘要。

### 3.6 wake.reason 的语义（必须写进 SKILL.md）

- `inactiveStatus` = **有线程闲着**（`notLoaded`），它会让 `wait_threads` 立即返回。**这是"该派活"的信号，不是"没有变化"。** 上一轮出现 468 次，被当成了后者。
- `turnCompleted` = 某线完成了一个 turn，有新内容可读。
- `actionableStatus` = 需要动作。
- 无 wake 且 `polls` 为空 = 真的没有变化。

`ledger.py sync` 输出的摘要必须把 `inactiveStatus` 的 node 单独归入 `idle_nodes[]`，与 `no_change` 区分开。

## 4. 三个角色

### 4.1 公共段（三角色共享）

**任务分工**：impl / investigate 优先 `/call-grok`；review 走 `do-review` 路由到 `skills/reviews/` 的四条 track（`code-review` / `standards-review` / `spec-review` / `safety-review`）；验收由 session 自己做（`verification-before-completion`）。

**为什么这条是硬提示**：上一轮 compaction 次数为 主控 32 / checkout 30 / inventory 22 / customer 18 / catalog 18，impl 与 investigate 的过程占了这些 context 的绝大部分。`/call-grok` 是独立 CLI 进程，只回收结论——**这是对 F9 最省事的对冲**。review 不外包是因为它需要吃本 session 的上下文才能判断；验收同理。

**反面证据**：上一轮 broker 开头 1.5 小时自己 `spawn_agent` 开了 `review_code` / `review_standards` / `review_spec` / `review_safety` / `closure_*`——这些是 `skills/reviews/` 四条 track 的克隆。broker 不该自己造审计。

### 4.2 Role A · 任务包子 thread

**使命与方法完全不变**：`/impl-package` 6 步主流程，执行阶段 `dev-with-track` + `subagent-driven-development`。

role 段开头必须写明：*"你的使命是完成任务包，方式由 `/impl-package` 定义。本段只规定你什么时候必须跟 broker 说话，不改变你的开发方式。"*

上报边界（沿用上一轮 goal 原文，这条本来就是对的）：非 seam / 共享基座的问题优先自己完成；确认是共享的，才上报给 broker 转给 Foundation。

调度接口：H1、H2。

### 4.3 Role B · Foundation 子 thread

**使命**：产出 seam。没有自己的任务包，由 broker 指派。

**硬规则**：**"保持待命"对本角色是非法指令。** 空闲时的合法动作只有两个——向 broker 要下一个 seam 任务，或报告"本线 seam 已交付 + artifact 指针"。

> 依据：上一轮 02:48:43 broker 主动命令 F5 待命（"仅在出现可消费 Customer/Inventory/Checkout seam 时继续"），F5 此后 2 小时零产出。Foundation 是 seam 的生产者，让生产者等消费者就是把环闭上（F2）。

交付即在 `seams.jsonl` 登记 `seam_id` + `consumers` + `artifact`。

### 4.4 Role C · 主控 thread

**使命**：让整体推进。不直接写业务代码，但——**seam 缺失是它的待办，不是外部阻塞。**

> 依据：上一轮 04:47:18 broker 自述"当前阻塞来自缺失的跨域上游契约……而不是未调度"，把自己的活归类成了外部阻塞（F7）。而 `create_thread` 派新 Foundation 线这条路全程可用且有效（17/17 成功，F5/F6 产出 63/56 个 commit），它只是被停用了——02:14 之后 5.5 小时一次没派。

硬规则：H3（停滞二选一 + pending 决策立即上报）、H4 登记、不自己做审计。

## 5. 账本 schema

运行时目录：`%TEMP%\codex-thread-broker\<coordination_id>\`
routing registry 仍是同级的 `%TEMP%\codex-thread-broker\<coordination_id>.json`，由 `owner-thread-broker` 管，**本设计不改动它**（它 13.75 小时零串线，是上一轮唯一完全没出问题的部件）。

三个 append-only jsonl。字段一次写全，第一轮不迁移。

### progress.jsonl

```json
{"ts":"2026-08-01T04:48:07+02:00","round":412,"node":"catalog",
 "head":"f69a8b73","state":"awaiting_seam",
 "waiting_on":["seam:order_core_writer"],
 "last_report_ts":"2026-08-01T04:48:07+02:00",
 "note":"T1/T2/T3/T5 BLOCKED"}
```

`state` 枚举：`working` / `awaiting_seam` / `awaiting_owner` / `done`。

### seams.jsonl

```json
{"ts":"...","seam_id":"order_core_writer","producer":"f6_order_core",
 "consumers":["inventory","checkout"],"status":"assigned",
 "artifact":null}
```

`status` 枚举：`assigned` / `delivered`。`artifact` 形如 `commit:800521e8`。

### decisions.jsonl

```json
{"ts":"...","decision_id":"freeze_order_core_ownership",
 "raised_by":"f6_order_core","blocks":["inventory","checkout","f6_order_core"],
 "question":"...","status":"pending","answer":null}
```

## 6. `scripts/ledger.py` 接口契约

纯标准库 Python 3，Windows 优先，不依赖第三方包。所有时间输出为本地时区。

| 子命令 | 行为 |
| --- | --- |
| `init --coordination-id <id>` | 建运行时目录与三个空 jsonl；已存在则幂等返回 |
| `sync --coordination-id <id> --round <n>` | 定位主控 rollout（按 registry 的 `controller.current_session_id`），**按 byte offset 增量读**，抽最近一次 `wait_threads` 的完整输出；跑 §3.5 自检；合并进 `progress.jsonl`；打印决策就绪摘要 |
| `report --coordination-id <id> --node <n> --state <s> [--head H] [--waiting-on ...] [--note ...]` | 子线写自己的 progress 行 |
| `seam --coordination-id <id> --seam-id <s> --producer <p> [--consumers ...] [--deliver <artifact>]` | 登记/交付 seam |
| `decide --coordination-id <id> --raise <decision-id> --by <node> --blocks ... --question ...` / `--answer <decision-id> --text ...` | owner 决策队列 |
| `stall-check --coordination-id <id>` | 连续 N 轮（默认 3）所有 node 的 `head` 无变化 → 退出码 2 并打印 `MUST_ACT`；有 pending decision → 退出码 3 并打印 `MUST_ESCALATE`；否则 0 |

`sync` 的决策就绪摘要格式（给 broker 读的，必须紧凑）：

```
ROUND 412  valid=yes  offset=51203941
idle_nodes:      f5_catalog, foundation          <- inactiveStatus，该派活
changed_nodes:   catalog(f69a8b73 <- 71f19b74)
unchanged:       customer, checkout, inventory, f6_order_core
pending_decisions: 1  (freeze_order_core_ownership, raised_by=f6_order_core, blocks=3)
stall_streak:    0/3
seams_unowned:   0        # 阶段1 仅报数，阶段2 阻断
```

### 6.1 待探针项（实现前必须先答）

**rollout 写入是否实时？** 具体问：在同一个 turn 内，前一个 exec 的 `custom_tool_call_output` 是否在下一个 exec 启动前就已 flush 到 jsonl 文件？

- 若是 → `sync` 直接读即可。
- 若否（有 flush 延迟）→ `sync` 需要一个有界重试（如 3 次 × 2 秒），并在超时后打印 `SYNC STALE: rollout not flushed`，把它当成一次 invalid round 而不是静默用旧数据。

探针方法：在一个 codex 会话内，先 exec 打印一个唯一 marker，紧接着 exec 用 shell 去自己的 rollout 文件里 grep 这个 marker，看能否命中。

## 7. 目录与迁移

```
skills/thread-harness/
  SKILL.md                       # 入口地图 + 三个 role 段 + 公共提示
  owner-thread-broker/           # 从 skills/ 整体搬入，职责与 skill name 均不变
  references/
    design-notes.md              # 本文件
    poll-contract.md             # §3 的可复制版本，供 broker 直接引用
    ledger-schema.md             # §5 的可复制版本
  scripts/
    ledger.py
  agents/openai.yaml
```

搬迁安全性依据：`impl-package` 已确立此惯例——"所有阶段执行器都递归聚合在本目录下……物理位于本目录下但保留公共 skill name；调用方按名称路由，不依赖旧的根目录路径"。因此 `$owner-thread-broker` 引用不会断。

**与 `skills/codex-harness` 的关系**：那是纯脚本 runner 路线的 POC（`disable-model-invocation: true`），与本 harness 是两条路线。本轮不合并、不改动它。是否最终吸收，等第一轮跑完再定。

## 8. 第一轮的读数（这是实验，不是"再试试"）

| # | 读数 | 基线（上一轮） |
| --- | --- | --- |
| 1 | `ROUND INVALID` 计数 | 无此机制；实际发生了 158 轮无声退化 |
| 2 | 停滞计数器触发后，模型选了 (a) 还是 (b)，**还是绕过输出第三种** | 输出了 104 次"本轮 loop 检查完成" |
| 3 | 各线 compaction 次数 | 主控 32 / checkout 30 / inventory 22 / customer 18 / catalog 18 |
| 4 | 零推送的线是否开始推送 | 7 条里 5 条全程零推送 |
| 5 | 无归属 seam 数量（决定 H4 校验值不值得开） | 未测量；环由此形成 |

**读数 2 是最关键的。** 整套设计里风险最高且完全未验证的假设是：模型在 compaction 每 12 分钟一次的条件下能不能守住硬规则。若守不住，方向要换成"把 broker 拆成短生命周期的多轮 session"，而不是继续加固一条 13 小时长 thread。
