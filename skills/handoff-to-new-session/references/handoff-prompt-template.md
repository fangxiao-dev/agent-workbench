# Handoff Prompt Template

Fill these two compact cards from verified package records. A Ticket may span sessions; the package active checkpoint is the normal recovery authority. These cards are not a summary of the old conversation or a duplicate of the implementation package. Keep them together within 16 bullets / roughly 900 Chinese characters unless a named authorization or blocker genuinely needs more context. Never add commands, test lists, design detail, task decomposition, file boundaries, secrets, controlled inputs, or historical evidence already available from the authority entry point.

## First-stage anchor prompt

```text
[TASK / PACKAGE] 的全新独立 local session；不继承旧会话历史。

执行锚点（首轮和后续命令都必须使用此 workdir）：
- worktree：[ABSOLUTE_WORKTREE_PATH]
- expected HEAD：[FULL_GIT_HEAD]
- [AUTHORITY_ANCHOR_BLOCK: package + entry point, OR downstream context anchors]
- [OPTIONAL_READ_ONLY_VALIDATION_ANCHORS_OR_N/A]

首轮只在上述 worktree 做只读 anchor 检查。任一不符：只报告 `anchor FAIL: source worktree setup mismatch` 与实际值，停止，不 repair。全部匹配：只报告 `anchor PASS` 与锚点值，停止；不要读取恢复记录或开始工作。
```

## Second-stage continuation prompt

Send this only after the title and first-stage `anchor PASS` are confirmed.
For a downstream protocol extension, replace the task-specific lines with that protocol's complete continuation contract, but retain the final understanding-receipt lines. Do not combine the two task contracts.

```text
Continuation 已就绪。通过 package 与 entry point 从文档化 active checkpoint [CHECKPOINT] 恢复；不回溯重做已登记工作。Context compact 只作异常兜底，不取代 checkpoint。

极简快照：
- current attempt / binding：[ATTEMPT_AND_BINDING]
- status：[COUNTED_STATUS_AND_LATEST_GATE]
- next action：[SINGLE_RECORDED_NEXT_ACTION]
- already earned：[ONE_RELEVANT_PROOF_OR_N/A]
- still required：[REMAINING_CLOSURE_PROOF]

边界：
- 未提交内容只保护：不得 reset、checkout、clean、覆盖或重建。
- 调度：mode=[MODE] / worker=[WORKER] / schedule=[SCHEDULE] / review=[REVIEW]；[MAIN_SESSION_AND_SUBAGENT_BOUNDARY]
- 收口：[GO_SCOPE_AUTOMATIC_VERIFICATION_REVIEW_CLAIM_AUDIT_GATE_RULE_OR_N/A]
- [ONE_LINE_AUTHORIZATION_OR_N/A]；[NAMED_BLOCKER_OR_STOP_CONDITION_OR_N/A]
- 不得把凭证、真实客户数据、PDF/CSV/provider payload、oracle artifact 或秘密写入 Git、聊天或临时文件。
- 仍需单独授权：[ACTIONS_REQUIRING_SEPARATE_AUTHORIZATION]

收到后先用一条简洁 commentary 回报本 session 的目标与 next actions、所用 skill/方法及用途，以及本 session 应完成后汇报、因具名 blocker 停止，还是按记录移交。
这是理解回报，不是执行预演；覆盖影响执行与收口的约束、授权和 blocker，不展开执行步骤或实现细节，也不等待批准。发出后立即从 entry point 恢复最小记录并执行 Next Action，仅在上述具名输入、授权或 blocker 缺失时停止。
```
