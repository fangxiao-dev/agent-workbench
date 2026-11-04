# Task Lifecycle Rules

These rules decide task status and cross-field consequences.

## New Plan

Use when the user is recording an idea, plan, future work, bug, or feature before implementation starts.

- `状态`: `计划中`
- `工作区`: `主工作区`
- `验证链路`: `不涉及`
- `优先级`: infer from wording:
  - urgent, now, current, immediately, "马上做" -> `当前`
  - next batch, soon, after current work, "下一批" -> `下一批`
  - someday, backlog, future roadmap, "未来" -> `未来规划`

Only fill `### 来源链接/路径`, `### 当前进度`, and `### 下一步建议` if no implementation has started.

## In Implementation

Use when the user says work has started, code is being changed, or the task is assigned to a worktree.

- `状态`: `实施中`
- `工作区`: `worktree` when an active task worktree carries progress
- `工作区`: `主工作区` only for small direct-main work or explicit main-workspace execution
- Keep existing `优先级` unless the user changes it

## In Verification

Use when implementation is done enough to test, review, or manually verify.

- `状态`: `验证中`
- Keep current `工作区` while verification still happens in the worktree
- Set `验证链路` from actual coverage:
  - local tests, local browser, local simulation only -> `本地链路`
  - full real external/deployed/prod-like path verified -> `真实链路`
  - some real external path verified, but not the full workflow -> `部分真实链路`
  - documentation/planning/no runtime validation needed -> `不涉及`

Fill `### 验证状态` and `### 残余风险`.

## Complete

Use when the task is finished, merged back to trunk/main, archived, or no longer needs active follow-up.

- `状态`: `已完成`
- `工作区`: `主工作区`
- `优先级`: clear it with `null`
- Keep final `验证链路` as the actual strongest coverage achieved
- `### 当前进度`: summarize the completed result
- `### 下一步建议`: say whether future work should be a new task
- `### 验证状态`: summarize commands, manual checks, and skipped external checks
- `### 残余风险`: list remaining uncertainty or "暂无明确残余风险"

## Blocked

Use when the task still matters but cannot progress due to credentials, permissions, environment, design decisions, external dependencies, or unavailable data.

- `状态`: `阻塞`
- Keep `优先级`; it remains in the queue
- Keep current `工作区`
- `### 当前进度`: explain what has been done
- `### 下一步建议`: state the unblock condition
- `### 残余风险`: state what cannot be proven while blocked

## Shelved

Use when the task was started or planned but should not continue for now because direction changed, value is insufficient, or the user no longer needs it.

- `状态`: `搁置`
- `优先级`: usually clear it with `null`
- `工作区`: `主工作区` unless an active worktree still carries unresolved cleanup
- Body should explain why it is shelved and what condition would revive it.
