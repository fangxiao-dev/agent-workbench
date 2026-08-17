---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用；新 package 以 Ticket 为执行轴，不重新定义 Decision/Spec/Plan/Ticket。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`。当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。本 skill 拥有执行控制、finding 分流、验证和 Gate 的语义判断；current state、Progress、Attempt Execution Record、active checkpoint、execution findings 和 current Gate 的日常物理写入由主 session 直接调用现有语义 CLI 或写入其拥有的成文内容。只有证据矛盾、恢复、部分写入补齐、跨 stage 对账或异常排查才按需调用 `/impl-package:standing-bookkeeper` slow path；它返回结构化修复输入，不成为第二个 state writer。旧 package 的 Task Handoff 仅作兼容恢复材料，各上游 artifact 仍由 owning skill 维护。
需要委派或决定本地执行时，通过 `/impl-package:subagent-driven-development` 取得 scheduling contract；本 skill 只消费调度结果。

## Restore

在第 1 步 `package validate` 返回后，把当前处境渲染作为恢复起点，再进入第 2 步的 progress/checkpoint 读取。主 session 控制循环在每一轮真正推进动作前，用同一调用刷新处境与可选动作。两处都按下面顺序把 validator 结果和宿主 compaction pressure 接到 renderer；`--json` 让主控可以读取 `digest`、`selected`、`parallel_matches`、`undetermined` 和 `unmatched`：

```powershell
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> package validate
$validationResult = if ($LASTEXITCODE -eq 0) {
  '{"projection_drift":false,"source":"package validate"}'
} else {
  '{"projection_drift":true,"source":"package validate"}'
}
$compactionPressure = python <host-tools-root>/scripts/compaction_pressure.py
$renderArgs = @('--package', '<package>', '--validation-result', $validationResult, '--compaction-pressure', $compactionPressure, '--json')
if ($previousDigest) { $renderArgs += @('--since', $previousDigest) }
python <impl-package-plugin-root>/scripts/situation.py render @renderArgs
```

这里的布尔值是对 `package validate` 退出结果的结构化适配：成功传 `false`，非零结果保守传 `true`；不解析 stdout/stderr。`$compactionPressure` 是宿主侧测量的单行 JSON，至少含 `high` 布尔；如何测量由宿主决定（`<host-tools-root>` 指提供该测量工具的仓库，不是插件根），插件不假设宿主具备这个能力。测不到时省略该参数，`attempt.compaction_pressure_high` 保持无法判定而非 false。若非零同时意味着 `package.state_invalid`，renderer 自己推导的 P0 `package.record.state-missing` 仍按表的顺序优先显示。渲染结果是参考，不是 gate；主控可以按实际判断偏离建议，但要在轨迹中写一行理由。

首次调用不设置 `$previousDigest`；每次从结果读取当前 `digest` 保存到 `$previousDigest`，下一轮追加 `--since $previousDigest`。digest 命中时只返回一行“处境未变”，否则返回完整内容并带上新的 digest。需要 human 输出中的无法判定处境名单时，显式追加 `--explain-undetermined`；默认 human 输出只保留计数。

1. 运行 `package validate`；跨 session 或授权绑定比较点时附 `--commit <Git commit>`。
2. 打开根 `progress.md`，读取 current Attempt、可选合同别名、Composition、Ticket 状态、blocker、active checkpoint、next action、Gate 及 Execution Record 指针；只有旧 package 才读取 Task/DAG/Handoff 轴。
3. 只沿当前动作读取必要 Ticket、Task、Handoff、Execution Record judgment、review 或 evidence；不要重读全部历史。
4. 根据初始 bundle approval 和实际 diff确认仍在同一 package。implementation、behavior、acceptance、data/security 与 package record 更新均沿用该 approval；新 package 从 owning stage 取得新的初始 bundle approval。

## 主 session 控制循环

每轮在 Investigate、Decide、Implement 或 Evaluate 任何一步落地前，先按 Restore 上面的 `package validate` → 结构化 `--validation-result` → `situation.py render --json` 顺序查看当前处境与可选动作；这只是导航参考，不是推进 gate。

1. **Investigate**：确认首个真实违约边界、输入、持久状态、权威来源和已通过边界。
2. **Decide & seam**：现有 Decision/Spec 能唯一裁决时作为 implementation defect；存在多个合理业务结果才请求 owner。
3. **Implement**：只修复已证实、当前可归责的范围；派发时给 primary ownership、禁区、成功条件、反例和局部验证。
4. **Evaluate**：使用最便宜且忠实的证据。昂贵 runtime/E2E 重跑必须有新修复、环境变化或决定性观察目标。

步骤 1、3 的事实调查、实现、修复和验证策略由 `/impl-package:subagent-driven-development` 统一形成；本 skill 只消费其 `mode / worker / schedule / review` 与结果合同。步骤 2 和 4 由主 session 把控，package 记录由主 session 直接调用现有语义 CLI 或写入 judgment 落盘；只有异常 slow path 才消费 bookkeeper 的对账回执。
结构化写入与下一次派发没有硬依赖时，可以放在同一个 block 里并行发出；不必先等待落账再派活，只有下一动作确实依赖写入结果时才等待对应 CLI receipt 或 validation。
依赖是否释放由新 package 的 typed Ticket dependency 与 canonical state 判断；旧 package 才额外读取 DAG。Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。

## State、ER 与 Handoff

- 状态变化优先使用语义 Ticket 命令 `ticket satisfy|block|needs-revalidation|pending|retire ... --expect ...`；SATISFIED 必须带当前 `--revision`/`--environment`，BLOCKED/RETIRED 使用直接 evidence；stale transition 必须重新读取当前状态。旧 `set-state ticket ...` 仅作兼容别名。
- 新 package 不产生 `READY/RUNNING/DONE` Task 状态；旧 package 的 Task `DONE` 不等于 Ticket `SATISFIED`。
- 主 session 直接通过 `recovery checkpoint`、`recovery judgment` 等现有入口写入 checkpoint、judgment 和其他已确定执行事实；worker 默认只返回结构化 evidence，不直接写 package state 或 Execution Record。遇到证据矛盾、恢复或部分写入补齐时，可调用 slow path 协助对账，主 session 复核后仍由自己执行 CLI。
- `recovery checkpoint` 是 active checkpoint 写入快捷入口，更新 `state.activeCheckpoints[subject]`。
- 新 package 在 BLOCKED、retry、跨 session/owner 或需要交接时写文档化 active checkpoint；checkpoint 不授权派发、不释放依赖，也不创建 Task Handoff。旧 package 的 handoff 仅作迁移材料。
- checkpoint 只记录下一动作与恢复证据，不授权派发；长期判断写 ER judgment。compact 只作异常兜底，不是正常交接权威。
- 合同或计划实际变化直接记录受影响 Ticket（旧 package 另含受影响 Task）并保留未受影响 evidence；同一 package 持续沿用 initial bundle approval。

```powershell
Get-Content .\er-payload.json -Raw |
  python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> recovery judgment
```

`<impl-package-plugin-root>` 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。

3.5 的 `recovery judgment` payload 只使用 `purpose=judgment`、`subject=attempt|ticket:<id>`、`title`、`content` 和可选 evidence；checkpoint 使用显式 `recovery checkpoint --subject ... --next ...`，旧 package 的 Task Handoff 只在迁移时读取。

## 处境投递与轨迹

处境表漏掉某个当前处境时，按判断行动并走 escape 出口是合法路径，不是违规；若主控偏离渲染建议，也只需记录理由，不把 renderer 当成阻断器。**每一次 escape 必须写一行轨迹**，包括偏离渲染建议和处境表没覆盖当前处境两种；escape 是唯一既不产生产物、也无法从其它行推导的事件，处境表只能靠这些行发现自己的缺陷。派发的发起与返回、finding 定级与分流、来源路由判断和需要声明的 fact 照常写行，但它们本身就伴随一次调用或状态转换；Ticket 选择由随后 dispatch 的 `subject` 表明，不必单独写行。轨迹位置与格式遵循 `../../references/situation-inputs.md`（运行时不需要打开，仅在维护处境表或写 per-package 覆盖时查阅）和 `docs/skill-design/impl-package-situation-table-260815/trail-schema.md`（运行时不需要打开，仅在维护轨迹格式或写 per-package 覆盖时查阅）：`execution/<attempt>/trail.jsonl` 中每个非空行是 JSON object，事件使用 `dispatch`、`result`/`worker-return` 或 `kind=fact`，带正确的 `subject`，fact 带 `key`、`value`、`ts`，需要 Git 对账时带 `head`；`dispatch` 可带本次派发所依据的 renderer 12 位 `situation_digest`，缺失由只读审计报告，不阻断渲染。轨迹只追加、不改写已有行；发现某行写错时追加一条正确的 fact（同 key 取最新）或补一行说明，改写历史会让回放失去意义。交接时若当前 trail 已满，先按 trail schema 轮换为带序号归档并新建 `trail.jsonl`，随后在新轨迹中重新声明仍成立的 fact。首版全部显式写行，不要求改 `impl_package_state.py`。

## Review、Findings 与人工验收

当 `do-review` parent 已接受并归类 Track C / Spec fidelity finding 时，修复派发前读取 [Runtime Protocol](references/runtime-protocol.md) 的 Findings 路由并消费同一 ReviewRun 已记录的一次性独立 source recheck。其余 finding 的定级/closure 和 terminal Gate 前分流动作由处境表按当前处境投递。

- 通过 `/impl-package:do-review` 运行 initial、finding-closure 和 terminal-final review；review topology、适用范围和 coverage 由该 skill 拥有。本 skill 消费报告，terminal pass 要求 terminal-final coverage 完整且所有阻断 finding 已关闭。
- 本 skill 不重复调度 reviewer，记录缺失或 incomplete 时交回 `do-review`。该检查不创建 Ticket/Attempt 状态，也不替代 finding-closure 或 terminal-final。
- Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 把入口、oracle、环境、失败反馈和 teardown owner 写入 judgment 或 canonical handoff，并取得结果 evidence。

## Verify and Gate

完成声明的审计动作由处境表按当前处境投递；Gate 只判断 current Attempt：

- `blocked`：保持 active，记录 gap 和 next action。
- `pass`：所有 earned Task/Ticket、适用验证、review、manual acceptance 和 findings closure 均满足。
- `fail | defer`：如实终结；后续实现进入 patch Attempt。

terminal Gate 必须完成 Stage 7：记录 Durable Delta 及 `_pending.md`/truth pointer，或通过 `--no-durable-delta-reason` 明确无增量原因。terminal 后 state、active checkpoint 和 Execution Record 冻结。

Gate CLI 拥有 comparison commit 与 lifecycle 校验。长任务由主 session 直接完成 state/ER/Gate 等 durable 写入，再输出最终叙述；transport disconnect 后从这些幂等事实恢复，不创建第二个完成结论。只有写入异常需要对账时才调用 slow path。

先由本 skill 根据 canonical state、Gate 和 evidence 确定实施、验证、Gate、backfill/合入状态，以及 Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作。若 active skill catalog 中存在 `talk-to-boss`，再用它组织这些已经确定的事实；它不参与状态判断。可选 skill 缺失不阻塞收口。
