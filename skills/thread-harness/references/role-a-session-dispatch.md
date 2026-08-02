# Role A clean-session 交接模板

Role A handoff 的恢复权威是当前任务包 entry，不是 controller 或 source session 的聊天历史。
交接分成纯任务包 preflight 与正式 Role A registration 两阶段，避免 child 在 registry 更新前开始工作。

## 固定约束

- source session 先停在原子 checkpoint，并只在既有任务包 entry 追加最小恢复记录：当前 HEAD、计数状态、单一 Next Action、已获证据、剩余证据与 WIP 边界。
- 不创建通用 handoff 文档，不复制聊天摘要；现有未提交内容只保护，不 reset、checkout、clean、覆盖或重建。
- 使用 `create_thread` + `target.environment={type:"local"}`；禁止 fork、worktree/snapshot/`startingState`。
- 默认 `model=gpt-5.6-luna`、`thinking=max`，除非 Owner 覆盖。
- 第一阶段 prompt 不含 harness、coordination、registry、ledger 或 Role A 指令；child 只核对任务包 anchor。
- `previous_session_ids` 只属于 registry 内部路由历史。任何 child prompt、registration card 或 child 校验都不得读取、携带、打印或要求匹配该字段。

## 固定流程

1. source session 写好任务包 checkpoint，确认 owned process 已停，并完成 parent preflight。
2. 用第一阶段 prompt 创建 clean local session；child 只报告 anchor PASS/FAIL 并停止。
3. controller 设置短标题，更新 registry 的 current routing，并复核 sibling 未变化。
4. controller 发送第二阶段 Role A registration + assignment card。
5. child 只校验 current controller 与本 node 的 current session/worktree/branch projection；匹配后登记状态并按任务包 entry 继续。
6. 做一次 `wait_threads(..., timeoutMs:0)` 快照。registry race 修正后复用同一 clean session，不再创建新 session。

## 第一阶段 prompt

```text
接手任务包 <package_topic>。这是全新、独立的 local session；任务包 entry 是唯一恢复事实来源。

执行锚点（首轮及后续命令均使用此 workdir）：
- worktree：<absolute_worktree>
- expected HEAD：<full_head>
- package：<package_path>
- entry point：<single_entry_point>

首轮只用 Test-Path / git rev-parse 确认 HEAD、package 与 entry point。
任一不符仅报告 `source worktree setup mismatch` 并停止，不得 repair。
全部匹配仅报告 `role-a anchor PASS` 与四个锚点并停止；不得开始实现、验证或协调。
```

## 第二阶段 prompt

```text
第二阶段 registration 已就绪。读取 $thread-harness 并按 Role A 工作；任务包 entry 是恢复与执行权威。

Routing：
- coordination_id=<coordination_id>
- registry=<absolute_registry_path>
- ledger repo=<absolute_ledger_repo>
- node=<node_id>；expected current session=<new_thread_id>

解析 registry 后只输出 current controller 与本 node 的 current session/worktree/branch projection。
精确匹配才按 ledger schema append：
- state=<working_or_awaiting_seam>
- head=<actual_head>
- waiting_on=<seam_id_or_none>
否则报告 `harness mismatch` 并停止，不得修改 registry。

Package checkpoint：
- package=<package_path>
- entry=<single_entry_point>
- checkpoint=<latest_checkpoint_heading_or_pointer>

Assignment card（本轮唯一任务）：
- next action：<one_concrete_action>
- exact inputs：<max_6_exact_paths_or_artifact_pointers>
- already earned：<one_material_proof_or_N/A>
- still required：<remaining_closure_proof>
- authorization：<explicitly_allowed_actions>
- exclusions：<explicit_exclusions>

上下文纪律：
- 只读 nearest AGENTS、必需 skill、package entry 与 exact inputs；禁止 broad package/doc scan。
- investigation/impl 优先 $call-grok；review 走 $do-review；验收由当前 session 完成。
- 不向聊天打印完整文件、测试日志、registry 或 ledger；只输出短 projection/摘要。

直接推进 next action，不写 blocker-only proposal。H1/H2/H4 严格执行，只回报 current controller。
```

## 停止条件

- anchor、title、local environment、current routing 或 exact inputs 不符：停止，不 repair。
- 返回 `clientThreadId`：报 incomplete delivery，不伪造 session id。
- source writer/owned process 未停止，或任务包 checkpoint 不足以恢复：先回报 controller，不扩大读取范围。
