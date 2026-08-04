# Thread Harness · 历史设计记录

本文件保留历史设计背景与事故复盘，**不是运行规范，也不是当前实现权威**。当前行为以 `SKILL.md`、角色页、`poll-contract.md`、`ledger-schema.md` 与 `session-dispatch.md` 为准；不要从本文件复制运行命令或模板。

证据来源：2026-08-01 对 coordination_id `remove-lark-runtime` 的调度复盘（1 主控 + 7 子线，13.75 小时，全线死锁）。完整报告见 `D:\CodeSpace\agent-eval-20260801\REPORT.md`，findings 编号 F1–F10 在下文被直接引用。

---

## 1. 要解决的问题（一句话）

上一轮失败**不是**模型犯糊涂、不是额度耗尽、不是缺授权、不是崩溃。是**没有任何组件对"整体是否在推进"负责**：broker 把自己定义成不写代码的调度者，子线把自己定义成"没有 exact artifact 就待命"，于是产出契约的责任落进缝隙；唯一能发现这件事的人（Owner）睡着了 8 小时。

所以本 harness 的设计目标不是"让它跑得更久"，而是**让它卡住时会叫人，且尽量少地卡住**。

## 2. 四条硬规则（第一轮强制）

其余一切都是启发式与意图偏置。硬的只有这四条，且每条都对应一个已发生的失效。

| # | 硬规则 | 对应 finding |
| --- | --- | --- |
| H1 | **回报触发条件**：任一 thread 在 turn 结束前，若 ①`head` 变了 ②状态从 working 转为 waiting ③产生 owner 级阻塞——三者之一成立，必须发送结构化 H1 envelope 回 broker；child 不直接写 ledger | F3：7 条线里 5 条从不主动回报，F6 唯一能解环的 Owner 请求因此永远没送达 |
| H2 | **账本字段与写入时机**：controller 验证 H1 的 registry source session 与 HEAD 后代关系后，代 child append；字段按 §5 schema | F9：全局进度只活在 context 里，末期每 12 分钟被 compaction 清洗一次 |
| H3 | **停滞上限 + 二选一**：连续 5 轮所有 node 的 git HEAD 无变化，broker 必须二选一——(a) 派发新工作（含 create_thread 开新 Platform 线），(b) 向 Owner 报告并结束 loop（即 `act --halt --reason`）。**禁止第三种输出。** 从第 3 轮起若仍有 active / working node，每轮必须直接 `read_thread`；只有具体且最新的执行心跳可将 streak 归零。另：`decisions.jsonl` 有尚未上报的 `pending` 项时立即上报，不进入下一轮；已上报但仍 pending 的决策不再豁免停滞判定 | F1：Owner 是唯一解卡装置；F7：broker 把自己的待办归类成外部阻塞。上一轮它输出了 104 次"本轮 loop 检查完成" |

**H3 的 `MUST_ACT` 准确含义是「既没有 committed progress，也没有在阈值前确认到 fresh heartbeat」，不是「整体停止」。** 一条线可能正在活跃工作、只是还没 commit，所以：

- Git HEAD 仍是每轮的廉价主信号，不增加每轮 message cache，也不改变 append-only ledger schema。
- 从 `3/5` 起每轮付一次语义读取成本：对 active / working node 直接 `read_thread`。具体的新测试、finding closure、patch 或正在执行的新命令算 heartbeat；重复等待文案、旧报告和单纯 active 状态不算。
- fresh heartbeat 通过 `ledger.py heartbeat` 在 `sync-state.json` 写 reset marker，将 streak 归零；全员 idle 时不重置，按 `idle_nodes` 派活。
- 到 `5/5` 后不再允许 heartbeat 绕过 `MUST_ACT`，仍执行二选一。
- 已通过 `act --escalate` 上报且 `ts` 不早于最新 raise 的 pending decision 只作为 `pending_escalated` 显示，不再屏蔽 `MUST_ACT`。
| H4 | **seam 必须登记生产者**：任何 `awaiting_seam` 都要指向一个 `seam_id`，该 seam 必须由 controller 在 `seams.jsonl` 里登记一条带 `producer` 的记录 | F2/F7：环的成因是"跨域上游契约"是个没有归属的名词 |

H4 的分阶段：**当前只登记不校验**，脚本仅在 `sync` 摘要报 `seams_unowned` 计数。**H4 是给 agent 的行为规则，不是脚本里的门禁。**

阶段 2（`waiting_on` 指向的 seam 查不到 producer → 报错阻断）**暂不开启**。依据：读数 5 当初的定义就是「决定 H4 校验值不值得开」，2026-08-02 那一轮回来是 **0**——7 个 seam 全部带 producer 交付。此时开阻断拦不到任何东西，却新增一类误伤（把合法轮次判死）。**读数 5 非零时再开。** schema 一次写全，不迁移。

### 2.1 贯穿性原则：地面真相优先于账本纪律

**凡是能从 git、rollout 等客观来源直接读到的事实，就不要依赖模型主动上报。**

这条来自 2026-08-01 的外部评审。它指出的最严重缺陷是：`head` 字段一度混用 Desktop 的 `latestTurn.id` 与 git SHA，于是一条线只要产生一个新 turn（哪怕什么都没做）停滞计数就被重置——**H3 正是要抓"只出 turn 不出活"，却被这个混用废掉了。**

修法不是要求模型更认真地上报，而是换数据源：

| 事实 | 错误做法（依赖纪律） | 现在的做法（地面真相） |
| --- | --- | --- |
| 某条线有没有真的产出 | 读 Desktop turn id | `git -C <worktree> rev-parse HEAD`，worktree 来自 registry |
| 无 commit 时是否仍有真实执行心跳 | 每轮缓存消息或只看 active 状态 | 从 `3/5` 起直接 `read_thread`；具体新进展才 reset |
| broker 有没有真的派活 | 让 broker 自己记 dispatch 行 | `sync` 读 rollout 时数 `send_message_to_thread` / `create_thread` 调用 |
| 轮询是否覆盖了全部子线 | 信任投影里模型打印的 `n` | 从调用 arguments 解析实际 ids，与 registry children 做**集合**比对 |
| 子线上报的 `head` 是不是真的 | 子线自己跑 `report --head`，没有任何东西能证伪 | 子线只发 H1 envelope，controller 用 `validate_report_source` 校验：source session 必须等于 registry 里该 node 的 current session、head 必须是完整 40 位 SHA、必须是上一条账本 head 的后代、且必须在该 worktree 的当前历史上 |

判断规则：**一个事实如果模型有动机漏报或美化，就必须找到不经模型的来源；找不到的，才退回账本纪律并接受它可能失效。**

子线的 `state` / `waiting_on` 属于后者——只有子线自己知道它在等什么，没有客观来源。所以这两个字段仍靠 H1 上报，controller 验证后写入；代价是 `sync` **不得覆盖**它们（poll 行只写 poll 能证明的东西）。

## 3. 轮询契约（poll contract）

### 3.1 已核实的运行时约束

对上一轮 4016 次 exec 调用的解析结论，实现时不要挑战这些：

- exec 是沙箱 JS，**无模块加载**：`require` / `eval` / `import` / `new Function` 出现次数均为 **0**。
- `tools.codex_app__*` 绑定**只存在于 exec 的 JS 里**，不是一等 function_call 工具，`tools.shell_command` 够不着。
- 可用绑定全集（观测到的）：`shell_command`、`apply_patch`、`update_plan`、`web__run`、`codex_app__{wait_threads, send_message_to_thread, read_thread, read_thread_terminal, list_threads, create_thread, set_thread_title, list_projects, load_workspace_dependencies, fork_thread}`。
- **结论：无法让模型"执行一个文件"。那段 JS 必须由模型每轮亲手敲出来。**

`fork_thread` 本 harness 不使用。

补充的平台约束（2026-08-01 复审已核对工具声明原文）：

- **`wait_threads` 单次最多 8 个 targets。** 声明原文：*"Wait for the first of up to eight Codex threads to complete or need attention."* 本 harness 假设 children ≤ 8（上一轮是 7）。超过 8 需要稳定分片 + 跨片合并，**本轮明确不做**，见 §9.2。
- **`create_thread` 不是无条件的自授权动作。** 声明原文：*"Create a separate task only when the user explicitly asks for a new task."*
  推论很重要：**授权必须来自 Owner 本人在 goal 或对话里给出，controller 自己写一段"允许 create_thread"不构成自授权。** 主控 goal 模板里那句授权必须是你亲手放进去的，不能由上一任 controller 代写进接手 prompt。
- **`create_thread` 无法给子线设置持久 goal。** 它的参数只有 prompt、target、可选 model/thinking；`create_goal` 只作用于当前 task，没有目标 thread 参数。所以 §7 那条"goal 免疫 compaction"的优势**只有主控享有**，子线的 H1/H2 会随 compaction 流失。
  这是平台能力缺口，不是设计选择。缓解手段只能是主控用 `never_reported` / `stale_reports` 检测漏报，而不是相信子线记得。Owner 手动进 child 设 goal 是 UI 上做得到的，**但 2026-08-01 实测证明这条路走不通**：child 是被动接受调度的，goal 每轮推它「朝目标推进」，而它此刻正确的状态往往是等派活，两股力拉扯半小时后进入死循环，撤掉后影响不大。只有主控有 goal；子线角色规则随 compaction 流失这件事，改由交接链路兜底（主控从 `never_reported` / `stale_reports` / `session_age_h` 看出异常并触发自交接）。

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

### 3.4 固定 JS 片段

**片段正文与字段清单只存在于 [poll-contract.md](poll-contract.md)**，本页不复制第二份——它随自检判据一起演进，两处必然漂移。

五条不可动摇的性质：`timeoutMs` 固定为平台允许的 `120000`；`targets` 等于 ledger 机械推导出的 wait 集合：优先为 **runnable watch-set**，为空时回退为全部 active children，不含 controller 自己；HEAD 采集仍覆盖全部 active children；输出是那个固定投影，字段一个不能少；`txt` 截断到 500 字符。`awaiting_seam`、`awaiting_owner`、`done` 不进入正常阻塞 wait，controller dispatch 后的 producer 重新进入 watch-set；空集合只改变目标集合，不取消 120 秒 poll。

**语法都是实跑验证过的**（可选链 `?.`、`(x||[])`、`String.slice`），刻意不用 `??`（未见证据）。

**为什么是投影而不是全量**：全量 payload 里的 `latestAssistantMessage.text` 不设上限（子线回报常达 800–1500 字），7 条线一轮就能吃掉几 KB 到几十 KB，正是 F9 的燃料。投影把每轮成本压到约 3.5KB 上限且**可预测**。需要某条线全文时用 `codex_app__read_thread` 单独取——**默认有界、按需全量**。

### 3.5 自检：静默退化 → 响亮报错

`ledger.py sync` 必须校验最近一次 `wait_threads` 的调用与输出：

| 判据 | 不符时的报错 |
| --- | --- |
| 调用 source（legacy `arguments` / modern `input`）里 `timeoutMs == 120000` | `timeoutMs <n> != 120000` |
| 输出可解析为 JSON 且 `v == 1` | `projection missing or wrong version` |
| 输出含 `n` 与 `polls` 两个键 | `projection shape altered (missing <key>)` |
| 实际 ids 集合等于 ledger 推导的 wait 集合（runnable 非空时为 runnable，否则为全部 active child） | `targets mismatch (missing=<...>, unexpected=<...>)` |
| `polls` 每个元素含 `id` / `status` / `turn` / `turnStatus` / `txt` 五个键 | `poll entry shape altered` |

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

`ledger.py sync` 输出的摘要必须把 `inactiveStatus` 的 node 单独归入 `idle_nodes[]`，与 `no_change` 区分开；同时输出 `poll_targets`，让固定 wait 的目标集合可审计。

## 4. 三个角色

### 4.1 公共段（三角色共享）

**任务分工**：impl / investigate 优先 `/call-grok`；review 走 `do-review` 路由到 `skills/reviews/` 的四条 track（`code-review` / `standards-review` / `spec-review` / `safety-review`）；验收由 session 自己做（`verification-before-completion`）。

**为什么这条是硬提示**：上一轮 compaction 次数为 主控 32 / checkout 30 / inventory 22 / customer 18 / catalog 18，impl 与 investigate 的过程占了这些 context 的绝大部分。`/call-grok` 是独立 CLI 进程，只回收结论——**这是对 F9 最省事的对冲**。review 不外包是因为它需要吃本 session 的上下文才能判断；验收同理。

**反面证据**：上一轮 broker 开头 1.5 小时自己 `spawn_agent` 开了 `review_code` / `review_standards` / `review_spec` / `review_safety` / `closure_*`——这些是 `skills/reviews/` 四条 track 的克隆。broker 不该自己造审计。

### 4.2 Role A · 任务包子 thread

**使命与方法完全不变**：`/impl-package` 6 步主流程，执行阶段 `dev-with-track` + `subagent-driven-development`。

role 段开头必须写明：*"你的使命是完成任务包，方式由 `/impl-package` 定义。本段只规定你什么时候必须跟 broker 说话，不改变你的开发方式。"*

上报边界（沿用上一轮 goal 原文，这条本来就是对的）：非 seam / 共享基座的问题优先自己完成；确认是共享的，才上报给 broker 转给 Platform。

调度接口：H1、H2。

### 4.3 Role B · Platform 子 thread

**使命**：产出 seam。没有自己的任务包，由 broker 指派。

**硬规则**：**"保持待命"对本角色是非法指令。** 空闲时的合法动作只有两个——向 broker 要下一个 seam 任务，或报告"本线 seam 已交付 + artifact 指针"。

> 依据：上一轮 02:48:43 broker 主动命令 F5 待命（"仅在出现可消费 Customer/Inventory/Checkout seam 时继续"），F5 此后 2 小时零产出。Platform 是 seam 的生产者，让生产者等消费者就是把环闭上（F2）。

交付即在 `seams.jsonl` 登记 `seam_id` + `consumers` + `artifact`。

### 4.4 Role C · 主控 thread

**使命**：让整体推进。不直接写业务代码，但——**seam 缺失是它的待办，不是外部阻塞。**

> 依据：上一轮 04:47:18 broker 自述"当前阻塞来自缺失的跨域上游契约……而不是未调度"，把自己的活归类成了外部阻塞（F7）。而 `create_thread` 派新 Platform 线这条路全程可用且有效（17/17 成功，F5/F6 产出 63/56 个 commit），它只是被停用了——02:14 之后 5.5 小时一次没派。

硬规则：H3（停滞二选一 + 尚未上报的 pending 决策立即上报）、H4 登记、不自己做审计。

### 4.5 为什么 session 交接分两阶段

一次性把 registration 和任务一起发给 child，会出现一个无法消除的竞速：child 第一个 turn 就去读 registry，而 controller 此时还没拿到新 `threadId`、registry 里还是旧值，于是 child 报 mismatch。2026-08-02 实跑里这类 mismatch 出现过，且需要 Owner 手工介入才解开。

拆成两阶段消除了这个窗口：第一阶段 child 只核对锚点然后停住，controller 在这个停顿里更新 registry，第二阶段才真正开工。

**为什么替换由退休 session 自己发起 `create_thread`**（Role A / Role C）：只有它知道自己的 WIP 边界、已获证据与单一 Next Action，这些必须先写回恢复权威再交接才是原子的；主控代劳就得先把这些吸进自己的上下文，而它的上下文是最稀缺的。Role B 例外——Platform 没有自述状态，恢复权威是主控写的 assignment card，自交接没有意义。

**为什么不另造中间态 handoff 卡片**：`$handoff-to-new-session` 原文即 *"a compact, complete initial prompt, **not a temporary handoff document**"*。交接材料就是 child 的首条 prompt 本身；再写一份临时卡片让主控转手，既违反被引用 skill 的约定，也把一个原子动作拆成两步。

### 4.6 goal 的准入判据

goal 只保留规避后会让 agent 少做工作的硬规则，以及本 coordination 专有的目标、结束判据、授权和排除项。动态进展从 registry、ledger 与任务包读取；跨 coordination 仍成立的纠正写回对应 skill，不重复塞进 goal。

**为什么只在轮边界交接**：固定 poll 的 ids 是在轮次开头内联进 JS 的，轮中交接会让 registry 变而本轮 ids 不变，`sync` 的集合比对判 `ROUND INVALID`，白白作废一轮并污染读数 1。不放宽 `sync` 校验——它是整个设计里最重要的单点。

**为什么档位要显式指定**：实测 `create_thread` 时显式给 `model` / `thinking` 是生效的，不给会落到平台默认。但它只决定起点——session 跑过多轮后档位会被平台自动降到 terra，这是 Codex 的机制，本 harness 不对抗它。后果是长跑的主控逐渐变钝，而主控读不到自己的 `turn_context`，所以 `session_age_h` 是唯一可用的代理信号。

## 5. 账本 schema

正式运行时目录：由 `--registry <absolute-registry-json>` 的 registry sibling 与其中 `coordination_id` 推导；旧的 `THREAD_HARNESS_BROKER_ROOT` + `--coordination-id` 兼容路径仍可用。
routing registry 由 `owner-thread-broker` 管，**本设计不改动其路由职责**（它 13.75 小时零串线，是上一轮唯一完全没出问题的部件）。

四个 append-only JSONL。字段一次写全，第一轮不迁移；controller 是唯一写入者，child 只发送 H1 envelope。

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
 "decision_instance_id":"<uuid>",
 "raised_by":"f6_order_core","blocks":["inventory","checkout","f6_order_core"],
 "question":"...","status":"pending","answer":null}
```

## 6. `scripts/ledger.py` 接口契约

纯标准库 Python 3，Windows 优先，不依赖第三方包。所有时间输出为本地时区。

| 子命令 | 行为 |
| --- | --- |
| `init --registry <absolute-json>` | 建 registry sibling/coordination_id 运行时目录与四个空 jsonl；已存在则幂等返回 |
| `sync --registry <absolute-json> --round <n>` | 定位主控 rollout（按 registry 的 `controller.current_session_id`），**按 byte offset 增量读**，按 ledger 推导 wait 集合校验固定 wait（runnable 为空时回退到全部 active child），同时为全部 active children 采集 HEAD；抽最近一次 `wait_threads` 的完整输出；跑 §3.5 自检；合并进 `progress.jsonl`；打印决策就绪摘要 |
| `route --registry <absolute-json> --node <n> --new-session <session> [--expect-current <session>]` | 只更新 registry 中一个 node 的 session 路由：旧 session 进入 `previous_session_ids`，刷新 `updated_at`；校验乐观锁与全 registry 当前 session 冲突；不写 JSONL 或 `sync-state.json` |
| `report --registry <absolute-json> --node <n> --source-session <session> --state <s> [--head H] [--waiting-on ...] [--note ...]` | controller 验证 H1 source session 与 HEAD 后代后写 progress 行；旧 `--coordination-id` 调用兼容 |
| `seam --registry <absolute-json> --seam-id <s> --producer <p> [--consumers ...] [--deliver <artifact>]` | controller 登记/交付 seam；未知 producer/consumer 是用法错误，退出 `64` |
| `decide --registry <absolute-json> --raise <decision-id> --by <node> --blocks ... --question ...` / `--answer <decision-id> --text ...` | controller/Owner 决策队列；每次 raise 生成 `decision_instance_id`，answer/escalate 绑定当前 instance |
| `heartbeat --registry <absolute-json> --node <n> --evidence <text>` | 仅在 `3/5` 或 `4/5` 且 controller 已直接读 thread 确认 fresh heartbeat 后使用；只写 `sync-state.json` reset marker，不写 JSONL |
| `preflight --registry <absolute-json>` | 开跑前只读校验 registry：worktree 存在且可读 HEAD、active child 无共享 worktree/branch、registry branch 与实际 checkout 一致、active `children <= 8`、active session id 不重复、controller rollout 可定位、运行时已 `init`。完整性失败退 `6`，其他阻断退 `5` |
| `stall-check --registry <absolute-json>` | 最近 halt 的 `halt_poll_seq` 未被更大的有效 poll seq 超过 → 退出码 4 并打印 `HALTED`；连续 N 轮（默认 5）所有 node 的 `head` 无变化 → 退出码 2 并打印 `MUST_ACT`；从 `3/5` 起、到 `5/5` 前 → 退出码 0 并打印 `CHECK_HEARTBEAT`；有尚未上报的 pending decision → 退出码 3 并打印 `MUST_ESCALATE`；否则 0 |

止血版运行时约束：四个 JSONL mutation 都在 coordination 级跨进程写锁内执行；每次 append 以完整 UTF-8 bytes 写入并 flush/fsync。每个新 mutation batch 在同一锁内从 `sync-state.json` 与现有 JSONL 的最大值中恢复并领取单调 `ledger_seq`，用来消除同秒 report/dispatch 的顺序歧义；legacy 行缺失该字段时才回退到时间戳判断，字段存在但类型非法会 fail-closed。扫描到任一坏行时先打印 `LEDGER INTEGRITY FAILED: <file>:<line> <reason>`，`sync`、`stall-check`、`report`、`seam`、`decide`、`act`、`heartbeat`、`preflight` 停止并返回 `6`；`status` 仍输出诊断但也返回 `6`，不把 partial rows 当作可信 current state。此锁不提供跨文件事务原子性。

`sync` 的决策就绪摘要格式（给 broker 读的，必须紧凑）：

```
ROUND 412  valid=yes  offset=51203941
poll_targets:    f5_catalog, checkout, inventory, f6_order_core
idle_nodes:      f5_catalog, foundation          <- inactiveStatus，该派活
changed_nodes:   catalog(f69a8b73 <- 71f19b74)
unchanged:       customer, checkout, inventory, f6_order_core
session_age_h:   f6_order_core=7.2, checkout=5.8, inventory=2.1
pending_decisions: 1  (freeze_order_core_ownership, raised_by=f6_order_core, blocks=3)
stall_streak:    0/5
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

第一轮新增一个读数（来自外部评审）：

| # | 读数 | 用途 |
| --- | --- | --- |
| 6 | `dispatches_since_progress` —— 派了多少次消息但没有任何 node 的 git HEAD 变化 | 判断 H3 的选项 (a) 是否被"派一次 audit"伪装。见 §9 |

## 9. 明确不做（本轮），及理由

写下来是为了避免下一轮有人重新捡起来当成遗漏。

### 9.1 H3 选项 (a) 的完整机读定义

评审指出："派发新工作"没有可验证的 deliverable 要求，所以 broker 可以用「已派 Platform 做一次增量 readiness 检查；若无新 artifact 则保持等待」蒙混过关——形式上像 (a)，实质是等待的包装版。**这个批评是对的**，上一轮确实反复出现过这种行为。

完整解法需要定义：deliverable 与验收条件、producer 必须转 `working`、audit/sidecar 不得计入、下一轮验证 assignment 真的进入执行。这是一整套语义，属于阶段 2 的 I1（依赖必须有 owner）范畴。

**本轮做最小版：留痕，不验证。** `MUST_ACT` 之后 broker 必须调 `ledger.py act`；`--dispatch` 要求填 `seam_id` + `producer` + `deliverable` 三个字段，缺一个就退 64；选 (b) 结束 loop 时用 `--halt --reason`，缺 `reason` 也退 64。

它证明不了派发是真的，但**逼你说出派给谁、要造什么**——"已派 Platform 做一次增量 readiness 检查"填不进这三个字段。`stall-check` 会报 `last_must_act_answered: yes|no`，只报告不阻断。

配套的测量：`dispatches_since_progress` 从 rollout 数派发次数，且**只被 code 级 HEAD 推进清零**（docs-only commit 不清零，见下）。这个数持续增长而 code 不动，就是"在派活但没派出成果"的直接证据。

> docs/code 之分是必须的：上一轮七条分支里**六条的终态 commit 都是 `docs(...)` 记录阻塞**。如果不区分，任何一次"提交一份说明我被阻塞的文档"都会把计数清零，读数 6 直接失去意义。分类用 `git show --name-only` 看触及路径，是客观判据不是启发式。
>
> 但 `stall_streak` 本轮**不**收紧——任何 HEAD 变化仍算推进。收紧要等看过真实数据，否则容易把合法文档工作误杀。

理由：完整的机读判据（assignment 生命周期、验收条件、下一轮执行证明）设计错了比没有更糟——会把合法的探索性派发也堵死，逼模型学会绕过判据本身。先用一轮真实数据看清"伪装派活"占多大比例。

### 9.2 children > 8 的分片

`wait_threads` 单次上限 8 个 target。当前场景 7 条线够用。分片需要稳定的分组规则加跨片轮次合并，会显著复杂化 `sync` 的增量语义。**已知限制，超过 8 条线时本 harness 不适用。**

### 9.3 子线的持久 goal 与 turn-finalizer hook

`create_thread` 没有 goal 参数，平台也没有 turn 结束时自动写账本的 hook。所以子线的 H1 无法获得主控那样的 compaction 免疫；子线发送 envelope，controller 单写 ledger。

**这是平台能力缺口，不是可以靠设计补上的东西。** 能做的只有让主控检测漏报（`never_reported` / `last_report_ts`），把"子线忘了上报"从静默失效变成可见信号。第一轮读数 4 就是量这个的。

**Owner 手动给 child 设 goal 这条路已经试过并否决。** 2026-08-01 实测：child 是被动接受调度的，goal 每轮推它「朝目标推进」，而它此刻正确的状态往往是等主控派活，两股力拉扯，半小时后进入死循环；撤掉之后影响不大。加上 child 有多条、每次交接都要重贴，成本不成比例。

**结论：只有主控有 goal。** 子线角色规则随 compaction 流失这件事，改由交接链路兜底——主控从 `never_reported` / `stale_reports` / `session_age_h` 看出某条线不对劲，触发自交接，新 session 重新读 skill。**变蠢是可恢复的，失控才不可恢复。**

### 9.4 `polls: []` 不判为退化

空的 `polls` 数组在"真的没有变化"时是合法返回，无法与"模型偷懒不打印"区分。**接受这个假阴性**——强行拒绝会在正常无变化的轮次里持续误报，反而训练 broker 忽略 `ROUND INVALID`。

缓解：投影里加了 `timedOut` 字段，可以把"等满 120 秒确实没变化"与"被唤醒却没内容"分开，后者更可疑。复审提到工具声明暗示 timeout 返回时会带全部 target 的 compact progress，但这一点未经实测确认，所以不作为判据，只作为读数。

### 9.5 `validate_call` 的 decoy 绕过 —— 结构上封不死

复审构造了一个能通过全部自检的伪造：放一个未使用的正确 `const ids = [...]`，实际却传 `targets: []` 和 `timeoutMs: 1000`。

**这一层封不死，原因是结构性的**：rollout 只记录 exec 打印的内容（§3.3），**无法证明实际传给 `wait_threads` 的参数是什么**。任何基于源码文本的校验都能被"多写一段没用的正确代码"绕过。

不修的判断依据是威胁模型：本 harness 防的是**长跑压力下的逐步简化**（上一轮的真实退化路径：`text(r)` → `text({pollCount, wake})` → `text({pollCount})`），不是主动伪造。decoy 需要写**更多**代码而不是更少，不在退化路径上。

部分缓解：`polls[].id` 必须属于 registry children 且不重复——这能抓住返回内容与目标集合对不上的情况。

**记录它是为了：如果第一轮真的观察到 decoy 类行为，说明威胁模型判断错了，那时要换的是整个校验层的位置（比如让子线也各自记账、交叉对账），而不是继续加正则。**

### 9.6 其余已知边界

- 坏行不自动截断、重写或猜测修复；`status` 的 partial 摘要只用于诊断，返回码 `6` 才是可信信号。
- seam producer 可被后续行改写，`artifact` 是自由文本；当前 H4 只检查 ownership 是否存在，不校验交付语义。
- dispatch 计数只认存在配对 output 的 `send_message_to_thread` / `create_thread` 调用，不追踪工具调用后的业务结果。
