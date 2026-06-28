# Slice Sizing & Risk

把 "slice 多宽" 当成 gate：每个 candidate slice 都要估 size/risk，并据此选定 sizing decision。Size 不按 LOC，而按以下信号判断；任一偏高即视为 wide / high-risk。

## Size / Risk Signals

- **Call-sites / modules touched**：改动是否分散到多处文件或调用点。
- **Cross-cutting**：是否横切关注点（错误清洗、路径/序列化、鉴权等）。横切 slice 单个 worker 极易漏掉边缘 case，是最强的返工预测信号。
- **Design uncertainty**：实现方案已写明，还是要 worker 自行探索。
- **Seam coupling**：与其他 slice 在集成处的耦合程度。
- **Verifiability**：能否独立 demo / 验证；不能独立验证本身就是 mis-sliced 信号。

## Sizing Decisions

不要默认就拆，按场景选：

- **`keep`**：slice 局部、可独立验证、seam 明确、风险低。
- **`vertical-split`**：能切成各自可独立验证的纵向子 slice 时，拆。
- **`tracer-bullet-follow-ups`**：先打通一条端到端最小路径固定 seam，再 fan out 其余实现。
- **`design-interface-gate`**：横切关注点优先用此。实现前先派 design/spec subagent 产出简短接口契约或受影响 call-site 清单，再交 worker。硬拆横切关注点常常放大集成 seam，慎拆。
- **`escalate-to-user`**：当拆分会改变交付边界，或 size 估计不确定且影响计划范围时，带上估计与可选项在 approval quiz 中跟用户对齐。

Plan 阶段的估计天然不精确，做不到零返工；运行期的返工兜底（rework budget / circuit-breaker）属于执行/runner 契约，不在本 skill 范围。
