# 常青文档回刷应用记录

- 阶段：`apply`
- 应用时间：
- 项目：
- 来源审计报告：
- Apply 时的 Source HEAD：
- Owner 批准：`<audit/report path>` + 精确 item ID

## 已应用条目

| 条目 ID | 来源 | 结果 | 长期归属位置 | `_pending.md` 关闭情况 |
| --- | --- | --- | --- | --- |

`Origin` 是 `pending-registry` 或 `gap-catching`；`pending-registry` item 必须同时关闭来源 `_pending.md` 里对应的登记行，`gap-catching` item 必须先补一条登记再关闭——两者在这张表的最后一列都要写明关闭结果，不能只写自己的 `done.json` 而不动 `_pending.md`。

## 延期 / 冲突 / 拒绝

| 条目 ID | 处置 | 原因 | `_pending.md` 状态 |
| --- | --- | --- | --- |

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
