---
target: skills/call-grok
updated: 2026-08-19
---
## 原则

- [待验证] 三阶段行为只在 frontmatter 触发摘要与 wrapper 注入协议中出现；Skill 正文、caller contract 和测试不复制阶段定义。（证据: R1）
- [待验证] `SKILL.md` 保持 60 行以内，删除防御性 no-op；VERIFY 同时承担自测与按需独立 subagent closure，不强制 commit。（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-19
- 采纳将 THINK → IMPLEMENT → VERIFY 固化为 wrapper 行为，同时保持 `SKILL.md` 薄。
- 采纳合并 self-verification 与 independent internal closure，并删除 commit 强制和无意义的 authority 防御文案。
- 采纳删除 Skill、caller contract 与重复测试中的阶段复述，以 runtime protocol 为行为 SSOT。
