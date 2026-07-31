# 非 portfolio 模式的报告骨架

`SKILL.md` 承载 portfolio 的输出骨架。当路由落到下面某一模式时读取本文件；三条通用纪律（条目必须带标题与理由、每组最多展开 5 条、零结果与未执行范围不写）在所有模式中同样成立。

## Issue brief

给定 Issue 编号、URL 或 parent 时使用。

先用一句话说明这个 Issue 现在卡在哪一位手上、卡在什么上。再按下列层级给事实，每层只写存在的部分：

- 直接 parent 与 sub-issue：编号 + 标题 + 各自的 readiness。
- 依赖：`blockedBy` 与 `blocking` 双向都写，并说明依赖是否已解除。
- 直接 PR 与子树 PR 分开列，不要合并成一个 PR 列表；子树 PR 说明来自哪个 sub-issue。

readiness 与 PR 证据不一致时写明冲突的具体形态，不要只写"需要确认"。

## Focused report

用户给定模块、主题、label、assignee 或上下文时使用。

开头仍是结论句：现在最该处理的是哪一件、为什么。筛选依据写在结论句之后的一行，例如"按 label `area:auth` 筛选，未包含标题含 auth 但无该 label 的 Issue"——它是限定范围的补充说明，不是开场白，不能顶替结论句排到最前面。之后沿用 portfolio 骨架。不因名称相似把 Issue 纳入范围。

## Contract audit

用户要求"检查组合/面板"时使用。

按 hard violation、advisory、unknown 三段排列，hard violation 在前。每条写清违反了合同的哪一条规则、当前实际组合是什么、以及最小修正是什么。同类违规合并成一条并列出全部编号，不要逐个重复规则说明。

unknown 段只写限制了哪个结论的 unknown。

## Repository hygiene

只有用户明确说"Repository hygiene"时才扫描全部开放 PR；portfolio 不做这个扫描。

报告未关联 parent 或 leaf Issue 的 PR：编号 + 标题 + 它看起来应该挂到哪里（推测要标为推测）。无法判断归属的 PR 单列，不要强行分配。
