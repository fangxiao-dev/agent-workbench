# Independent Review Prompts

## Normal full review：三路并行与统一返回

正常 full review 启动三个 fresh subagent。编排器支持模型选择时，A、B、C 各自从 `gpt-5.6-terra` / `reasoning_effort=high` 与 `gpt-5.6-sol` / `reasoning_effort=high` 两档中选用合适 profile；由编排 agent 按审查对象、风险与上下文复杂度决定，task、owner 或 host 的明确要求优先。模型选择不改变三路的独立性、输入或职责。主 session 向三路发送同一个精简、同 revision 的 candidate bundle：candidate plan、earned Ticket/DAG、candidate projection、必要 D/S contract、联合校验证据、审查边界与只读约束。不得附带主审 findings、预期 verdict、预设 materiality 或 owner 偏好。三路均不得修改文件、写 ledger、晋升 formal finding 或向 owner 提问。

- A：使用下方 Outside Voice prompt，对完整 bundle 独立开展开放式审查。
- B：只检查 Scope 与 Architecture，优先追踪 authority、tenant、transaction、lineage、custody；不要代替 C 深读实现质量、测试或性能。
- C：只检查 Code Quality、Tests 与 Performance，优先追踪实现边界、failure/recovery、验证充分性与调用放大；不要代替 B 重审范围或架构。

三路都按以下格式返回：

```text
assigned_dimensions:
  - <dimension>
dimension_status:
  <dimension>: reviewed | not_applicable | finding
  reason: <与 candidate 相关的简短理由>
candidates:
  - claim: <待主 session 判断的材料性主张>
    evidence_pointer: <bundle 路径、文件:行或可复核命令输出定位>
    reasoning: <为什么构成或可能构成风险>
    risk: <contract / behavior / security / operations / cost>
checked_boundaries: [<已检查、但未形成 candidate 的关键边界>]
tensions_or_unknowns: [<冲突或不能由输入证明的事项>]
challenge_assumption: <最值得挑战的一个假设>
```

主 session 只复核 evidence pointer 和冲突点，合并去重并按 evidence gate 晋升 formal findings；它不重做每一路的维度深读。A 的不可用沿既有 Outside Voice 的 degraded 规则处理；B/C 的不可用或不可复核结论必须标记 `review input incomplete` 并重试或补齐输入，不能由主 session inline 补写为已审或进入 clearance。

## Bundle admission：由 `impl-planning` 启动的 fresh reviewer

只有调用方已按确切名称选择 `plan-review mode=bundle-admission` 时使用。该 reviewer 自身必须是相对主 session 的 fresh context；不要再启动额外 reviewer，也不要读取或创建 plan-review ledger。

给 admission reviewer 的输入只包含当前 plan、earned Ticket/DAG（如存在）、必要 Decision/Spec contract、Composition、联合校验结论与以下目标：

```text
独立判断这个 bundle plan 能否进入 owner approval。只基于提供的材料检查实际相关的 Scope、Architecture、Code Quality、Tests、Performance 风险；不要修改任何文件，不要推断 owner 的产品意图，也不要把缺失信息补成通过。

先报告一行配置：Mode=bundle-admission、Independent reviewer=fresh、Additional Outside Voice=no、Ledger=no。再显式扫描以下 full-review escalation signals：跨模块/服务/系统或外部 contract；权限、身份、租户/数据范围、资金或会计正确性、外部或持久化 mutation、通知、不可逆或 single-use 动作；并发、锁、CAS/claim、重复执行、replay、partial success、unknown outcome、crash recovery、迁移或 rollback；错误路径、operator signal、mutation authority、恢复责任或 acceptance oracle 存在多种合理解释；mock/stub/fixture 可能遮蔽真实协议、provider、序列化、权限、事务或版本边界。Signal 描述固有风险，不因计划已经写出缓解措施而消失。

按 unavailable → revise → full review → ready 的优先级返回唯一 verdict，并附简短、可核验证据、trigger scan 和下一动作。材料不足以有效审查时 revise；修订后仍须重新扫描固有 signal。存在任一 signal 时 full review，即使计划完整；只有没有缺口且 signal=none 时 ready。full review 表示调用方必须按确切 `skills/plan-review/SKILL.md` 路径转入正常 workflow，并在完成后交接经 `verify-clearance` 成功验证的 ledger 绝对路径；revise 表示指出 owning skill 的最小修订；unavailable 表示没有独立判断条件，不能当作通过。
```

不要向它提供主 session findings、预期 verdict、预设 materiality 或 owner 偏好。收到结果后，调用方只能保留 verdict 或把 `ready` 升级为 `full review`，不能反向降级。

## Focused closure verification：由 `impl-planning` 启动的 fresh verifier

只有调用方已按确切名称选择 `plan-review mode=focused-closure-verification`，且提供有限 closure brief 时使用。该 verifier 必须是相对主 session 的 fresh context；closure brief 是待验证的输入，不是预设结论。保留正常 full-review 的只读、ledger 和 candidate snapshot 约束，但不要再次启动开放式问题发现。

给 verifier 的输入是同一 candidate bundle、必要 Decision/Spec contract、当前 review ledger 基线，以及每项均包含原 finding、resolution/owner decision、需要重验的完整影响链与预期 verification evidence 的 closure brief。

```text
独立验证这个已冻结 closure batch 是否真的闭合。逐项检查原 finding 的 resolution 是否在 input → state/storage → consumer → audit/privacy → failure recovery → verification evidence 链路中一致，并检查 candidate 是否超出声明的 D/S/P、authority 或 public-contract 边界。不要寻找相邻改进、不要建议新抽象、不要产生新的 formal finding。

若 closure brief/证据/输入不足，返回 blocked。若发现直接矛盾、该链路有材料性遗漏，或新证据证明既定边界已变，返回 reopen-full-review，说明唯一升级理由并停止。只有每项均被证据支持且没有升级信号时才返回 closure-verified。附逐项的可核验证据和下一动作。
```

新材料性证据不是在本模式中继续开新 wave 的授权；它只触发 `reopen-full-review`，由调用方把已知项和升级理由合并成下一批 closure sweep。

## Outside Voice：每轮必选

给 fresh agent 的第一条任务只包含目标 plan/package、必要 contract、只读边界和以下目标，不要附带主审 findings 或预期答案：

```text
独立审查这个工程实施计划。寻找主审可能忽略的错误假设、跨边界风险、failure modes、测试缺口和范围遗漏；追踪 material 变化从目标与 contract 到 consumer、user/operator outcome 和验收 oracle。用可核验证据支持 candidates；不要修改目标，也不要推断 owner 的产品意图。返回你独立发现的 candidates、检查过但不适用的维度，以及最值得挑战的一个假设。

不要把 candidate plan 尚未登记、Tickets/DAG 尚未发布等 finding；这些是 clearance 后的 workflow 动作。聚焦计划的异常本身。
```

收到独立输出后再与主审结果合并。相同结论去重；证据或建议冲突时保留 tension，不要静默选边。

## 风险触发的 Judge/Critic

高影响自动归纳、证据冲突、不可逆性、跨边界影响或主审明显不确定时，让 fresh reviewer 检查 evidence sufficiency、owner gate、遗漏维度、错误收敛和未声明依赖。已经完成 Outside Voice 的同一 fresh context 可以继续承担此能力，但必须先完成不受主审 findings 污染的独立观察。

## 降级

无法取得 fresh context 时，不要 inline 模拟 Outside Voice。继续主审，报告 `Outside Voice=unavailable` 与原因，保留 findings，但禁止 `fully reviewed` 或 `cleared` verdict。
