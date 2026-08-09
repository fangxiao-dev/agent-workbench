# Plan Bundle Activation Runbook

本 runbook 只描述已批准 Plan/Ticket/DAG bundle 的直接激活，不建立 review ledger、transaction journal、receipt 或内容绑定。

## 前提

- Decision/Spec gates 已通过，Plan 已 frozen。
- Composition 所需 Ticket/DAG 已完成 joint validation 与适用 plan review。
- owner 批准的是当前展示的完整 bundle；跨 session 时记录批准 commit，并确认实际 diff 未扩大合同或 authority。
- 所有路径为仓库相对路径，package ID 带日期前缀且不可变。

## 激活

```text
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> init --attempt <id> --plan <repo-relative-plan>
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> validate
```

`init` 先校验完整候选，再发布当前 Attempt 的 Draft Ticket、初始化 current state、创建 Attempt Execution Record，并生成 Ticket/DAG/Progress 投影。失败后不得凭部分文件继续；修复输入并重试同一命令，或用 `refresh-progress` 修复 projection。

激活不执行 commit、push、merge、release 或外部 mutation。成功后进入 `/impl-package:execution-preflight`，由它确认本轮 write-set 和授权。
