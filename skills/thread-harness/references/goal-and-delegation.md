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

1) 敲这段 JS，原样敲，不要"优化"它：

const ids=[<各 node 的 current_session_id>];
const r=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),timeoutMs:180000});
text(JSON.stringify({v:1,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({id:p.thread?.id,status:p.thread?.status?.type,turn:p.latestTurn?.id,turnStatus:p.latestTurn?.status,txt:(p.latestAssistantMessage?.text||"").slice(0,500)}))}));

字段一个都不能少。你不打印的东西 ledger.py 读不到——rollout 记录的是你打印的内容，不是工具的原始返回。

2) python <repo>/skills/thread-harness/scripts/ledger.py sync --coordination-id <coordination-id> --round <n>
3) python <repo>/skills/thread-harness/scripts/ledger.py stall-check --coordination-id <coordination-id>
4) 按 stall-check 退出码走：
   0 → 按 sync 摘要正常决策
   2 MUST_ACT → 见下方"不可违反"第 1 条
   3 MUST_ESCALATE → 立即向我报告 pending 决策，本轮结束

### 不可违反

1. stall-check 返回 2 时，你只有两个选项：派发新工作（含 create_thread 开新 Foundation 线），
   或向我报告并结束 loop。禁止输出"继续等待"、"本轮无变化"、"保持现状"这类第三选项。
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
| 「loop模式：wait threads -> 每隔3min检查」 | 自然语言的时间词不会变成阻塞语义。实测 1707 次调用里只有 5 次真用了 180000ms，964 次用的是 0 或 1000ms，退化成 13 秒一轮的忙等 | 写成参数 `timeoutMs: 180000`，并给出原样片段 |
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
   ledger.py sync 是靠这个字段去定位要读哪个 rollout 的。不先更新，第一次 sync 会去读上一任的 rollout。
2) 再跑 sync 恢复全局状态，不要从对话历史重建：
   python <repo>/skills/thread-harness/scripts/ledger.py sync --coordination-id <id> --round <n>
3) 按 references/goal-and-delegation.md 的主控模板重新设置 goal 文本，
   其中内联的 ids 数组要与 registry 当前的 children session id 逐一核对——
   sync 的自检会做集合比对，对不上会每轮判 ROUND INVALID。

接手时你需要知道的锚点（派发方在下面填好）：
- controller worktree / branch / expected HEAD：<...>
- 父 package 与 entry point：<...>
- 当前 round 序号：<n>
- 当前 pending seams / pending decisions：<...>
- 授权边界与不可改的 Owner WIP：<...>
- 什么算这次 coordination 结束：<...>
```

---

## 三、开跑前的检查清单

- [ ] registry 已建，全部 node 的 `current_session_id` / `worktree` / `branch` 正确
- [ ] `ledger.py init --coordination-id <id>` 已跑，三个 jsonl 存在
- [ ] **effort 档位确认**（上一轮它在第 8 小时静默掉到 `none`，模板化空转随即开始；主控读不到自己的 turn_context，这条只能人工确认）
- [ ] goal 文本里的 `ids` 数组与 registry 一致
- [ ] 各子线已用对应模板派生，且首条回报已收到
