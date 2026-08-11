---
target: plugin-marketplace/plugins/impl-package/skills/investigate-before-implement
updated: 2026-08-11
---
## 原则

- [待验证] 调查 skill 只建立原因、影响面、既有方案和前置事实，不承担 worker 选择、并行准入或 Task 设计。（证据: R1, R2）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-11（调查门降载）

- 采纳将 investigate 收敛为实施依据判断层，并把调度和具体派发移交给各自 owner — 用户明确同意“降载 3 者，同时明确各自的任务，并且把配置分流到更合理的地方”。

### R2 · 2026-08-11（二次降载审计）

- 采纳保持 investigate 当前最小边界，不为形式对称继续增加调度字段或路由规则；本轮降载集中在 SDD、dispatch 和重复入口。
