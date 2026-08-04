# <NN> — <Ticket 标题>

**Ticket ID：** <ticket-id>

## 运行时验收状态（Runtime Acceptance Status）

<!-- impl-package:projection runtime-state begin -->
- 值：UNRECORDED
- 直接证据：none（Draft 尚无 runtime record）
<!-- impl-package:projection runtime-state end -->

**发布状态（Publication Status）：** Draft
**执行尝试 ID（Attempt ID）：** <attempt-id>
**规格修订（Spec Revision）：** S<n>
**计划修订（Plan Revision）：** P<n>

<!-- Plan Revision 是本 ticket 创建/最后确认时依据的 P<n>。plan 升级后，旧 P 号表示需要按实际 delta 判断影响；未受影响 ticket 可批量确认并机械更新，不重新起草或重批相同内容。 -->

<!-- 当当前 Composition earned DAG 时，Draft Ticket 先交给 create-task-dag 形成联合拆解 bundle；只有 bundle 联合校验通过并经 owner 一次 review 后，才可发布为 Approved。Ticket Approved 不代表 DAG 已创建或已单独通过。 -->

## 建设内容

<一个范围窄、边界完整、用户可见的交付与验收切片。>

## 验收标准

- **AC-1：** <可观察结果或约束>
  - 证据：<计划证据或人工验证 owner>

## 阻塞依赖

- <implementation|acceptance|release>: <ticket-id>

没有阻塞边时填写 `None`。

不要添加 worker ownership、task 分配、文件级步骤或 runtime task status。

Ticket 的 acceptance state 由 `.impl-package/runtime-state.json` 记录，并由本段 marker 投影；恢复入口是 package 根 `progress.md`，执行历史位于 `execution-records/index.md`。Ticket 不写 Phase、Next 或 Progress，也不承载 Task/worker 进度。
