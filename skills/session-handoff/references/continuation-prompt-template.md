# Continuation Prompt Template

After saving the handoff file, return a continuation prompt directly in chat. Do not save this as a file.

Use this structure and fill in the concrete details:

```text
已将 handoff 落盘。请先阅读 [HANDOFF_FILE_PATH]，然后继续这个任务。

当前目标：
[CURRENT_GOAL]

当前状态：
[CURRENT_STATUS]

工作区约束：
[WORKSPACE_OR_WORKTREE_CONSTRAINTS]

必读文件：
- [FILE_1]
- [FILE_2]
- [FILE_3]

首个推荐动作：
[FIRST_RECOMMENDED_ACTION]

继续实现前，先验证当前状态，不要直接假设 handoff 中提到的修复或未验证项已经成立。

如果以下开放问题仍未确认，请先确认再动手：
- [OPEN_ISSUE_1]
- [OPEN_ISSUE_2]
```

## Requirements

- Always include the handoff file path.
- Always include the current goal and current status.
- Always tell the next session to verify the current state before continuing.
- If there are open issues, list them explicitly.
- If there are no open issues, say that no known open issues remain but verification should still happen first.
