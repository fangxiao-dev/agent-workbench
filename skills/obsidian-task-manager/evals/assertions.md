# Eval Assertions

Use these objective checks when reviewing skill/script changes.

## create-current-bug

- `operation` is `create`.
- `status` is `计划中`.
- `priority` is `当前`.
- `taskType` is `bug`.
- `verificationPath` is `不涉及`.
- `workspace` is `主工作区`.

## create-future-feature

- `operation` is `create`.
- `status` is `计划中`.
- `priority` is `未来规划`.
- `taskType` is `新增功能`.

## start-worktree

- `operation` is `update`.
- `status` is `实施中`.
- `workspace` is `worktree`.
- Existing priority is not cleared.

## verification-partial-real

- `operation` is `update`.
- `status` is `验证中`.
- `verificationPath` is `部分真实链路`.
- Body includes `### 验证状态` and `### 残余风险`.

## complete-merged

- `operation` is `update`.
- `status` is `已完成`.
- `workspace` is `主工作区`.
- `priority` is `null` or omitted only if already absent.
- Body includes final verification and residual-risk text.

## blocked-credentials

- `operation` is `update`.
- `status` is `阻塞`.
- Priority is preserved unless explicitly changed.
- Next step states the unblock condition.

## Script-Level Checks

- All label fields in generated Markdown are YAML arrays.
- `validate` reports completed tasks with priority as an error.
- `validate` reports completed tasks outside `主工作区` as an error.
- Dry-run does not modify the vault.
- `--apply` only writes under `10_Tasks/`.
