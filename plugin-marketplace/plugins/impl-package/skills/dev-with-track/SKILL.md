---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用；不重新定义 Decision/Spec/Plan/Ticket/DAG。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`。当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。本 skill 维护 current state、Progress、Attempt Execution Record、条件式 Task Handoff、execution findings 和 current Gate；各上游 artifact 仍由 owning skill 维护。
需要委派或决定本地执行时，通过 `/impl-package:subagent-driven-development` 取得 scheduling contract；本 skill 只消费调度结果。

## Restore

1. 运行 `validate`；跨 session 或授权绑定比较点时附 `--commit <Git commit>`。
2. 打开根 `progress.md`，读取 current Attempt、可选合同别名、Composition、Ticket/Task 两条状态轴、blocker、active checkpoint、next action、Gate 及 Handoff/Execution Record 指针。
3. 只沿当前动作读取必要 Ticket、Task、Handoff、Execution Record judgment、review 或 evidence；不要重读全部历史。
4. 根据批准 commit 与实际 diff 判断 authority/contract 是否仍成立。implementation-only 继续；行为、acceptance、数据/安全或 mutation authority 变化回 owning stage。

## 主 session 控制循环

1. **Investigate**：确认首个真实违约边界、输入、持久状态、权威来源和已通过边界。
2. **Decide & seam**：现有 Decision/Spec 能唯一裁决时作为 implementation defect；存在多个合理业务结果才请求 owner。
3. **Implement**：只修复已证实、当前可归责的范围；派发时给 primary ownership、禁区、成功条件、反例和局部验证。
4. **Evaluate**：使用最便宜且忠实的证据。昂贵 runtime/E2E 重跑必须有新修复、环境变化或决定性观察目标。

步骤 1、3 的事实调查、实现、修复和验证策略由 `/impl-package:subagent-driven-development` 统一形成；本 skill 只消费其 `mode / worker / schedule / review` 与结果合同。步骤 2 和 4 由主 session 把控。
依赖是否释放只由 DAG、typed Ticket dependency 与 canonical state 判断。Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。

## State、ER 与 Handoff

- 状态变化只使用 `set-state ... --expect ... --evidence ...`；stale transition 必须重新读取当前状态。
- `READY/RUNNING` 不得越过未释放 Task dependency；Task `DONE` 不等于 Ticket `SATISFIED`。
- 主 session 通过 `er-add` 写 checkpoint/judgment；worker 默认不直接写 Execution Record。
- `checkpoint` 是 attempt-level 恢复快捷入口，并更新 `state.resume`。
- 仅在 BLOCKED、retry、跨 session/owner 或并行委派时创建 `execution/<attempt>/task-handoffs/<task-id>-handoff.md`。
- 上述恢复条件发生但当前 attempt 没有 DAG Task 时，改用 Attempt-level ER checkpoint 记录 dispatch 返回的恢复事实和唯一下一动作。
- 合同或计划实际变化只把受影响 Task/Ticket 设为 `NEEDS-REVALIDATION`；未受影响 evidence 保留。

```powershell
Get-Content .\er-payload.json -Raw |
  python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> er-add
```

`<impl-package-plugin-root>` 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。

payload 使用 `purpose=checkpoint|judgment`、`subject=attempt|ticket:<id>|task:<id>`、`title`、`content`、checkpoint 的 `nextAction` 和可选 evidence。

## Review、Findings 与人工验收

- 通过 `/impl-package:do-review` 运行 initial、finding-closure 和 terminal-final review；review topology、适用范围和 coverage 由该 skill 拥有。本 skill 消费报告，terminal pass 要求 terminal-final coverage 完整且所有阻断 finding 已关闭。
- P1/P2 finding 必须修复并 closure verify；editorial suggestion 不阻断 Gate。
- package 级 `execution-findings.md` 在 terminal Gate 前必须完成分流：Decision rationale→Decision，规范行为→Spec，执行判断→Execution Record，长期知识→Durable Delta/`_pending.md`。
- Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 把入口、oracle、环境、失败反馈和 teardown owner 写入 judgment 或 canonical handoff，并取得结果 evidence。

## Verify and Gate

completion claim 先交给 `/impl-package:verification-before-completion`。Gate 只判断 current Attempt：

- `blocked`：保持 active，记录 gap 和 next action。
- `pass`：所有 earned Task/Ticket、适用验证、review、manual acceptance 和 findings closure 均满足。
- `fail | defer`：如实终结；后续实现进入 patch Attempt。

terminal Gate 必须完成 Stage 7：记录 Durable Delta 及 `_pending.md`/truth pointer，或通过 `--no-durable-delta-reason` 明确无增量原因。terminal 后 state、resume、Execution Record 冻结。

Gate CLI 拥有 comparison commit 与 lifecycle 校验。长任务先完成 state/ER/Gate 等 durable 写入，再输出最终叙述；transport disconnect 后从这些幂等事实恢复，不创建第二个完成结论。

若 active skill catalog 中存在 `talk-to-boss`，优先按其汇报合同输出；否则直接分别说明实施、验证、Gate、backfill/合入状态，给出 Task/Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作。可选 skill 缺失不阻塞收口。
