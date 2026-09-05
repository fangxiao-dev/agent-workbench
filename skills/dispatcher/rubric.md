---
target: skills/dispatcher
updated: 2026-09-05
---

## 原则

- [已确认] Topic 是共享 foundation、ownership 与 closure point 的横向交付范围；不新增 Delivery Lane 对象、持久状态或第二套调度系统。
- [已确认] 默认沿一条 lane 派发既定方向和 write-set 内的一个 baby step；同一方向和 write-set 内的机械附属跟随同一步，只有结果会改变 Topic 决策、ownership、dependency、authorization、资源 admission 或立即释放另一条 Topic 时才拆分。
- [已确认] baby step 以主控 return point 为边界，不打包到 Topic closure；相邻 return point 只在接口稳定且不减少并行机会时合并。
- [已确认] 消费 return 后检查受影响候选并补派，整批结束或准备 idle 时全局重扫；连续 `INCOMPLETE`、新 caller/producer 家族或 write-set 外溢统一触发一次 foundation investigation，不叠加细碎 guard。
- [已确认] 优先降低主控调度负担，不以增加模板、字段、预算或持久化记录换取局部形式完整。
- [已确认] review lane 与 work lane 的独立性和上下文连续性是两件事：reviewer 不审自己实现的增量，但默认沿同 review scope 复用并只接新的 base/head 与本次增量。（证据: R6）
- [已确认] 逐步复核的节拍靠可观察信号维持：派审与冻结增量同一次消费，派审滞后或 delta 积压是并发过载信号；不设固定 lane 数或数字预算。（证据: R6）
- [待验证] worker 复用使用可观察的上下文可信度信号。（证据: R2, R3, R4）

## 决策记录（滚动，最近 ≤5 轮）

### R2 · 2026-09-02

- 采纳固定 Topic closure point、step 级 resource key 与完整 effect footprint；共享 key 只阻塞实际依赖它的步骤。
- 采纳共享操作的合并只是一种优化；不得因此延迟已解锁的独立动作。
- 采纳 worker 复用取决于 ownership、failure model 与动作边界仍可准确复述，不按会话时长或固定轮数机械切换。
- 继续否决 Delivery Lane 对象、资源矩阵模板、数字预算和持久调度状态。
- 用户原话：GO，按最小。

### R3 · 2026-09-02

- 采纳把重复且无法解释的错误、边界复述失败、结果无法归因和 write-set 外溢写成 fresh worker 的可观察触发信号。
- 用户原话：这样写比较好吧；更新。

### R4 · 2026-09-02

- 保留 fresh worker 的可观察触发信号，删除不驱动动作的防御性说明。
- 用户原话：不要写这个防御性文字。

### R5 · 2026-09-02

- 采纳把结构 foundation 与下游行为或安全 finding 的分步规则合并进既有 dependency 语义，不新增特例段，也不在 SDD 复制。
- 用户原话：统一；同意。

### R6 · 2026-09-05

- 采纳同 review scope 默认复用 reviewer：独立性由“不审自己实现的增量”保证，上下文连续性有助于发现旧问题被重新引入；换人条件写成可观察信号（scope 变化、上下文失真、反复漏检、沿用旧结论不核查新 diff）并要求简述理由。
- 采纳逐步复核的节拍规则：冻结增量与派审同属一次 return 消费；在途 review 按轮消费；派审滞后或 delta 积压到 findings 赶不上下一步时先消化再扩并发。
- 采纳“增量大到 review 跟不上”作为额外切分信号，仍不设行数上限。
- 继续否决固定 lane 数与数字 dispatch budget。
- 用户原话：不必每个 Step 都强制 fresh；主要不是同一个 Step 被重复审查，而是 Step 多、Review 派发滞后且消化不够及时。
