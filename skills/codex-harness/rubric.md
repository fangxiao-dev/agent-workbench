---
target: skills/codex-harness
updated: 2026-07-18
---
## 原则

- [已确认] Codex Harness 默认采用最小控制面，只硬性守住角色边界、权限、写入隔离、Owner gate、事实验收和资源收口，不把 Worker 数量、具体拆分或 turn 顺序变成验收门。
- [已确认] Eval 应直接验证 Skill 能否指导正确行为，而不是只验证配置、脚本或 JSON 结构存在。
- [已确认] 结构化事实和禁止动作优先于自然语言“完成”说明，同时保留 Agent 自主决定拆分、Lite/Full、内部 Subagent 和实现策略的空间。
- [已确认] 外部 mutation 未获 Owner 决策时必须 fail closed，不得用空 commit 或自然语言伪造完成。
- [已确认] Codex Harness 新增 Eval 或协议版本按 `0.1` 步进，不使用整数版本跳跃。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-18

- 采纳「以真实案例建立 Eval-to-Skill 闭环，Eval 结果直接指导入口 Skill 优化」。
- 采纳「Eval 使用 hard invariant、forbidden action、advisory quality 三层断言」。
- 采纳「新 Eval 版本使用 `v0.1`，后续按 `0.1` 步进」。
- 不采纳「把 fresh context、Worker dispatch、活跃写 worktree 和 assurance mode 的独立性记录为偏好」— 用户明确这是运行时设计事实，不是个人偏好。

### R2 · 2026-07-18

- 采纳「失败或 quarantine 预演不得升级为成功交付或权威调度结论」— 只有有效结构化终态和对应事实证据可以改变该结论。
- 采纳「文档保持薄，只解释角色、证据和授权边界；运行时字段、超时收口和状态细节进入 Schema/runner」。
- 采纳「代码 delivery 图与外部 operator/promotion 图分开表达；未授权外部动作只阻断显式依赖它的下游」。
