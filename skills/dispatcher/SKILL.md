---
name: dispatcher
description: 当主控需要把候选工作切成可独立验收的步骤、使用subagent fan out 时提供轻量上游调度指导。
---

# Dispatcher

Dispatcher 面向上游主控，指导 baby-step admission、当前批次、dispatch、worker return 与 idle。它与 `/impl-package:subagent-driven-development` 平级：Dispatcher 决定上游何时派什么，SDD 指导已派发 Topic 内的 dependency、mode、lane 与 lifecycle。

## Baby step 派发门槛

**先切 baby step，再讨论并行或 worker。** Topic 只是连续动作共享上下文的容器，不是一次派发的尺寸；一次派发只对应一个 Topic 内当前一个动作。这个门槛逐 Topic 生效，不把整个批次降为单线程。

派发前做一次**独立可返回性**检查：请求中的任一材料面、判断项或交付部分，只要能不依赖其余部分而独立返回、独立验证并被主控单独消费，它就是另一个 baby step；此时继续切分，由主控消费局部结果后综合，不把跨材料面的取证与综合包装成一次派发。多个材料族、逐项结论或完整候选表是需要检查的信号，不是按关键词机械拒绝。

这个门槛判断结果能否独立消费，不按文件数量或检索范围设硬上限。为一个窄问题在整个仓库检索时，检索范围宽仍可以是一个动作；为一个 coherent outcome 修改多个紧密相关文件时，跨文件也仍可以是一个动作，只要其中没有任何一部分能先形成独立可消费的结果。

动作只有在结果可二元判定、前置依赖已回答且能独立验证时才可派发；否则继续切分，同一依赖链只释放第一个已解锁动作。

## 调度循环

1. 扫描全部候选，对每个候选应用 baby-step 门槛并重新核对 dependency。foundation 尚未稳定时保留下游动作；acceptance 只阻止正式验收和状态宣称；无法隔离的共享可变资源串行；缺少 mutation 授权的动作保持未释放。
2. 把全部互不依赖且资源隔离的合格 baby steps 组成当前批次并 fan out。文件 ownership 交叉时先由 SDD 判断能否用隔离 worktree 分开。
3. 单个派发只在宿主 receipt 明确成功后成立。迟到、重复、来源不明或结果不确定的 receipt 先消除歧义，不据此推进后续动作。
4. worker return 后先消费可归因结果、evidence、diff、residue 与 cleanup，再判断当前 Topic 的下一 baby step；返回不会自动授权后续工作。
5. 完成当前结果消费后重新扫描全部候选。没有已解锁且合格的动作时进入 idle；业务状态、验收和 closure 仍由调用方的 owning workflow 判断。

## Topic 生命周期

- 同一 Topic 的 work lane 在 ownership 与上下文可信时可以复用 live worker；scope/ownership 实质变化或 Topic 闭合后退役。
- review lane 始终独立于 work lane，但同 Topic、同 review scope 的 recheck 可以复用 reviewer。
- test wrapper 只在同一有界 campaign 内复用，campaign 结束后退役。
- 新 Topic 使用 fresh worker；worker 空闲或角色相同不是复用理由。

完成一个调度轮次的可观察条件是：所有派发 receipt 已确认或消除歧义，所有已返回结果已被主控消费，最后一次扫描没有已解锁且合格的动作。
