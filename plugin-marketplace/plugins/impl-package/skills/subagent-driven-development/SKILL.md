---
name: subagent-driven-development
description: 当调查、实现、修复或验证需要主 session 与 worker 协作时使用；在启动前形成 mode、具体 worker、schedule 和 review 策略，并消费统一结果。
---

# Subagent-Driven Development

这是 Impl-Package 的唯一 worker 编排入口。它不重写业务需求、Task/Ticket、授权或验收，只把已经确定的 bounded unit 变成一份可执行策略，并在主 session 集成前收口 worker 结果。

## 先形成策略

每个非本地 bounded unit 启动前都必须输出：

```yaml
mode: investigate | implement | fix | verify
worker: main-session | "$grok-worker" | "@luna-worker" | "<model>/<effort>" | "prompt:<slug>"
schedule: local | serial | parallel
review: none | required
reason: <仅在 local、blocked、显式 override 或 review 判断不显然时填写>
resources: <只记录真实共享资源、顺序和 cleanup owner>
reuse: <只在同一 source unit 需要不可转移 live state 时填写>
```

- `worker` 必须显式存在；默认是 `$grok-worker`。`main-session` 只用于原子本地动作，且必须说明 reason。
- `schedule=serial` 用于单个委派或有序 batch；只有两个以上彼此隔离的 bounded unit 才能 `parallel`。共享可变资源时按 [Parallel Work Admission](references/parallel-work-admission.md) 判定。
- 未填写 `reuse` 时使用 fresh invocation；context compaction 后从 canonical input 重新启动。角色相同、空闲或共享 worktree 都不是复用理由。
- `investigate`、`implement`、`fix` 默认继承同一逻辑 worker；复杂度只改变 `review`，不更换 Implementer/Fixer。

## Mode selection

- `investigate`：事实不足时建立 cause、blast radius、existing solution 和 boundary facts；返回 `EVIDENCE_SUFFICIENT` 或 `EVIDENCE_GAP`，不代替授权或实施。
- `implement`：消费已释放的 Plan/Ticket/DAG bounded unit，返回变更、局部验证和残余风险。
- `fix`：只消费已确认且已边界化的 finding；局部 `DONE` 不等于 finding closure，closure 由 reviewer 完成。
- `verify`：只运行既定、无写副作用的检查；长时间或高回显检查交给 worker，快速有界检查可留在主 session。

各 mode 的输入、模板和直接输出见 [Mode Contracts](references/mode-contracts.md)。

## Worker resolver

读取 [Worker Resolver](references/worker-resolver.md) 后再启动。解析不到唯一实体、宿主不支持 invocation、授权不匹配或 brief 不完整时，在启动前返回 `BLOCKED`，不猜测近似 worker。

- `$grok-worker` 解析到现有 `skills/call-grok/` Skill；编排层不传 `model` 或 `effort`，直接使用该 Skill 的设置和 adapter 合同。
- `@luna-worker` 解析到宿主已有的全局 agent profile；本仓库不修改用户级 TOML，也不复制一份 registry。
- 直接 model/profile、prompt-backed worker 和 `main-session` 都使用同一输入/输出合同。

## 生命周期与失败

执行结果统一为 `Outcome: DONE | BLOCKED | INCOMPLETE`，并附 `mode`、`worker`、`source_unit`、`evidence`、`artifacts`、`blocker`、`fallback_from` 和 `session_id`。默认 `$grok-worker` 只有在进程已清理、diff/residue 可归因且可安全重放时，才允许一次 fresh `@luna-worker` fallback；业务 `BLOCKED` 不 fallback，第二次 `INCOMPLETE` 归一为 `BLOCKED`。详见 [Worker Resolver](references/worker-resolver.md)。

`review=required` 时，worker 的 `DONE` 先标记 `review_state: PENDING_REVIEW`；reviewer PASS 后标记 `review_state: PASSED`，finding 进入同一 worker 的 `fix`，UNCERTAIN/BLOCKED 原样上交。`review=none` 的 DONE 使用 `review_state: NOT_REQUIRED`。复杂度与 reviewer 门槛见 [Review Gate](references/review-gate.md)。

主 session 始终负责最终集成、证据采信、Ticket acceptance 和 Gate 判断；worker 的局部 DONE、review PASS 或测试通过都不单独代表 package 完成。
