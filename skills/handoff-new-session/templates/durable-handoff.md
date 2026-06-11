# 耐久 Handoff 模板

## 第一部分：handoff 文件结构

按这个结构写 handoff 文件。Codex `create_thread` 路径下，child prompt 使用第二部分的索引式结构——prompt 不复述本文件内容，本文件是唯一事实源。

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
- 必须可执行。plan 已完成本地实现时，写成 closure orchestration 清单：仍需 owner 授权的外部动作、可先准备的材料（PR 描述、issue 更新文案、merge 清单）；禁止写成“等待 owner 指示”。
```

写作要求：

- 面向不知道对话历史的新会话写。
- 区分事实与假设；高信号优先，每个列表保持短。
- 不贴 secrets、token、env 值、完整日志。
- 不放 skill 沉淀 / continuous-learning 讨论。

## 第二部分：continuation prompt（chat 内返回或用于 create_thread，不落盘）

Prompt 定规则和索引，不复述 handoff 事实。**不要复制 Fresh Workspace State、Verified Gates、External State 等事实段**——它们只住在 rolling handoff 文件里。

# Continuation Prompt

长流程 prompt 应该是短启动器：10–25 行左右，只给执行模式和索引。不要在 prompt 里展开 closure checklist、PR body、issue comment、gate 结果、外部状态或 issue 细节；这些都住在 rolling handoff / plan / issue 文件里。

```text
你正在接手 [WORKFLOW_NAME] 的 rolling handoff。按 rolling handoff 的 Next Action 继续执行，直到下一个 handoff trigger、明确 blocker、plan 完成且 closure 收口、或 owner 要求停止。

执行模式：
- 你是 orchestration runner，不是一次性报告生成器。
- 主 session / 新 session 关注调度和 seaming，尽量派用 subagent 执行单个任务。
- 交接触发点：session context auto compact 了，或者自行识别到的大 gate。
- 第一条可见更新只简短说明：1) 会继续自动推进；2) 会按协作契约使用 worker/reviewer subagent（如当前阶段不需要 subagent，说明原因）。然后继续执行，不要等待 parent ACK。
- 先读 skill/rule，再验证 workspace；事实以 rolling handoff 为准。

硬护栏：
- 不 push / PR / GitHub issue/comment/close / merge，除非 owner 明确授权。
- 边界清晰的 implementation slice 先派 worker subagent；主 session/new session 负责调度、seam、review/gate、checkpoint commit、rolling handoff。

必读：
- [HANDOFF_NEW_SESSION_SKILL_PATH]
- [AUTO_HANDOFF_TRIGGERS_RULE_PATH]
- [ROLLING_HANDOFF_PATH]
- [PLAN_PATH]

第一步：
切到 [WORKTREE_PATH]，运行 `git status --short --branch` 和 `git log -1 --oneline`（expected HEAD: [EXPECTED_HEAD_ONELINE]），读取 rolling handoff 的 Open Issues / Not Completed / Next Action，然后发送上述短进度更新并继续推进。
```

要求：prompt 必含可执行 mission、执行模式、显式 subagent 授权、显式 handoff triggers、硬护栏、skill/rule/files 索引、HEAD 一行校验和、首条可见更新要求。事实细节、完整契约、开放问题全部留在 handoff 文件，prompt 只指向它们。
