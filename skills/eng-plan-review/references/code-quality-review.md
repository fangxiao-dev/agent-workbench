# Code Quality Review

## 组织与仓库惯例

检查计划是否复用仓库已有模块边界、命名、状态、错误和扩展模式，还是平行发明第二套入口、registry、adapter 或 orchestration。新责任必须有清楚 owner，不能为了局部方便制造跨层反向依赖。

保持 DRY 和 explicit over clever，但区分偶然相似与真正共享 contract。挑战过度设计与不足设计，判断 diff 是否围绕一个最小完整目标，而不是机械追求最少行数。

## Contract 与 Source of Truth

检查 CLI、schema、配置、持久化状态、实现任务、示例和测试的名称、基数、默认值与生命周期是否一致并由同一权威来源驱动。识别重复 source of truth、易漂移的派生状态、双写和依赖人工同步的镜像。

修改已有 abstraction 或 contract 时枚举真实消费者、legacy caller、兼容路径和跨平台镜像；不能只更新最显眼入口。触及架构图、inline diagram、运行手册或 contract 文档时检查 freshness。

## 错误、状态与边界

区分 validation、domain failure、dependency failure、partial success 和 programmer error，确认错误在正确边界转换、记录、重试或呈现。不要用通用 catch、静默 fallback 或无限重试抹平不同恢复语义。

检查 temporal coupling、隐式调用顺序、共享可变状态，以及“调用者必须记住”的前置/清理动作。对 create/resume/retry/overwrite/complete/reopen 等生命周期确认非法状态不会依赖偶然调用顺序。

## Abstraction、迁移与维护

新增 abstraction 应有真实变化轴或多个消费者；已有 abstraction 不应被旁路。识别结构重构、行为变化和迁移是否被混成难以审阅、验证或回退的一步。

计划应说明迁移后何时删除 dead code、旧入口、compat shim、feature flag、双读或双写，避免把临时状态永久包装成技术债。技术债可以有界延期；material 或可能长期滞留的延期按需说明影响、owner/destination 和重新进入条件。

只判断 plan 是否为实现提供足够约束和验证，不滑向逐行代码 review。泛泛的风格偏好、没有实际消费者的假想复用和纯审美意见不要晋升为 finding。
