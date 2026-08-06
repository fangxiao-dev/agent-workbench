# 执行型交接

执行型 handoff 只保存下一 session 会改变动作判断的事实：worktree、branch、HEAD Git commit、dirty paths、package、current attempt/state、blocker、next action、授权边界和已验证阶段。

## Compact anchor

```text
python <handoff-skill>/scripts/compact_anchor.py --worktree <absolute-local-worktree> --expected-head <git-commit> --package-path <repo-relative-package>
```

脚本输出当前 Git 状态和 canonical package validation。dirty 文件名直接以仓库相对路径列出，便于判断 write-set 冲突；不生成第二套 freshness 证明。

## 恢复规则

1. HEAD、package 和授权范围匹配时，从根 `progress.md` 的 current Attempt、blocker、active checkpoint 和 next action 恢复。
2. dirty path 与 write-set 冲突时，先展开对应 diff；无冲突不要求全量重读。
3. 跨 session approval 应给出批准时的 Git commit；比较实际 diff 是否扩大 contract/authority。
4. 只打开 next action 需要的 plan、Ticket、DAG、Execution Record、Task Handoff 和 evidence。
5. 产品语义冲突、目标环境不明、shared/production mutation 或超授权时停止并请求 owner。

执行编排继续遵循仓库通用入口：主 session/子 agent 调度使用 `$subagent-driven-development`（`skills/subagent-driven-development/`）；写入前调查使用 `$investigate-before-implement`（`skills/investigate-before-implement/`）；独立只读审查使用 `$reviewer`（`skills/reviewer/`）。这些 workflow 和 role 定义不在 handoff 中重复；handoff 只保存当前选择和任务特定输入。

## Handoff 内容

- 当前实施、验证、Gate、合入分别处于什么阶段；
- Task/Ticket 总数、已处理数、剩余数和 blockers；
- 首个可执行动作；
- 不要重复的工作和暂不读取的材料；
- repo-relative 权威路径；
- commit/push/merge/外部 mutation 的授权状态。

不要复制 plan、测试矩阵、历史日志或 Gate 正文。临时 handoff 文件可以位于 OS 临时目录；其中引用仓库文件时一律写仓库相对路径。
