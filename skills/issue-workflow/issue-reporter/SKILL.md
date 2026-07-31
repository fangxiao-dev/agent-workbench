---
name: issue-reporter
description: 只读报告 GitHub Issue、PR 证据、父子关系和 label 合同健康度；适用于 portfolio、聚焦简报、audit 或 PR hygiene。
disable-model-invocation: true
---

# Issue Reporter

从当前 GitHub 工作图谱生成简短、可行动的只读报告。绝不创建、编辑、评论、打 label、分配、关闭或准备 mutation。

## 读取合同与范围

先读取 [机器合同](../references/issue-contract.yaml) 与 [语义边界](../references/issue-contract.md)，再用 `issue_workflow.py snapshot`、`validate` 和 `report` 获取事实。不要主动读取 `../assets/design/`；它不是运行时参考。`gh` 不可用、私库不可读或原生关系缺失时，报告 unknown，不把它说成合规。

按用户请求选择一种模式。落到 portfolio 以外的模式时，读取 [报告骨架](references/report-formats.md)：

- 无范围或“现在有什么”：portfolio，按下面的输出骨架给报告。
- Issue 编号、URL 或 parent：Issue brief。
- 用户给定模块、主题、label、assignee 或上下文：focused report。
- “检查组合/面板”：contract audit。
- 明确说“Repository hygiene”：才扫描全部开放 PR；普通 portfolio 不做这个扫描。

## 报告边界

label 只说明工作形态与下一位行动者，不证明代码已实现或 PR 已合并。发现 Issue readiness 与 PR 证据不一致时写“需要 `$issue-triage` 确认交接”。Hygiene 是当前事实计算出的异常，不是新 label 或待办状态。

## 输出

报告按“下一步做什么”组织，不按扫描过程组织。开头一句话给结论：现在最该处理的是哪一件、为什么是它。不要用扫描总量和合规计数开场。

之后按 Next actions、Blocked、Initiatives、Hygiene 分组。每个条目必须是编号 + 标题 + 一句“为什么现在轮到它”，禁止只给编号列表——裸编号让用户必须逐个点开才知道是什么工作。每组按可立即推进的程度排序，最多展开 5 条，其余压成一行“另有 N 条：#a、#b、#c”。

只写会改变结论的事实。计数为零的分组、本次未执行的扫描范围、以及不影响任何结论的 unknown 都不出现；影响结论的 unknown 照常写明，并说清它限制了哪一条结论。

每个异常说明为什么应交给 `$issue-triage` 提出最小修正，但 reporter 本身不追问、不制作计划、不写入。

## needs-info 分桶

`report` 的 `needsInfo` 字段把 needs-info 存量按机械信号分三桶，不打分、不排百分比：

- `labelLag`：已有直接 PR、assignee，或正文已含非空 `## Acceptance`——很可能已经能动，只是 label 没跟上事实。列进 Next actions 最前面，说明应交给 `$issue-triage` 核对并转 ready。
- `singleGap`：正文有非空 `## Outcome` 但缺 `## Acceptance`，且无 `blockedBy`——只差一个事实或一个决策。判断缺的是事实还是决策时才用语义判断，分别提示转 `ready-for-agent` 或 `ready-for-human`；桶的归属本身只看结构信号，不看语义。
- `emptyNumbers`：正文为空或只有标题——定义确实为空，不展开，只给计数和编号。

三桶的存在把“57 个 needs-info”换成“几条大概率能动 + 一批真空壳”，这才是分桶要交付的结论，不是重新排序。`labelLag` 内如需要排序，按 `updatedAt` 最近优先；不要为其余桶发明额外排序维度。
