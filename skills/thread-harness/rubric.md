---
target: skills/thread-harness
updated: 2026-08-02
---
## 原则

- [已确认] 停滞检测平时只用 Git HEAD 作为廉价信号；默认阈值为 5 轮，从 `3/5` 起每轮直接读取 active / working thread 的最新内容（证据: R1, R2）。
- [已确认] 不为 heartbeat 增加每轮消息缓存或修改 append-only JSONL ledger schema；fresh、具体的工作心跳可重置 streak，重复内容、旧进展或仅 active 状态不可重置（证据: R1）。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-01

- 采纳「平时看 HEAD；接近 `5/5` 时直接 read_thread；无需修改 ledger schema，也无需每轮缓存消息；确认仍有具体心跳则计数归零」— 用户明确确认并要求执行。

### R2 · 2026-08-01

- 修正主动检查起点为 `3/5`，并在 `3/5`、`4/5` 每轮直接 read_thread；用户明确指出不应等到 `4/5` 才开始。

### R3 · 2026-08-02

- Owner 明确本轮采用单一显式 `--registry <absolute-json>`，runtime 从 registry sibling 推导；不新增 `--broker-root`，旧 `--coordination-id` / 环境变量调用继续兼容。
- Owner 明确 child registry 的 `active` 缺失按 `true` 处理；poll、children 上限、worktree/branch 唯一性只作用于 active child；inactive 保留，done 不自动退休但不进入 `idle_nodes`。
- Owner 明确 controller 是 ledger 唯一写入者；child 只发送包含 `v/node/session_id/event/state/head/waiting_on/artifact/note` 的结构化 H1，controller 验证 current session 与 worktree HEAD 关系后写 report/seam/decide。
- ~~replacement source child 写 Temp prepare-only card，由 controller 转手创建继任者~~ —— **R4 已推翻，见下**。
- Owner 明确不加 `act --resume`；halt 记录当前 poll seq，Owner 明确恢复后的新有效 poll/sync 自动使旧 halt 失效；`status` 在 runtime 缺失时只读并输出 `runtime_uninitialized`，不得创建文件。

### R4 · 2026-08-02

- 推翻 R3 第 4 条：replacement 由**退休 session 自己**调 `create_thread`（Role A / Role C），不再写 Temp prepare-only card、不再由 controller 转手创建。用户理由：`$handoff-to-new-session` 本就是为 session 自交接设计的，SKILL 与 prompt 模板已成熟，中间卡片是在成熟机制上重造一层。该 skill 原文亦明确 *"not a temporary handoff document"*。Role B 仍由 controller 建（无自述状态）。
- 引用外部 skill 时不重复定义它已经拥有的东西（card 路径、prompt 形状、流程步骤）；本 skill 只写 harness 特有的 override。
