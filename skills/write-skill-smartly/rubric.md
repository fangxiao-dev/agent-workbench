---
target: skills/write-skill-smartly
updated: 2026-08-10
---
## 原则

- [已确认] 文案、规则澄清和局部非语义修正默认使用 focused validation；仅改变触发、工作流、输出合同或脚本行为时才要求完整 benchmark。
- [已确认] `write-skill-smartly` 支持 Agent 自动发现，也保留 `$write-skill-smartly` 显式调用。
- [已确认] 每次写 Skill 都读取独立的 `writing-for-agents`；完整 creator 方法论只在高风险或用户要求时进入。
- [已确认] 新写内容和汇报默认使用简体中文，同时保留代码、标识符和既有 Skill 的主语言。

## 决策记录（滚动，最近 ≤5 轮）
### R3 · 2026-08-10
- 用户将入口从显式调用改为自动调用；description 只覆盖创建、修改、评测和优化 Skill 的真实分支，避免扩张到一般文档编辑。
- Codex `agents/openai.yaml` 同步允许 implicit invocation。

### R2 · 2026-08-10
- 收起本地 `skill-creator` 为内部 `SUB-SKILL`，由 `write-skill-smartly` 按风险路由；Codex 系统自带版本不变。
- 新增 Codex `agents/openai.yaml`，明确禁止隐式调用；`writing-for-agents` 保持独立且 Agent 可见。

### R1 · 2026-07-15
- 采纳「focused validation 默认路径」— 用户明确要求普通文字与规则修正不再自动触发双基线、评分、benchmark 和 viewer。
