# 常青文档回刷审计报告

- 阶段：`audit`
- 生成时间：
- 项目：
- Source HEAD / dirty 基线：
- 目标分支 / 已解析 commit：
- 配置路径：
- Contract preflight：`current` / `advisory`
- Contract drift advisory packages：
- 可选 pending 路径（可为空）：
- `records.done` 路径 / 状态：

## 执行结论

- Contract drift advisory（不阻断 audit）：
- 来自 pending-registry 的候选（可选人工队列）：
- 来自 gap-catching 的候选（terminal Gate + target 可达 + 不在 done）：
- 被 done 过滤的 item（含原因）：
- 已覆盖：
- 冲突：
- 无 delta（含 Gate `none`）：
- 建议 apply 边界：

## 常青权威覆盖

| 层级 | 常青 root / owner | 发现状态 | 结果 | 候选 ID | 证据备注 |
| --- | --- | --- | --- | --- |

每个 configured system/context/module stable root 必须出现；省略的 `contextKnowledge` 不生成虚拟行。Result 仅用 `candidate`、`already-covered`、`conflict`、`no-delta`。

## 候选 Delta

| ID | 来源 | Module | 目标位置 | Pending 引用（如有） | 陈述 | 当前证据 | 现有覆盖 | 风险 | 建议 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

`Origin` 只用 `pending-registry`（可选人工队列）或 `gap-catching`（terminal Gate Durable Delta 且不在 done）。Item ID 为 `<package-path>::<delta-id>`。

## Done 过滤

| ID | 来源 | comparisonCommit | 过滤原因 |
| --- | --- | --- | --- |

## Pending 登记（如配置）

| pending 路径 | 未关闭条目数 | 已核验仍成立 | 需要 owner 裁决 |
| --- | --- | --- | --- |

## Gap-Catching 发现

| 条目 ID | 来源任务包 | comparisonCommit | 受影响 module | 建议 disposition |
| --- | --- | --- | --- | --- |

## 任务包退役候选

| 任务包 ID | Gate 终态 | 目标分支 Git 证据 | Durable delta / done 关闭情况 | 吸收去向 | 入站引用 | 剩余目录内容 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |

只报告候选，不在 audit 里清理；执行见 [package retirement runbook](../references/package-retirement-runbook.md)。

## 冲突与 Owner 决定

| ID | 冲突权威 | 安全不变量 | 所需决定 |
| --- | --- | --- | --- |

## 当前系统知识边界

| 受影响常青文档路径 | 当前合同处置 | 退役 / future 决定 | 验证 |
| --- | --- | --- | --- |

Canonical system docs 不保留历史/退役能力的兼容说明。只有 owner 已批准的 future capability 才可登记 TODO，且必须明确为非当前合同、写明目标与前提。

## 建议 Apply 顺序

仅列 item ID、目标和依赖；audit 不执行。破坏性操作（含 Package Retirement）单独列出，需要独立的 destructive-apply 批准。

## 只读声明

除本报告文件（CLI 输出或用户明确指定路径）外，未修改 stable docs、pending、`records.done`、source packages 或代码。
