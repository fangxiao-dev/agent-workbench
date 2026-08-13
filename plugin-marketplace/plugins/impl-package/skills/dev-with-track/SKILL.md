---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用；新 package 以 Ticket 为执行轴，不重新定义 Decision/Spec/Plan/Ticket。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`。当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。本 skill 维护 current state、Progress、Attempt Execution Record、active checkpoint、execution findings 和 current Gate；旧 package 的 Task Handoff 仅作兼容恢复材料，各上游 artifact 仍由 owning skill 维护。
需要委派或决定本地执行时，通过 `/impl-package:subagent-driven-development` 取得 scheduling contract；本 skill 只消费调度结果。

## Restore

1. 运行 `validate`；跨 session 或授权绑定比较点时附 `--commit <Git commit>`。
2. 打开根 `progress.md`，读取 current Attempt、可选合同别名、Composition、Ticket 状态、blocker、active checkpoint、next action、Gate 及 Execution Record 指针；只有旧 package 才读取 Task/DAG/Handoff 轴。
3. 只沿当前动作读取必要 Ticket、Task、Handoff、Execution Record judgment、review 或 evidence；不要重读全部历史。
4. 根据批准 commit 与实际 diff 判断 authority/contract 是否仍成立。implementation-only 继续；行为、acceptance、数据/安全或 mutation authority 变化回 owning stage。

## 主 session 控制循环

1. **Investigate**：确认首个真实违约边界、输入、持久状态、权威来源和已通过边界。
2. **Decide & seam**：现有 Decision/Spec 能唯一裁决时作为 implementation defect；存在多个合理业务结果才请求 owner。
3. **Implement**：只修复已证实、当前可归责的范围；派发时给 primary ownership、禁区、成功条件、反例和局部验证。
4. **Evaluate**：使用最便宜且忠实的证据。昂贵 runtime/E2E 重跑必须有新修复、环境变化或决定性观察目标。

步骤 1、3 的事实调查、实现、修复和验证策略由 `/impl-package:subagent-driven-development` 统一形成；本 skill 只消费其 `mode / worker / schedule / review` 与结果合同。步骤 2 和 4 由主 session 把控。
依赖是否释放由新 package 的 typed Ticket dependency 与 canonical state 判断；旧 package 才额外读取 DAG。Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。

## State、ER 与 Handoff

- 状态变化只使用 Ticket `set-state ... --expect ...`；SATISFIED 必须带当前 `--revision`/`--environment`，BLOCKED/RETIRED 使用直接 evidence；stale transition 必须重新读取当前状态。
- 新 package 不产生 `READY/RUNNING/DONE` Task 状态；旧 package 的 Task `DONE` 不等于 Ticket `SATISFIED`。
- 主 session 通过 `checkpoint` 写 active checkpoint、通过 `er-add` 写 judgment；worker 默认不直接写 package state 或 Execution Record。
- `checkpoint` 是 active checkpoint 写入快捷入口，更新 `state.activeCheckpoints[subject]`。
- 新 package 在 BLOCKED、retry、跨 session/owner 或需要交接时写文档化 active checkpoint；checkpoint 不授权派发、不释放依赖，也不创建 Task Handoff。旧 package 的 handoff 仅作迁移材料。
- checkpoint 只记录下一动作与恢复证据，不授权派发；长期判断写 ER judgment。compact 只作异常兜底，不是正常交接权威。
- 合同或计划实际变化只把受影响 Ticket（旧 package 另含受影响 Task）设为 `NEEDS-REVALIDATION`；未受影响 evidence 保留。

```powershell
Get-Content .\er-payload.json -Raw |
  python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> er-add
```

`<impl-package-plugin-root>` 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。

3.5 的 `er-add` payload 只使用 `purpose=judgment`、`subject=attempt|ticket:<id>`、`title`、`content` 和可选 evidence；checkpoint 使用显式 `checkpoint --subject ... --next ...`，旧 package 的 Task Handoff 只在迁移时读取。

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

terminal Gate 必须完成 Stage 7：记录 Durable Delta 及 `_pending.md`/truth pointer，或通过 `--no-durable-delta-reason` 明确无增量原因。terminal 后 state、active checkpoint 和 Execution Record 冻结。

Gate CLI 拥有 comparison commit 与 lifecycle 校验。长任务先完成 state/ER/Gate 等 durable 写入，再输出最终叙述；transport disconnect 后从这些幂等事实恢复，不创建第二个完成结论。

若 active skill catalog 中存在 `talk-to-boss`，优先按其汇报合同输出；否则直接分别说明实施、验证、Gate、backfill/合入状态，给出 Task/Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作。可选 skill 缺失不阻塞收口。
