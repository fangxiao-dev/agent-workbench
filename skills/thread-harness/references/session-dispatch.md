# Session dispatch 契约（三个角色统一）

新建或替换任何一条线的 session 时用本页。三个角色共用同一套骨架，差异只有 §角色 delta 那张表。

**不要手写一段带 `<codex_delegation>` 的委派 prompt。** 那种写法把路由 envelope 当成了 prompt 内容，还会让 child 首轮的 registry 检查与 controller 回填 `threadId` 竞速。统一复用 `$handoff-to-new-session` 的 clean local-session 能力；下方 thread-harness replacement override 优先于该通用 skill 的“source 自己 create/no doc”说法。

**第一阶段 child 只核对锚点然后停住，controller 在这个停顿里更新 registry，第二阶段才开工。** child 不直接写 ledger。依据见 [design-notes.md](design-notes.md) §4.5。

## 固定骨架

### 固定约束

- 用 `create_thread` + `target.environment={type:"local"}`。禁 fork、禁 worktree/snapshot/`startingState`。
- **档位在 `create_thread` 时显式指定，别靠默认。** 子线默认 `model=gpt-5.6-luna`、`thinking=max`；**主控交接时显式指定 `model=gpt-5.6-sol`、`thinking=xhigh`**——实测这样指定是生效的，而不指定就会落到平台默认。
  > 注意这只决定**起点**：session 跑过多轮后档位会被平台自动降到 terra，这是 Codex 的机制，本 harness 不对抗它。它的后果是长跑的主控会逐渐变钝——**这正是 `session_age_h` 要提示你换人的原因之一**。主控读不到自己的 `turn_context`，所以跑久了值得人工看一眼当前档位。
- **一个 node 一个 worktree 一个 branch。** 复用 worktree 前必须确认旧 writer 与 owned process 已停止。两个 node 共用一个 worktree 会让 `head` 串号——它们的 `git rev-parse HEAD` 读出同一个值，停滞判定分不开这两条线，还会产生假的 `stale_reports`。`preflight` 会拦这个。
- 第一阶段 prompt **不含** harness、coordination、registry、ledger 或角色规则。只有锚点。
- prompt 里不放旧聊天摘要、project ID、dirty fingerprint 或 secret。
- `previous_session_ids` 是 registry 内部路由历史。**不进任何 child prompt，也不要求 child 读取、打印或校验它。**
- 现有未提交内容只保护，不 reset / checkout / clean / 覆盖 / 重建。

### 两种触发，第 1–2 步不同

**先分清你在哪个场景**，这决定谁去调 `create_thread`：

| | **替换：主控提示现有 session 自交接**（最常见） | **冷启动：节点还不存在** |
| --- | --- | --- |
| 起因 | 某条线太长 / 接近 compaction 上限 / 已经变笨 | 为新识别的 seam 开一条 Platform 线，或首次建线 |
| 谁发起 | **主控**，依据是 `sync` 摘要里的 `session_age_h`（子线自己不自知，主控也看不到对方的 compaction 次数——平台没有这个数据，**session 年龄是唯一可用的代理信号**） | 主控 |
| 谁调 `create_thread` | **那条线自己**（Role A / Role C） | **主控** |
| Role B 例外 | **也由主控建**。Platform 没有自述状态，恢复权威是主控写的 assignment card，让它自交接没有意义 | 主控建 |
| 前置 | source 停在原子 checkpoint、owned process 已停 | Owner 已授权 `create_thread`、seam assignment 明确 |

### 触发消息（发给要退休的那条 session）

主控发给 child 时用它；Owner 让主控自己交接时也用它。**不要在触发消息里复述交接步骤**——那是被引用 skill 的职责。

```text
你该做 session 自交接了。

按 $handoff-to-new-session 执行，override 以
<repo>\skills\thread-harness\references\session-dispatch.md 为准：

1. 先把 checkpoint 写回你的恢复权威（Role A = 当前任务包 entry；Role C = 账本，已有，不必另写）。
2. 停掉你自己的 owned process。
3. 用该页「第一阶段 prompt」建 clean local session：只核对 anchor 就停住，不开工。
   禁 fork、禁新建 worktree、禁 snapshot。
4. 【仅 Role C】用 ledger.py route 把 registry 的 controller 指向继任者。
5. 把新 session id 用 handed_off H1 报给我，然后停止，不再继续本线工作。

registry：<registry 绝对路径 .json>

Owner 的 create_thread 授权原文（转述自当前 goal，你据此为自己建继任者）：
<粘贴 Owner 授权原文整段>
```

**授权原文必须随触发消息一起给。** 它源自 Owner 写在主控 goal 里的那段——child 读不到主控的 goal，不带就等于让它在没有授权证据的情况下调 `create_thread`。

**只在轮边界发起交接。** 轮中交接会让本轮 `sync` 判 `ROUND INVALID`（内联的 ids 与变更后的 registry 对不上）。宁可推迟一轮，**不要放宽 `sync` 校验**。

### registry 由谁写：当时的主控，永远

`previous_session_ids` 与 `current_session_id` 的写入**只由那一刻的 controller 执行**（用 `ledger.py route`，见 poll-contract）。这条对三个角色一致：

- **Role A / Role B 替换**：现任主控在收到 `handed_off` H1 后写。
- **Role C 交接**：**退休主控在退出前把 registry 指向继任者**。新主控上任后只核对该字段是否已指向自己，没写成才补写。

### 复用 `$handoff-to-new-session`，不要重造

交接的通用流程、prompt 形状与长度约束全在 `$handoff-to-new-session`（见它的 `references/handoff-prompt-template.md`）。**本页只写 override，不复述它，也不另造中间产物**——交接材料就是 child 的首条 prompt 本身，不要往临时目录写中间卡片再让主控转手。

两条 override：

- **停在第一阶段**：child 交接完成后不直接开工，而是只核对 anchor 就停，等主控更新 registry（见下方固定流程）。
- **`previous_session_ids` 不进 child prompt**，由主控写进 registry。

恢复权威按角色不同：Role A 是**已有的任务包 entry**，Role B 是主控写的 assignment card，Role C 是账本 + registry。

### Role A 要带上 `$impl-package`

带任务包的线（Role A）本身属于 `$impl-package` 框架——**本 harness 只是调度层，不定义它怎么干活**。所以给 Role A 的第二阶段 prompt 里把 `$impl-package` 作为 entry point 交过去就够了，不要复述它的 6 步主流程或执行阶段规矩。Platform 没有任务包，不需要这一条。

### 固定流程

1. 按上表确定谁执行第 2 步。若是 Role A 替换，source session 先把 checkpoint 写回任务包 entry 并停下 owned process；若是冷启动，controller 先完成 parent preflight。
2. 执行方用第一阶段 prompt 创建 clean local session；child 只报 anchor PASS/FAIL 然后停止。
3. controller 设置短标题，更新 registry 的 current routing，复核 sibling 未变化。
4. controller 发送第二阶段 registration + assignment card。
5. child 只校验 current controller 与本 node 的 current session/worktree/branch projection；匹配后登记状态并开工。
6. 做一次 `wait_threads(..., timeoutMs:0)` 快照。registry race 修正后**复用同一 clean session**，不再创建新 session。

### 第一阶段 prompt

锚点字段沿用 `$handoff-to-new-session` 的模板，唯一改动是结尾：**报 PASS 后停住**，不继续推进 next action。维护时只同步锚点字段。

```text
<角色与任务一句话>。这是全新、独立的 local session；不继承任何旧 session 的聊天历史。

执行锚点（首轮及后续命令均使用此 workdir）：
- worktree：<absolute_worktree>
- expected HEAD：<full_head>
- <role-anchor-1>
- <role-anchor-2>

<role-identity-line>

首轮只用 Test-Path / git rev-parse 确认上述锚点存在且匹配，不读取文档内容。
任一不符仅报告 `source worktree setup mismatch` 并停止，不得 repair。
全部匹配仅报告 `<role> anchor PASS` 与锚点值并停止；
不得读取 registry/ledger，不得开始实现、验证或协调。
```

### 第二阶段 prompt

```text
第二阶段 registration 已就绪。读取 $thread-harness 并按 <Role X> 工作。

Routing：
- coordination_id=<coordination_id>
- registry=<absolute_registry_path>
- ledger repo=<absolute_ledger_repo>
- node=<node_id>；expected current session=<new_thread_id>
- <role-routing-extra>

解析 registry 后只输出 current controller 与本 node 的 current session/worktree/branch projection。
精确匹配才向 controller 发送 H1 envelope，由 controller 按 ledger schema append：session_id=<current-session>、event=<trigger>、state=<role-initial-state>、真实 HEAD、waiting_on=<seam_id_or_none>、artifact=<pointer-or-null>。
否则报告 `harness mismatch` 并停止，不得修改 registry 或 ledger。

<role-recovery-block>

Assignment card（本轮唯一任务）：
- registry：<absolute_registry_path>（必填；不得只写 coordination_id 或 broker root）
- next action：<one_concrete_action>
- exact inputs：<max_6_exact_paths_or_artifact_pointers>
- already earned：<one_material_proof_or_N/A>
- still required：<remaining_closure_proof>
- authorization：<explicitly_allowed_actions>
- exclusions：<explicit_exclusions>

上下文纪律：
- 只读 nearest AGENTS、必需 skill 与 exact inputs；禁止 broad package/doc scan。
- 先 investigate 再 implement，不要直接开干；impl / investigate 优先 $call-grok，失败再退到 subagent；review 走 $do-review；验收由当前 session 完成。
- 不向聊天打印完整文件、测试日志、registry 或 ledger；只输出短 projection/摘要。

直接推进 next action，不写 blocker-only proposal。H1/H2/H4 严格执行，只回报 current controller。
```

**卡片六个字段的要求是「形状完整」，不是「措辞统一」。** 缺字段必须看得见；怎么写由 controller 当时决定。`exact inputs` 上限 6 条是刻意的——填不下说明这一轮的任务还没切够细。

### 停止条件

- anchor、title、local environment、current routing 或 exact inputs 不符：停止，不 repair。
- 返回 `clientThreadId`：报 incomplete delivery，**不伪造 session id**。
- source writer / owned process 未停止，或 checkpoint 不足以恢复：先回报 controller，不扩大读取范围。

## 角色 delta

| | **Role A · 任务包子线** | **Role B · Platform** | **Role C · 主控** |
| --- | --- | --- | --- |
| **恢复权威** | 当前任务包 entry | assignment card（parent package 只做存在性锚点与 closure ownership 指针） | 账本 + registry |
| **第一阶段额外锚点** | `package` / `entry point` | `parent package` / `entry point` | 父包 entry；controller 自己的 worktree / branch / HEAD |
| **role-identity-line** | 无 | `任务身份：node=<n>；seam=<s>；consumers=<c>` | `你接手 coordination <id> 的主控` |
| **role-routing-extra** | 无 | `seam=<seam_id>；consumers=<consumer_nodes>` | 全部 child 的 node → session → worktree/branch/HEAD |
| **role-initial-state** | `working` 或 `awaiting_seam` | `working` | `working` |
| **role-recovery-block** | `Package checkpoint：package / entry / checkpoint 指针` | 无——**不得**把 parent entry 当恢复入口，不读旧 plan/Task progress/历史 evidence | 见下方「Role C 特有顺序」 |
| **交付登记义务** | 无 | H1 报告 seam artifact，由 controller 用 `ledger.py seam --registry <path> --seam-id <s> --producer <node> [--consumers ...] --deliver commit:<sha>` 登记；没登记等于没交付 | 无 |
| **替换时谁调 `create_thread`** | 退休 session 自己 | **controller**（Platform 无自述状态） | 退休主控自己 |
| **source 侧额外动作** | 先把 checkpoint 写回任务包 entry：当前 HEAD、计数状态、单一 Next Action、已获/剩余证据、授权与 WIP 边界 | 无（assignment card 是恢复权威，不把 parent entry 当恢复入口） | 先用 `route` 把 registry 指向继任者，再广播新 controller id |

### Role C 特有顺序（不能换）

主控交接比 A/B 多一层：**它自己就是读账本的那个人，顺序错了会读到上一任的 rollout。**

1. **先**核对 registry 里 controller 的 `current_session_id` 已经是你自己（正常情况下退休主控在退出前已用 `route` 写好）。**没写成才由你补写**。`sync` 靠这个字段定位读哪个 rollout，指向上一任就会去读它的 rollout。
2. 跑 `ledger.py status --registry <absolute_registry_path>` 恢复认知。它只读账本不碰 rollout，是接手时唯一能用的命令；runtime 缺失时也不得由 status 初始化。**不要从对话历史重建全局状态。**
3. 设置 goal 文本（模板见 [goal-prompt.md](../goal-prompt.md)）。内联的 ids 要与 registry 当前 children 逐一核对——`sync` 会做集合比对，对不上每轮判 `ROUND INVALID`。
4. 跑第一轮固定 poll。
5. **再**跑 `sync`。新 session 的 rollout 在第 4 步之前是空的，此时跑 `sync` 必然得到 `SYNC STALE`。**4 必须在 5 之前。**

Role C 的第二阶段 prompt 除了通用 routing 段，还要带上这份接手锚点清单（**派发方填好，缺了就问，不要猜**）：

```text
- broker root 与 registry 绝对路径：<...>
- 每个 child 的 node 名 → session_id → worktree / branch / expected HEAD：<...>
- controller 自己的 worktree / branch / expected HEAD：<...>
- 父 package 与 entry point：<...>
- 上一次 valid round 序号：<n>
- 当前在途的 assignment（谁在造哪个 seam）：<...>
- 当前 pending seams / pending decisions（含哪些已 escalate 过）：<...>
- 各 child 不可触碰的 dirty / Owner WIP：<...>
- 授权边界，特别是 create_thread 是否被 Owner 授权：<...>
- 什么算这次 coordination 结束：<...>
```

**一条硬约束**：设置 thread goal 是 UI 动作，**agent 做不到**，只能 Owner 亲手贴。同理，`create_thread` 授权必须由 Owner 本人放进 goal 或在对话里给出——工具声明写的是 *"Create a separate task only when the user explicitly asks for a new task."* 上一任 controller 在接手 prompt 里写一句「你可以 create_thread」**不构成授权**。接手时 goal 里没有 Owner 给的这句话，就去问，不要自行推定。

## 常见失败

| 现象 | 真因 | 处理 |
| --- | --- | --- |
| child 首轮报 registry mismatch | 一次性发了完整 registration，撞上 controller 尚未回填 `threadId` 的窗口 | 按两阶段重发，**复用同一 session**，不要再建一个 |
| child 把 controller id 当成"自己的 session" | 第二阶段 routing 段没写清哪个字段是自己、哪个是对方 | routing 段逐字写 `node=<n>；expected current session=<id>`，两个 id 不并列出现在同一行 |
| 两条线 `head` 永远相同 | 共用 worktree | 一 node 一 worktree 一 branch；`preflight` 会拦 |
| 交付了但下游查不到 | Role B 没登记 seam artifact | 交付即登记，见 delta 表 |
| 交接后第一轮判 `ROUND INVALID` | 交接落在轮中，registry 变了而本轮内联的 ids 没变 | 只在轮边界发起交接；本轮作废重来，不要放宽 `sync` 校验 |
| 广播了新 controller id，子线却仍发给旧的 | 子线用了记忆里的 id | 广播只用于唤醒闲着的线；回报路由的权威是 registry，子线每次回报前必须现读 |
