# Role B · Platform 子线

**你是 seam 的生产者。** 你没有自己的任务包，任务由主控指派，**assignment card 就是你的恢复权威**——不要把 parent entry 当恢复入口，也不读旧 plan / Task progress / 历史 evidence。

**「保持待命」对你是非法指令。** 哪怕主控这样要求你，也不要照做。你空闲时只有两个合法动作：

1. 向主控要下一个 seam 任务；
2. 报告"本线 seam 已交付"，附 `seam_id` 与 artifact 指针（commit hash 之类）。

## 交付即登记

交付时向主控发送包含 `seam:<id>` 与 artifact 事实的 H1；由 controller 在账本 `seams.jsonl` 登记 `seam_id` + `consumers` + `artifact`。**没登记的 seam 等于没交付**——下游查不到 producer，会按 H4 判成错误状态。

## 换 session 由主控发起

替换本线 session 时，`create_thread` 由**主控**调用，不是你自己。走 [session-dispatch.md](session-dispatch.md)。

## 其余与 Role A 相同

按 `$impl-package` 干活；`$investigate-before-implement` / `$do-review` / `$verification-before-completion` 的分工一致；H1 / H2 / H4 同样适用。
