---
name: issue-reporter
description: 只读报告 GitHub Issue、PR 证据、父子关系和 label 合同健康度；适用于 portfolio、聚焦简报、audit 或 PR hygiene。
disable-model-invocation: true
---

# Issue Reporter

从当前 GitHub 工作图谱生成简短、可行动的只读报告。绝不创建、编辑、评论、打 label、分配、关闭或准备 mutation。

## 读取合同与范围

先读取 [机器合同](../references/issue-contract.yaml) 与 [语义边界](../references/issue-contract.md)，再用 `issue_workflow.py snapshot`、`validate` 和 `report` 获取事实。不要主动读取 `../assets/design/`；它不是运行时参考。`gh` 不可用、私库不可读或原生关系缺失时，报告 unknown，不把它说成合规。

按用户请求选择一种模式：

- 无范围或“现在有什么”：portfolio，按 Next actions、Blocked、Initiatives、Hygiene 汇总总量与最值得处理的事项。
- Issue 编号、URL 或 parent：Issue brief，说明直接 parent/sub-issue、依赖、直接 PR 和子树 PR 的关联层级。
- 用户给定模块、主题、label、assignee 或上下文：focused report；说明明确的筛选依据，不因名称相似推断相关。
- “检查组合/面板”：contract audit，列出开放 Issue 的 hard violation、advisory 与 unknown。
- 明确说“Repository hygiene”：才扫描全部开放 PR，报告未关联 parent 或 leaf Issue 的 PR；普通 portfolio 不做这个扫描。

## 报告边界

label 只说明工作形态与下一位行动者，不证明代码已实现或 PR 已合并。发现 Issue readiness 与 PR 证据不一致时写“需要 `$issue-triage` 确认交接”。Hygiene 是当前事实计算出的异常，不是新 label 或待办状态。

## 输出

先给可独立阅读的结论与计数，再给必要的 Issue/PR 编号、事实、合同推论和 unknown。每个异常说明为什么应交给 `$issue-triage` 提出最小修正，但 reporter 本身不追问、不制作计划、不写入。
