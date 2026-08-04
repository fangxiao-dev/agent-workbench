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

如果下一 session 要继续代码、测试、implementation package 或其他有工作树状态的执行任务，读取 `references/task-execution.md`。它补充 compact bootstrap、分层读取、live snapshot 和启动动作的要求；普通知识交接不需要读取。

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

避免包含：

- 已在 plan.md 中列出的完整文件清单。
- 已在 gate.md 中列出的完整测试矩阵。
- 长 diff、长日志、完整 API payload、完整业务数据。
- 可从 commit 或 issue 直接读取的细节。

对于执行型交接，输出 compact control map，而不是把主控文档、Ticket、证据或历史 ER 提前展开。必须给出下一 session 的首个可执行动作、不要重复/暂不读取的工作、当前授权边界，以及已开始但没有可用结果的操作。不要把“已实现”“已验证”“已验收”“package closed”混写成一个完成状态；用来源和计数区分它们。

## 推荐结构

默认使用这个结构；如果任务很小，可以删减空章节。

```markdown
# 交接：<简短任务名称>

日期：<YYYY-MM-DD>

## 下一会话目标

## 启动控制图

## 下一会话首个动作

## 当前快照

## 权威产物

## 已完成

## 必须记住 / 门禁

## 待用户决定事项

## 备注
```

执行型交接可以在该模板中增加 `已完成（阶段限定）`、`开放 seam / gate`、`不要重复 / 暂不读取` 和 `授权与外部边界`，但仍应引用权威 artifact，不复制其正文。

## 安全与脱敏

Redact API keys、passwords、tokens、PII 和其他敏感信息。不要粘贴完整外部 API payload、完整客户/订单/商品敏感数据或可复现凭证；给摘要和 evidence 路径即可。

## 启动入口

执行型 handoff 只写下一 session 首轮立即需要的唯一 entry point；没有则省略。不要枚举后续可能使用的 skills，也不要把延后 skill 名称写入待粘贴的新 session prompt，因为显式名称可能触发立即读取并挤占启动上下文。后续 skill 由实际执行 seam 按需触发。
