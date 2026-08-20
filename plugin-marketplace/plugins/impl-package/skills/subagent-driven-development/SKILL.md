---
name: subagent-driven-development
description: 当调查、实现、修复或验证需要主 session 与 worker 协作时使用；在启动前形成 mode、具体 worker 和 review 策略，并消费统一结果。
---

# Subagent-Driven Development

这是 Impl-Package 的唯一 worker 编排入口：不重写业务需求、Task/Ticket、授权或验收，只把已确定的 bounded unit 变成可执行策略，并在主 session 集成前收口 worker 结果。逻辑角色（investigate/implement/fix/review）到 provider 的映射和策略格式由 preset/orchestrator 承接，本 skill 只保留判断。

## 先形成策略

每个非本地 bounded unit 启动前都显式输出：

- `mode: investigate | implement | fix | review`
- `worker: main-session | <默认 worker> | "<model>/<effort>" | "prompt:<slug>"`
- `review: none | required`
- `review_scope: none | checkpoint | closure`
- `reason: <仅在 local、blocked、显式 override 或 review 判断不显然时填写>`
- `resources: <只记录真实共享资源、顺序和 cleanup owner>`
- `reuse: <只在同一 source unit 需要不可转移 live state 时填写>`

- `worker` 必须显式存在，默认 worker 由宿主 registry 决定（见 Worker Resolver）；`main-session` 仅用于原子本地动作且必须说明 reason。`review=none` 必须配 `review_scope=none`，`review=required` 必须明确 `checkpoint` 或 `closure`，不能留给 reviewer 临场猜。
- 上游 Owner/`readyTickets` 已明确并行候选时读取 [Parallel Work Admission](references/parallel-work-admission.md)，但该 reference 不负责发现候选；未填 `reuse` 用 fresh invocation，compaction 后从 canonical input 重启，角色相同、空闲或共享 worktree 都不是复用理由。
- `investigate`、`implement` 可沿用调用者选择的同一逻辑 worker；已确认 finding 只能给 fresh `fix` invocation。复杂度只增加 reviewer gate，不自动换 implementer。
- investigate 默认低推理，只返回固定 6 行（Investigation / cause / blast radius / existing solution / boundary facts / unresolved facts），禁止 `READY|BLOCKED`；implement brief 只含 source_unit、成功条件、禁改路径、文件列表和一条验证命令，禁止粘整张 Ticket/全量 AC；reviewer 只收 caller 指定的 diff 路径与 AC ID，报告限 verdict、P0/P1 findings、residual_gaps，禁止再读 plan/spec/contract-design 整章。

## Mode selection

- `investigate`：事实不足时建立 cause、blast radius、existing solution 和 boundary facts；返回 `EVIDENCE_SUFFICIENT|EVIDENCE_GAP`，只释放实施判断，不释放授权、验收或 Gate，也不输出 `READY|BLOCKED`。
- `implement`：消费已释放的 Plan/Ticket bounded unit；旧 package 才可消费既有 DAG unit。
- `fix`：只消费已确认且已边界化的 finding；不重新裁决、不扩大范围、不宣称 closure，且必须 fresh invocation。
- `review`：只运行既定、无写副作用的检查；`review_scope` 区分 checkpoint 与 closure。输入、模板和直接输出见 [Mode Contracts](references/mode-contracts.md)。

## Worker resolver

启动前读取 [Worker Resolver](references/worker-resolver.md)；解析不到唯一实体、宿主不支持 invocation、授权不匹配或 brief 不完整时返回 `BLOCKED`，不猜近似 worker。

## Review、并行与失败

shared seam、安全、数据完整性、并发、migration、不可逆外部副作用或 policy 要求时必须 `review=required` 并显式选 `checkpoint|closure`；非显然时选 `none` 并写 reason，不为每个文件或小动作增加 checkpoint。reviewer 独立 fresh，finding 交 fresh fixer 按同一 scope 重审。

共享可变运行资源必须隔离；不能隔离就串行并记录顺序、owner、cleanup，全部返回后由主 session 做集成验证。解析失败、授权不匹配或 brief 不完整时启动前 `BLOCKED`；仅默认 worker 的 `INCOMPLETE` 在进程已清理、diff/residue 可归因且可安全重放时允许一次 fresh 默认 worker fallback，业务 `BLOCKED` 不 fallback，第二次 `INCOMPLETE` 归一为 `BLOCKED`。

## 生命周期与结果

统一结果为 `Outcome: DONE | BLOCKED | INCOMPLETE`，附 `mode`、`worker`、`source_unit`、`evidence`、`artifacts`、`blocker`、`fallback_from`、`session_id`；resolver 负责 fallback 与失败归一。`review=required` 的 DONE 先为 `review_state: PENDING_REVIEW`，独立 reviewer PASS 后才是 `PASSED`；finding 交 fresh fixer 按同一 scope 重审，主 session 发现的 finding 可直接进入 fresh fixer；`UNCERTAIN|BLOCKED` 原样上交。`review=none` 的 DONE 为 `NOT_REQUIRED`，reviewer 门槛见 [Review Gate](references/review-gate.md)。

主 session 始终负责最终集成、证据采信、Ticket acceptance 和 Gate 判断；worker 的局部 DONE、review PASS 或测试通过都不单独代表 package 完成。
