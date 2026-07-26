# Handoff Initial Prompt Template

Fill every bracketed field from the verified source records. Keep every section. Use `N/A` only when the section has no applicable fact. Keep concrete commands and parameters, design details, Task steps, file boundaries, tests and implementation instructions out of the prompt; name the single Impl-Package entry point and let it recover those details. Send the filled result directly as the `create_thread` prompt; do not save it as a handoff file.

```text
接手 [TASK_OR_TICKET_NAME]：从已完成的 [CHECKPOINT_OR_PHASE] 快照继续，不继承旧会话历史，也不要回溯重做已记录的工作。第一步请将本 session 切换至下列既有 implementation worktree；不要把新 session 继承的初始目录当作锚点或 mismatch。

恢复锚点：
- Target working directory：[ABSOLUTE_WORKTREE_PATH]
- Expected HEAD：[FULL_GIT_HEAD]
- 首先切换至该路径；切换后才核对当前工作目录与其余锚点。

权威入口：
- Task / ticket：[TASK_OR_TICKET_IDENTIFIER_AND_PURPOSE]
- Package directory：[PACKAGE_DIRECTORY]
- Impl-Package entry point：[IMPL_PACKAGE_ENTRY_POINT] — [PURPOSE]
- Current binding / scope：[VALUE_OR_N/A]

当前快照：
- 总量与阶段状态：[COUNTED_STATUS_OR_N/A]
- 已完成（仅限已完成阶段）：[COMPLETED_PHASES]
- 未完成或尚未证明：[REMAINING_WORK]
- 可能存在未提交实现；它不是恢复锚点，也不需要与 parent 比较。仅保护它：禁止 reset、checkout、clean、覆盖或重建。

已验证与未验证：
- 已验证：[VERIFICATION_SUMMARY_OR_N/A]
- 尚未验证及原因：[UNVERIFIED_ITEMS_OR_N/A]

首轮导航与只读核对：
1. 先将本 session 的工作目录切换至 `[ABSOLUTE_WORKTREE_PATH]`。不要比较或报告继承的初始目录。
2. 切换后确认当前工作目录是该路径，再从 `[PACKAGE_DIRECTORY]` 读取当前记录，并通过 `[IMPL_PACKAGE_ENTRY_POINT]` 选择恢复所需的最小材料。
3. 确认当前完整 HEAD 等于 `[FULL_GIT_HEAD]`。

无法切换至目标工作目录，或切换后任一锚点不符时：立即停止并报告 `source worktree setup mismatch`，说明失败的锚点。不得自行复制、cherry-pick、reset、checkout、clean 或重做实现。

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

通过上述首轮核对后，直接通过 `[IMPL_PACKAGE_ENTRY_POINT]` 恢复并继续 package 已登记的 Next Action，不要再次等待确认。具体命令、参数、设计细节、Task 拆解、文件边界和测试选择均由该 entry point 从 package 中恢复，本 prompt 不重复。

若 Next Action 需要但尚未具备的输入、授权或环境：[EXPLICIT_BLOCKER_AND_STOP_CONDITION_OR_N/A]。只有该 blocker、核对失败或 owner 要求停止时才停止。
```
