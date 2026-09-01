---
name: dispatcher
description: 当主控需要先形成连续 Topic、再选择当前 coherent step 并使用 subagent fan out 时提供轻量上游调度指导。
---

# Dispatcher

Dispatcher 面向上游主控，指导 Topic-first admission、当前批次、dispatch、worker return 与 idle。它与 `/impl-package:subagent-driven-development` 平级：Dispatcher 决定上游何时派什么，SDD 指导已派发 Topic 内的 dependency、mode、execution lane 与 lifecycle。

## Topic-first 派发门槛

**先形成 Topic，再选择当前 coherent step。** Topic 是共享 foundation、ownership 与 closure point 的连续交付 lane；它不要求新增模板、持久记录或第二套状态。一次派发只授权一个 Topic 的当前 coherent step，这个边界逐 Topic 生效，不把整个批次降为单线程。

默认保留能在既定方向和 write-set 内一起完成的最大 coherent step。必要的局部调查、实现、focused test、lint/format、普通重跑与当前动作产生的机械 cleanup 可以留在同一次派发。只有某个子结果会独立改变以下任一项时才继续切分：

- Topic 的实现方向或是否继续；
- dependency、write ownership 或 authorization；
- 当前批次的资源 admission；
- 是否立即释放另一条可并行 Topic。

多个材料族、逐项结论或完整候选表只是检查信号；知识来源能分别阅读或返回，不等于必须分别派发。这个门槛不按文件数量、步骤数、内部命令数或检索范围设硬上限：为一个窄决策检索整个仓库仍可以是一个动作；多个紧密相关文件共同形成一个 coherent outcome 时也保持同一步。

前置依赖已回答且能独立验证的动作才可派发；否则继续切分，同一依赖链只释放第一个已解锁动作。

## 调度循环

1. 扫描全部候选，按共享 foundation、ownership 与 closure point 形成 Topic，并重新核对 dependency。foundation 尚未稳定时保留下游动作；acceptance 只阻止正式验收和状态宣称；无法隔离的共享可变资源串行；缺少 mutation 授权的动作保持未释放。
2. 为每个已解锁 Topic 选择当前最大 coherent step，把互不依赖且资源隔离的步骤组成当前批次并 fan out。文件 ownership 交叉时先由 SDD 判断能否用隔离 worktree 分开。
3. 单个派发只在宿主 receipt 明确成功后成立。迟到、重复、来源不明或结果不确定的 receipt 先消除歧义，不据此推进后续动作。
4. worker return 后先消费可归因结果、evidence、diff、residue 与 cleanup，再判断当前 Topic 的下一步；返回不会自动授权后续工作。既定边界内的 tooling retry、format、普通重跑或机械 cleanup 续接当前动作，不创建新业务 step。
5. 当前批次的 receipt 与 return 全部确认或消除歧义后，再全局扫描候选并形成下一批；没有已解锁且合格的动作时进入 idle。业务状态、验收和 closure 仍由调用方的 owning workflow 判断。

同一 Topic 连续两次 `INCOMPLETE`、broad check 新发现一类 caller/producer，或实际 write-set 超出原 ownership 时，停止继续派更小的 fix；先释放一个 foundation investigation，重新确定 Topic 边界。

## Topic 生命周期

- 同一 Topic 的 work execution lane 在 ownership 与上下文可信时可以复用 live worker；scope/ownership 实质变化或 Topic 闭合后退役。
- review execution lane 始终独立于 work lane，但同 Topic、同 review scope 的 recheck 可以复用 reviewer。
- test execution lane 只在同一有界 campaign 内复用，campaign 结束后退役。
- 新 Topic 使用 fresh worker；worker 空闲或角色相同不是复用理由。

完成一个调度轮次的可观察条件是：当前批次所有派发 receipt 已确认或消除歧义，所有已返回结果已被主控消费，最后一次 Topic-first 扫描没有已解锁且合格的动作。
