---
name: subagent-driven-development
description: 当调查、实现、修复或验证需要主 session 与 worker 协作时使用；在启动前形成 mode、具体 worker 和 review 策略，并消费统一结果。
---

# Subagent-Driven Development

这是 Impl-Package 的唯一 worker 编排入口。它不重写业务需求、Task/Ticket、授权或验收，只把已经确定的 bounded unit 变成一份可执行策略，并在主 session 集成前收口 worker 结果。

## 先形成策略

每个非本地 bounded unit 启动前都必须输出：

```yaml
mode: investigate | implement | fix | review
worker: main-session | "$grok-worker" | "@luna-worker" | "<model>/<effort>" | "prompt:<slug>"
review: none | required
review_scope: none | checkpoint | closure
reason: <仅在 local、blocked、显式 override 或 review 判断不显然时填写>
resources: <只记录真实共享资源、顺序和 cleanup owner>
reuse: <只在同一 source unit 需要不可转移 live state 时填写>
```

- `worker` 必须显式存在；默认是 `$grok-worker`。`main-session` 只用于原子本地动作，且必须说明 reason。
- `review=none` 时 `review_scope=none`；`review=required` 时明确选择 `checkpoint` 或 `closure`，不能留给 reviewer 临场猜测。
- 上游 Owner/`readyTickets` 已明确存在并行候选时，读取 [Parallel Work Admission](references/parallel-work-admission.md)；该 reference 不负责发现候选。
- 未填写 `reuse` 时使用 fresh invocation；context compaction 后从 canonical input 重新启动。角色相同、空闲或共享 worktree 都不是复用理由。
- `investigate`、`implement` 可以沿用调用者选择的同一逻辑 worker；已确认 finding 只能交给 fresh `fix` invocation。复杂度只增加 reviewer gate，不自动切换 implementer。

## Mode selection

- `investigate`：事实不足时建立 cause、blast radius、existing solution 和 boundary facts；返回 `EVIDENCE_SUFFICIENT` 或 `EVIDENCE_GAP`，不代替授权或实施。
- `implement`：消费已释放的 Plan/Ticket bounded unit；旧 package 才可消费既有 DAG unit。
- `fix`：只消费已确认且已边界化的 finding；不重新裁决、不扩大范围、不宣称 closure，且必须使用 fresh invocation。
- `review`：只运行既定、无写副作用的检查；`review_scope` 区分 checkpoint 与 closure。

各 mode 的输入、模板和直接输出见 [Mode Contracts](references/mode-contracts.md)。

## Worker resolver

读取 [Worker Resolver](references/worker-resolver.md) 后再启动。解析不到唯一实体、宿主不支持 invocation、授权不匹配或 brief 不完整时，在启动前返回 `BLOCKED`，不猜测近似 worker。

## 生命周期与失败

执行结果统一为 `Outcome: DONE | BLOCKED | INCOMPLETE`，并附 `mode`、`worker`、`source_unit`、`evidence`、`artifacts`、`blocker`、`fallback_from` 和 `session_id`。默认 `$grok-worker` 只有在进程已清理、diff/residue 可归因且可安全重放时，才允许一次 fresh `@luna-worker` fallback；业务 `BLOCKED` 不 fallback，第二次 `INCOMPLETE` 归一为 `BLOCKED`。详见 [Worker Resolver](references/worker-resolver.md)。

`review=required` 时，`DONE` 先是 `review_state: PENDING_REVIEW`；独立 reviewer PASS 后才是 `review_state: PASSED`，finding 交给 fresh fixer 并按同一 scope 重审。主 session 自己发现的 finding 可直接进入 fresh fixer；`UNCERTAIN/BLOCKED` 原样上交。`review=none` 的 DONE 为 `review_state: NOT_REQUIRED`。reviewer 门槛见 [Review Gate](references/review-gate.md)。

主 session 始终负责最终集成、证据采信、Ticket acceptance 和 Gate 判断；worker 的局部 DONE、review PASS 或测试通过都不单独代表 package 完成。
