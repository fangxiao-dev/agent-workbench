# Authorization Contract

初始 Decision/Spec/Plan bundle 进入 execution 前只需要一次完整的 owner final approval，明确目标、范围/write-set、允许的 mutation、禁区、验收和需要 HITL 的动作。

该初始 approval 覆盖同一 package 后续的 plan、state、progress、Execution Record、evidence、review、Gate 和普通实现更新；每个 update、attempt 或 session 均沿用该 approval。新 package 使用新的 initial bundle approval。

对 destructive、production/shared mutation、push、merge、release、数据迁移和其他外部副作用使用独立的明确授权；普通 package update 直接使用初始 bundle approval。

本合同以现有 package 内容、initial approval、Git commit 和实际 diff 作为唯一内容、批准、版本与审计依据。

委派执行仍由 `/impl-package:subagent-driven-development` 编排；本合同只传递任务特定授权，不定义 worker 角色或业务 prompt。
