# Legacy Task Handoff: <Task ID>

- Attempt：<attempt-id>
- Canonical path：execution/<attempt-id>/task-handoffs/<task-id>-handoff.md
- Task state：<BLOCKED|RUNNING|READY>
- Blocker / reason：
- Evidence：<repo-relative-path#anchor>
- Next action：
- Affected Tickets：<ids | none>
- Authorized write-set：<repo-relative paths>
- Receiver / owner：

仅旧 3.4/Task package 在实际 BLOCKED、重试、跨 session/owner 移交或并行委派时创建。Ticket-only package 使用 active checkpoint，不创建此文件。它是可更新的局部接手快照，不是状态或 Execution Record；公共恢复入口为根 `progress.md`。
