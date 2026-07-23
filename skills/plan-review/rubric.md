---
target: skills/plan-review
updated: 2026-07-22
---
## 原则

- [待验证] 当前唯一且未 stale 的审查上下文中，低风险的机械字段（如 manifest hash）由 agent 自动绑定和记录；用户的 `Apply` 应直接授权已展示的修正集合，只有该集合发生实质变化才重新确认。（证据: R1）
- [待验证] `plan-review` 保持 explicit opt-in：只有用户明确点名或上游编排按确切名称/路径选择时调用，不因语义相似、计划复杂或风险信号被模型主动识别。（证据: R2）
- [待验证] Bundle admission 必须报告实际审查配置，并把跨边界 contract、权限/租户/财务或持久化 mutation、single-use/replay/recovery 与 mock 遮蔽真实边界视为固有 full-review signal；signal 不因计划已描述缓解措施而消失。（证据: R3）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-22
- 采纳「agent 自动填入 manifest hash」— 用户原话：agent不是脚本，你做出占位符就行了，应该交给他自己填入和理解吧；并确认该偏好。

### R2 · 2026-07-22
- 采纳「plan-review 不被主动识别」— 用户原话：要用户或者有明显的编排去主动调用它，而不是自己“理解”需要。

### R3 · 2026-07-22
- 采纳「审查配置必须可见，固有高风险必须升级」— 用户指出 Outside Voice/ledger 等配置可以不阻塞但必须报告，并以 DATEV 会计语义、RBAC、tenant authority、真实本地 profile 与 replay 防护为反例，要求 full review 触发不能依赖 reviewer 把风险误判成已由计划文字消除。
