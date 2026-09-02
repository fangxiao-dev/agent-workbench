---
target: skills/dispatcher
updated: 2026-09-02
---

## 原则

- [已确认] 复用 Topic 作为顶层连续交付 lane，不新增 Delivery Lane 对象、持久状态或第二套调度系统。
- [已确认] 默认派发既定方向和 write-set 内最大的 coherent step；只有结果会改变 Topic 决策、ownership、dependency、authorization、资源 admission 或立即释放另一条 Topic 时才拆分。
- [已确认] 当前批次收齐后再全局重扫；连续 `INCOMPLETE`、新 caller/producer 家族或 write-set 外溢统一触发一次 foundation investigation，不叠加细碎 guard。
- [已确认] 优先降低主控调度负担，不以增加模板、字段、预算或持久化记录换取局部形式完整。
- [待验证] worker 复用使用可观察的上下文可信度信号。（证据: R2, R3, R4）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-01

- 采纳 Topic-first、最大 coherent step、batch drain 与单一反抖动规则。
- 否决独立 Delivery Lane 实体、lane 模板、数字 dispatch budget、多级 stabilization checkpoint 和持久化 lane 状态。
- 用户原话：只想保留性价比最高的，不要再增加主控负担。

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
