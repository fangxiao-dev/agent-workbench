# Logger Handoff Quality Gate

用于耐久交接前的 logger / handoff 审核。这个规则只在真正 handoff 前加载；日常记录不要求始终满足全部结构。

## 审核目标

判断新 thread 是否能只靠 handoff prompt 和必要文件快速恢复当前状态，而不需要读取旧 thread 的完整历史。

审核员只做质量判断和修改建议，不实现代码，不推进任务。

## 必查项

- 当前事实是否前置：
  - worktree、branch、HEAD、dirty/clean 状态。
  - 当前阶段、已完成、未完成、明确不要提前做的任务。
  - 下一步第一动作。

- 状态是否新鲜：
  - handoff 是否在 commit 和外部状态更新之后、基于 fresh git 输出写成（Checkpoint 规定 commit 先于写 handoff）。
  - handoff 中的 HEAD / dirty 状态与主 session 提供的 fresh git 输出是否一致。
  - 如果存在历史事实，是否明确标注并用 fresh state 覆盖。
  - 是否要求 child session 先运行 `git status --short --branch` 和 `git log -1 --oneline`。

- gate 是否可信：
  - 关键测试命令和结果是否写清。
  - gate 结果是否足以说明当前 checkpoint 的质量。
  - 如果 gate 不是在最新状态后运行，是否明确标注风险。

- 外部状态是否清楚：
  - issue / PR / comment 是否列出动作类型。
  - 是否明确 not pushed / not merged / not closed 等未完成外部状态。
  - 是否避免让 child 重复发评论或误关 issue。

- 协作 contract 是否完整：
  - 用户明确偏好是否写成执行规则。
  - subagent / main session 的所有权边界是否清楚。
  - 一次性权限是否没有被升级成长期权限。

- 噪声是否被降级：
  - timeline、worker 名字、中间 gate、小修复过程是否没有挤占 handoff 的主视野。
  - 只有仍有恢复价值的错误、决策、风险进入 handoff。

## 建议输出格式

```text
Logger handoff review: APPROVED / NEEDS CHANGES

Blocking issues:
- ...

Recommended edits:
- ...

Stale or risky facts:
- ...

Noise to move out of handoff:
- ...
```

如果没有阻塞项，审核员仍应指出残余风险，例如“需要 child session 先确认 fresh git state”。
