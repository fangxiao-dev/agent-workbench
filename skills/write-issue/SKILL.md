---
name: write-issue
description: 用中文起草或压缩 GitHub Issue 的标题与正文；不决定 label/关系，也不发布远程变更。
disable-model-invocation: true
---

# 编写 Issue

把已知事实写成短、清楚、方便人和 agent 接手的中文 Issue 正文。此 skill 是文字助手，不是 router 或 GitHub writer。

## 输入与边界

先读取用户提供的事实、相关 Issue/PR 和仓库 Issue 约定。若已有 `$issue-triage` proposal，只使用其中已确认的 work shape、labels、关系、人员和链接；不自行补全或修改它们。没有 proposal 但用户在问“要建什么、谁负责、如何标记、是否建 sub-issue”时，转交 `$issue-triage`。

绝不调用 `gh`、Python runtime 或任何远端写入。它也不创建评论、分支、assignee、reviewer、labels 或关系。

## 写作

- initiative 按 `skills/issue-workflow/templates/initiative.md` 起草，保留且写实 `## Closure condition`。
- 普通 leaf 或 investigation 按 `skills/issue-workflow/templates/actionable-issue.md` 起草；模板其余章节都是软引导，只保留承载事实的章节。
- 首屏写 Outcome、范围和可观察的 Acceptance；持久设计、测试或 CI 证据链接到权威文档或 PR，不复制长日志。
- Stakeholders 仅在已确认需要留存知情人时包含明确的 `@mention`；FYI 不暗示 assignee。
- 实际 branch 尚未开始时不写 `Working Branch`。

## 输出

返回建议标题和 Markdown 正文，并标明仍缺的事实。用户要发布时，要求通过 `$issue-triage` 将这份正文纳入完整 proposal 后确认。
