# 常青文档回刷验证记录

- 阶段：`verify`
- 项目：
- 配置路径：
- 引用的 audit/apply 证据：

## 结果

- 检查数：
- 通过数：
- 失败数：
- 判决：`passed` / `failed`

## 确定性检查

| 检查 | 结果 | 证据 / 失败原因 |
| --- | --- | --- |

`configured-paths`、`pending-discovery`、`canonical-links`、`audit-contract`（如提供 `--audit-json`）、`inventory-candidates` 各占一行。

## 语义检查

| 条目 / 边界 | 结果 | 证据 / owner 决定 |
| --- | --- | --- |

## `_pending.md` 对账

- 各处 `_pending.md` 是否仍能唯一定位（无歧义/缺失）：
- 未关闭登记数：
- 未解决 owner decision 或 evidence gap：

## 已识别的任务包退役候选

| 任务包 ID | 结构性条件（Gate 终态 + 无未关闭登记 + 已在 done record）是否满足 | 仍需 agent 核实的第三条 |
| --- | --- | --- |

## 剩余阻断项

列出失败检查与仍需 owner 决策的条目。Verify 通过不自动表示整个开发任务、合入或发布 closed，也不表示 Package Retirement 候选已经可以清理。
