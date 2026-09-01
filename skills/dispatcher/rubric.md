---
target: skills/dispatcher
updated: 2026-09-01
---

## 原则

- [已确认] 复用 Topic 作为顶层连续交付 lane，不新增 Delivery Lane 对象、持久状态或第二套调度系统。
- [已确认] 默认派发既定方向和 write-set 内最大的 coherent step；只有结果会改变 Topic 决策、ownership、dependency、authorization、资源 admission 或立即释放另一条 Topic 时才拆分。
- [已确认] 当前批次收齐后再全局重扫；连续 `INCOMPLETE`、新 caller/producer 家族或 write-set 外溢统一触发一次 foundation investigation，不叠加细碎 guard。
- [已确认] 优先降低主控调度负担，不以增加模板、字段、预算或持久化记录换取局部形式完整。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-01

- 采纳 Topic-first、最大 coherent step、batch drain 与单一反抖动规则。
- 否决独立 Delivery Lane 实体、lane 模板、数字 dispatch budget、多级 stabilization checkpoint 和持久化 lane 状态。
- 用户原话：只想保留性价比最高的，不要再增加主控负担。
