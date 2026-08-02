# Session dispatch 契约（三个角色统一）

新建或替换任何一条线的 session 时用本页。三个角色共用同一套骨架，差异只有 §角色 delta 那张表。

**不要手写一段带 `<codex_delegation>` 的委派 prompt。** 那种写法把路由 envelope 当成了 prompt 内容，还会让 child 首轮的 registry 检查与 controller 回填 `threadId` 竞速。统一复用 `$handoff-to-new-session` 的 clean local-session 能力；下方 thread-harness replacement override 优先于该通用 skill 的“source 自己 create/no doc”说法。

## 为什么分两阶段

一次性把 registration 和任务一起发给 child，会出现一个无法消除的竞速：child 第一个 turn 就去读 registry，而 controller 这时还没拿到新 `threadId`、registry 里还是旧值，于是 child 报 mismatch。

拆成两阶段就没有这个窗口——**第一阶段 child 只核对锚点然后停住，controller 在这个停顿里更新 registry，第二阶段才真正开工。** child 不直接写 ledger。

## 固定骨架

### 固定约束

- 用 `create_thread` + `target.environment={type:"local"}`。禁 fork、禁 worktree/snapshot/`startingState`。
- 默认 `model=gpt-5.6-luna`、`thinking=max`，除非 Owner 覆盖。
- **一个 node 一个 worktree 一个 branch。** 复用 worktree 前必须确认旧 writer 与 owned process 已停止。两个 node 共用一个 worktree 会让 `head` 串号——它们的 `git rev-parse HEAD` 读出同一个值，停滞判定分不开这两条线，还会产生假的 `stale_reports`。`preflight` 会拦这个。
- 第一阶段 prompt **不含** harness、coordination、registry、ledger 或角色规则。只有锚点。
- prompt 里不放旧聊天摘要、project ID、dirty fingerprint 或 secret。
- `previous_session_ids` 是 registry 内部路由历史。**不进任何 child prompt，也不要求 child 读取、打印或校验它。**
- 现有未提交内容只保护，不 reset / checkout / clean / 覆盖 / 重建。

### 两种触发，第 1–2 步不同

**先分清你在哪个场景**，这决定谁去调 `create_thread`：

| | **替换：主控提示现有 session 自交接**（最常见） | **冷启动：节点还不存在** |
| --- | --- | --- |
| 起因 | 某条线太长 / 接近 compaction 上限 / 已经变笨 | 为新识别的 seam 开一条 Foundation 线，或首次建线 |
| 谁发起 | **主控**——它看得到轮次与 compaction 迹象，子线自己往往不自知 | 主控 |
| 谁调 `create_thread` | **controller**（source child 只准备交接卡） | **主控** |
| 为什么 | 只有 source 知道自己的 WIP 边界、已获证据与单一 Next Action；它把这些机械写入 Temp card，controller 只校验并触发，不重新分析总结 | 没有 source session 可提示 |
| Role B 例外 | **也由主控建**。Foundation 没有自述状态，恢复权威是主控写的 assignment card，让它自交接没有意义 | 主控建 |
| 前置 | source 停在原子 checkpoint、owned process 已停 | Owner 已授权 `create_thread`、seam assignment 明确 |

**主控的触发消息只需要三件事**：说明要做自交接、指向 `$handoff-to-new-session`、给出本 skill 的路径作为 override 依据。不要在触发消息里复述交接步骤——那是被引用 skill 的职责。

### 复用 `$handoff-to-new-session`，不要重造

自交接的通用能力（clean local session、anchor check、不 fork、不建 worktree）已经在 `$handoff-to-new-session` 里。本页只做**override 与简化**，不重写它：

- **override**：交接完成后不是直接开工，而是停在第一阶段等主控更新 registry（见下方固定流程）。
- **override**：`previous_session_ids` 由主控写进 registry，不进 child prompt。
- **简化**：不产出通用 handoff 文档。source child 写一张 prepare-only card 到用户 Temp；Role A 的恢复权威仍是**已有的任务包 entry**，Role B 是 assignment card，Role C 是账本 + registry。

### thread-harness replacement override

这是本 skill 对 `$handoff-to-new-session` 当前“source 自己 create/no doc”流程的明确 override，仅适用于 child replacement：

1. source child 在停下 owned process 后生成紧凑 prepare-only card，写入用户 Temp：`%TEMP%\codex-thread-harness\handoffs\`。
2. card 写入 Temp，不写入 worktree、不提交 Git、不放 secrets，且只记录恢复所需事实：`version`、`registry` 绝对路径、`coordination_id`、`node`、`source_session_id`、worktree、branch、HEAD、恢复 authority、单一 next action、exact inputs、already earned、still required、authorization、exclusions 与 WIP boundary。
3. source child 对 card 做 SHA-256，并只向 controller 发送“card path + hash + H1 envelope”；不发送新 session id，也不调用 `create_thread`。
4. controller 重新读取并校验 card path/hash、registry source session、worktree/branch/HEAD 与恢复 authority；校验通过后才实际 `create_thread`、回填 registry、发送第二阶段 registration + assignment card 并验收。

最小 card 形状：

```json
{"version":1,"kind":"thread-harness-prepare-only","registry":"<absolute-registry-json>","coordination_id":"<id>","node":"<node>","source_session_id":"<current-session-id>","worktree":"<absolute-worktree>","branch":"<branch>","head":"<full-git-sha>","authority":"<package-entry-or-assignment-card>","next_action":"<one-concrete-action>","exact_inputs":["<absolute-path-or-artifact>"],"already_earned":"<material-proof-or-N/A>","still_required":"<remaining-proof>","authorization":"<allowed-actions>","exclusions":"<explicit-exclusions>","wip_boundary":"<short-boundary>"}
```

### Role A 要带上 `$impl-package`

带任务包的线（Role A）本身属于 `$impl-package` 框架——**本 harness 只是调度层，不定义它怎么干活**。所以给 Role A 的第二阶段 prompt 里把 `$impl-package` 作为 entry point 交过去就够了，不要复述它的 6 步主流程或执行阶段规矩。Foundation 没有任务包，不需要这一条。

### 固定流程

1. 按上表确定谁执行第 2 步。若是 Role A 替换，source session 先把 checkpoint 写回任务包 entry 并停下 owned process；若是冷启动，controller 先完成 parent preflight。
2. controller 读取并验证 prepare-only card；执行方用第一阶段 prompt 创建 clean local session；child 只报 anchor PASS/FAIL 然后停止。
3. controller 设置短标题，更新 registry 的 current routing，复核 sibling 未变化。
4. controller 发送第二阶段 registration + assignment card。
5. child 只校验 current controller 与本 node 的 current session/worktree/branch projection；匹配后登记状态并开工。
6. 做一次 `wait_threads(..., timeoutMs:0)` 快照。registry race 修正后**复用同一 clean session**，不再创建新 session。

### 第一阶段 prompt

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
- impl / investigate 优先 $call-grok；review 走 $do-review；验收由当前 session 完成。
- 不向聊天打印完整文件、测试日志、registry 或 ledger；只输出短 projection/摘要。

直接推进 next action，不写 blocker-only proposal。H1/H2/H4 严格执行，只回报 current controller。
```

**卡片六个字段的要求是「形状完整」，不是「措辞统一」。** 缺字段必须看得见；怎么写由 controller 当时决定。`exact inputs` 上限 6 条是刻意的——填不下说明这一轮的任务还没切够细。

### 停止条件

- anchor、title、local environment、current routing 或 exact inputs 不符：停止，不 repair。
- 返回 `clientThreadId`：报 incomplete delivery，**不伪造 session id**。
- source writer / owned process 未停止，或 checkpoint 不足以恢复：先回报 controller，不扩大读取范围。

## 角色 delta

| | **Role A · 任务包子线** | **Role B · Foundation** | **Role C · 主控** |
| --- | --- | --- | --- |
| **恢复权威** | 当前任务包 entry | assignment card（parent package 只做存在性锚点与 closure ownership 指针） | 账本 + registry |
| **第一阶段额外锚点** | `package` / `entry point` | `parent package` / `entry point` | 父包 entry；controller 自己的 worktree / branch / HEAD |
| **role-identity-line** | 无 | `任务身份：node=<n>；seam=<s>；consumers=<c>` | `你接手 coordination <id> 的主控` |
| **role-routing-extra** | 无 | `seam=<seam_id>；consumers=<consumer_nodes>` | 全部 child 的 node → session → worktree/branch/HEAD |
| **role-initial-state** | `working` 或 `awaiting_seam` | `working` | `working` |
| **role-recovery-block** | `Package checkpoint：package / entry / checkpoint 指针` | 无——**不得**把 parent entry 当恢复入口，不读旧 plan/Task progress/历史 evidence | 见下方「Role C 特有顺序」 |
| **交付登记义务** | 无 | H1 报告 seam artifact，由 controller 登记（`ledger.py seam --deliver commit:<sha>`）；没登记等于没交付 | 无 |
| **替换时谁调 `create_thread`** | controller 读取 prepare-only card 后创建 | **controller** | 退休主控自己 |
| **source 侧额外动作** | 先把 checkpoint 写回任务包 entry，再写 Temp prepare-only card：当前 HEAD、计数状态、单一 Next Action、已获/剩余证据、授权与 WIP 边界 | 写 Temp prepare-only card；assignment card 仍是恢复权威，不把 parent entry 当恢复入口 | 广播新 controller id 给全部 child |

### Role C 特有顺序（不能换）

主控交接比 A/B 多一层：**它自己就是读账本的那个人，顺序错了会读到上一任的 rollout。**

1. **先**用 `$owner-thread-broker` 把 registry 里 controller 的 `current_session_id` 改成自己。`sync` 靠这个字段定位读哪个 rollout，不先改就会去读上一任的。
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
