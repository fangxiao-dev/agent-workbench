# 总体判定：**修正后可用**

核心理念是成立的：Dispatcher 已经抓住了 **Topic 不是派发单元、每次只授权一个 baby step、返回不自动授权下一步、业务完成由 owning workflow 决定** 这几个关键点。

但目前还不能直接作为可靠的上游调度合同使用。问题不在于缺少更多概念，而在于控制面没有闭合：

1. Dispatcher 与 SDD 的 ownership 有实质重叠，并且已经出现规则不一致；
2. dispatch attempt、迟到/重复 return、in-flight、idle 等状态没有形成可执行的关联协议；
3. 现有 evals 主要验证理想路径，几乎发现不了上述控制面错误。

以下判断仅依据提供的文件内容，不假设仓库历史，也不假设未提供的 reference 文件会补足这些合同。

---

# P0

**无。**

没有明确证据表明该 Skill 在普通理想路径下必然失效，也没有发现会直接要求越权 mutation、绕过业务验收或造成不可逆副作用的设计。

---

# P1

## P1-1：Dispatcher 与 SDD 的 ownership 没有真正分开，并且已有直接规则冲突

**明确证据**

`skills/dispatcher/SKILL.md:8` 声明：

> Dispatcher 决定上游何时派什么，SDD 指导已派发 Topic 内的 dependency、mode、lane 与 lifecycle。

但 Dispatcher 随后自己处理了：

* dependency 与 authorization：`skills/dispatcher/SKILL.md:18, 22`
* resource admission 与 worktree：`skills/dispatcher/SKILL.md:22-23`
* worker lane 与 lifecycle：`skills/dispatcher/SKILL.md:28-33`

与此同时，SDD 也直接处理了上游调度职责：

* dependency 分类：`subagent-driven-development/SKILL.md:37-48`
* 当前批次与 fan-out：`subagent-driven-development/SKILL.md:50-54`
* lane 与 lifecycle：`subagent-driven-development/SKILL.md:56-68`
* return 消费与重排：`subagent-driven-development/SKILL.md:70-83`

而且已经存在两处不一致：

第一处是 worktree 决策人：

* Dispatcher：文件 ownership 交叉时“**由 SDD 判断**”能否隔离，见 `skills/dispatcher/SKILL.md:23`
* SDD：由“**caller 根据 write ownership 与资源交叉决定**”，见 `subagent-driven-development/SKILL.md:12`

第二处更严重，是 acceptance dependency 的作用范围：

* Dispatcher：acceptance“**只阻止正式验收和状态宣称**”，见 `skills/dispatcher/SKILL.md:22`
* SDD：acceptance dependency 阻止“**正式验收、evidence 采信和状态宣称**”，见 `subagent-driven-development/SKILL.md:42`

“只阻止”明确排除了 evidence 采信，因此这不是单纯详略差异。

**判断**

当前设计不是简单的“两个 Skill 共享原则”，而是两个 Skill 都在定义 admission、dependency、batch 和 lifecycle，只是抽象层级略有不同。只要二者分别维护，就会继续漂移；acceptance 规则已经证明这种漂移正在发生。

此外，“已派发 Topic 内的 dependency”本身也不成立。是否存在未回答的 foundation、resource 或 authorization dependency，必须在派发前决定，而不能等到“已派发”后才由下游方法判断。

**用户影响**

同一个候选动作可能因为加载了不同 Skill 而得到不同结果：

* 一处允许采信 evidence，另一处禁止；
* 一处认为 Dispatcher 已完成资源判断，另一处认为应交给 SDD；
* 上游可能在 dependency 尚未明确时就派发，或者两个 Skill 重复执行当前批次规划。

这会直接破坏 Skill 作为合同的唯一性。

---

## P1-2：缺少 dispatch attempt 身份与 return 幂等规则，迟到或重复 return 实际上没有被定义

**明确证据**

`skills/dispatcher/SKILL.md:24` 只处理了 receipt：

> 迟到、重复、来源不明或结果不确定的 receipt 先消除歧义。

但用户要求覆盖的是 receipt 之外的：

* 迟到 return
* 重复 return
* 被重试或替代 attempt 的旧 return
* 来源不明的 return

`skills/dispatcher/SKILL.md:25` 只说消费“可归因结果”，没有定义如何归因，也没有规定至少需要哪些身份：

* baby-step ID
* dispatch attempt ID
* Topic/lane
* worker/session ID
* 当前 attempt 与 superseded attempt 的关系

SDD 在 `subagent-driven-development/SKILL.md:72-77` 定义了 `DONE | BLOCKED | INCOMPLETE` 等结果状态，但同样没有 attempt correlation 或重复消费规则。

现有 eval 4 只覆盖“来源不明的 receipt”，没有覆盖迟到或重复 return；eval 5 只覆盖正常 return 后的 worker 复用。

**判断**

“可归因”目前只是要求，不是可执行规则。没有 attempt identity，就无法判断一个 return 是：

* 当前有效结果；
* 同一结果的重复投递；
* 已被 supersede 的旧 worker 的迟到结果；
* 另一个 Topic 或 lane 的错误回传。

**用户影响**

主控可能：

* 重复消费同一个 diff 或 evidence；
* 对同一 baby step 授权两次后续工作；
* 把旧 attempt 的结果覆盖到新 attempt；
* 重复执行 cleanup；
* 在 stale return 基础上推进 dependency chain。

涉及 mutation 时，这会从调度歧义升级为真实代码或外部状态冲突。

---

## P1-3：`idle`、调度轮次完成与仍有 in-flight worker 的状态没有区分

**明确证据**

`skills/dispatcher/SKILL.md:26`：

> 没有已解锁且合格的动作时进入 idle。

`skills/dispatcher/SKILL.md:35` 将调度轮次完成定义为：

* 所有 dispatch receipt 已确认或消除歧义；
* 所有**已返回**结果已消费；
* 最后一次扫描没有已解锁且合格的动作。

这里没有要求：

* 所有已接受的 dispatch 已经返回；
* 没有 active/in-flight worker；
* 没有等待中的 current attempt。

从逻辑上说，“所有已返回结果已消费”在一个 worker 尚未返回时也可以成立，因为当前根本没有 returned result。于是下面的状态满足现有条件：

1. receipt 已成功；
2. worker 正在运行；
3. 当前没有其他可派发动作；
4. 没有已返回结果需要消费。

此时 Dispatcher 可以同时判定“idle”和“调度轮次完成”。

**判断**

现在至少混合了三个不同概念：

1. **dispatch-idle**：现在没有新的可派发动作，但可能仍有 worker 在运行；
2. **quiescent**：没有 unresolved receipt、in-flight worker、未消费 return 或可派发动作；
3. **workflow closure**：业务工作是否整体完成，由 owning workflow 判断。

第 3 点已经正确外放，但前两点没有分开。

**用户影响**

调用方可能在 worker 尚未完成时：

* 停止等待或不再收集 return；
* 退役 worker/session；
* 释放共享资源或 cleanup owner；
* 向用户显示“当前工作已结束”；
* 错误触发整体 closure 检查。

---

## P1-4：现有 evals 不能覆盖或发现主要控制面错误

**明确证据**

当前五个 eval 的覆盖范围是：

* eval 1：多个可独立材料面的拆分；
* eval 2：宽检索、窄结论；
* eval 3：多文件 coherent outcome；
* eval 4：当前批次、来源不明 receipt、正常 return 后重扫；
* eval 5：同 Topic worker 复用与新 Topic fresh worker。

没有任何 eval 覆盖：

* foundation / acceptance / resource / authorization dependency 的差异；
* acceptance 未满足时 evidence 能否被采信；
* 文件 worktree 隔离不了 DB、端口、测试数据等共享资源；
* failed/rejected dispatch；
* worker crash、cancel、lost；
* retry 与 superseded attempt；
* 迟到、重复或来源不明的 return；
* in-flight worker 存在时能否进入 idle；
* `BLOCKED` / `INCOMPLETE` return；
* residue 或 cleanup 未完成；
* review lane 与 work lane 的独立性；
* Task Queue 与业务状态机的 ownership 边界。

eval 4 虽然提到了 receipt 歧义，但没有给出歧义最终解析为“成功”还是“失败”。这两种结果对应完全不同的后续状态：

* 成功：该 attempt 应进入 in-flight；
* 失败：该动作可能重新成为候选；
* 未解决：不能满足轮次完成条件。

当前 expected output 只要求说“先消除歧义”，没有要求输出明确的状态转移。

**判断**

仅从 `evals.json` 可见的场景与断言判断，一个实现即使存在以下错误，也可以通过全部五个 eval：

* 接受 superseded worker 的迟到 return；
* 重复消费同一个 return；
* worker 仍在运行时宣布 idle；
* acceptance 未满足时采信 evidence；
* 两个 worktree 同时写同一个测试数据库。

**用户影响**

Skill 文档后续即使被错误修改，evals 仍会给出“通过”的假安全感。对调度 Skill 来说，这比普通文档覆盖不足更危险，因为错误集中在低频但高影响的异常路径。

---

# P2

## P2-1：触发范围描述过窄，并与 AGENTS、SDD 的触发范围重叠

**明确证据**

Dispatcher 的 frontmatter 描述为：

`skills/dispatcher/SKILL.md:3`

> 当主控需要……使用 subagent fan out 时……

但实际正文还负责：

* 单个 dispatch receipt；
* worker return；
* lifecycle；
* idle；
* 同一 dependency chain 的串行释放。

这些情况不一定存在 fan-out。

AGENTS 的定义更宽：

`AGENTS.md:34`

> 用于 upstream controller scheduling：baby-step admission、current batch、dispatch receipt、worker return、Topic lifecycle 和 idle。

同时 SDD 的 frontmatter 在 `subagent-driven-development/SKILL.md:3` 中，对任何“使用 subagent、异步或并行”的请求都可能触发；其正文又包含当前批次与 fan-out。

**判断**

单 worker 串行调度、receipt 歧义处理或 idle 判断时，Dispatcher 可能因为“不属于 fan-out”而不被触发；而初次要求使用 subagent 时，SDD 又可能先于 Dispatcher 被选中。

**用户影响**

实际路由会依赖宿主对 description 的语义匹配，而不是稳定的职责边界。结果可能是：

* 应加载 Dispatcher 时只加载 SDD；
* 两个 Skill 同时介入 upstream admission；
* 顺序和责任因宿主而异。

---

## P2-2：baby-step 规则容易过度拆分，并与“全部 fan-out”组合成无背压调度

**明确证据**

`skills/dispatcher/SKILL.md:14` 使用了强制规则：

> 任一材料面、判断项或交付部分，只要能……独立消费，它就是另一个 baby step；此时继续切分。

`skills/dispatcher/SKILL.md:23` 又要求：

> 把全部互不依赖且资源隔离的合格 baby steps 组成当前批次并 fan out。

eval 1 明确固化了“多个材料族分别派发，主控综合”的期望。

虽然 `skills/dispatcher/SKILL.md:16` 排除了按文件数和检索范围机械切分，但没有处理另一类成本：

* 共享 comparison context；
* 同源证据重复读取；
* 跨材料异常只能通过横向比较发现；
* 宿主并发槽位；
* provider rate limit；
* token 与调度成本；
* 主控综合成本。

**推断**

该规则把“可以独立返回”近似等同于“应该独立派发”。两者并不等价。

例如，同一个规范文件中的三个相互关联判断可以分别返回，但拆成三个 worker 后，可能重复读取全部上下文，并且没人负责发现三项之间的矛盾。再与“全部 fan-out”结合，候选数量大时会产生派发爆炸。

**用户影响**

可能出现：

* 大量微型 worker；
* 重复取证和重复上下文加载；
* 综合成本高于执行成本；
* 不同 worker 使用不一致的 comparison point；
* 超过宿主并发或额度限制。

更稳妥的门槛应是“一个 bounded outcome”，而不是“任何可以独立表达的子结论都必须成为独立 dispatch”。

---

## P2-3：worker lifecycle 只覆盖正常复用和退役，没有覆盖异常终止与跨宿主能力差异

**明确证据**

`skills/dispatcher/SKILL.md:30-33` 只定义：

* 同 Topic 何时复用 live worker；
* review/test worker 何时复用；
* 新 Topic 使用 fresh worker；
* Topic 结束或 scope 变化时退役。

没有定义：

* receipt 成功后 worker 未启动；
* worker crash 或连接丢失；
* worker 被宿主取消；
* caller 主动 cancel；
* worker 长期失联后的状态；
* ownership 何时释放；
* cleanup 完成前能否 retry；
* 宿主不支持 persistent/live worker 时如何降级。

AGENTS 又明确该仓库面向多个宿主，见 `AGENTS.md:3, 12`。不同宿主未必都支持对同一 live worker 继续 follow-up。

SDD 在 `subagent-driven-development/SKILL.md:60` 提到“持续卡住”可换 worker，但没有给出 attempt、cleanup 和 ownership 的过渡规则。

**判断**

正常生命周期是清楚的，异常生命周期没有闭合。这里不需要复杂的 worker supervisor，但至少要定义“何时判定旧 attempt 终止、何时允许释放 ownership 和创建新 attempt”。

**用户影响**

主控可能在旧 worker 仍有副作用能力时重派新 worker，或者相反，因为无法证明旧 worker 已终止而永久卡住。

---

# P3

## P3-1：若干关键条件无法被观察性判定

**明确证据**

以下术语承担了控制作用，但没有最小判定标准：

* “ownership 与上下文可信”：`skills/dispatcher/SKILL.md:30`
* “scope/ownership 实质变化”：`skills/dispatcher/SKILL.md:30`
* “同一有界 campaign”：`skills/dispatcher/SKILL.md:32`
* “保留下游动作”：`skills/dispatcher/SKILL.md:22`
* “live worker”与“test wrapper”：`skills/dispatcher/SKILL.md:30, 32`

SDD 使用的是 “test lane”，Dispatcher 使用 “test wrapper”，见 `subagent-driven-development/SKILL.md:62` 与 `skills/dispatcher/SKILL.md:32`。

**判断**

这些概念本身合理，但两个独立主控可能对同一状态作出不同判断。例如 worker 已修改了 write-set、comparison point 发生变化、或 review scope 增加一个文件时，是否仍算“同一 scope”并不明确。

**用户影响**

主要是实现一致性和可维护性问题，不会单独导致系统不可用，但会增加跨宿主行为漂移。

---

# 已做得好的地方

第一，**Topic 与派发单元的区分是正确的**。`skills/dispatcher/SKILL.md:12` 和 `subagent-driven-development/SKILL.md:8, 16` 都明确 Topic 是连续上下文容器，而一次 dispatch 只授权当前动作。这能避免把整条需求链一次性交给 worker。

第二，**没有按文件数量或检索范围机械划分任务**。Dispatcher 第 14—16 行配合 eval 2、eval 3，有效区分了：

* 全仓搜索一个窄事实；
* 多文件共同形成一个不可分割 outcome；
* 多个真正可独立消费的材料面。

这部分 eval 设计是有效的。

第三，**return 不自动授权后续动作**表达得很清楚。`skills/dispatcher/SKILL.md:25` 与 SDD 第 20、72 行一致，主控必须先消费结果，再重新 admission。这是防止 worker 自行扩权的关键规则。

第四，**资源冲突没有被简化为文件冲突**。SDD 第 12、52—54 行明确提到 DB、端口、测试数据和外部记录，且说明 worktree 只解决文件隔离。原则正确，问题只是应该明确由谁在派发前作最终判断。

第五，**Task Queue 与业务状态机的顶层边界基本正确**：

* `AGENTS.md:35` 把 Task Queue 限定为显式队列持久化；
* `skills/dispatcher/SKILL.md:26` 把业务状态、验收和 closure 留给 owning workflow；
* `subagent-driven-development/SKILL.md:79` 把 worker 结果限定为 Topic-local facts。

目前没有证据表明 Dispatcher 正在夺取 Ticket、业务 acceptance 或整体 closure 的 ownership。

第六，**work/review lane 独立、新 Topic fresh worker**的原则在 Dispatcher 与 SDD 中基本一致。这是一个好的默认安全边界。

---

# 最小修改建议

不需要引入完整 Task Queue、事件总线或复杂 orchestrator。最小修改可以控制在一个 ownership 段落、一组状态定义和三个 eval。

## 1. 只保留一个规则 owner

把边界明确成：

* **Dispatcher**：candidate admission、dependency/resource 决策、current batch、dispatch attempt、receipt、return correlation、dispatch-idle/quiescence；
* **SDD**：已 admission 的单个 baby step 如何写 brief、选择 mode、组织 work/review/test lane、执行 focused verification；
* **Task Queue**：只有显式请求时持久化已 admission 的 steps，不参与裁决；
* **Owning workflow**：业务状态、acceptance、Gate 与整体 closure。

dependency taxonomy 应只在一个地方完整定义，另一个 Skill 直接引用，不应各写一个简化版本。尤其要统一 acceptance dependency 是否阻止 evidence 采信；从 SDD 现有语义看，更安全的表述是：

> 可以接收和检查 evidence，但在 acceptance dependency 未解除前，不得将其采信为 canonical evidence，也不得据此正式验收或宣称状态。

## 2. 增加最小 dispatch attempt 合同

不需要复杂 schema，只需明确每次 dispatch 至少绑定：

`step_id + attempt_id + topic_id + lane + worker/session identity`

并补充四条规则：

1. receipt 只有在能绑定当前 attempt 时才算成功；
2. return 只有匹配当前有效 attempt 才可消费；
3. 同一 attempt 的重复 return 幂等处理，只消费一次；
4. superseded、未知或迟到 return 隔离记录，不更新状态、不授权后续工作。

## 3. 把 idle 拆成两个调度状态

建议使用：

* **dispatch-idle**：当前没有可 admission 的新动作，但允许存在 in-flight worker；
* **quiescent**：没有 unresolved receipt、in-flight attempt、未消费 return 或可 admission 动作；
* **workflow closure**：继续由 owning workflow 判断。

这样既不夺取业务 closure，也不会把“暂时无新任务”误判为“调度已完全静止”。

## 4. 放松强制拆分，并给 fan-out 增加容量条件

将“只要可以独立消费就必须拆分”改为：

> 可以独立消费是拆分信号；只有单独返回具有独立消费者、dependency 顺序、风险隔离或验证价值时才必须拆分。共享 comparison context 或拆分成本显著时，可以保留为一个 bounded outcome。

当前批次也不应要求无条件派发“全部”合格动作，而应允许：

> 当前批次包含全部合格动作，实际 dispatch 可以在宿主容量、成本和并发配额内分 wave 释放；未释放动作保持 admitted，不视为 dependency blocked。

## 5. 为异常 worker 增加一个最小退役条件

至少明确：

* 宿主明确报告 failed/cancelled/lost；
* caller 完成或确认无需 cleanup；
* 旧 attempt 的 mutation capability 已终止或被隔离；

三者满足后，才允许释放 ownership 并创建新 attempt。宿主不支持 live worker 复用时，使用 fresh worker 加有界 handoff context，而不是把“复用”设为必要条件。

---

# 最值得新增的 3 个 eval

## Eval 6：retry 后收到迟到且重复的旧 return

**场景**

一个 baby step 的 `attempt-a1` receipt 成功。随后宿主明确报告 a1 已失败，并确认其 mutation capability 已终止、cleanup 完成。主控创建 `attempt-a2`，a2 正常返回并已消费。之后 a1 又迟到返回两次，且带有 diff 和 focused test 结果。

**必须判定**

* a1 已被 supersede；
* 两次 a1 return 都不能被消费为当前结果；
* 不得合并其 diff、采信其 evidence 或授权下一步；
* 第二次 a1 return 还必须被识别为重复；
* 只有 a2 的结果能驱动后续 admission。

**能发现的错误实现**

* 没有 attempt identity；
* last-write-wins；
* 重复 return 被消费两次；
* stale return 自动授权 follow-up。

---

## Eval 7：没有新动作，但仍有 in-flight worker

**场景**

两个已 admission 的 baby steps 均获得成功 receipt，两个 worker 都仍在运行。当前扫描没有其他已解锁且合格动作，也没有已返回结果。

**必须判定**

* 可以称为 dispatch-idle；
* 不能称为 quiescent；
* 不能称为调度完全结束；
* 不能据此宣称业务 closure；
* worker return 后仍需消费并重新扫描。

随后补充两个 worker 都已返回、结果已消费、无 unresolved receipt、无新动作，才允许判定 quiescent；整体 closure 仍交给 owning workflow。

**能发现的错误实现**

* 利用“所有已返回结果已消费”的空真值提前完成；
* 把 idle 等同于没有 active worker；
* Dispatcher 越权宣称业务完成。

---

## Eval 8：dependency、共享资源与 Skill ownership 的交叉场景

**场景**

当前有三个候选动作：

1. A 会绑定一个尚未稳定的 foundation 数据形状；
2. B 只准备可回收、资源隔离的 fixture，但 acceptance dependency 尚未解除；
3. C 与 D 位于不同 worktree、文件 write-set 不交叉，但会同时修改同一个共享测试数据库。

没有显式 `task-queue.json` 或 queue CLI 请求。

**必须判定**

* A 保持未释放；
* B 可以作为独立 baby step 派发，但其结果只能收集和检查，不能在 acceptance 解除前采信为 canonical evidence 或宣称状态；
* C 与 D 仍需串行，因为 worktree 不隔离共享数据库；
* admission 和串行决策由 Dispatcher/caller 在派发前完成；
* SDD 只指导已 admission 动作的 mode、brief 和 lane；
* 不应自动创建或修改 Task Queue；
* 不应更新业务状态或宣称 closure。

**能发现的错误实现**

* 把 acceptance 当成所有 dispatch 的 blocker；
* 把收到 evidence 等同于采信 evidence；
* 认为不同 worktree 就一定可以并行；
* 把资源 admission 推给已派发 worker；
* Dispatcher 越权持久化队列或修改业务状态。
