# Handoff Initial Prompt Template

Fill this compact anchor card from verified package records. It is not a summary of the old conversation or a duplicate of the implementation package. Keep it within 16 bullets / roughly 900 Chinese characters unless a named authorization or blocker genuinely needs more context. Never add commands, test lists, design detail, task decomposition, file boundaries, secrets, controlled inputs, or historical evidence already available from the authority entry point.

```text
接手 [TASK / PACKAGE]，从 [CHECKPOINT] 继续；不继承旧会话历史，也不回溯重做已登记工作。

执行锚点（首轮和后续命令都必须使用此 workdir）：
- worktree：[ABSOLUTE_WORKTREE_PATH]
- expected HEAD：[FULL_GIT_HEAD]
- package：[PACKAGE_DIRECTORY]
- entry point：[IMPL_PACKAGE_ENTRY_POINT]

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
- [ONE_LINE_AUTHORIZATION_OR_N/A]
- [NAMED_BLOCKER_OR_STOP_CONDITION_OR_N/A]
- 不得把凭证、真实客户数据、PDF/CSV/provider payload、oracle artifact 或秘密写入 Git、聊天或临时文件。
- 仍需单独授权：[ACTIONS_REQUIRING_SEPARATE_AUTHORIZATION]

首轮只在上述 worktree 做只读 anchor 检查：确认 HEAD、package 和 entry point。任一不符即报告 `source worktree setup mismatch` 并停止；不得自行 repair。通过后由 entry point 恢复最小记录并直接执行已登记 Next Action，不要再次等待确认。
```
