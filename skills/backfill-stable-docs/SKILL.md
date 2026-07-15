---
name: backfill-stable-docs
description: Use when auditing, applying approved durable knowledge deltas, or independently verifying an evergreen module-knowledge layer.
---

# Backfill Stable Docs

公共入口 `$backfill-stable-docs` 维护项目的常青 module-knowledge 快照。它只做意图路由：默认执行 audit；apply 和 verify 分别加载独立 runbook。不要把 runbook 名当成独立 Skill，也不要使用 Plugin namespaced 调用。

## 共享输入合同

- 目标项目必须是 Git top-level；配置取显式 `--config <path>`，否则取项目根 `.stable-docs-backfill.json`。
- 每份配置只定义一个 context；monorepo 的 repo-wide 与 nested domain 必须使用两份配置、两次独立运行，禁止引入 `contexts[]` 或混合其 state、pending、implementation packages。
- 所有确定性脚本位于本 Skill 的 `scripts/`。它们从自身解析后的物理路径推导 enclosing `agent-workbench` Git top-level，并把其 portable `repository + commit` 写作 `methodActivation`。本机绝对 method path 不进入项目记录。
- 该锚点同时要求同一 commit 含本 Skill 和 `skills/impl-package/SKILL.md`；它证明两者原子版本，不参与目标项目 Git range。
- Project Source Watermark 必须在目标项目内且是固定 Source HEAD 的 ancestor。缺失或不可信时 fail closed；bootstrap 只接受 owner 明确给出的有界 source manifest。
- Plugin-era audit/state 仅是 provenance，不能直接 apply；先重新 audit，得到当前 repository+commit 锚点的报告。

完整的双锚点、source selection、carry-forward 合同见 [双锚点与来源选择](references/source-selection-and-dual-anchor.md)。

## 路由

| 用户意图 | 读取 | 写入边界 |
| --- | --- | --- |
| 未指定阶段、盘点、扫描、报告 | [audit runbook](references/audit-runbook.md) | 只允许 `_compaction/` 下的新报告；不改 canonical docs、pending、水位线或链接 |
| 只应用某报告的批准 item ID | [apply runbook](references/apply-runbook.md) | 只写 owner 明确批准且 evidence 未漂移的 item；其余保持 pending |
| 检查 authority、链接、覆盖率、pending、水位线或残留 | [verify runbook](references/verify-runbook.md) | 不补写内容、不隐式 apply |

如果意图含混，默认 audit。apply 必须同时给出 audit/report 路径和 owner 批准的精确 item ID；“全部处理”不是批准清单。verify 绝不因为发现问题而修复文档。

## 持久知识边界

`CONTEXT.md` 与 `docs/top-level-knowledge/**` 只承载当前产品语言、意图、架构与行为。退役能力的 provenance 留在 Git 历史、migration ledger、implementation package 或 compaction report/apply record；只有 owner 已批准的 future 能作为明确标记的 TODO 留下。历史输入与当前权威冲突时按 source 顺序和 owner conflict gate 裁决，不通过把历史说明留在常青层回避裁决。

## 输出

最终说明实际 runbook、method activation、Source HEAD、报告或 apply record 路径、candidate/covered/conflict/pending 计数、carry-forward、水位线验证结果与仍需 owner 决策的 item ID。只有用户明确要求 PR 时才读取 [PR Summary 模板](assets/pr-summary-template.md)。
