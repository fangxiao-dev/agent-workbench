# Authorization Contract

初始 Decision/Spec/Plan bundle 进入 execution 前只需要一次完整的 owner final approval，明确目标、范围/write-set、允许的 mutation、禁区、验收和需要 HITL 的动作。

该初始 approval 覆盖同一 package 后续的 plan、state、progress、Execution Record、evidence、review、Gate 和普通实现更新；每个 update、attempt 或 session 均沿用该 approval。新 package 使用新的 initial bundle approval。

对 destructive、production/shared mutation、push、merge、release、数据迁移和其他外部副作用使用独立的明确授权；普通 package update 直接使用初始 bundle approval。

本合同以现有 package 内容、initial approval、Git commit 和实际 diff 作为唯一内容、批准、版本与审计依据。

委派执行由 `$dispatcher` 编排；本合同只传递任务特定授权，不定义 worker 角色或业务 prompt。

## 渐进读取常见误判

- 跳过 anchor 就开始读材料，会把 package 或 authority 已漂移的工作区误当成同一任务。
- 没有先建立 control map，下一动作可能越过 write-set，或漏掉已经存在的 blocker/Gate 边界。
- 把全量材料读取当成恢复证明，会增加选择性漏读；只读 active unit 才能让当前动作的证据边界保持可辨。
