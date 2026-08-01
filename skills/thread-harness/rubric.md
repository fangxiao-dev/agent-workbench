---
target: skills/thread-harness
updated: 2026-08-01
---
## 原则

- [已确认] 停滞检测平时只用 Git HEAD 作为廉价信号；默认阈值为 5 轮，从 `3/5` 起每轮直接读取 active / working thread 的最新内容（证据: R1, R2）。
- [已确认] 不为 heartbeat 增加每轮消息缓存或修改 append-only JSONL ledger schema；fresh、具体的工作心跳可重置 streak，重复内容、旧进展或仅 active 状态不可重置（证据: R1）。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-01

- 采纳「平时看 HEAD；接近 `5/5` 时直接 read_thread；无需修改 ledger schema，也无需每轮缓存消息；确认仍有具体心跳则计数归零」— 用户明确确认并要求执行。

### R2 · 2026-08-01

- 修正主动检查起点为 `3/5`，并在 `3/5`、`4/5` 每轮直接 read_thread；用户明确指出不应等到 `4/5` 才开始。
