---
name: dispatcher
description: 当主控需要先形成 Topic、再选择当前 baby step 并使用 subagent fan out 时提供轻量上游调度指导。
---

# Dispatcher

Dispatcher 面向上游主控，指导 Topic-first admission、当前批次、dispatch、worker return 与 idle。它与 `/impl-package:subagent-driven-development` 平级：Dispatcher 决定上游何时派什么，SDD 指导已派发 Topic 内的 dependency、mode、execution lane 与 lifecycle。

## Topic-first 派发门槛

**先形成 Topic，再选择当前 baby step。** Topic 是共享 foundation、ownership 与 closure point 的横向交付范围；它不要求新增模板、持久记录或第二套状态。一次派发只授权一个 Topic 当前一条 lane 上的一个 baby step，这个边界逐 Topic 生效，不把整个批次降为单线程。

每个 Topic 首次 admission 时用一句话固定 closure point；在它关闭前不得为了释放后续动作静默缩小。closure point 或 ownership 实质变化时，按新边界重新 admission。

默认把既定方向和 write-set 内能共同完成的工作组织为一个 baby step，取到第一个有意义的主控 return point 为止，而不是 Topic closure；return point 是主控检查 diff/evidence 并据此决定是否授权下一段工作的边界。同一 worker 或 work lane 可以在主控消费 return 后连续承接下一步，但连续性不构成预授权。同一方向和 write-set 内的机械附属不单独派发，跟随同一步；相邻 return point 只有在接口已完全稳定、后段只是机械接线，且合并不会减少并行机会或主控决策能力时才可合并。必要的局部调查、实现、focused test、lint/format、普通重跑与当前动作产生的机械 cleanup 可以留在同一次派发。只有某个子结果会独立改变以下任一项时才继续切分：

- Topic 的实现方向或是否继续；
- dependency、write ownership 或 authorization；
- 当前批次的资源 admission；
- 是否立即释放另一条可并行 Topic。

多个材料族、逐项结论或完整候选表只是检查信号；知识来源能分别阅读或返回，不等于必须分别派发。这个门槛不按文件数量、步骤数、内部命令数或检索范围设硬上限：为一个窄决策检索整个仓库仍可以是一个动作；多个紧密相关文件共同形成一个 coherent outcome 时也保持同一步。增量规模本身不是切分理由，但它有一个可观察后果：一步的增量大到轻量 delta review 无法在下一步返回前给出结论时，findings 就赶不上下一步的 brief，逐步复核退化成批量返工；出现这个信号时按可独立验证的接口边界再切一刀，仍不设行数上限。

前置依赖已回答且能独立验证的动作才可派发；同一依赖链只释放第一个已解锁动作。结构 foundation 会改变下游行为或安全 finding 的 ownership、failure model 或验证判据时，foundation 就是该动作，return 与行为不变验证通过后再重扫。

## 调度循环

1. 扫描全部候选，按共享 foundation、ownership 与 closure point 形成 Topic，并重新核对 dependency。foundation 尚未稳定时保留下游动作；acceptance 只阻止正式验收和状态宣称；无法隔离的共享可变资源串行；缺少 mutation 授权的动作保持未释放。resource dependency 绑定当前 baby step 的具体 resource key，并按 read、write 与 observation 的完整 effect footprint 判断；读取或验证共享可变状态也占用对应 key。一个 key 只阻塞依赖它的步骤，不阻塞整个 Topic 或 Ticket。
2. 为每个已解锁 Topic 选择当前 baby step，把互不依赖且资源隔离的步骤组成当前批次并 fan out。`PARALLEL | SERIAL` 只比较当前候选 baby step 的实际 effect footprint，不使用 Topic 或 Ticket 的最终 write-set 并集；未来步骤会冲突不影响当前步骤并行，冲突到达时再串行。review、验证或 worker 在途只阻塞依赖其结论或资源的步骤；其他 Ticket 的只读调研与准备继续释放。文件 ownership 交叉时先由 SDD 判断能否用隔离 worktree 分开。共享操作的合并与复用只是调度优化，不是 dependency；只有不延迟已解锁的独立动作时才合并，否则先执行当前合格步骤并在 return 后重扫。
3. 单个派发只在宿主 receipt 明确成功后成立。迟到、重复、来源不明或结果不确定的 receipt 先消除歧义，不据此推进后续动作。中断或换 session 后恢复时，先按已有 report/artifact 与 trail 核对在途 review 是否已产出结论，确认缺失后才补派，不无条件重派。
4. worker return 后先消费可归因结果、evidence、diff、residue 与 cleanup，再判断当前 Topic 的下一步；返回不会自动授权后续工作。冻结该步增量与派出对应的轻量 delta review 属于同一次 return 消费，不先连续提交多步再集中派审。既定边界内的 tooling retry、format、普通重跑或机械 cleanup 续接当前动作，不创建新业务 step。
5. 每次消费 return 后检查受影响候选，核对 dependency、授权与资源后补充派发，不等待无关 worker；当前批次全部结束或准备进入 idle 时再全局扫描。在途 review 的返回同样按轮消费；派审持续滞后于实现返回，或未消费的 delta review 堆积到 findings 已经赶不上下一个 baby step 时，先消化 review 再释放新的并行 step——实施并发的上限来自这个可观察信号，不设固定数字。没有已解锁且合格的动作时进入 idle。业务状态、验收和 closure 仍由调用方的 owning workflow 判断。

同一 Topic 连续两次 `INCOMPLETE`、broad check 新发现一类 caller/producer，或实际 write-set 超出原 ownership 时，停止继续派更小的 fix；先释放一个 foundation investigation，重新确定 Topic 边界。

## Topic 生命周期

- 同一 Topic 的 work execution lane 只有在 ownership、failure model 与动作边界稳定，且 worker 仍能准确复述这些事实时才复用。连续重复且无法可靠解释的错误、不能准确复述既定边界、结果无法归因或实际 write-set 外溢，均触发 fresh worker；Topic 闭合后退役。
- review execution lane 始终独立于 work lane，reviewer 不审自己实现的增量；同 Topic、同 review scope 默认复用 reviewer，每次只交新的 base/head 与本次增量。scope 实质变化、上下文压缩失真、反复漏掉同类问题，或沿用旧结论而不核查新 diff 时换 fresh reviewer 并简述理由。
- test execution lane 只在同一有界 campaign 内复用，campaign 结束后退役。
- 新 Topic 使用 fresh worker；worker 空闲或角色相同不是复用理由。

完成一个调度轮次的可观察条件是：当前批次所有派发 receipt 已确认或消除歧义，所有已返回结果已被主控消费，最后一次 Topic-first 扫描没有已解锁且合格的动作。
