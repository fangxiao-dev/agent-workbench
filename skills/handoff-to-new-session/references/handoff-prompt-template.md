# Handoff Prompt Template

Fill these two compact cards from verified package records. They are not a summary of the old conversation or a duplicate of the implementation package. Keep them together within 16 bullets / roughly 900 Chinese characters unless a named authorization or blocker genuinely needs more context. Never add commands, test lists, design detail, task decomposition, file boundaries, secrets, controlled inputs, or historical evidence already available from the authority entry point.

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
For a downstream protocol extension, replace this card with that protocol's complete continuation contract; do not combine the two.

```text
Continuation 已就绪。通过 package 与 entry point 从 [CHECKPOINT] 恢复；不回溯重做已登记工作。

极简快照：
- current attempt / binding：[ATTEMPT_AND_BINDING]
- status：[COUNTED_STATUS_AND_LATEST_GATE]
- next action：[SINGLE_RECORDED_NEXT_ACTION]
- already earned：[ONE_RELEVANT_PROOF_OR_N/A]
- still required：[REMAINING_CLOSURE_PROOF]

边界：
- 未提交内容只保护：不得 reset、checkout、clean、覆盖或重建。
- 调度模式：[default-long / ordinary]；[MODE_SPECIFIC_MAIN_SESSION_AND_SUBAGENT_RULE]
- 收口：[GO_SCOPE_AUTOMATIC_VERIFICATION_REVIEW_CLAIM_AUDIT_GATE_RULE_OR_N/A]
- [ONE_LINE_AUTHORIZATION_OR_N/A]；[NAMED_BLOCKER_OR_STOP_CONDITION_OR_N/A]
- 不得把凭证、真实客户数据、PDF/CSV/provider payload、oracle artifact 或秘密写入 Git、聊天或临时文件。
- 仍需单独授权：[ACTIONS_REQUIRING_SEPARATE_AUTHORIZATION]

现在从 entry point 恢复最小记录并执行已登记 Next Action；无需再次确认，仅在上述具名输入、授权或 blocker 缺失时停止。
```
