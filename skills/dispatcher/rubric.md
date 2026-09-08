---
target: skills/dispatcher
updated: 2026-09-08
---

## 原则

- [已确认] Dispatcher 是 model-invoked 的通用执行协作入口；SDD 的委派、dependency、mode、资源隔离、lifecycle 与 return 方法并入本 Skill，不保留平级入口。
- [已确认] 主路径保持五步：明确范围、发现候选、形成合同、核实返回并及时审查、限定阻塞并继续安排；不新增持久调度系统。
- [已确认] Topic 是连续工作可用的组织概念，简单任务可直接表达目标、边界和返回条件；一次委派仍止于可验证结果或下一主控判断点。
- [已确认] 主动释放有实际收益的独立工作；局部 foundation、acceptance、resource 或 authorization barrier 只影响对应候选。
- [已确认] 并行按当前动作的完整 effect footprint 判断；worktree 只隔离文件，DB、端口、测试数据、输出与外部记录分别核验。
- [已确认] `investigate | implement | fix | verify` 与三组 outcome 词汇整体保留，供通用路径和 Impl-Package 使用。
- [已确认] worker brief 保留成功行为、不变量、ownership、真实路径验证、返回边界和 cleanup；同一结果的机械附属留在一次委派。
- [已确认] worker/reviewer 复用取决于相关上下文可信、ownership 与 scope 稳定；Topic 名称、固定等待时间和 `INCOMPLETE` 次数不机械驱动换人。
- [已确认] 每个代码 return 在同次消费中固定增量并及时派独立 delta review；无法立即派审时记录具体欠项并在后续扫描处理。
- [已确认] formal review 的业务 requirement 归 owning workflow；Impl-Package 的七类 material risk 归 dev-with-track，topology/coverage/closure 归 do-review。
- [已确认] Impl-Package 工作无需预登记；`candidate_id` 只标识实际派发工作及可信续接，资源与授权由主控按当前事实判断。

## 决策记录（滚动，最近 ≤5 轮）

### R7 · 2026-09-08

- Owner 批准合并 Dispatcher 与 SDD，保留 `$dispatcher` 名称并改为 model-invoked。
- 主文件压缩为五步循环，仅保留 `delegation.md` 与 `resource-isolation.md` 两个分支 reference。
- 删除 Topic-first 全面强制、新 Topic 一律 fresh、固定 15/30 分钟观察、连续两次 `INCOMPLETE`、finding 固定捆绑和三条 lane 强制对象。
- 保留结果边界、四类 dependency、四个 mode、真实资源隔离、可归因 return 与独立 delta review。

### R6 · 2026-09-05

- 同 review scope 默认复用独立 reviewer；每次输入新的固定增量。
- 派审滞后或 delta 积压是并发过载信号，不设固定 lane 数或数字预算。

### R5 · 2026-09-02

- 结构 foundation 改变下游行为或安全 finding 时先稳定 foundation。

### R4 · 2026-09-02

- worker 复用使用可观察的上下文可信度信号。

### R2 · 2026-09-02

- 共享 resource key 只阻塞依赖它的步骤；共享操作合并只是优化。
