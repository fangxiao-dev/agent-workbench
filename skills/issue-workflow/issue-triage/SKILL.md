---
name: issue-triage
description: 根据自然语言和 GitHub 上下文路由 Issue；先给简短 proposal，获得确认后才发布已列出的 GitHub 变更。
disable-model-invocation: true
---

# Issue Triage Router

将用户的工作请求路由成最小、可确认的 GitHub Issue 变更。此 skill 是唯一的 Issue 工作流写入入口；它不把 PR 当作需求入口，也不自动评论、建分支、关闭或修复历史事项。

## 运行时合同

每次调用先读取 [共享机器合同](../references/issue-contract.yaml) 与 [语义边界](../references/issue-contract.md)。目标仓库存在 `.agents/issue-workflow.yaml` 时读取它以解析人员 alias；未知或冲突 alias 必须标为 `unknown`，不能猜测 @ 人。仅在将要写正文时读取 [initiative 模板](../templates/initiative.md) 或 [actionable 模板](../templates/actionable-issue.md)。不要主动读取 `../assets/design/`，它只用于用户明确要求追溯设计。

## 路由

1. 收集刚好足够的事实：用户输入、指定的 Issue/PR、相关 parent/sub-issue、已知依赖、当前 branch 和稳定文档链接。需要仓库事实时，调用 `issue_workflow.py snapshot`；关系读不到时保留 unknown。不要为了普通 issue triage 强制代码复现、grilling 或全仓检索。
2. 判断最小工作形态：需要多个独立切片、协调 owner 或关闭条件时建 `work:initiative`；主要未知是事实/决策时建 `work:investigation`；单一可验收工作建普通 leaf；只有独立验收、assignee、branch 或依赖才建 sub-issue。PR 可直接关联 parent 或 leaf。
3. 选择 type 与当前 readiness。`needs-info` 是定义不足，`ready-for-human` 是下一位需要决策/授权/review，`blocked` 是已知依赖，必须记录依赖、阻塞原因和解除条件。高优先级但可推进的工作保留实际 readiness，并在 proposal 中简短说明优先次序；不使用 priority label。状态交接只反映下一位行动者。
4. 用 `issue_workflow.py validate` 和 `plan` 计算组合、label diff、关系和人员 operation。Python 不决定业务分类，也没有 apply 子命令；若计划无效、snapshot 过期或关系未知，缩小结论或问一个最小问题。
5. 在任何远端写入前，输出不超过五行的 proposal，逐项列出创建/更新、labels、parent/dependency/PR、body diff，以及 `bodyMention`、`commentMention`、`issueAssignee`、`prReviewer`。说明一条关键依据并写明“等待确认”。

## 确认后发布

只在用户对当前完整 proposal 明确确认后，用已认证的 `gh` 执行 proposal 内的操作。一次确认可覆盖同一份逐项列表（包括 backlog sweep）；发现新 Issue、额外 @mention、关闭动作或范围扩大时停止并重新 proposal。

- 创建或编辑时只写确认过的标题、最小正文、labels、assignee、原生 parent/sub-issue 或 dependency、PR 关联和指定 mention。
- initiative 必须有非空 `## Closure condition`；实际开始分支工作后才写 `Working Branch`，不得凭空创建分支指针。
- 历史 Issue 规范化只改约定最小区块和已列 labels/关系；信息不足用 `needs-info`，不臆测 assignee、branch、PR、文档或关闭。
- 发布后只回读本次受影响对象，并报告成功、失败和仍为 unknown 的字段。

## 输出

普通路由先给 proposal；已确认发布后给受影响 Issue/PR、实际写入字段和回读结果。用户只问现状、面板、关系或异常时改用 `$issue-reporter`，不要准备 mutation。
