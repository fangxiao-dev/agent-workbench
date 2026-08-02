---
name: thread-harness
description: >
  多 thread 编排的角色定义与控制流。当一个主控 thread 需要长时间调度多条子 thread
  推进同一个目标时使用：确定自己是主控 / 任务包子线 / Foundation 子线中的哪个角色、
  什么时候必须向上回报、怎么轮询、怎么判断整体是否还在推进、卡住了怎么办。
  涉及 broker loop、wait_threads、派发任务、seam 缺失、停滞、Owner 决策上报时适用。
  线程路由（thread-id 与 topic 绑定）由本目录下的 owner-thread-broker 负责，本 skill 不重复。
---

# Thread Harness

一个主控 thread 带若干子 thread 长跑时，最容易出的不是某一步做错，而是**整体停下来了却没人发现**。本 skill 定义三个角色的边界与四条硬规则，目的只有一个：**让系统卡住时会叫人，且尽量少地卡住。**

设计依据与实测证据见 [design-notes.md](references/design-notes.md)（一次 13.75 小时全线死锁的复盘）。**先读本页，需要细节再进 references。**

## 先确定你是谁

| 你的处境 | 你的角色 | 读哪一段 |
| --- | --- | --- |
| 你有一个明确的任务包要做完 | **任务包子线** | §Role A |
| 你没有任务包，被指派去造某个共享的东西 | **Foundation 子线** | §Role B |
| 你负责调度别人、自己不写业务代码 | **主控** | §Role C |

三个角色共用同一套账本与回报契约，所以先读 §公共约定。

线程路由（谁是谁、session id 绑定）不在这里，用 `$owner-thread-broker`。它管路由，本 skill 管控制流，两者不重叠。

## 四条硬规则

只有这四条是硬的，其余全是引导。每条都对应一次真实失效。

- **H1 回报触发**：turn 结束前，若 ①`head` 变了 ②状态从 working 转为 waiting ③产生 Owner 级阻塞——三者任一成立，**必须**写账本并 `send_message_to_thread` 回主控。
- **H2 账本**：状态变更即 append，字段见 [ledger-schema.md](references/ledger-schema.md)。**不要把进度只留在自己的上下文里**，它会被 compaction 清掉。
- **H3 停滞二选一**（主控专属）：连续 5 轮所有 node 的 `head` 无变化 → 必须二选一：派发新工作，或向 Owner 报告并结束 loop。**没有第三个选项。** 从 `3/5` 起，若仍有 active / working node，每轮必须直接 `read_thread` 看最新进展；任一 thread 有具体、最新的工作心跳才可执行 `ledger.py heartbeat` 把 streak 归零。重复等待文案、旧进展或仅有 active 状态都不算心跳。全员 idle 时不重置，`idle_nodes` 仍是独立派活信号。账本里有尚未上报的 pending 决策时立即上报，不进入下一轮；已上报但仍 pending 的决策不再豁免停滞判定。
- **H4 seam 归属**：任何"我在等某个上游产物"都要指向一个 `seam_id`，且该 seam 在账本里必须有 `producer`。**等一个没人负责造的东西，是错误状态，不是阻塞状态。**

## 公共约定（三个角色都适用）

### 任务怎么分工

- **impl / investigate 优先用 `$call-grok`**：它是独立 CLI 进程，只回收结论，不吃你的上下文预算。
- **review 回到 subagent**：走 `$do-review` 路由到 `skills/reviews/` 的四条 track（code / standards / spec / safety）。**不要自己造审计 agent**——那四条已经存在了。
- **验收由你自己做**：`$verification-before-completion`，不外包。

为什么前两条分得这么开：review 和验收需要吃你本 session 的上下文才能判断，外包出去会失真；而 impl 和 investigate 的**过程**对你毫无价值，只有结论有价值——那正是最该外包的部分。上一轮各线 compaction 达 18–32 次，绝大部分上下文就是被 impl 过程占掉的。

### 一轮循环长什么样

主控每轮：敲固定 JS 片段 → `ledger.py sync` → 读摘要 → `ledger.py stall-check` → 按退出码决策。
子线每轮：干活 → 若命中 H1 触发条件则 `ledger.py report` + 回报主控。

轮询的固定片段与 `wake.reason` 语义见 [poll-contract.md](references/poll-contract.md)。**那段 JS 要原样敲，不要"优化"它。** 它打印的那个投影就是 `ledger.py` 的全部输入——**rollout 只记录你打印的内容，不记录工具的原始返回**，所以少打印一个字段，主控就永久少一份判断依据。任何简化都会被 `sync` 的自检当场拦下并作废本轮。

### 一个容易搞反的语义

`wait_threads` 返回的 `wake.reason == "inactiveStatus"` 意思是**有线程闲着**，不是"没有变化"。前者要派活，后者才是等。上一轮它出现了 468 次，被当成了后者，于是主控安静地空转了几个小时。

---

## Role A · 任务包子线

**你的使命是完成任务包，方式由 `$impl-package` 定义。本段只规定你什么时候必须跟主控说话，不改变你的开发方式。**

新建或替换 Role A session 时，使用 `$handoff-to-new-session` 的 clean local-session 能力，并按 [Role A clean-session 交接模板](references/role-a-session-dispatch.md) 分两阶段执行：source 先把 checkpoint 写回当前任务包 entry；第一阶段 child 只核对任务包 anchor；controller 更新 current routing 后，第二阶段 child 才读取 Role A 规则并继续 Next Action。`previous_session_ids` 只留在 registry 内部，不进入 child prompt，也不由 child 校验。

按 impl-package 的 6 步主流程走，执行阶段用 `$dev-with-track` + `$subagent-driven-development`。这些已经设计好了，本 skill 不复述也不覆盖。

调度接口只有两条：

- **H1**：状态变化就回报主控，不要等它来问。它拉取你的机制不可靠。
- **H2**：写账本。

上报边界（什么该自己扛、什么该往上递）：

> 非 seam / 共享基座类的问题，优先自己完成。确认是共享的东西，才上报给主控转给 Foundation。

判断"是不是共享"的启发式：如果修好它只对你这个包有意义，那是你的活；如果别的包也在等同一个东西，那是 seam。拿不准就上报并说明你的判断依据——**误报的成本远低于漏报**，上一轮的死锁就是漏报堆出来的。

### 一个反模式

当你发现"当前没有安全的独立 lane"时，**"提交一份记录我被阻塞的文档"不算产出**。它看起来像进展，实际是停滞的伪装。上一轮七条分支里六条的最后一个 commit 都是这种 `docs(...)`。

正确动作是 H1：把阻塞写成一条带 `seam_id` 的账本记录并回报主控，然后**明确说自己空了**。空闲是一个需要被调度的信号，不是一个需要被文档化的状态。

---

## Role B · Foundation 子线

**你是 seam 的生产者。**你没有自己的任务包，任务由主控指派。

**「保持待命」对你是非法指令。** 哪怕主控这样要求你，也不要照做。你空闲时只有两个合法动作：

1. 向主控要下一个 seam 任务；
2. 报告"本线 seam 已交付"，附 `seam_id` 与 artifact 指针（commit hash 之类）。

原因很直白：所有人都在等 seam，而你是造 seam 的。**让生产者去等消费者，环就闭上了。** 上一轮主控亲手让一条 Foundation 线待命，那条线此后两小时零产出，是死锁闭合的关键一步。

交付时在账本 `seams.jsonl` 登记 `seam_id` + `consumers` + `artifact`。没登记的 seam 等于没交付——下游查不到 producer，会按 H4 判成错误状态。

其余开发方式与 Role A 相同（impl-package 体系、公共约定）。

---

## Role C · 主控

**你的使命是让整体推进。你不直接写业务代码——但 seam 缺失是你的待办，不是外部阻塞。**

这是主控最容易犯的错，值得单独说清楚：当所有子线都报"我在等某个跨域上游契约"时，正确的读法不是"外部条件不具备"，而是"**我还没安排人去造它**"。你手上一直有 `create_thread` 这个动作，派一条新的 Foundation 线去造，这条路是通的。

新建或替换 Foundation session 时，不得手写一段带 `<codex_delegation>` 的 Role B prompt，也不得 fork 主控历史。必须以 `$handoff-to-new-session` 为 clean-session 基线，并按 [Foundation clean-session 派发模板](references/foundation-session-dispatch.md) 的两阶段 override 执行：第一阶段只核对 anchor；拿到新 `threadId` 后由 controller 更新 registry / assigned seam；第二阶段 child 才注册 working 并开始实现。这样既保持空白 session，也消除 child 首轮与 registry 更新的竞速。

### 每轮做什么

1. 敲 [poll-contract.md](references/poll-contract.md) 里的固定 JS 片段（`timeoutMs: 120000`，覆盖全部 node，只回一行短确认）
2. 跑 `ledger.py sync`，读那段紧凑摘要
3. 跑 `ledger.py stall-check`，按退出码走：
   - `0` `OK` → 正常，按摘要决策
   - `0` `CHECK_HEARTBEAT` → 已到 `3/5` 或 `4/5`；直接读取 active / working thread。若确认具体、最新进展，执行 `ledger.py heartbeat --node <node> --evidence "<一句话>"`；否则不重置
   - `2` `MUST_ACT` → **H3 二选一**，派发新工作用 `act --dispatch`，向 Owner 报告并结束 loop 用 `act --halt --reason`；禁止输出"继续等待"
   - `3` `MUST_ESCALATE` → 立即向 Owner 报告尚未上报的 pending 决策，并用 `act --escalate --decision-id <d>` 留痕，本轮结束
   - `4` `HALTED` → loop 已被终止，**不要继续轮询**；先向 Owner 确认再决定是否恢复

摘要里 `idle_nodes` 非空 = 有线闲着 = 该派活。这跟 `unchanged` 是两回事。heartbeat 只写 `sync-state.json` 的运行时 reset marker，不修改四个 append-only JSONL，也不要求缓存每轮 thread 消息。

### 你不做的事

- **不做审计。** 需要 review 就走 `$do-review`。上一轮主控开头 1.5 小时全在给自己造 review agent，而那些 track 仓库里本来就有。你的上下文是稀缺资源。
- **不让 Foundation 线待命。**（见 Role B）
- **不自行批准 Owner 级决策。** 授权边界与提案格式用 `$owner-thread-broker`。

### 什么时候该叫醒 Owner

`decisions.jsonl` 里出现 `pending` 就叫，不要攒。判断"这是不是 Owner 级"的启发式：如果这个决定会改变谁拥有什么、或者会产生不可逆的外部影响，那就是 Owner 的。技术选型和执行顺序是你的。

拿不准就报——上一轮有一条 Owner 级阻塞在子线里躺了三小时没被上报，代价是整条链空转。

---

## 参考

- [design-notes.md](references/design-notes.md) — 设计依据、四条硬规则的证据、第一轮要观察的读数
- [poll-contract.md](references/poll-contract.md) — 固定 JS 片段、wake 语义、一轮的动作序列
- [ledger-schema.md](references/ledger-schema.md) — 三个 jsonl 的字段定义
- [role-a-session-dispatch.md](references/role-a-session-dispatch.md) — 新建/替换 Role A 的 clean-session 两阶段交接模板
- [foundation-session-dispatch.md](references/foundation-session-dispatch.md) — 新建/替换 Role B 的 clean-session 两阶段派发模板
- [owner-thread-broker](owner-thread-broker/SKILL.md) — 线程路由与 Owner 授权边界
