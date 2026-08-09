# 常青文档回刷应用记录

- 阶段：`apply`
- 应用时间：
- 项目：
- 来源审计报告 / CLI 输出：
- Apply 时的 Source HEAD：
- Owner 批准：`<audit/report path 或 CLI 输出>` + 精确 item ID

## 已应用条目

| 条目 ID | 来源 | 结果 | 长期归属位置 | `records.done` 写入 | pending 关闭（如有） |
| --- | --- | --- | --- | --- | --- |

`Origin` 是 `pending-registry` 或 `gap-catching`。所有已处置 item 必须写入 `records.done`（含 `id` / `packagePath` / `deltaId` / `comparisonCommit`）。`pending-registry` item 若来自 `_pending.md` 还需关闭对应行；`gap-catching` item **不要**伪造 pending 再关闭。

## 延期 / 冲突 / 拒绝

| 条目 ID | 处置 | 原因 | `records.done` | pending 状态 |
| --- | --- | --- | --- | --- |

## 破坏性 Apply（如适用）

| 路径 / Package ID | 操作 | Owner 授权引用 | 执行前重新核对结果 |
| --- | --- | --- | --- |

只在有独立 destructive-apply 授权时填写；普通 item 批准不能覆盖这类操作。

## 验证

- 已批准条目与 diff 映射：
- Canonical owner / pointer 检查：
- 链接 / anchor 检查：
- 项目特定检查：
- `git diff --check`:

## 范围声明

仅应用 owner 批准的报告条目 ID。破坏性操作只针对独立、精确到路径或任务包 ID 的 destructive-apply 批准执行；未批准条目未纳入。
