---
target: skills/backfill-stable-docs
updated: 2026-07-15
---
## 原则

- [已确认] Audit/apply 失效必须按 item-local evidence 和语义影响收缩；同 repository 的方法版本或 descendant Source HEAD 漂移不能迫使未受影响 item 重做。

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-15
- 采纳「以 item-scoped fingerprint 替代全局 method commit/Source HEAD 等值门」— 用户原话：改为 item-scoped fingerprint；只让受影响 item 失效。
