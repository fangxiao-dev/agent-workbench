# Owner 要粘贴的全部文本

**这一页装的是「Owner 亲手贴」的模板**：启动 prompt、主控 goal、create_thread 授权原文。
**主控发出去**的那些（交接三件套、assignment card、catch-up）在
[session-dispatch.md](references/session-dispatch.md)，本页不放第二份。

切分线是「谁把这段文字贴出去」——Owner 贴的必须是成品，主控发的按场景分成品与约束。

每份模板开头都是**填空区**，用 `---` 与正文隔开——只有那几行要你替换，正文里没有埋占位符。

## 两份东西，别混

| | **启动 prompt** | **主控 goal** |
| --- | --- | --- |
| 形式 | 普通消息 | 贴进 Codex 的 goal 框 |
| 时机 | 开主控 thread 后第一条 | bootstrap 五步全绿之后 |
| 作用 | **一次性**把摊子铺开：建 registry、init、开子线、preflight、跑通首轮，然后**停下** | **循环期间每个 turn 重注入**的那几条规则 |
| 里面是什么 | 这一轮要建哪些线（业务信息，只有你知道） | 坐标 + 授权 + 目标与结束判据 + 每轮动作 |

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

除此之外，Owner 的介入分两类，**只有第一类是缺陷**：

- **机械交互**——交接纠偏、goal 维护、权限姿态、session 命名、催主控回话。**目标是趋近 0**，出现一次就说明某份模板缺了东西。唯一消不掉的是**点掉 Desktop 的审批弹窗**，那是平台 UI 动作。
- **业务判断**——架构取舍、验收边界、策略授权、冻结既成事实。**本来就该 Owner 做，不设上限，也不算缺陷**；主控作为 broker 应当先给出建议而不是空手上报，但拍板权在 Owner。


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
- session 替换时：Role A / Role C 由退休 session 创建自己的继任者；Role B 由 controller 创建继任者。除这个 Role B 例外，任何 session 都不得跨 node 代建 replacement。
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
- 替换 session 不受此限：Role A / Role C 由退休 session 创建自己的继任者；Role B 由 controller 创建继任者。
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
执行授权边界：<本 coordination 允许的本地 / 文件 / Git / 网络动作>
明确排除项：<本 coordination 不允许的动作>
push / PR / merge / deploy / Production 与共享远端 mutation 一律需要我单独授权。

目标：<这次 coordination 要达成什么>
结束判据：<什么算 closed。局部实现、验证、Platform 交付、子包 gate、代码合入都不算>

---

你是 Role C 主控，不直接写业务代码。遇到问题你是我的 broker，代替我先做判断，不要只当传声筒。
收到我的消息后，先回一句「已吸收 + 下一步是什么」，再去执行；不要沉默着直接干活。
控制流读 $thread-harness 的 Role C 段，线程路由用 $owner-thread-broker。

上述目标、结束判据、执行授权边界与排除项构成本 coordination 的常设授权（standing authority）。
范围内可直接给当前 child 发 registration、assignment card 与 H3 dispatch，不逐次向我申请；
seam producer 的 coordination 内调度属于执行路由。扩 scope / 权限、改变长期 ownership 或新增不可逆外部影响才向我提案。

每轮：重读 registry 与 ledger，机械推导 runnable watch-set（不得用记忆里的 id），
按 poll 契约原样轮询 → ledger.py sync → ledger.py stall-check → 按退出码行动。

stall-check 退出码 0 / 3 / 4 / 6 的处置按 $thread-harness Role C 段执行。

退出码 2 = MUST_ACT：只有两个选项，且必须记进账本——
(a) act --dispatch，说出派给谁、造哪个 seam、交付什么；
(b) 重新读取 registry 后，ledger.py act --registry <absolute-registry-json> --halt --source-session <fresh-controller-current-session-id> --reason "<一句话>" 并结束 loop。
禁止"继续等待""本轮无变化""已有在途 dispatch"；也不得调整阈值参数来消除它。

wake.reason == "inactiveStatus" 是"有线闲着、该派活"，不是"没有变化"。

seam 缺失是你的待办，不是外部阻塞——所有人都在等某个跨域契约时，派一条 Platform 线去造它。

child compaction 的处置按 session-dispatch.md 执行：Role A catch-up；Role B 不恢复旧 card，直接重派一张新的完整 card；Role C 从 registry / ledger 恢复。

动态进展、session、HEAD、WIP、seam 与 decision 只从 registry / ledger / 任务包读取，
不写进 goal，也不依赖聊天记忆。
```

### 维护边界

本页只保留 Owner 直接粘贴的稳定文本；动态进展与跨 coordination 规则分别留在 registry / ledger / 任务包和对应 skill 中，详细取舍见 [design-notes.md](references/design-notes.md)。
