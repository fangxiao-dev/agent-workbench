# 耐久 Handoff 模板

## 第一部分：handoff 文件结构

按这个结构写 handoff 文件；Codex `create_thread` 路径下，child prompt 直接复用同样的段落骨架。

默认文件名使用 rolling handoff：`docs/exchange/handoffs/handoff-<slug>-current.md`。只有用户要求、审计冻结、长期分叉、或多个 child 必须从不同时间点恢复时，才额外写 `handoff-<slug>-MMDDhhmm.md` 归档快照。

```md
# Rolling Handoff: [Workflow Name]

## Handoff Mode
- Rolling current handoff; this is the only continuation entrypoint.
- Supersedes: [older timestamped handoffs, if relevant].
- Archived snapshot: [only when this file is intentionally frozen].

## Current Objective
- 当前目标、本轮要推进到哪里、为什么现在做。

## Fresh Workspace State
- 实现 worktree 的绝对路径；多 workspace 时写明各自角色（实现 / 主工作区 / 协调）。
- branch、HEAD、dirty/clean、与 trunk 的偏差（ahead/behind）。
- 一律取自实际 git 输出，不靠记忆。

## Completed / Not Completed
- 已完成、部分完成、未完成分开写。
- 明确不要提前做的任务单独列出。

## Verified / Not Verified
- 跑过的关键命令、gate 与结果。
- 未验证项与风险；验证被阻塞时写明 blocker。

## What Changed
- 行为级变更摘要（代码、逻辑、UI、工作流、文档），不要原始编辑清单。

## Pitfalls / Do Not Repeat
- 每个重要问题：现象、根因、解法、是根治还是缓解。
- 已排除的错误假设和失败路线，避免 child 重走。

## External State
- issue/PR/comment/邮件等外部动作及类型。
- 明确 not pushed / not merged / not closed 等未完成外部状态。

## Open Issues
- 遗留 bug、验证缺口、待定决策。
- child 改代码前必须先确认的事项。

## Collaboration Contract
- 用户明确偏好写成执行规则；inferred 行为标注 inferred / pending confirmation。
- 一次性权限不升级为长期权限；subagent / main session 所有权边界写清。

## Next Action
- 新会话第一动作；必读文件（短清单）；首个验证命令或手动检查。
```

写作要求：

- 面向不知道对话历史的新会话写。
- 区分事实与假设；高信号优先，每个列表保持短。
- 不贴 secrets、token、env 值、完整日志。
- 不放 skill 沉淀 / continuous-learning 讨论。

## 第二部分：continuation prompt（chat 内返回，不落盘）

```md
# Continuation Prompt

## Handoff
已将 handoff 落盘。请先阅读 `[HANDOFF_FILE_PATH]`，然后继续这个任务。

## Current Objective
[CURRENT_GOAL]

## Current State
[CURRENT_STATUS]

## Workspace Constraints
[WORKSPACE_OR_WORKTREE_CONSTRAINTS]

## Collaboration Contract
[COLLABORATION_CONTRACT_SUMMARY；只写最关键的 2-4 条硬规则，例如主 session 不直接实现清晰 slice、先派 worker subagent、主 session 负责 seam/integration gate、禁止未授权 push/PR。完整协作细节放在 handoff 文件和 Required Skill Context 中。]

## Required Skill Context
- `[HANDOFF_NEW_SESSION_SKILL_PATH]`

## Required Rule Context
- `[AUTO_HANDOFF_TRIGGERS_RULE_PATH]`

## Required Files
- [FILE_1]
- [FILE_2]

## First Recommended Action
[FIRST_RECOMMENDED_ACTION]

## Verification Rule
继续实现前，先验证当前状态，不要假设 handoff 中提到的修复或未验证项已经成立。

## Open Issues
如果以下开放问题仍未确认，请先确认再动手：
- [OPEN_ISSUE_1]
```

要求：使用带章节的 Markdown prompt；必含 handoff 文件路径、当前目标、当前状态、工作区约束、精简协作契约、Required Skill Context、本 skill 路径、Required Rule Context、自动 handoff 触发 rule 路径、“先验证再继续”的指令；没有开放问题时也要写明“无已知开放问题，但仍需先验证状态”。协作契约在 prompt 中保持短，只放最关键护栏；完整规则写入 handoff 文件、本 skill 和 Required Rule Context。
