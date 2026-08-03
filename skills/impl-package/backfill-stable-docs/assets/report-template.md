# 常青文档回刷审计报告

- 阶段：`audit`
- 生成时间：
- 项目：
- Source HEAD / dirty 基线：
- 目标分支 / 已解析 commit：
- 配置来源 / digest：
- Contract preflight：`current` / `advisory`
- Contract drift advisory packages：
- 已发现的 `_pending.md` root：
- 配置缺口（`_pending.md` 歧义/缺失）：
- System pending 冷启动 owner 决定：

## 执行结论

- Contract drift advisory（不阻断 pending-registry audit）：
- 来自 `_pending.md` 的候选（主渠道）：
- 来自 gap-catching 的候选（兜底）：
- 已覆盖：
- 冲突：
- 无 delta module：
- 建议 apply 边界：

## 常青权威覆盖

| 层级 | 常青 root / owner | Pending 路径 | 发现状态 | 结果 | 候选 ID | 证据备注 |
| --- | --- | --- | --- | --- | --- | --- |

每个 configured system/context/module stable root 必须出现；省略的 `contextKnowledge` 不生成虚拟行。多个 root 共用一个 pending register 时保留各 root 的 coverage，但登记候选只消费一次。Discovery status 使用 `ok`、`cold-start`、`missing`、`ambiguous`；`cold-start` 是非阻塞 owner decision，不算 config gap。Result 仅用 `candidate`、`already-covered`、`conflict`、`no-delta`。

## 候选 Delta

| ID | 来源 | Module | 目标位置 | Pending 引用（如有） | 陈述 | 当前证据 | 现有覆盖 | 风险 | 建议 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

`Origin` 只用 `pending-registry`（来自 `_pending.md` 主渠道）或 `gap-catching`（gate 已 terminal 但没有对应登记，重新发现）。`pending-registry` 行必须填 `Pending ref`，指向来源 `_pending.md` 文件和其中的登记行。

## Pending 登记交叉核验

| `_pending.md` 路径 | 登记条目数（未关闭） | 已核验仍成立 | 需要 owner 裁决 |
| --- | --- | --- | --- |

## Gap-Catching 发现

| 来源任务包 | 为何没有对应登记 | 受影响 module | 建议 disposition |
| --- | --- | --- | --- |

## 任务包退役候选

| 任务包 ID | Gate ledger 终态 | 目标分支 Git 证据 | Pending 关闭情况 | 吸收去向 | 入站引用 | 剩余目录内容 | 备注 |
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

除本报告文件（写入配置 `records.reports` 目录）或用户明确指定的外部 output directory 外，未修改 stable docs、`_pending.md`、`done.json`、source packages 或代码。
