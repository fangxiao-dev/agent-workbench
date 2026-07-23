# Handoff Initial Prompt Template

Fill every bracketed field from the verified source records. Keep every section. Use `N/A` only when the section has no applicable fact. Send the filled result directly as the `create_thread` prompt; do not save it as a handoff file.

```text
接手 [TASK_OR_TICKET_NAME]。这是一个干净的新 Codex thread：从已完成的 [CHECKPOINT_OR_PHASE] 快照继续，不继承旧会话历史，也不要回溯重做已记录的工作。

恢复锚点：
- Parent implementation worktree（本次 working-tree snapshot 的唯一来源）：[ABSOLUTE_WORKTREE_PATH]
- Expected HEAD：[FULL_GIT_HEAD]
- 注意：你的 Codex-managed child worktree 路径可以不同；只要 HEAD 与下列权威入口一致即可。不要尝试切换、复制或重建到 parent 路径。

权威合同与入口：
- Task / ticket：[TASK_OR_TICKET_IDENTIFIER_AND_PURPOSE]
- Entry [1]：[PATH] — [PURPOSE]
- Entry [2]：[PATH] — [PURPOSE]
- Entry [3]：[PATH_OR_N/A] — [PURPOSE_OR_N/A]
- Current binding / decision / scope（仅来自上列入口记录）：[VALUE_OR_N/A]

当前快照：
- 总量与阶段状态：[COUNTED_STATUS_OR_N/A]
- 已完成（仅限已完成阶段）：[COMPLETED_PHASES]
- 未完成或尚未证明：[REMAINING_WORK]
- 可能存在未提交实现；它不是恢复锚点，也不需要与 parent 比较。仅保护它：禁止 reset、checkout、clean、覆盖或重建。

已验证与未验证：
- 已验证：[VERIFICATION_SUMMARY_OR_N/A]
- 尚未验证及原因：[UNVERIFIED_ITEMS_OR_N/A]
- Package read-only working-tree validation：[EXACT_READ_ONLY_COMMAND_AND_EXPECTED_RESULT_OR_N/A_NO_READ_ONLY_COMMAND_DEFINED]。不得在首轮运行会修改工作树或调用外部系统的命令。

首轮只读核对：
1. 先只读 [ENTRY_DOCUMENTS_TO_READ_FIRST]。
2. 确认当前完整 HEAD 等于 `[FULL_GIT_HEAD]`。
3. 确认 [REQUIRED_ENTRY_DIRECTORY_OR_DOCUMENTS] 存在并可读取。
4. 仅当上方定义了 read-only package validation command 时运行它。
5. 查看 `git status --short` 仅用于保护现有改动；不与 parent 输出比较，也不作为 mismatch 条件。

任一项不符时：立即停止并报告 `new worktree setup mismatch`，说明失败的锚点。不得自行复制、cherry-pick、reset、checkout、clean 或重做实现。

硬协作与授权合同：
- 协作模式：[EXPLICIT_MAIN_SESSION_AND_SUBAGENT_OWNERSHIP]
- 本轮已允许：[LOCALLY_AUTHORIZED_ACTIONS]
- 仍需单独授权：[ACTIONS_REQUIRING_SEPARATE_AUTHORIZATION]
- 后续 gate / owner 签署：[REQUIRED_APPROVALS_OR_N/A]
- 未提交实现的保护规则：不得清理、覆盖、提交、push 或创建 PR，除非本 prompt 明确授权或 owner 另行明确授权。

数据与外部边界：
- 受控输入、凭证和敏感数据：[SENSITIVE_DATA_RULES_OR_N/A]
- 已发生的外部状态：[EXTERNAL_STATE_OR_N/A]
- 禁止的外部动作：[PROHIBITED_EXTERNAL_ACTIONS_OR_N/A]

通过上述首轮核对后，继续以下 Next Action，不要再次等待确认：
[NEXT_ACTION]

若 Next Action 需要但尚未具备的输入、授权或环境：[EXPLICIT_BLOCKER_AND_STOP_CONDITION_OR_N/A]。只有该 blocker、核对失败或 owner 要求停止时才停止。
```
