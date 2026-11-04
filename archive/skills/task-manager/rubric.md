---
target: skills/task-manager
updated: 2026-07-15
---
## 原则

- [已确认] 已明确授权且唯一定位的单条 task upsert 可直接写入；来源落盘、多 artifact、批量或覆盖操作保留预览与确认。

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-15
- 采纳「单条可逆 upsert 直接 apply」— 用户明确要求消除已授权写入的重复 dry-run 和二次确认。
