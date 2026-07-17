---
name: handoff
description: 将当前会话压缩为下一位 agent 可直接接手的聚焦交接文档。适用于用户要求交接、上下文快照、续接说明，或为另一会话、agent、worktree 做准备，尤其适合已有计划、提交、Issue 或产物应被引用而非复制的情形。
argument-hint: "下一会话将用于处理什么？"
disable-model-invocation: true
---

# 交接

把当前会话压缩成一份下一位 agent 能直接接手的交接文档。交接文档的价值在于保存当前状态、入口和风险，而不是复制已有计划或日志。

## 输出位置

把 handoff 文档保存到用户 OS 的临时目录，不要保存在当前 workspace。完成后把文件路径告诉用户。

## 聚焦范围

如果用户传入参数或补充说明，把它当成下一 session 的 focus。围绕这个 focus 收窄内容：

- 排除与下一步无关的历史讨论、旁支分支、已关闭问题和旧调查细节。
- 只保留下一位 agent 继续工作必须知道的状态、入口、边界和决策。
- 如果用户明确说“聚焦本次任务”或类似要求，不要回顾完整聊天史。

## 引用优先

不要复制已经存在于 PRD、plan、ADR、issue、commit、diff、测试日志或 artifact 里的内容。只写：

- artifact 路径或 URL；
- 该 artifact 的用途；
- 下一位 agent 应先看哪几个文件。

同一目录下的多个权威文件，用“base directory + filenames”表达，不要逐条写绝对路径。只有跨仓库、临时目录、外部 artifact、下载文件或其他容易找错的位置，才使用绝对路径。

## 内容边界

优先写 snapshot，不写 plan detail。

应该包含：

- 当前 worktree / repo / branch / dirty state。
- 最新相关 commits 或尚未提交的变更状态。
- 下一步真正的入口，例如要读的 plan、gate、issue、task ledger。
- 不能忘的 gate、授权要求、外部系统读写边界。
- 已经完成且会影响下一步判断的验证摘要。
- 用户还需要做的 residual decisions。
- suggested skills。

避免包含：

- 已在 plan.md 中列出的完整文件清单。
- 已在 gate.md 中列出的完整测试矩阵。
- 长 diff、长日志、完整 API payload、完整业务数据。
- 可从 commit 或 issue 直接读取的细节。

## 推荐结构

默认使用这个结构；如果任务很小，可以删减空章节。

```markdown
# 交接：<简短任务名称>

日期：<YYYY-MM-DD>

## 下一会话目标

## 当前快照

## 权威产物

## 已完成

## 必须记住 / 门禁

## 建议使用的 Skills

## 待用户决定事项

## 备注
```

## 安全与脱敏

Redact API keys、passwords、tokens、PII 和其他敏感信息。不要粘贴完整外部 API payload、完整客户/订单/商品敏感数据或可复现凭证；给摘要和 evidence 路径即可。

## 建议使用的 Skills

交接文档必须包含 `建议使用的 Skills` 章节。只推荐下一会话确实可能需要调用的 skill，并用一句短说明解释原因。
