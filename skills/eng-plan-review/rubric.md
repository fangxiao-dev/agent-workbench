# Engineering Review Rubric

Material 指会影响行为、contract、数据、安全、运营、发布或显著工程成本的事项。用具体证据和可观察风险判断材料性，不使用固定文件数、类数量或阶段数量作为替代。

## 使用方式

这些横切镜头贯穿每个 candidate、formal finding 和聚焦维度；Scope、Architecture、Code Quality、Tests、Performance reference 只增加观察角度，不能替代本 rubric。先追踪 `goal → contract → consumer → user/operator 可观察结果 → acceptance oracle`，再判断建议是否改变真实结果。

最小完整变更只覆盖与目标相关的 material success、error、recovery、migration、distribution 和 verification 路径；不相关路径可以跳过并说明理由。不要把完整性变成固定覆盖率、文件数、阶段数或 completeness score。

## 横切镜头

- **Goal and observable outcome**：计划步骤必须能回到目标、已接受约束、验收条件或用户/operator 可见结果；只描述内部结构而没有 observable oracle 是实施风险。
- **控制 blast radius**：优先局部、可回退和边界清晰的变更；扩大范围必须保护真实需求。
- **Boring by default**：成熟简单的方案优先，但不要以“简单”为名遗漏完整 contract、失败处理或分发链路。
- **Incremental and reversible**：识别可分阶段交付、迁移窗口、rollback 和不可逆点。
- **Systems over heroes**：让验证、ownership 和故障恢复依赖可重复机制，不依赖个人记忆或手工救火。
- **Essential over accidental complexity**：挑战无价值抽象、重复基础设施和含糊 glue，同时保留问题本身需要的复杂度。
- **Right-sized change shape**：区分结构准备、行为变化和迁移；混在同一不可分步骤会增加验证与回退风险时，先让变更容易，再做行为变更。
- **Ownership follows architecture**：检查模块、部署单元、团队/on-call 与 handoff 边界是否一致；跨边界人工同步和长期 glue work 是耦合信号。
- **Failure is evidence**：当前变更触及已知 regression、revert、incident 或脆弱迁移时，按需读取相关历史并让失败经验约束设计；不要每轮全量考古。
- **Production ownership**：检查谁观察、响应和修复生产失败，以及用户在失败时看到什么。
- **Reliability is a trade-off**：存在明确 SLO、latency、durability、capacity 或 error budget 时，检查 rollout、降级、观测和资源选择是否符合该 contract。
- **Developer experience**：检查构建、测试、调试、发布和维护成本是否被计划真实覆盖。

这些是启发式工具，不是逐项评分表。根据计划信号选择能改变 scope、architecture、test、rollout、finding 或 owner decision 的镜头；不要在结论中机械复述原则名。
