---
name: dispatch-bounded-task
description: 当批准的 Plan、Ticket 或 DAG 已提供已释放的实现、review 修复或只读验证单元、授权边界和 scheduling contract 时使用；选择 Implementer、Fixer 或 Verifier 及其 worker，并回收局部证据。
---

# Dispatch Bounded Task

本 skill 把一个已释放 bounded unit 适配为具体派发。单元设计、调度和正式验收仍由各自 owner 负责。

## 派发

1. 确认调用者给出批准来源、已释放单元、授权边界和完整 scheduling contract。
2. 新增实现选择 Implementer；已确认且已边界化的 review finding 选择 Fixer；只执行既定检查并返回证据选择 Verifier。finding 的原因、合同、范围或处置仍未确定时返回 `BLOCKED`。
3. 先遵守调用者指定的 worker、宿主/授权约束和 scheduling contract。未输出 `reuse:` 时新建 subagent，`call-grok` 也始终启动 fresh process；存在 `reuse:` 时只沿用其中指定的同一 source unit 和 agent，不启动 `call-grok`。
4. 对 Implementer 和 Fixer 使用同一复杂度判据：跨模块、接口、状态机或 shared seam，或触及安全、数据完整性、并发、migration、外部副作用时为复杂；其余合同冻结、ownership 局部且可直接验证的单元为普通。
5. 按 worker profile 派发；表格只定义首选与 `INCOMPLETE` 后的一次 fresh fallback。业务 `BLOCKED` 原样上交。

| 角色 | 普通首选 | executor fallback | 复杂任务 |
|---|---|---|---|
| Implementer | `call-grok`：`grok-4.5`、`effort=high` | `luna-worker` | [@luna-worker](subagent://luna-worker) (gpt-5.6-luna/max) |
| Fixer | `call-grok`：`grok-4.5`、`effort=high` | `luna-worker` | default subagent |
| Verifier | 调用者指定或当前宿主适配的验证 worker | 无额外默认；失败时 `BLOCKED` | 同普通策略 |

6. 在派发边界把任一 worker 的原生结果统一映射为 `Outcome: DONE | BLOCKED | INCOMPLETE`。普通 Implementer 或 Fixer 读取 `call-grok` 并提供完整角色 prompt，但不改变其 JSON 接口。`INCOMPLETE` 时读取 [Worker Failure Recovery](references/worker-failure-recovery.md)；只有进程已清理且 residue 可归因时，才允许表格中的一次 fresh fallback。无 fallback、cleanup 或 residue 不确定，或 fallback 再次未完成时，统一返回 `BLOCKED`。
7. 读取 [Bounded Task 模板](references/task-templates.md)，填入当前单元，并原样传递 scheduling contract 后派发。Fixer 不得用未证实的替代解释撤销已确认 finding 或既有修复；新证据与输入合同冲突时返回 `BLOCKED` 交给 owner 裁决。

## 返回合同

- `Outcome: DONE`：返回局部产出和直接证据。Implementer 返回变更、文件和局部验证；Fixer 还返回 finding ID/来源，但不表示 finding 已 closure；Verifier 返回既定动作的 red/green 证据。三者都不表示 Ticket accepted。
- `Outcome: BLOCKED`：合同、authority 或 scope 未决；包含 source unit、原因、建议动作和可选 Ticket ID，不得 fallback。
- `Outcome: INCOMPLETE`：executor 未完成；包含 source unit、terminal status、cleanup 和 residue，由本 skill 决定一次 fallback 或归一为 `BLOCKED`。
- Working Branch owner 集成产出、处理 seam/冲突并采信共享验证；`/impl-package:dev-with-track` 负责正式 review、finding closure verification、Ticket acceptance 与 package 收口。
