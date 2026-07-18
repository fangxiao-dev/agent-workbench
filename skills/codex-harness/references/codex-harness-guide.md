# Codex Harness/Crew 当前运行指南

本指南适用于显式调用 `$codex-harness`、`$codex-crew` 或 `$codex-crew-lite` 的任务。当前实现仍是 POC/early-runner；以下流程描述职责边界和可验证的运行契约，不代表生产级隔离、cleanup 或跨版本兼容已经闭合。

## 职责分工

- 主会话是用户侧 broker：提交问题、确认 parent 提出的 Lite/Full 模式、转发普通纠偏和 owner decision，并向用户呈现最终交付；主会话不创建 worker、不管理 worktree，也不替 parent 做实现编排。
- 持久 parent 是唯一 execution controller：分析问题、选择并提议模式、生成 dispatch manifest、调用 dispatcher、判断 worker 结果、组织验证，并在同一 parent thread 中继续处理纠偏或 owner decision。
- worker 是独立执行单元：每个 task 使用 fresh App Server thread 和独立 Git worktree，只处理 manifest 中的 disjoint ownership；worker 不能扩大范围或自行取得 owner authority。
- `scripts/codex_harness_dispatch.py` 是底层 worker/worktree primitive，只负责 manifest/state、worktree 准备、worker 启动和结构化 outcome；它不选择模式、不拥有 parent thread、不询问 owner，也不自动 merge、promote 或删除 worktree。

## 运行流程

1. 主会话显式启动一个持久 parent；routing turn 必须是只读的，并返回带 `run_id` 的结构化 Lite/Full 建议。
2. 主会话检查建议后显式确认模式；controller 恢复同一个 parent thread，不能因为确认或普通纠偏而创建第二个 parent。
3. Lite 仅用于已理解、范围明确且不需要 redesign、接口/权限变化、迁移、不可逆外部副作用或改变验收口径的问题。Full 用于需要 Harness policy、Impl-Package binding、独立验证、review/gate 或持续恢复的问题。
4. parent 在已确认模式下创建 manifest 和 dispatch state，再显式调用 dispatcher；独立 worker 之间必须保持 task、worktree 和可写资源 disjoint。
5. worker 返回结构化 `succeeded`、`needs_parent`、`needs_owner` 或 `failed`。`needs_parent` 由 parent 在同一 thread 中判断和纠偏；`needs_owner` 只在范围、权限、不可逆外部副作用或验收歧义需要 owner 决策时转回主会话。
6. 主会话转发 owner decision 后，parent 在原 thread 开始新 turn；独立任务不得复用旧上下文。完成前由 parent 检查 worktree diff、声明的验证命令和其他适用 gate；dispatcher 不代替独立验收。
7. 只有在 status、diff、verification evidence 和 terminal disposition 均已检查后，才由授权调用方决定 promotion、merge 或 cleanup；本流程不自动执行这些动作。

## 显式调用入口

```powershell
python scripts/codex_harness_crew.py start --repository-root . --issue-file issue.md --state .codex/crew/parent.state.json
python scripts/codex_harness_crew.py confirm-mode --state .codex/crew/parent.state.json --mode lite
python scripts/codex_harness_crew.py continue --state .codex/crew/parent.state.json --message "继续处理已确认的纠偏"
python scripts/codex_harness_crew.py status --state .codex/crew/parent.state.json
```

确认模式后，parent 才可以按需调用 dispatcher：

```powershell
python scripts/codex_harness_dispatch.py init-state --manifest .codex/crew/lite.json --parent-state .codex/crew/parent.state.json --state .codex/crew/lite.dispatch.state.json
python scripts/codex_harness_dispatch.py ensure-worktrees --state .codex/crew/lite.dispatch.state.json
python scripts/codex_harness_dispatch.py start-workers --state .codex/crew/lite.dispatch.state.json --parallelism 2
```

主会话不应把上述 dispatcher 命令当作自己的 scheduler；它只通过 parent controller 接收路由、owner request、验证证据和交付状态。

## 必须保持的运行契约

- 独立任务使用 fresh context；同一 work package 的 correction、retry 或 process resume 才能延续同一 parent thread。
- 一个持久 parent thread 同时只能由一个 controller 驱动；发现 lease、state 或 history 不一致时应 fail closed。
- Parent Result 和 worker result 必须是结构化 JSON，并绑定当前 `run_id`/`task_id`；自然语言完成说明不能替代 artifact、diff、命令退出码或其他独立验证。
- Worktree 隔离只隔离本地文件写入，不证明共享服务、远端状态、迁移或后续 merge 不会冲突。
- owner decision 返回 parent 后仍是同一请求的 continuation，不得静默替换成 fresh parent；未决的 `needs_owner` 不是整体完成。

## Canonical 资产索引

- 共同 continuation、single-writer、owner routing 和 cleanup 边界：[codex-crew-continuation-contract.md](codex-crew-continuation-contract.md)
- Parent route/status/state 协议：[codex-crew-parent.schema.json](../assets/codex-crew-parent.schema.json)
- Worker/worktree dispatch 协议：[codex-crew-dispatch.schema.json](../assets/codex-crew-dispatch.schema.json)
- Lite manifest 示例：[codex-crew-lite.v0.json](../assets/codex-crew-lite.v0.json)
- Full manifest 示例：[codex-crew.v0.json](../assets/codex-crew.v0.json)
- Harness runtime policy：[codex-harness-runtime-policy.v0.json](../assets/codex-harness-runtime-policy.v0.json) 及其 [JSON Schema](../assets/codex-harness-runtime-policy.schema.json)

上述结构化资产是配置和协议的事实源；Skill 文本只说明入口和边界，不在多处复制 policy 值。
