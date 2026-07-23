# Independent Review Prompts

## Bundle admission：由 `impl-planning` 启动的 fresh reviewer

只有调用方已按确切名称选择 `plan-review mode=bundle-admission` 时使用。该 reviewer 自身必须是相对主 session 的 fresh context；不要再启动额外 reviewer，也不要读取或创建 plan-review ledger。

给 admission reviewer 的输入只包含当前 plan、earned Ticket/DAG（如存在）、必要 Decision/Spec contract、Composition、联合校验结论与以下目标：

```text
独立判断这个 bundle plan 能否进入 owner approval。只基于提供的材料检查实际相关的 Scope、Architecture、Code Quality、Tests、Performance 风险；不要修改任何文件，不要推断 owner 的产品意图，也不要把缺失信息补成通过。

先报告一行配置：Mode=bundle-admission、Independent reviewer=fresh、Additional Outside Voice=no、Ledger=no。再显式扫描以下 full-review escalation signals：跨模块/服务/系统或外部 contract；权限、身份、租户/数据范围、资金或会计正确性、外部或持久化 mutation、通知、不可逆或 single-use 动作；并发、锁、CAS/claim、重复执行、replay、partial success、unknown outcome、crash recovery、迁移或 rollback；错误路径、operator signal、mutation authority、恢复责任或 acceptance oracle 存在多种合理解释；mock/stub/fixture 可能遮蔽真实协议、provider、序列化、权限、事务或版本边界。Signal 描述固有风险，不因计划已经写出缓解措施而消失。

按 unavailable → revise → full review → ready 的优先级返回唯一 verdict，并附简短、可核验证据、trigger scan 和下一动作。材料不足以有效审查时 revise；修订后仍须重新扫描固有 signal。存在任一 signal 时 full review，即使计划完整；只有没有缺口且 signal=none 时 ready。full review 表示调用方必须转入正常 plan-review workflow；revise 表示指出 owning skill 的最小修订；unavailable 表示没有独立判断条件，不能当作通过。
```

不要向它提供主 session findings、预期 verdict、预设 materiality 或 owner 偏好。收到结果后，调用方只能保留 verdict 或把 `ready` 升级为 `full review`，不能反向降级。

## Outside Voice：每轮必选

给 fresh agent 的第一条任务只包含目标 plan/package、必要 contract、只读边界和以下目标，不要附带主审 findings 或预期答案：

```text
独立审查这个工程实施计划。寻找主审可能忽略的错误假设、跨边界风险、failure modes、测试缺口和范围遗漏；追踪 material 变化从目标与 contract 到 consumer、user/operator outcome 和验收 oracle。用可核验证据支持 candidates；不要修改目标，也不要推断 owner 的产品意图。返回你独立发现的 candidates、检查过但不适用的维度，以及最值得挑战的一个假设。
```

收到独立输出后再与主审结果合并。相同结论去重；证据或建议冲突时保留 tension，不要静默选边。

## 风险触发的 Judge/Critic

高影响自动归纳、证据冲突、不可逆性、跨边界影响或主审明显不确定时，让 fresh reviewer 检查 evidence sufficiency、owner gate、遗漏维度、错误收敛和未声明依赖。已经完成 Outside Voice 的同一 fresh context 可以继续承担此能力，但必须先完成不受主审 findings 污染的独立观察。

## 降级

无法取得 fresh context 时，不要 inline 模拟 Outside Voice。继续主审，报告 `Outside Voice=unavailable` 与原因，保留 findings，但禁止 `fully reviewed` 或 `cleared` verdict。
