---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用；新 package 以 Ticket 为执行轴，不重新定义 Decision/Spec/Plan/Ticket。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`；当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。本 skill 拥有执行控制、finding 分流、验证和 Gate 的语义判断；current state、Progress、Attempt Execution Record、active checkpoint、execution findings 和 current Gate 的日常物理写入由主 session 直接调用语义 CLI 或写入其拥有的成文内容。只有证据矛盾、恢复、部分写入补齐、跨 stage 对账或异常排查才按需调用 `/impl-package:execution-boundaries` slow path；它返回结构化修复输入，不成为第二个 state writer。旧 package 的 Task Handoff 仅作兼容恢复材料，各上游 artifact 仍由 owning skill 维护。需要委派或决定本地执行时，通过 `/impl-package:subagent-driven-development` 取得 scheduling contract；本 skill 只消费调度结果。

## Restore

`package validate` 返回后，把 validator 结果和宿主 compaction pressure 通过现有 `situation.py render --json` 注入；处境与可选动作是恢复起点，主 session 在每轮真正推进前用同一入口刷新。结构化输出供主控读取 `digest`、`selected`、`parallel_matches`、`undetermined` 和 `unmatched`；成功/非零 validator 结果分别映射为 `projection_drift=false/true`，不解析 stdout/stderr。compaction pressure 由宿主测量，至少含 `high` 布尔；插件不假设宿主具备该测量能力，测不到时省略，`attempt.compaction_pressure_high` 保持未知而不是 false；若同时存在 `package.state_invalid`，renderer 的 P0 顺序优先。渲染是导航参考，不是 Gate；主控偏离建议必须记理由并走 escape。

首次调用不带 `$previousDigest`；后续保存返回的 `digest` 并用 `--since`，命中时只显示“处境未变”，需要人读无法判定名单时显式加 `--explain-undetermined`，默认只显示计数。

恢复顺序如下：

1. 运行 `package validate`（跨 session 或授权绑定比较点附 Git commit）。成功/非零 validator 结果分别映射为 `projection_drift=false/true`，不解析 stdout/stderr；这样 renderer 消费的是结构化事实，而不是对命令文本的猜测。
2. 读取根 `progress.md` 的 current Attempt、Ticket 状态、blocker、active checkpoint、next action、Gate（不读 `state.json` 全文或 situation JSON 全量）。恢复只需要当前投影与合法动作，避免把全量 state 或 situation JSON 当成推进依据。
3. 只沿当前动作读必要 Ticket 切片，不重读全部历史或已 `SATISFIED` Ticket 的 evidenceIndex。当前动作不需要重播已完成历史，狭读也保留恢复边界。
4. 用初始 bundle approval 与实际 diff 确认仍在同一 package；implementation、behavior、acceptance、data/security 和 package record 更新沿用该 approval，新 package 从 owning stage 取得新的初始 bundle approval。这样同一 package 不会在恢复时悄然换合同，新 package 才重新取得 approval。

## Ticket 激活 preflight

选择 PENDING Ticket 做首次 dispatch 时，若 Planned Verification 声明 `Evidence Lane Contract`，主 session 调用 `/impl-package:execution-preflight` 核 URL 身份、端口 owner、库分离和 cleanup owner，只输出 `READY | BLOCKED`；每个 Ticket 首次激活一次，不放进每轮控制循环，子代理不得判 lane 生死。昂贵 runtime/E2E 真正运行前再核 health、session 和 S3。

## 主 session 控制循环

每轮在 Investigate、Decide、Implement 或 Evaluate 落地前先刷新 Restore 处境与合法动作；它只是导航，不是推进 Gate。

1. **Investigate**：确认首个真实违约边界、输入、持久状态、权威来源和已通过边界。
2. **Decide & seam**：现有 Decision/Spec 能唯一裁决时作为 implementation defect；证据支持多个合理业务结果时才请求 owner。
3. **Implement**：只修复已证实、当前可归责的范围；派发时给 primary ownership、禁区、成功条件、反例和局部验证。
4. **Evaluate**：使用最便宜且忠实的证据；昂贵 runtime/E2E 重跑必须有新修复、环境变化或决定性观察目标。

步骤 1、3 的事实调查、实现、修复和验证策略由 `/impl-package:subagent-driven-development` 统一形成，本 skill 只消费其 `mode / worker / schedule / review` 与结果合同；步骤 2、4 由主 session 把控，package 记录由主 session 直接落盘。结构化写入与下一次派发没有硬依赖时可以并行；只有下一动作依赖写入结果时才等待 CLI receipt 或 validation。依赖是否释放由新 package 的 typed Ticket dependency 与 canonical state 判断；旧 package 才额外读取 DAG，Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。

## State、ER 与 Handoff

- 状态变化优先使用语义 Ticket 命令 `ticket satisfy|block|needs-revalidation|pending|retire ... --expect ...`；`SATISFIED` 必须带当前 `--revision`/`--environment`，`BLOCKED`/`RETIRED` 使用直接 evidence，stale transition 先重新读取状态；旧 `set-state ticket` 仅作兼容别名。
- 新 package 不产生 `READY/RUNNING/DONE` Task 状态；旧 package 的 Task `DONE` 不等于 Ticket `SATISFIED`。
- 主 session 直接通过 `recovery checkpoint`、`recovery judgment` 等入口写 checkpoint、judgment 和已确定执行事实；worker 默认只返回结构化 evidence，不直接写 package state 或 Execution Record。证据矛盾、恢复或部分写入补齐时可调用 slow path，主 session 复核后仍由自己执行 CLI。
- `recovery checkpoint` 更新 `state.activeCheckpoints[subject]`；新 package 在 BLOCKED、retry、跨 session/owner 或交接时写 active checkpoint，但 checkpoint 不授权派发、不释放依赖、不创建 Task Handoff；旧 package 的 handoff 仅作迁移材料。
- checkpoint 只记录下一动作与恢复证据，长期判断写 ER judgment；compact 只作异常兜底，不是正常交接权威。合同或计划实际变化直接记录受影响 Ticket（旧 package 另含受影响 Task）并保留未受影响 evidence；同一 package 持续沿用 initial bundle approval。

3.5 的 `recovery judgment` payload 只使用 `purpose=judgment`、`subject=attempt|ticket:<id>`、`title`、`content` 和可选 evidence；checkpoint 使用显式 `recovery checkpoint --subject ... --next ...`。CLI 路径取当前已加载 skill 所属的插件根目录，不假设 workbench 仓库或宿主缓存路径。

## 处境投递与轨迹

处境表漏掉当前处境时按判断行动并走 escape 出口是合法路径；偏离渲染建议或表外行动都必须追加一行 `kind=escape`，带 `subject`、`deviation`、`reason`。escape 是唯一既不产生产物、也不能由其它行推导的事件；处境表靠它发现缺陷。dispatch、escape、fact、worker-return 走语义 `trail append`，CLI 校验 event kind、fact key、review 字段和 dispatch 的当前 situation digest；finding 定级与分流、来源路由和需要声明的 fact 也按相应轨迹记录。轨迹只追加、不改写，写错时追加更正。Ticket 选择由随后 dispatch 的 `subject` 表明，不必另写选择事件；显式交接使用 `recovery checkpoint --handoff`，先写 state checkpoint，再在新 trail 保留仍成立的 fact 并记录 handoff，随后轮换 trail；普通 checkpoint 不轮换；老 package 或异常补写才按 schema 手写轨迹。

## Review、Findings 与人工验收

当 `do-review` parent 已接受并归类 Track C / Spec fidelity finding 时，修复派发前读取 [Runtime Protocol](references/runtime-protocol.md) 的 Findings 路由并消费同一 ReviewRun 已记录的一次性独立 source recheck；其余 finding 的定级、closure 和 terminal Gate 前分流动作由处境表按当前处境投递。

- 通过 `/impl-package:do-review` 运行 initial、finding-closure 和 terminal-final review；review topology、适用范围和 coverage 由该 skill 拥有。本 skill 只消费报告，terminal pass 要求 terminal-final coverage 完整且所有阻断 finding 已关闭。
- 本 skill 不重复调度 reviewer；记录缺失或 incomplete 时交回 `do-review`。该检查不创建 Ticket/Attempt 状态，也不替代 finding-closure 或 terminal-final。
- Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 把入口、oracle、环境、失败反馈和 teardown owner 写入 judgment 或 canonical handoff，并取得结果 evidence。

## Verify and Gate

完成声明的审计动作由处境表按当前处境投递；Gate 只判断 current Attempt：`blocked` 保持 active 并记录 gap/next action；`pass` 须全部 earned Task/Ticket、适用验证、review、manual acceptance 和 findings closure 满足；`fail | defer` 如实终结，后续实现进入 patch Attempt。

terminal Gate 必须完成 Stage 7：记录 Durable Delta 及 `_pending.md`/truth pointer，或用 `--no-durable-delta-reason` 明确无增量；terminal 后冻结 state、active checkpoint 和 Execution Record。Gate CLI 拥有 comparison commit 与 lifecycle 校验。长任务由主 session 先完成 state/ER/Gate 等 durable 写入再输出叙述；transport disconnect 后从幂等事实恢复，不创建第二个完成结论，只有写入异常需要对账时才调用 slow path。

先由本 skill 根据 canonical state、Gate 和 evidence 确定实施、验证、Gate、backfill/合入状态，以及 Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作；若 active skill catalog 存在 `talk-to-boss`，再由它组织这些已确定事实，不参与状态判断。可选 skill 缺失不阻塞收口。
