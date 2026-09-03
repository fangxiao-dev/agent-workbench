---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一业务动作、记录 evidence、处理 findings 或写 Gate 时使用；作为业务主控选择动作、消费调度结果并维护 Ticket/State/Evidence/Gate。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`；当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。

## 业务控制循环

1. **刷新事实**：优先消费匹配当前 session/package 的 `Impl-Package Resume Capsule v1`；不存在或已失配时执行 Restore，取得 current Attempt、blocker、合法 action 与 situation digest。
2. **选择动作**：根据 Ticket typed dependency 与 canonical state 选择 Investigate、Decide、Implement 或 Evaluate。implementation edge 阻止绑定未稳定语义的下游实现；acceptance edge 只阻止正式验收与状态宣称；release edge 在 Gate 前复核。
3. **裁决语义**：Decision/Spec 能唯一裁决时作为 implementation defect；存在多个合理业务结果时才请求 Owner。finding 的定级、disposition 与 acceptance point 也由本 Skill 判断。
4. **形成 Topic**：按共享 foundation、ownership 与 closure point 把当前业务动作组织为连续 Topic，明确 bounded outcome、禁改范围、comparison point、成功条件与局部验证；需要 mutation 的 PENDING Ticket 先完成对应 preflight。
5. **交给 Dispatcher**：对候选执行 Topic-first admission，选择每个 Topic 的当前 coherent step 并形成批次；review 或长时验证在途不等于 Attempt 阻塞，继续释放不依赖其结论且资源隔离的其他 Ticket 调研或准备；宿主 receipt 明确后确认派发，当前批次 return 全部消费后再全局重扫。Progress/checkpoint 不授权 dispatch。
6. **执行 bounded worker**：对每个已派发 Topic，caller 按 `/impl-package:subagent-driven-development` 分类 dependency、决定当前或隔离 worktree，并形成 mode、lane、lifecycle 与 review requirement。
7. **消费结果**：核对可归因 diff、evidence、residue、cleanup 和 review 状态；局部 DONE 或 checkpoint PASS 只释放对应 Topic 下一步。随后用 package CLI 写 state/evidence/checkpoint/judgment/trail，当前批次收齐后再由 Dispatcher 全局重扫；调度 idle 后依据 canonical state、evidence、review 与 Gate 判断继续、blocked 或 closure。

完成标准：每轮都有唯一业务下一动作；调度循环 idle 只表示当前没有已解锁且合格的动作，Ticket/package closure 仍由本 Skill 根据 canonical facts 判断。

## Owner 边界

本 Skill 选择业务动作并拥有 Ticket readiness、语义裁决、State、Evidence、Execution Record、Checkpoint 与 Gate。两个平级 Skill 承担执行方法：

- `$dispatcher` 面向上游主控，拥有 Topic-first admission、coherent current step、当前批次、派发 receipt、worker return、Topic lifecycle 和 idle；
- `/impl-package:subagent-driven-development` 面向下游 bounded worker，拥有 Topic、dependency class、mode、lane、lifecycle 与 review requirement。

主 session 是 package State、Evidence、Execution Record、Checkpoint 与 Gate 的唯一 writer。调用方为每个 Topic 提供 objective、scope、write-set、acceptance、authorization、verification 和输出合同，并按 SDD 选择当前或隔离 worktree；provider/executor 由 Owner 或宿主选择。

需要快速定位业务→调度→worker→状态写入时读取 [Control Flow](references/control-flow.md)；恢复、返工、evidence 或 Gate mutation 读取 [Runtime Protocol](references/runtime-protocol.md)。

证据矛盾、恢复、部分写入补齐、跨 stage 对账或异常排查时按需调用 `/impl-package:execution-boundaries` slow path；主 session 复核其结构化修复输入并执行最终写入。旧 Task Handoff 只作兼容恢复材料。

## Restore

首次确认 package anchor 后，Codex 从当前已加载 Skill 解析 plugin root，并调用 `python <plugin-root>/hooks/impl_package_hooks.py activate --package <package>` 绑定当前 session；其它宿主跳过。若有匹配 Capsule，只消费其中的恢复事实并复核 package、HEAD 与 initial approval，不把 Capsule 当作 acceptance 或 Gate evidence。

Capsule 缺失、失配、Hook 未信任/禁用，或本轮发生 state mutation 时，读取 [Runtime Protocol](references/runtime-protocol.md) 的完整恢复顺序。真正 dispatch 前仍运行普通 `situation.py render` 生成 credential；偏离建议或表外行动使用 `escape` 记录理由。

显式离开 package 工作时，Codex 调用同一脚本的 `deactivate`；同 session 未解绑就切换到普通 SDD 时，后续 resume/compact 仍会注入 Capsule。Restore 只是导航，不推进 Gate。

## Ticket 激活 preflight

PENDING Ticket 首次激活且 Planned Verification 声明 `Evidence Lane Contract` 时，调用 `/impl-package:execution-preflight` 核 URL identity、端口 owner、库分离和 cleanup owner，只消费 `READY | BLOCKED`。昂贵 runtime/E2E 真正运行前再核 health、session 和 S3。

## State、ER 与 Trail

- Ticket 状态使用 `ticket satisfy|block|needs-revalidation|pending|retire ... --expect ...`；`SATISFIED` 携带当前 revision/environment，`BLOCKED`/`RETIRED` 携带直接 evidence。stale transition 先重读。
- 登记 `supporting` 或执行 `ticket satisfy` 前，逐 stable claim 核对 artifact 是否直接覆盖该 acceptance atom 的完整语义；部分覆盖不登记 `supporting`，Ticket 保持 `PENDING`。执行期发现一个 claim 内含可独立失败或需不同 oracle/evidence lane 的子句时，交回 `impl-planning` 修订受影响 Ticket；若该 Ticket 已 `SATISFIED`，先用 `needs-revalidation` 失效对应 evidence，不能由执行者临时把宽 claim 解释为已满足。
- worker 只返回结构化事实；所有 state mutation 走语义 CLI，证据矛盾或部分写入时经 slow path 对账后仍由主 session 执行最终写入。
- `recovery checkpoint` 只保存下一动作与恢复 evidence；长期判断写 `recovery judgment`。checkpoint 不授权派发、不释放 dependency、不创建新 Task 状态。
- `dispatch`、`worker-return`、`fact`、`escape` 使用 `trail append`；轨迹只追加，写错时追加更正。显式 handoff 先写 checkpoint，再轮换 trail。
- 新 package 不产生 `READY/RUNNING/DONE` Task 状态；旧 Task `DONE` 也不等于 Ticket `SATISFIED`。

## Review、Findings 与人工验收

- `/impl-package:do-review` 拥有 initial、finding-closure、terminal-final topology、comparison point、coverage 与 closure；本 Skill 只消费报告。
- accepted finding 作为同 Topic work lane 的 bounded fix 交给 Dispatcher；下游 worker 遵循 SDD。review lane 独立于 work lane，是否复用 reviewer 由同 Topic lifecycle 决定。派发前若同一 Topic 已经过两次以上修复方向仍未收敛、同一 finding 或同一机制在后续 round 重新出现，或 review 结论跨多个 writer、多个入口或共享 authority/lock seam，先按 `/diagnosing-bugs` 做定位再决定修复动作；其余直接 bounded fix。diagnosing-bugs 只返回定位结论，Ticket/Attempt 状态与 dependency release 继续由本流程处理，finding closure 继续由 `/impl-package:do-review` 拥有。
- terminal pass 要求 terminal-final coverage 完整且所有阻断 finding 已关闭；记录缺失或 incomplete 时交回 `do-review`。
- Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 记录入口、oracle、环境、失败反馈与 teardown owner。

## Verify and Gate

Gate 只判断 current Attempt：`blocked` 保持 active 并记录 gap/next action；`pass` 要求所有 required Ticket/verification/review/manual acceptance/findings closure 已满足；`fail|defer` 如实终结，后续实现进入 patch Attempt。

terminal Gate 必须完成 Stage 7：记录 Durable Delta 与 truth pointer，或写明无增量理由；terminal 后冻结 state、checkpoint 和 Execution Record。transport disconnect 后从幂等事实恢复，不创建第二个完成结论。

先由本 Skill 根据 canonical state、Gate 与 evidence 判断 Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作；若 catalog 中存在 `talk-to-boss`，再由它组织叙述，不参与状态判断。
