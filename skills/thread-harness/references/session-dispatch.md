# Session dispatch 契约（三个角色统一）

新建或替换任何一条线的 session 时用本页。三个角色共用同一套骨架，差异只有 §角色 delta 那张表。

**不要手写一段带 `<codex_delegation>` 的委派 prompt。** 统一复用 `$handoff-to-new-session` 的 clean local-session 能力；下方 thread-harness replacement override 优先于该通用 skill 的“source 自己 create/no doc”说法。
本禁令仅针对调用者把<codex_delegation>标签手写进 create_thread /
send_message_to_thread 的 prompt 字符串。

**第一阶段 child 只核对锚点然后停住，controller 在这个停顿里更新 registry，第二阶段才开工。** child 不直接写 ledger。

## 固定骨架

### 固定约束

- 用 `create_thread` + `target.environment={type:"local"}`。禁 fork、禁 worktree/snapshot/`startingState`。
- **档位在 `create_thread` 时显式指定，别靠默认。** 子线用 `model=gpt-5.6-luna`、`thinking=max`；**主控交接时用 `model=gpt-5.6-sol`、`thinking=xhigh`**。这只决定起点，平台会随 session 变长自动降档，主控读不到自己的 `turn_context`，跑久了值得人工看一眼。
- **一个 node 一个 worktree 一个 branch。** 复用 worktree 前必须确认旧 writer 与 owned process 已停止。`preflight` 会拦这个。
- 第一阶段 prompt **不含** harness、coordination、registry、ledger 或角色规则。只有锚点。
- prompt 里不放旧聊天摘要、project ID、dirty fingerprint 或 secret。
- `previous_session_ids` 是 registry 内部路由历史。**不进任何 child prompt，也不要求 child 读取、打印或校验它。**
- 现有未提交内容只保护，不 reset / checkout / clean / 覆盖 / 重建。

### 两种触发，第 1–2 步不同

**先分清你在哪个场景**，这决定谁去调 `create_thread`：

| | **替换：主控提示现有 session 自交接**（最常见） | **冷启动：节点还不存在** |
| --- | --- | --- |
| 起因 | `sync` 已观测到 compaction 达到角色阈值，或主控直接确认该线已经明显退化 | 为新识别的 seam 开一条 Platform 线，或首次建线 |
| 谁发起 | **主控**，依据是 `sync` 摘要里当前 child session 的 [`compaction_count`](poll-contract.md#compaction_count)，或主控直接确认的明显退化；存在时长不参与这项判断 | 主控 |
| 谁调 `create_thread` | **那条线自己**（Role A / Role C） | **主控** |
| Role B 例外 | **也由主控建**。Platform 没有持久恢复权威，replacement 由主控用一张新的完整 assignment card 重新派发 | 主控建 |
| 前置 | source 停在原子 checkpoint、owned process 已停 | Owner 已授权 `create_thread`、seam assignment 明确 |

### 触发消息（发给要退休的那条 session）

> **读者**：即将退休的那条线，它有本线的全部上下文。
> **恢复权威**：无——它不需要恢复，它需要交出去。
> **准入判据**：**这句话是不是只有我知道？** 是就写，否则指过去。

主控发给 child 时用它；Owner 让主控自己交接时也用它。

```text
你该做 session 自交接了。按 $handoff-to-new-session 执行，override 以
<repo>\skills\thread-harness\references\session-dispatch.md 为准。

registry：<registry 绝对路径 .json>

Owner 的 create_thread 授权原文（你据此为自己建继任者）：
<粘贴整段>

交接后你不再是权威：可以补充遗留事实与坑，如果要纠偏，必须先 read_thread 确认继任者
确实自己走偏了才能纠正，不得纠正继任者后续的 prompt。
```

**不要复述交接步骤**——写 checkpoint、停 owned process、建 clean session、`route`、报 `handed_off` H1，这些全是 `$handoff-to-new-session` 与本页其余各节的职责。触发消息只负责"该交班了"这一件事。

**授权原文必须随触发消息一起给。** child 读不到主控的 goal，不带就等于让它在没有授权证据的情况下调 `create_thread`。

**"不再是权威"禁的是替 Owner 裁决授权与边界，不是说话。** 退休线看不到 Owner 之后说了什么。发现继任者真的要出事时仍然要吭声：先 `read_thread` 核实，或回给 Owner。

**只在轮边界发起交接。** 轮中交接会让本轮 `sync` 判 `ROUND INVALID`。宁可推迟一轮，**不要放宽 `sync` 校验**。

### registry 由谁写：当时的主控，永远

`previous_session_ids` 与 `current_session_id` 的写入**只由那一刻的 controller 执行**（用 `ledger.py route`，见 poll-contract）。这条对三个角色一致：

- **Role A / Role B 替换**：现任主控在收到 `handed_off` H1 后写。
- **Role C 交接**：**退休主控在退出前把 registry 指向继任者**。新主控上任后只核对该字段是否已指向自己，没写成才补写。

### Thread-harness overrides

- **停在第一阶段**：child 交接完成后不直接开工，而是只核对 anchor 就停，等主控更新 registry（见下方固定流程）。
- **`previous_session_ids` 不进 child prompt**，由主控写进 registry。

### Role A 要带上 `$impl-package`

Role A 的第二阶段 prompt 必须以 `$impl-package` 为 entry point，不复述其流程；Role B 不带这一项。

### 固定流程

1. 按上表确定谁执行第 2 步。若是 Role A 替换，source session 先把 checkpoint 写回任务包 entry 并停下 owned process；若是冷启动，controller 先完成 parent preflight。
2. 执行方用第一阶段 prompt 创建 clean local session；child 只报 anchor PASS/FAIL 然后停止。
3. controller 设置短标题，更新 registry 的 current routing，复核 sibling 未变化。
4. controller 发送第二阶段 registration + assignment card。
5. child 向第二阶段给出的 current controller 发送最小 H1；controller 从消息来源绑定 node/session，并用 registry 验证后登记状态。
6. 做一次 `wait_threads(..., timeoutMs:0)` 快照。registry race 修正后**复用同一 clean session**，不再创建新 session。

### 第一阶段 prompt

> **读者**：一个全新的 session，此刻什么都不知道。
> **恢复权威**：worktree / branch / HEAD——都能用一条只读命令当场验真。
> **准入判据**：**这一行能不能被 child 用一条只读命令当场验真？** 不能就不进。

锚点字段沿用 `$handoff-to-new-session` 的模板，唯一改动是结尾：**报 PASS 后停住**。维护时只同步锚点字段。

```text
<角色与任务一句话>。这是全新、独立的 local session，不继承任何旧 session 的聊天历史。

执行锚点（首轮及后续命令均使用此 workdir）：
- worktree：<absolute_worktree>
- branch：<branch>
- expected HEAD：<full_head>
- <role-anchor-1>
- <role-anchor-2>

首轮只用 Test-Path / git rev-parse 核对上述锚点。
任一不符：只报 `source worktree setup mismatch` 与实际值，停止，不 repair。
全部匹配：只报 `<role> anchor PASS` 与锚点值，停住，不要做额外动作。
```

结尾那句"停住，不要做额外动作"已经蕴含了"不读 registry/ledger、不开始实现或协调"，所以不再单列禁令。

### 第二阶段 prompt

> **读者**：已经 anchor PASS、知道自己站在哪，但还不知道要干什么。
> **恢复权威**：Role A 是任务包 entry；Role B 无持久恢复权威，下方 card 只定义当前 assignment。Role C 不是 child，按后文特有顺序读取 registry + ledger。
> **准入判据**：**这行能否让 child 完成准入，或立即开始当前 assignment？** 不能就不进 prompt。

Role A / B 的完整第二阶段消息（registration + assignment）以对应模板为准，**不得超过 20 个非空逻辑行**。child routing 只有 current controller session id。

#### Role A prompt

```text
第二阶段 registration 已就绪。读取 $thread-harness 与 $impl-package，并按 Role A 工作。
回报对象：controller=<current_controller_session_id>
恢复权威：<package entry / checkpoint pointer>
向 controller 发送 state=working 的 H1，再从恢复权威读取并继续其中的 current Next Action。
状态变化只通过 H1 回报；不要调用 ledger.py。缺少可执行 Next Action 时询问 controller，不从聊天重建。
```

#### Role B prompt

```text
第二阶段 registration 已就绪。读取 $thread-harness 并按 Role B 工作。
回报对象：controller=<current_controller_session_id>
恢复权威：无；本卡仅定义当前 assignment。
<slug>：<一句话任务名>
- seam / 任务：<seam_id → consumers｜bounded task>
- next action：<一个可立即执行的动作>
- inputs：<最小充分的精确路径或 artifact 指针>
- done when：<当前 assignment 的结束判据>
状态变化只通过 H1 回报；不要调用 ledger.py。
需要新增权限时停止相关动作并询问 controller，获得明确的一次性授权后继续。
只读 nearest AGENTS、必需 skill 与 inputs，不做 broad scan。
```

### Assignment card（派发用，约束型）

> **读者**：一条已经在岗的线。
> **任务权威**：Role A 的持久恢复权威是任务包 entry；Role B 无持久恢复权威，这张卡只定义当前 assignment。
> **准入判据**：**这是不是 child 开始当前动作所需的最小切入点？** 不是就不进卡。

Role A 从 package entry 恢复并继续。Role B card 使用第二阶段模板里的四个字段：`seam / 任务`、`next action`、`inputs`、`done when`。

- **`seam / 任务`**：seam 必须写出 consumers；非 seam 就明写 bounded task。
- **`inputs`**：只列执行 `next action` 前必须读取的代码、当前契约或 artifact。当前 worktree 内用相对路径，跨 worktree 用绝对路径；历史 plan、execution record 或 evidence 只有精确 section / artifact 会改变当前动作时才可进入。必须复用的既有证据只给一个 artifact 指针，不复述摘要。
- **`done when`**：只写当前 assignment 的结束判据，不扩成 package 或 coordination 的完成声明。
- Role B 发生 compaction 后不恢复本卡，由 controller 重新验证最小切入点并派发一张新卡。

**fan-out（同一张卡发给多个 node）**：判据是「这张卡是不是每条线都要**立刻改变行为**？」否则不 fan-out，主控自己记住就行。fan-out 不承载任务内容，任务内容一律走单发的 card。

### Role A catch-up（compaction 后，约束型）

> **读者**：刚发生过 compaction、仍在岗的 Role A session。
> **恢复权威**：当前任务包 entry；controller 消息只提供回报目标。
> **准入判据**：**只补它读不回来的东西**；能自己读回来的一律只给指针。

```text
catch-up（你刚发生过 compaction）：
- 你的角色：Role A 任务包子线，按 $thread-harness Role A 执行
- 开发框架：$impl-package
- 回报对象：controller=<current_controller_session_id>
- 当前 assignment：<slug>
- 恢复权威：<绝对路径>
- 下一个动作：<one_concrete_action>

其余状态自己从上面的恢复权威读回。
```

- **角色与开发框架必须重述**——compaction 后的 child 已经不知道自己该去读什么。
- **硬上限 10 行。**
- **计数规则（controller 执行）**：只读取本轮 [`ledger.py sync` 摘要的 `compaction_count: <node>=<n>`](poll-contract.md#compaction_count)。同一 Role A current session 的 `n` ≤3 时发送 catch-up；`n` >3 时改为按上面的触发消息转交接。Role A 不自行估算或查找次数；`?` 表示本机 rollout 不可用，controller 停止计数判定并直接核查，不得猜成 0。
- **Role B 不用这个模板**：它没有持久恢复权威。compaction 后主控（controller）不读旧聊天、不恢复旧 card，而是发送一张新的最小 assignment card；缺关键输入时停止并询问 controller，新增权限按 Role B 权限规则处理。
- **Role C 不用这个模板**：主控 compaction 后走 `ledger.py status` 自己恢复（见 §Role C 特有顺序）。

### 停止条件

- anchor、title、local environment、current routing 或 inputs 不符：停止，不 repair。
- 返回 `clientThreadId`：报 incomplete delivery，**不伪造 session id**。
- source writer / owned process 未停止，或 checkpoint 不足以恢复：先回报 controller，不扩大读取范围。

## 角色 delta

| | **Role A · 任务包子线** | **Role B · Platform** | **Role C · 主控** |
| --- | --- | --- | --- |
| **恢复权威** | 当前任务包 entry；第二阶段不发 card | 无持久恢复权威；新 card 只定义当前 assignment | 账本 + registry |
| **第一阶段额外锚点** | `package` / `entry point` | `parent package` / `entry point` | 父包 entry；controller 自己的 worktree / branch / HEAD |
| **role-initial-state** | `working` 或 `awaiting_seam` | `working` | `working` |
| **role-recovery-block** | `Package checkpoint：package / entry / checkpoint 指针` | 无——**不得**把 parent entry 当恢复入口，不读旧 plan/Task progress/历史 evidence | 见下方「Role C 特有顺序」 |
| **交付登记义务** | 无 | H1 报告 seam artifact，由 controller 用 `ledger.py seam --registry <path> --seam-id <s> --producer <node> [--consumers ...] --deliver commit:<sha>` 登记；没登记等于没交付 | 无 |
| **替换时谁调 `create_thread`** | 退休 session 自己 | **controller**（Platform 无自述状态） | 退休主控自己 |
| **source 侧额外动作** | 先把 checkpoint 写回任务包 entry：当前 HEAD、计数状态、单一 Next Action、已获/剩余证据、授权与 WIP 边界 | 无 checkpoint；controller 重新验证事实后发新 card，不把 parent entry 或旧聊天当恢复入口 | 先用 `route` 把 registry 指向继任者，再广播新 controller id |

### Role C 特有顺序（不能换）

主控交接比 A/B 多一层：**它自己就是读账本的那个人，顺序错了会读到上一任的 rollout。**

Role C 的完整第二阶段消息同样不得超过 20 个非空逻辑行：

```text
第二阶段接手已就绪。读取 $thread-harness 并按 Role C 工作。
registry：<absolute_registry_path>
expected controller session：<new_controller_session_id>
核对 registry 的 controller.current_session_id，再运行 ledger.py status。
按 Owner goal 恢复目标、授权与结束判据；然后依次执行 preflight、首轮 poll、sync。
```

固定恢复顺序是：核对 registry 已指向自己 → `status` → Owner goal → `preflight` → 首轮固定 poll → `sync`。`status` 只读账本、不碰 rollout，也不初始化缺失 runtime；新 session 在首轮 poll 前运行 `sync` 必然得到 `SYNC STALE`。动态进展、child routing、HEAD、assignment、seam、decision 与 WIP 从 registry、ledger、任务包和当前 worktree 读取。

**一条硬约束**：设置 thread goal 是 UI 动作，**agent 做不到**，只能 Owner 亲手贴。同理，`create_thread` 授权必须由 Owner 本人放进 goal 或在对话里给出——工具声明写的是 *"Create a separate task only when the user explicitly asks for a new task."* 上一任 controller 在接手 prompt 里写一句「你可以 create_thread」**不构成授权**。接手时 goal 里没有 Owner 给的这句话，就去问，不要自行推定。

## 常见失败

| 现象 | 真因 | 处理 |
| --- | --- | --- |
| controller 拒绝首个 H1 | 第二阶段消息与 controller 更新 registry 发生竞争 | controller 重新核对来源 routing；正确后复用同一 child 重发，不再建 session |
| 两条线 `head` 永远相同 | 共用 worktree | 一 node 一 worktree 一 branch；`preflight` 会拦 |
| 交付了但下游查不到 | Role B 没登记 seam artifact | 交付即登记，见 delta 表 |
| `ROUND INVALID` | 本轮 poll 不符合固定契约 | 本轮作废；恢复固定 JS，确认 `timeoutMs=120000`、targets 等于当前 watch-set，且交接只发生在轮边界，然后重跑。不要拼旧输出或放宽 `sync` 校验。 |
| 广播了新 controller id，子线却仍发给旧的 | 交接消息没有明确替换回报对象 | 新主控广播逐字给出 `controller=<new_session_id>`；child 用它替换当前回报目标 |
