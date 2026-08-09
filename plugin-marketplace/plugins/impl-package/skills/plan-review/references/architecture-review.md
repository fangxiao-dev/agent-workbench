# Architecture Review

检查组件边界与责任、依赖方向、耦合、数据流、安全与权限边界、API/事件 contract、状态生命周期、容量假设、SPOF、失败隔离、迁移和可逆 rollout。对固定 identity 或可重复命令明确 create/resume/retry/overwrite/complete/reopen 语义，以及非法状态转换和并发选择规则。

检查组件边界是否与实际 ownership、部署单元、on-call 和 handoff 边界一致。小改动若要求多个服务、仓库或团队同步发布，视为耦合或 delivery-friction 信号；滚动发布期间确认新旧代码、schema、消息和持久化格式能够在明确窗口内共存。

对每条 material 新路径或集成至少构造一个真实生产失败场景：上游超时、下游部分成功、重复消息、重复执行、顺序变化、陈旧数据、权限错误、部署版本不一致或回滚中断。只选择与计划实际相关的场景。

确认计划说明失败由谁观察和处理、状态如何恢复、用户看到什么，以及 contract 改变是否交由 owner 决定。

存在明确 SLO、availability、latency、durability 或 error budget 时，检查降级、重试、容量和 rollout 是否符合可靠性 contract。若 accepted findings 形成两个以上 workstreams，按需给出简短 dependency map，标出共享 contract、migration gate、integration point、合并冲突面和真正可独立的 lane；不要为了形式拆分任务。

仅在边界、依赖或数据流难以用短列表表达时使用图示。输出 candidate 或 formal finding，不在本文件重复 evidence 和 owner gate 规则。
