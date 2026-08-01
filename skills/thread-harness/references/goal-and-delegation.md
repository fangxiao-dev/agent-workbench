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

### 每轮循环

0) 每轮先读 registry，拿到全部 children 当前的 current_session_id：
   Get-Content -Raw <registry 绝对路径>
   不要凭记忆写 id，也不要沿用上一轮的——子线换 session 后旧 id 会让每轮都判 ROUND INVALID。

1) 把上一步读到的 id **作为字面量内联**进下面这段，原样敲，不要"优化"它：

const ids=["<child-1 session id>","<child-2 session id>", ...];   // 全部 children，不含你自己
const raw=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),timeoutMs:120000});
const r=typeof raw==="string"?JSON.parse(raw):raw;
text(JSON.stringify({v:1,timedOut:r.timedOut,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({id:p.thread?.id,status:p.thread?.status?.type,turn:p.latestTurn?.id,turnStatus:p.latestTurn?.status,txt:(p.latestAssistantMessage?.text||"").slice(0,500)}))}));

字段一个都不能少。你不打印的东西 ledger.py 读不到——rollout 记录的是你打印的内容，不是工具的原始返回。
以 references/poll-contract.md 的版本为准，那里和自检判据一起更新。

2) python <repo>/skills/thread-harness/scripts/ledger.py sync --coordination-id <coordination-id> --round <n>
3) python <repo>/skills/thread-harness/scripts/ledger.py stall-check --coordination-id <coordination-id>
4) 按 stall-check 退出码走：
   0 → 按 sync 摘要正常决策
   2 MUST_ACT → 见下方"不可违反"第 1 条
   3 MUST_ESCALATE → 立即向我报告 pending 决策，本轮结束

### 不可违反

1. stall-check 返回 2（MUST_ACT）时，你只有两个选项，且**必须把选择记进账本**：

   (a) 派发新工作 —— 记：
       ledger.py act --coordination-id <id> --dispatch --seam-id <s> --producer <node> --deliverable "<一句话>"
   (b) 向我报告并结束 loop —— 记：
       ledger.py act --coordination-id <id> --escalate --decision-id <d>

   禁止"继续等待"、"本轮无变化"、"保持现状"这类第三选项。

   注意 (a) 要求你说出**派给谁、要造哪个 seam、交付什么**。如果这三样填不出来，
   那说明你想做的其实不是派活，请选 (b)。

   MUST_ACT 的准确含义是"没有 committed progress"，不是"全线都死了"。
   可能有线正在活跃工作只是还没 commit——这时正确动作仍是给**别的**空闲线派活，
   而不是把这一轮解释成"不算停滞"。
2. wake.reason == "inactiveStatus" 表示有线程闲着，是"该派活"的信号，不是"没有变化"。
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

## 二、子线委派 prompt 模板

用于 `codex_app__create_thread`。三个角色各一份，都很短——**详细规矩在被引用的 skill 里，这里只做锚定和角色指派。**

### Role A · 任务包子线

```text
<codex_delegation>
  <source_thread_id><主控 session id></source_thread_id>
  <input>
你是任务包 <package-id> 的负责子线。

角色：读 $thread-harness 的 Role A 段。你的使命是完成任务包，开发方式由 $impl-package
定义（6 步主流程，执行阶段 dev-with-track + subagent-driven-development）。thread-harness
只规定你什么时候必须跟主控说话，不改变你的开发方式。

锚点：
- worktree: <绝对路径>
- branch: <分支名>
- expected HEAD: <commit>
- 任务包: <docs/implementations/<package-id>/ 或实际路径>

账本：python <repo>/skills/thread-harness/scripts/ledger.py，coordination-id 是 <id>，
你的 node 名是 <node>。

必须遵守（其余按 impl-package）：
- head 变了 / 状态转 waiting / 出现 Owner 级阻塞 —— 三者任一，写账本并回报主控，不要等它来问。
- 等上游产物时必须指向一个 seam_id。等一个没人负责造的东西是错误状态，立即上报。
- "提交一份记录我被阻塞的文档"不算产出。空闲要说出来，让主控给你派活。
- impl / investigate 优先 $call-grok；review 走 $do-review；验收自己做。

授权边界：<明确写清可以做什么、绝对不可以做什么>
  </input>
</codex_delegation>
```

### Role B · Foundation 子线

```text
<codex_delegation>
  <source_thread_id><主控 session id></source_thread_id>
  <input>
你是 Foundation 线 <node>，负责产出 seam：<seam 的具体描述>。

角色：读 $thread-harness 的 Role B 段。你没有自己的任务包，任务由主控指派。

锚点：
- worktree: <绝对路径>
- branch: <分支名>
- expected HEAD: <commit>
- 上游输入: <可消费的候选 artifact 指针>

账本：python <repo>/skills/thread-harness/scripts/ledger.py，coordination-id 是 <id>，
你的 node 名是 <node>。

必须遵守：
- 「保持待命」对你是非法指令。哪怕主控这样要求也不要照做。空闲时只有两个合法动作：
  向主控要下一个 seam 任务，或报告"本线 seam 已交付"并附 seam_id 与 artifact 指针。
- 交付即在 seams.jsonl 登记 seam_id + consumers + artifact。没登记等于没交付。
- impl / investigate 优先 $call-grok；review 走 $do-review；验收自己做。

授权边界：<明确写清可以做什么、绝对不可以做什么>
  </input>
</codex_delegation>
```

### Role C · 接手主控（换 session 时）

换主控 session 时，新 session 的第一条 prompt 用 `$handoff-to-new-session` 组织，并额外交代：

```text
你接手 coordination_id <id> 的主控。读 $thread-harness 的 Role C 段。

按这个顺序做，顺序不能换：

1) 先用 $owner-thread-broker 把 registry 里 controller 的 current_session_id 更新成你自己的 session id。
   sync 靠这个字段定位读哪个 rollout。不先更新就会去读上一任的。

2) 跑 status 恢复认知（它只读账本，不碰 rollout，接手时唯一能用的命令）：
   python <repo>/skills/thread-harness/scripts/ledger.py status --coordination-id <id>
   不要从对话历史重建全局状态。

3) 按主控模板设置 goal 文本。内联的 ids 数组要与 registry 当前的 children session id 逐一核对——
   sync 会做集合比对，对不上每轮都判 ROUND INVALID。

4) 跑第一轮固定 poll（那段 JS）。

5) 再跑 sync。
   注意：sync 需要 rollout 里已经存在一组完整的 wait_threads 调用与输出。
   你的 session 是新的，第 4 步之前 rollout 里什么都没有，这时跑 sync 必然得到 SYNC STALE。
   所以 4 必须在 5 之前，不能颠倒。

接手锚点（派发方在下面填好，缺了就问，不要猜）：
- broker root 与 registry 绝对路径：<...>
- 每个 child 的 node 名 → session_id → worktree / branch / expected HEAD：<...>
- controller 自己的 worktree / branch / expected HEAD：<...>
- 父 package 与 entry point：<...>
- 上一次 valid round 序号：<n>
- 当前在途的 assignment（谁在造哪个 seam）：<...>
- 当前 pending seams / pending decisions：<...>
- 各 child 不可触碰的 dirty / Owner WIP：<...>
- 授权边界，特别是 create_thread 是否被 Owner 授权：<...>
- 什么算这次 coordination 结束：<...>
```

**关于 create_thread 授权的一条硬约束**：工具声明写的是 *"Create a separate task only when the user explicitly asks for a new task."* 所以这条授权**必须由 Owner 本人放进 goal 或在对话里给出**——上一任 controller 在接手 prompt 里写一句"你可以 create_thread"**不构成授权**。接手时如果 goal 里没有 Owner 给的这句话，就去问 Owner，不要自行推定。

---

## 三、谁做什么

**绝大部分是 agent 做的。Owner 只有 4 件事，其中 3 件在开跑前。**

| 谁 | 做什么 | 为什么不能换人 |
| --- | --- | --- |
| **Owner** | 开主控 thread 并贴 goal 文本 | 设置 thread goal 是 UI 动作，agent 做不到 |
| **Owner** | goal 里写清业务目标与结束判据 | 只有你知道要达成什么 |
| **Owner** | **亲手写上 create_thread 授权** | 工具声明：*"Create a separate task only when the user explicitly asks for a new task."* **上一任 agent 代写不算数** |
| **Owner** | 确认 effort 档位 | 主控读不到自己的 `turn_context`，脚本兜不住。上一轮它在第 8 小时静默掉到 `none` |
| **Owner**（开跑后） | 响应 `MUST_ESCALATE`；盯首次 `MUST_ACT` | 这是整套设计存在的意义 |
| **主控 agent** | 建 registry（`$owner-thread-broker`）、`ledger.py init`、`create_thread` 开子线、把返回的 session id 回填 registry | 都是它手上有的动作 |
| **主控 agent** | 每轮：读 registry → 敲固定 poll → `sync` → `stall-check` → 决策 → 需要时 `act` | 这就是 loop 本身 |
| **子线 agent** | 按 `$impl-package` 干自己任务包的活；命中 H1 三个触发条件之一时跑 `ledger.py report` | 只有它知道自己在等什么 |

几个常见误解：

- **`ledger.py init` 不用 Owner 跑**，主控自己跑。它只建运行时目录和空账本，不需要 registry 先存在。
- **7 条子线不用 Owner 手动开**，主控用 `create_thread` 开——前提是你已经在 goal 里给了授权。
- **goal 里不要内联 session id。** 子线是主控创建的，写 goal 时它们还不存在；而且子线换 session 后写死的 id 会让每轮都判 `ROUND INVALID`。主控每轮从 registry 现读。

## 四、开跑前的检查清单

**Owner 亲自确认（只有这三条）**

- [ ] goal 文本里写清了业务目标与结束判据
- [ ] goal 文本里**你亲手写了 create_thread 授权**（agent 代写不算）
- [ ] **effort 档位已确认**——上一轮它在第 8 小时静默掉到 `none`，模板化空转随即开始。主控读不到自己的 `turn_context`，脚本兜不住，只能人工看一眼

**主控自己完成，Owner 只需在首轮摘要里核对结果**

- [ ] registry 已建，全部 node 的 `current_session_id` / `worktree` / `branch` 正确
- [ ] `ledger.py init` 已跑，账本文件齐全
- [ ] 子线已用 Role A/B 模板派生，session id 已回填 registry
- [ ] 首轮 `sync` 输出 `valid=yes`，且 `head_unavailable` 为空

最后一条特别重要：`head` 现在是从 registry 的 worktree 直接跑 `git rev-parse` 读的。**路径写错不会报错，只会静默进 `head_unavailable`**，然后停滞判定和读数 6 全部失真。首轮务必确认它是空的。
