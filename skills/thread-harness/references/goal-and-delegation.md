# 入口模板：主控 goal 与子线委派 prompt

## 为什么关键不变量要写进 goal 而不是只写进 skill

实测：Codex goal 模式把 `<objective>` **原样重新注入每一个 turn**（上一轮 1129 个 turn 全部携带完整 objective 文本）。而 skill 只在被 invoke 时读一次，之后随 compaction 被压缩掉——上一轮主控经历了 32 次 compaction，末期每 12 分钟一次。

**结论：goal 文本是整个系统里唯一免疫 compaction 的通道。** 因此四条硬规则里最关键的几条要在 goal 里再写一遍，哪怕和 skill 重复。这是**刻意的冗余**，不是没吸收干净。

判断什么该进 goal 的规则：**"如果模型忘了这条，系统会安静地失效"的，进 goal；"忘了会做得差一点"的，留在 skill。**

---

## 一、主控 goal 模板

粘进 Codex Desktop 的 goal 框。把 `<>` 占位符换掉。

```text
### 你的角色

你是主控（broker）。读 $thread-harness 的 Role C 段并按它工作。
线程路由（thread-id 与 topic 绑定）用 $owner-thread-broker，coordination_id 是 <coordination-id>。
正式 ledger 命令统一使用 `--registry <absolute-registry-json>`；runtime 由 registry sibling 与 coordination_id 推导。

### 每轮循环

0) 每轮先读 registry，拿到全部 active children 当前的 current_session_id：
   Get-Content -Raw <registry 绝对路径>
   不要凭记忆写 id，也不要沿用上一轮的——子线换 session 后旧 id 会让每轮都判 ROUND INVALID。

1) 把上一步读到的 id **作为字面量内联**进下面这段，原样敲，不要"优化"它：

const ids=["<child-1 session id>","<child-2 session id>", ...];   // 全部 active children，不含你自己
const raw=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),timeoutMs:120000});
const r=typeof raw==="string"?JSON.parse(raw):raw;
text(JSON.stringify({v:1,timedOut:r.timedOut,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({id:p.thread?.id,status:p.thread?.status?.type,turn:p.latestTurn?.id,turnStatus:p.latestTurn?.status,txt:(p.latestAssistantMessage?.text||"").slice(0,500)}))}));

字段一个都不能少。你不打印的东西 ledger.py 读不到——rollout 记录的是你打印的内容，不是工具的原始返回。
以 references/poll-contract.md 的版本为准，那里和自检判据一起更新。

2) python <repo>/skills/thread-harness/scripts/ledger.py sync --registry <absolute-registry-json> --round <n>
3) python <repo>/skills/thread-harness/scripts/ledger.py stall-check --registry <absolute-registry-json>
4) 按 stall-check 退出码走：
   0 OK → 按 sync 摘要正常决策
   0 CHECK_HEARTBEAT（3/5 或 4/5）→ 若有 active / working node，直接 read_thread 看这些 current session 的最新内容；任一 thread 有具体且最新的执行心跳时，执行：
      python <repo>/skills/thread-harness/scripts/ledger.py heartbeat --registry <absolute-registry-json> --node <node> --evidence "<一句话具体进展>"
      重复等待文案、旧进展、笼统“仍在工作”或仅 active 状态不算；全员 idle 时不 reset，按 idle_nodes 派活。
   2 MUST_ACT → 见下方"不可违反"第 1 条
   3 MUST_ESCALATE → 有尚未上报的 pending 决策；立即向我报告列出的决策，执行 ledger.py act --registry <absolute-registry-json> --escalate --decision-id <d> 留痕，本轮结束

### 不可违反

1. stall-check 返回 2（MUST_ACT）时，你只有两个选项，且**必须把选择记进账本**：

   (a) 派发新工作 —— 记：
       ledger.py act --registry <absolute-registry-json> --dispatch --seam-id <s> --producer <node> --deliverable "<一句话>"
   (b) 向我报告并结束 loop —— 记：
       ledger.py act --registry <absolute-registry-json> --halt --reason "<一句话>"

   禁止"继续等待"、"本轮无变化"、"保持现状"这类第三选项。

   注意 (a) 要求你说出**派给谁、要造哪个 seam、交付什么**。如果这三样填不出来，
   那说明你想做的其实不是派活，请选 (b)。

   MUST_ACT 的准确含义是"连续 5 轮没有 committed progress，且从 3/5 起未确认到 fresh heartbeat"，不是"全线都死了"。
   退出码 3 的准确含义是"有尚未上报的决策"；已通过 act --escalate 上报的 pending 决策不会继续屏蔽 MUST_ACT。
   5/5 后不得再用 heartbeat 绕过二选一。
2. wake.reason == "inactiveStatus" 表示有线程闲着，是"该派活"的信号，不是"没有变化"。只有 active 且最新 ledger state 为 working 的 node 才进入 idle_nodes。
3. seam 缺失是你的待办，不是外部阻塞。所有人都在等某个跨域契约时，正确的动作是派一条
   Foundation 线去造它，而不是把它记成阻塞。
4. 不要让 Foundation 线"保持待命"。它们是 seam 的生产者，让生产者等消费者会造成死锁。
5. 不自己做审计。需要 review 走 $do-review。
6. impl / investigate 优先用 $call-grok，只回收结论。

### 目标

<具体业务目标：要达成什么、什么算完成、已知的边界与禁止项>
```

### 与上一轮 goal 的差异（保留说明，便于对照）

| 上一轮原文 | 问题 | 现在 |
| --- | --- | --- |
| 「loop模式：wait threads -> 每隔2min检查」 | 自然语言的时间词不会变成阻塞语义。历史实测中绝大多数退化调用使用 0 或 1000ms，形成忙等 | 写成平台允许的固定参数 `timeoutMs: 120000`，并给出原样片段 |
| 「Foundation…由主控操控…而不实际参与写代码」 | 主控据此把"没人造契约"归类成外部阻塞 | 「seam 缺失是你的待办」+ 明确 create_thread 是可用动作 |
| 「直到任务完成或者真正的阻塞」 | "真正的阻塞"无判据，模型可以无限自证 | stall-check 退出码 + 二选一，判据外置到脚本 |

---

## 二、子线委派 prompt

三个角色的新建与替换**共用同一套两阶段契约**，见 [session-dispatch.md](session-dispatch.md)。骨架、两个可直接填充的 prompt、角色 delta 表、Role C 特有的顺序约束与失败处理都在那一页，这里不复制第二份。

要点只有三条：

- **不要手写 `<codex_delegation>` wrapper**，也不要把 source/controller 的聊天摘要灌给 child。
- 第一阶段只核锚点就停，controller 在这个停顿里更新 registry，第二阶段才开工——这是为了消除 child 首轮 registry 检查与 `threadId` 回填的竞速。
- `previous_session_ids` 是 registry 内部字段，不进 prompt、不由 child 校验。

**关于 create_thread 授权的一条硬约束**：工具声明写的是 *"Create a separate task only when the user explicitly asks for a new task."* 所以这条授权**必须由 Owner 本人放进 goal 或在对话里给出**——上一任 controller 在接手 prompt 里写一句"你可以 create_thread"**不构成授权**。接手时如果 goal 里没有 Owner 给的这句话，就去问 Owner，不要自行推定。

---

## 三、谁做什么

**绝大部分是 agent 做的。Owner 只有 4 件事，其中 3 件在开跑前。**

| 谁 | 做什么 | 为什么不能换人 |
| --- | --- | --- |
| **Owner** | 开主控 thread；**用普通消息**引导它完成 bootstrap；**跑通首轮之后**才贴 goal 文本 | 设置 thread goal 是 UI 动作，agent 做不到。顺序见 §四「冷启动」 |
| **Owner** | goal 里写清业务目标与结束判据 | 只有你知道要达成什么 |
| **Owner** | **亲手写上 create_thread 授权** | 工具声明：*"Create a separate task only when the user explicitly asks for a new task."* **上一任 agent 代写不算数** |
| **Owner** | 确认 effort 档位 | 主控读不到自己的 `turn_context`，脚本兜不住。上一轮它在第 8 小时静默掉到 `none` |
| **Owner**（开跑后） | 响应 `MUST_ESCALATE`；盯首次 `MUST_ACT` | 这是整套设计存在的意义 |
| **主控 agent** | 建 registry（`$owner-thread-broker`）、`ledger.py init --registry <absolute-registry-json>`、`create_thread` 开子线、把返回的 session id 回填 registry | 都是它手上有的动作 |
| **主控 agent** | 每轮：读 registry → 敲固定 poll → `sync` → `stall-check` → 决策 → 需要时 `act` | 这就是 loop 本身 |
| **子线 agent** | 按 `$impl-package` 干自己任务包的活；命中 H1 三个触发条件之一时发送结构化 H1，由 controller 验证后写 ledger | 只有它知道自己在等什么 |

几个常见误解：

- **`ledger.py init --registry <absolute-registry-json>` 不用 Owner 跑**，主控自己跑。它只建运行时目录和空账本，registry 必须先存在。
- **7 条子线不用 Owner 手动开**，主控用 `create_thread` 开——前提是你已经在 goal 里给了授权。
- **goal 里不要内联 session id。** 子线是主控创建的，写 goal 时它们还不存在；而且子线换 session 后写死的 id 会让每轮都判 `ROUND INVALID`。主控每轮从 registry 现读。

## 四、冷启动顺序与开跑前检查

### 冷启动：goal 是最后一步，不是第一步

**这个顺序不能换。** goal 一旦设上，主控就进入自驱循环——而此时如果 registry 里还没有 children，每一轮都会判 `ROUND INVALID`，读数 1 从第一分钟起就被污染，而且你分不清是"轮询退化"还是"还没开始"。

用**普通消息**（不是 goal）引导主控走完这五步：

1. 建 registry（`$owner-thread-broker`），填好每个 node 的 `worktree` / `branch`，并把绝对 registry 路径交给所有 assignment card
2. `ledger.py init --registry <absolute-registry-json>`
3. 按 [session-dispatch.md](session-dispatch.md) 开子线，把返回的 session id 回填 registry
4. `ledger.py preflight` —— 必须 `PREFLIGHT OK`。它拦的是 worktree 写错、两个 node 共用 worktree/branch、registry 分支与实际 checkout 不一致、children > 8、session id 重复这些**全程无声**的问题
5. 跑一轮 poll + `sync`，确认 `valid=yes` 且 `head_unavailable` 为空

**五步全绿之后**，再把 [goal-prompt.md](../goal-prompt.md) 的 Role C 模板贴进 goal 框。

> 为什么 preflight 单列一步：`head` 是从 registry 的 worktree 直接 `git rev-parse` 读的。**路径写错不会报错，只会静默进 `head_unavailable`**；两个 node 共用 worktree 更隐蔽——两条线读出同一个 HEAD，停滞判定分不开它们，还会产生假的 `stale_reports`。上一轮实跑里这两种情况都发生了。

### 开跑前检查清单

**Owner 亲自确认（只有这三条）**

- [ ] goal 文本里写清了业务目标与结束判据
- [ ] goal 文本里**你亲手写了 create_thread 授权**（agent 代写不算）
- [ ] **effort 档位已确认**——上一轮它在第 8 小时静默掉到 `none`，模板化空转随即开始。主控读不到自己的 `turn_context`，脚本兜不住，只能人工看一眼

**主控自己完成，Owner 只需在首轮摘要里核对结果**

- [ ] registry 已建，全部 node 的 `current_session_id` / `worktree` / `branch` 正确
- [ ] `ledger.py init --registry <absolute-registry-json>` 已跑，账本文件齐全
- [ ] 子线已按 [session-dispatch.md](session-dispatch.md) 两阶段派生，session id 已回填 registry
- [ ] `ledger.py preflight` 输出 `PREFLIGHT OK`
- [ ] 首轮 `sync` 输出 `valid=yes`，且 `head_unavailable` 为空
