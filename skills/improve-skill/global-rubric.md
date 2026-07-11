---
target: global
updated: 2026-07-08
---
## 原则

- [已确认] skill 生态统一中文行文，保留英文术语 token（如 spec.md、NEEDS_SEAM、Granularity、slug）。用户原话确认为全局偏好，此前已在 feature-impl-planning、dev-with-track、create-task-dag 三个 skill 上执行。
- [已确认] Markdown 自然语言不按代码 80 字符硬折行；一个逻辑段落或列表项保持一物理行，换行只表达语义块边界，不能把术语、inline code 或链接拆开。

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08
- 采纳「中文行文 + 英文术语 token 为全局偏好」— 用户原话：是全局偏好

### R2 · 2026-07-11
- 采纳「Markdown prose 不使用代码行宽」为全局偏好 — 用户明确说明 80 字符只适用于代码，并要求从源头杜绝文档硬折行。
