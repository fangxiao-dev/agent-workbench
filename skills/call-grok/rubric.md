---
target: skills/call-grok
updated: 2026-07-21
---

## 原则

- [待验证] role 合同以最小必要的自然语言状态保证父 agent 能判断完成度，不以严格结构化输出限制 worker 的审查表达。
- [待验证] reviewer 的单轮预算保持短而专注；跨轮由父 agent 提供已审阅上下文，不能依赖续接 raw session。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-21
- 采纳「reviewer 默认 15 turns」：用户要求将 reviewer 控制到 15，且该约束写在 call-grok 的 role 设定中，不让 do-review 感知 Grok。
- 采纳「Cancelled 不视为完成」与「跨轮 fresh session」：用户确认这两个流程保护点。
- 否决「强制结构化 review 输出」：用户明确要求不要过度 canonical，字段只用于兜底流程，不限制 agent 主观能动性。
