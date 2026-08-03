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

两份都带 `coordination_id` / registry / 授权，**这是刻意重复，不要删**。

## 贴之前

**Role C 的 goal 不要在子线还没建好时就贴。** goal 一设就自驱循环，此时 registry 里没有 children，每轮都判 `ROUND INVALID`，从第一分钟起污染读数。完整冷启动顺序见 [run-procedure.md §四](references/run-procedure.md)。

## Owner 粘贴清单（*用户*手工要做的全部动作）

| 时机 | 贴什么 | 本文件哪一节 |
| --- | --- | --- |
| 开主控 thread 后第一条消息 | 启动 prompt，里面嵌一份授权原文 | §启动 prompt + §create_thread 授权原文 |
| bootstrap 五步全绿之后 | 主控 goal（填空区里再嵌一份授权原文） | §主控 goal |
| 要让某条 session 退休 | 触发消息 | [session-dispatch.md](references/session-dispatch.md) §触发消息 |
| 每次主控换 session | 主控 goal，**授权原文要重贴** | §主控 goal |

除此之外，*用户*只有三件需要反应的事：**响应 `MUST_ESCALATE`**、**点掉 Desktop 的审批弹窗**、**盯首次 `MUST_ACT`**。
其余的动作理论上都应该可以由*主控*thread作为broker来完成。


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
  ① 某个 seam 在账本里查不到 producer，需要开一条新的 Platform 线去造；
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
- 之后：在我确认 first wave 结果之前，不得再创建任何新的 Platform 线；
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
结束判据：<什么算 closed。局部实现、验证、Platform 交付、子包 gate、代码合入都不算>

---

你是 Role C 主控，不直接写业务代码。
控制流读 $thread-harness 的 Role C 段，线程路由用 $owner-thread-broker。
下面这几条是硬规则，其余按 skill 走。

每轮：重读 registry 与 ledger，机械推导 runnable watch-set（不得用记忆里的 id），
按 poll 契约原样轮询 → ledger.py sync → ledger.py stall-check → 按退出码行动；watch-set 为空时不执行虚假的阻塞 wait，直接选择派发或 halt。

不可违反：

1. stall-check 返回 2 时只有两个选项，且必须记进账本：
   (a) 派发新工作 → act --dispatch，要说出派给谁、造哪个 seam、交付什么
   (b) 报告我并结束 loop → act --halt --reason "<一句话>"
   禁止"继续等待""本轮无变化""保持现状"。(a) 的三个字段填不出来就选 (b)。

2. 每次 `decide --raise` 都有新的 `decision_instance_id`；`act --escalate` 只绑定当前 pending instance。已上报的 pending 不再屏蔽 MUST_ACT；
   决策没人应答而全线又没推进时，正确动作是 (b)，不是每轮重复上报同一 instance。

3. 退出码 4 = HALTED：loop 已终止，停止轮询等我，不要自行恢复。

4. 退出码 6 = LEDGER INTEGRITY FAILED：停止所有状态推进，保留坏账本供诊断，不截断、不重写、不猜测修复。

5. wake.reason == "inactiveStatus" 是"有线闲着、该派活"，不是"没有变化"。

6. seam 缺失是你的待办，不是外部阻塞。所有人都在等某个跨域契约时，
   正确动作是派一条 Platform 线去造它。

7. 不要让 Platform 线"保持待命"——让生产者等消费者会闭成死锁。

8. 一个 node 一个 worktree 一个 branch。

9. 不自己做审计。
```
