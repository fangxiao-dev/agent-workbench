# Owner 要粘贴的全部文本

**这一页是唯一的模板来源，其他文件只指过来、不放第二份。**

每份模板开头都是**填空区**，用 `---` 与正文隔开——只有那几行要你替换，正文里没有埋占位符。

## 两份东西，别混

| | **启动 prompt** | **主控 goal** |
| --- | --- | --- |
| 形式 | 普通消息 | 贴进 Codex 的 goal 框 |
| 时机 | 开主控 thread 后第一条 | bootstrap 五步全绿之后 |
| 作用 | **一次性**把摊子铺开：建 registry、init、开子线、preflight、跑通首轮，然后**停下** | **循环期间每个 turn 重注入**的那几条规则 |
| 里面是什么 | 这一轮要建哪些线（业务信息，只有你知道） | 每轮三步 + 8 条不可违反 + 目标与结束判据 |

**两份都带 coordination_id / registry / 授权，这是刻意重复不是冗余**：goal 是全系统唯一免疫 compaction 的通道，启动 prompt 会被压缩掉，所以循环期间还要用到的锚点必须在 goal 里再写一遍。

## 什么该进 goal

goal 是全系统**唯一免疫 compaction 的通道**（每 turn 原样重注入），也是最贵的位置：每一行都乘以轮数重复付出。**长文本会稀释真正关键的那几句——全是重点等于没有重点。**

判据只有一条：

> **忘了会让系统「安静地失效」的，进 goal；忘了只是「做得差一点」或者「会立刻报错」的，留在 skill。**

所以这里的每一条都对应一次真实失效，机制说明、命令语法、完整退出码表全部留在 [poll-contract.md](references/poll-contract.md) 与 [design-notes.md](references/design-notes.md)。文末「明确不进 goal」记录了逐条裁剪理由。

## 贴之前

**Role C 的 goal 不要在子线还没建好时就贴。** goal 一设就自驱循环，此时 registry 里没有 children，每轮都判 `ROUND INVALID`，从第一分钟起污染读数。完整冷启动顺序见 [run-procedure.md §四](references/run-procedure.md)。

## Owner 粘贴清单（你手工要做的全部动作）

| 时机 | 贴什么 | 本文件哪一节 |
| --- | --- | --- |
| 开主控 thread 后第一条消息 | 启动 prompt，里面嵌一份授权原文 | §启动 prompt + §create_thread 授权原文 |
| bootstrap 五步全绿之后 | 主控 goal（填空区里再嵌一份授权原文） | §主控 goal |
| 每次主控换 session | 主控 goal，**授权原文要重贴** | §主控 goal |

除此之外你只有三件反应式的事：**响应 `MUST_ESCALATE`**、**点掉 Desktop 的审批弹窗**、**盯首次 `MUST_ACT`**。

> **主控没法在你睡觉时换掉自己**——继任者拿不到 goal（设 goal 是 UI 动作，agent 做不到）。所以无人值守的运行时长上限不是工作量，而是主控的上下文预算。

---

## 启动 prompt（普通消息，不是 goal）

新开主控 thread 后第一条就贴这个。它只做 bootstrap，不启动轮询循环。

```text
coordination_id：<YYMMDDHH>-<slug>
registry：<registry 的绝对路径 .json>
父包 entry：<绝对路径>

要建的线（node 名 → 任务包或 seam → worktree → branch，一个 node 一套，不得共用）：
<列出来>

授权：
<贴下面「create_thread 授权原文」整段>

---

使用 $thread-harness 和 $owner-thread-broker。你是 Role C 主控。

本轮只做 bootstrap 与 readiness：不要开始轮询循环，不要设置 goal，做完停下等我。

按顺序做：
1. 建 registry，按上面的清单填好每个 node 的 node 名 / worktree / branch。
2. ledger.py init
3. 按 references/session-dispatch.md 的两阶段契约建子线，把返回的 session id 回填 registry。
4. ledger.py preflight，必须 PREFLIGHT OK。
5. 跑一轮固定 poll，然后 ledger.py sync，确认 valid=yes 且 head_unavailable 为空。

只回报一个简表：每个 node 的 session id / worktree / branch / HEAD，
以及 preflight 与首轮 sync 的结果。然后停下。
```

**第 3 步那份清单必须你来列**——主控不知道你想开几条线、每条对应哪个任务包。这是业务信息。

## create_thread 授权原文

工具声明是 *"Create a separate task only when the user explicitly asks for a new task."*，所以必须有你本人写下的一段话。**上一任 controller 在接手 prompt 里写「你可以 create_thread」不构成授权。**

默认版：

```text
create_thread 授权（我，Owner，明确给出）：

- 允许你在下列情况调用 create_thread：
  ① 某个 seam 在账本里查不到 producer，需要开一条新的 Foundation 线去造；
  ② 某条线需要替换 session。
- 允许各条子线为它自己创建继任者；不得为其他 node 创建任何 thread。
- active children 上限 8，达到上限后要新开线必须先退休一条。
- 不得为 review、审计或调研创建 thread——那些走 $do-review 与 $call-grok。
- 除以上情形外不得创建 thread。
```

带 first-wave gate 的版本（想先看一眼再放开，这一轮用的就是它）：

```text
create_thread 授权（我，Owner，明确给出）：

- bootstrap 阶段：允许你创建我列出的那些线，仅这些。
- 之后：在我确认 first wave 结果之前，不得再创建任何新的 Foundation 线；
  需要新线时向我报告并等待。
- 替换 session 不受此限：任何时候都允许某条线为它自己创建继任者。
- 不得为 review、审计或调研创建 thread。
```

---

## 主控 goal（贴进 goal 框的就是这一段）

```text
coordination_id：<id>
registry：<registry 的绝对路径 .json>
父包 entry：<绝对路径>

授权：
<贴本文件「create_thread 授权原文」整段>
push / PR / merge / deploy / Production 与共享远端 mutation 一律需要我单独授权。

目标：<这次 coordination 要达成什么>
结束判据：<什么算 closed。局部实现、验证、Foundation 交付、子包 gate、代码合入都不算>

---

你是 Role C 主控，不直接写业务代码。
控制流读 $thread-harness 的 Role C 段，线程路由用 $owner-thread-broker。
下面这几条是硬规则，其余按 skill 走。

每轮：重读 registry 取全部 active children 的 current_session_id（不得用记忆里的 id），
按 poll 契约原样轮询 → ledger.py sync → ledger.py stall-check → 按退出码行动。

不可违反：

1. stall-check 返回 2 时只有两个选项，且必须记进账本：
   (a) 派发新工作 → act --dispatch，要说出派给谁、造哪个 seam、交付什么
   (b) 报告我并结束 loop → act --halt --reason "<一句话>"
   禁止"继续等待""本轮无变化""保持现状"。(a) 的三个字段填不出来就选 (b)。

2. 同一条决策上报过一次就够。已上报的 pending 不再屏蔽 MUST_ACT；
   决策没人应答而全线又没推进时，正确动作是 (b)，不是每轮重复上报同一条。

3. 退出码 4 = HALTED：loop 已终止，停止轮询等我，不要自行恢复。

4. wake.reason == "inactiveStatus" 是"有线闲着、该派活"，不是"没有变化"。

5. seam 缺失是你的待办，不是外部阻塞。所有人都在等某个跨域契约时，
   正确动作是派一条 Foundation 线去造它。

6. 不要让 Foundation 线"保持待命"——让生产者等消费者会闭成死锁。

7. 一个 node 一个 worktree 一个 branch。

8. 不自己做审计。
```

---

## 为什么没有子线 goal

**只有主控有 goal。Role A / Role B 不设 goal，这是实测结论，不是省事。**

2026-08-01 试过给 child 加 goal，跑了半小时**进入死循环**，随后撤掉，撤掉后影响不大。原因是角色本身冲突：

- **child 是被动接受调度的**。goal 会让它每个 turn 都被推着「朝目标推进」，而它此刻正确的状态可能就是等主控派活——两股力互相拉扯，就转起来了。
- 理论上可以把 goal 写成「保持 stand down 直到另有指示」，但那等于用最贵的通道（每 turn 重注入）去表达「什么都别做」。
- 而且 child 有很多条，**每次交接后都要手动贴一遍 goal**，成本高到不成比例。

不加 goal 的代价，是 child 的角色规则会随 compaction 流失（平台缺口，见 design-notes §9.3）。现在这条被交接链路兜住了：

> skill 定义角色 → compaction 侵蚀 → 主控从 `never_reported` / `stale_reports` / `session_age_h` 看出这条线不对劲 → 触发自交接 → 新 session 重新读 skill

**变蠢是可恢复的，失控才不可恢复**——而交接机制现在能兜住前者，所以这个代价可以接受。

子线的角色定义在 `$thread-harness` 的 Role A / Role B 段，派发时由 [session-dispatch.md](references/session-dispatch.md) 的第二阶段 prompt 交给它。

## 明确不进 goal（记录裁剪理由）

写下来是为了避免下一轮有人把它们重新加回去。

| 被砍的内容 | 为什么不进 goal |
| --- | --- |
| `ledger.py` / `poll-contract.md` 的绝对路径 | 调用 `$thread-harness` 时平台会把 skill 路径一并给出，goal 里再写一遍是重复 |
| 各子命令的完整参数示例 | 拼错退 `64`，`--state` 传错会抛错并列出合法值。**响亮、自我修正**，不是静默失效 |
| 完整退出码表（0 / 1 / 3 / 64） | 命令本身就打印 `OK` / `MUST_ACT` / `MUST_ESCALATE` 等 token，语义自带。只有 `2` 和 `4` 的**后果**会被忘掉，所以只留这两条 |
| `CHECK_HEARTBEAT` 判定细节与 `heartbeat` 用法 | 忘了的后果是 streak 照常爬、`MUST_ACT` 提前触发——响亮。实跑印证：上一轮 goal 从未提过它，主控靠 skill 正确处理了 9 次 |
| "impl/investigate 优先 $call-grok、review 走 $do-review" | 忘了只是上下文用得更快，属于"做得差一点"。**这条是判断题**：子线没有 goal（见上一节），所以它只能留在 skill 与派发 prompt 里 |
| seam / 停滞 / 轮询机制的原理解释 | goal 只给结论与禁令。要理解"为什么"读 `design-notes.md` |
| 具体的 session id | 子线是主控创建的，写 goal 时还不存在；写死的 id 在换 session 后会让每轮判 `ROUND INVALID`。**每轮从 registry 现读** |
