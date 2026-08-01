# Foundation clean-session 派发模板

Clean session 只避免直接继承旧聊天；宽泛恢复 parent package 仍会迅速重新灌满上下文。
Foundation 新任务以 assignment card 为执行权威，parent package / entry 只做存在性锚点和 closure ownership 指针。

## 固定约束

- Owner 已授权新 task；复用 worktree 时旧 writer 与 owned process 已停止。
- 创建前只读确认 worktree、完整 HEAD、parent package/entry 存在及 seam assignment 明确。
- 使用 `create_thread` + `target.environment={type:"local"}`；禁止 fork、worktree/snapshot/`startingState`。
- 默认 `model=gpt-5.6-luna`、`thinking=max`，除非 Owner 覆盖。
- 不手写 delegation wrapper；prompt 不含旧聊天摘要、project ID、branch、dirty fingerprint 或 secret。
- child 不读旧 session、parent `plan.md`、Task progress、全量 registry 或历史 evidence。

## 固定流程

1. 用第一阶段 prompt 创建 session；child 只做 anchor check 并停止。
2. controller 设置短标题，更新 registry，登记 assigned seam，再复核 sibling。
3. 发送第二阶段 assignment card；child 只输出 controller + 本 node 的 routing projection。
4. child 登记 working 后直接按 card 工作，不从 parent entry 恢复历史。
5. 做一次 `wait_threads(..., timeoutMs:0)` 快照。
6. registry race 修正后复用同一 clean session，不再创建新 session。

## 第一阶段 prompt

```text
你是 coordination <coordination_id> 的全新 Role B Foundation task：<topic>。
不继承主控、旧 Foundation 或其他 task 的聊天历史；不得读取旧 session。

执行锚点（首轮及后续命令均使用此 workdir）：
- worktree：<absolute_worktree>
- expected HEAD：<full_head>
- parent package：<package_path>
- entry point：<single_entry_point>

任务身份：node=<node_id>；seam=<seam_id>；consumers=<consumer_nodes>。

首轮只用 Test-Path / git rev-parse 确认 HEAD、package 与 entry 存在，不读取文档内容。
任一不符仅报告 `source worktree setup mismatch` 并停止，不得 repair。
全部匹配仅报告 `foundation anchor PASS` 并停止；不得读取 registry/ledger 或开始实现。
```

## 第二阶段 prompt

```text
第二阶段 registration 已就绪。读取 $thread-harness 并按 Role B 工作；不得读取旧聊天、
parent plan/Task progress、历史 evidence，也不得把 package entry 当恢复入口。

Routing：
- coordination_id=<coordination_id>
- registry=<absolute_registry_path>
- ledger repo=<absolute_ledger_repo>
- node=<node_id>；expected session=<new_thread_id>
- seam=<seam_id>；consumers=<consumer_nodes>

解析 registry 后只输出 current controller 与本 node 的 session/worktree/branch projection。
精确匹配才 append state=working、真实 HEAD、无 waiting_on；否则报告 `harness mismatch` 并停止。

Assignment card（本轮唯一执行权威）：
- next action：<one_concrete_deliverable>
- exact inputs：<max_6_exact_paths_or_artifact_pointers>
- already earned：<one_material_proof_or_N/A>
- still required：<remaining_closure_proof>
- authorization：<explicitly_allowed_actions>
- exclusions：<explicit_exclusions>

上下文纪律：
- 只读 nearest AGENTS、必需 skill 和 exact inputs；禁止 broad package/doc scan。
- investigation/impl 先用 $call-grok；主 session 只接收结论并查看必要 diff/小窗口。
- 不向聊天打印完整文件、测试日志、registry 或 ledger；只输出短 projection/摘要。

直接推进 next action，不写 blocker-only proposal。H1/H2/H4 严格执行；
交付时登记 seam artifact，并只回报 current controller。
```

## 停止条件

- anchor、title、local environment、registry routing 或 exact inputs 不符：停止，不 repair。
- 返回 `clientThreadId`：报 incomplete delivery，不伪造 session id。
- 旧 writer/owned process 未停止或需要扩大 initial read set：先回报 controller。
