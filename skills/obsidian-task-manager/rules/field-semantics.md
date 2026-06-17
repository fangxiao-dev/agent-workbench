# Field Semantics

TaskManager label fields are for filtering. Narrative details belong in the body.

## Fixed Enums

```text
状态: 计划中 / 实施中 / 验证中 / 阻塞 / 搁置 / 已完成
优先级: 当前 / 下一批 / 未来规划
任务类型: 新增功能 / bug / 功能优化
验证链路: 本地链路 / 真实链路 / 部分真实链路 / 不涉及
工作区: 主工作区 / worktree
```

## 状态

`状态` is the current lifecycle stage.

- `计划中`: not started
- `实施中`: active implementation
- `验证中`: implemented enough to test or manually verify
- `阻塞`: should continue but cannot
- `搁置`: intentionally paused or no longer currently valuable
- `已完成`: finished and no active follow-up remains in this task

## 优先级

`优先级` is a planning queue signal for unfinished work only.

- `当前`: should be worked now
- `下一批`: queued after current work
- `未来规划`: backlog/roadmap

Clear priority when `状态` becomes `已完成` or usually when it becomes `搁置`.

## 任务类型

- `新增功能`: new capability, new page, new workflow, new integration surface
- `bug`: defect, regression, broken behavior, incorrect state
- `功能优化`: existing behavior improved, UX/copy/performance/refactor-like product improvement

Prefer `bug` when the user describes something currently wrong. Prefer `功能优化` when improving an existing correct behavior.

## 验证链路

`验证链路` records the strongest validation path actually covered.

- `本地链路`: local tests, local browser, local simulation, local TypeScript/build
- `真实链路`: full real external/deployed/prod-like path was verified
- `部分真实链路`: some real external part was verified but the whole business path was not
- `不涉及`: planning/docs/no runtime path

Do not use this field as a command log. Put commands and evidence in `### 验证状态`.

## 工作区

`工作区` means where current progress is carried now.

- `worktree`: active development or verification still lives in a task worktree
- `主工作区`: planning on trunk/main, completed work merged back, archived task, or direct-main work

It does not mean where the task historically happened. If a task is complete and merged, use `主工作区`.
