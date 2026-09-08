---
name: dev-with-track
description: 当批准 implementation plan 正式开始或恢复执行、确定业务重点与候选范围、记录 evidence、处理 findings 或写 Gate 时使用；拥有 Ticket readiness、语义裁决与 State/Evidence/Gate。
---

# Dev With Track

先读 `../../references/impl-package-composition-contract.md` 和 `../../references/impl-package-current-state.md`；当前 Attempt 涉及 material seam、browser/provider/native-tool 或真实系统运行验证时，再读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。

## 业务控制循环

1. **刷新业务事实。** 优先消费匹配当前 session/package 的 `Impl-Package Resume Capsule v1`；缺失或失配时执行 Restore，取得 current Attempt、canonical Ticket state、blocker、候选与 situation digest。
2. **确定重点和候选范围。** 根据 typed dependency、批准合同与 evidence 选定当前交付重点，同时把范围内相关剩余工作交给 Dispatcher 看见。`implementation` edge 阻止绑定未稳定语义的实现；`acceptance` edge 只阻止正式验收与状态宣称；`release` edge 在 Gate 前复核。Decision/Spec 能唯一裁决时按 implementation defect 处理；存在多个合理业务结果时请求 Owner。
3. **应用 `$dispatcher`。** 提供业务目标、事实、授权、候选 subject、dependency、acceptance 和禁改范围，由 Dispatcher 完成候选选择、brief、资源隔离、dispatch/receipt、worker return、delta review 与 idle。工作无需预登记；资源与授权由主控按当前事实判断。主控直接实现时遵守相同 write ownership、自证和独立 delta review 要求。Progress/checkpoint 不授权 dispatch。
4. **消费并记录。** 核对可归因 diff、evidence、residue、cleanup 和 review 状态；局部 `DONE`、`PASSED` 或 checkpoint PASS 只释放对应候选。随后用 package CLI 写 State、Evidence、Execution Record、Checkpoint 与 Trail；finding 的等级、disposition、影响范围和解决期限由本 Skill 判断。
5. **判断继续或收口。** Dispatcher idle 后仍按 canonical State、Evidence、required review、manual acceptance、findings closure 与 Gate 判断继续、blocked 或 closure。每轮记录当前交付重点、可推进候选、局部 blocker 与恢复入口；局部等待不自动关闭 package。

完成标准：业务范围与候选没有被单一恢复 next 缩窄；每个状态变化有直接 evidence；Dispatcher 的局部结果没有被误报为 Ticket/package 完成；Gate 只由 current Attempt 的 canonical facts 决定。

## Owner 边界

本 Skill 拥有 Ticket readiness、语义裁决、State、Evidence、Execution Record、Checkpoint 与 Gate；`$dispatcher` 是通用执行协作入口，拥有候选选择、委派合同、资源隔离、receipt、return、delta review 和 idle。主 session 是 package 权威状态的唯一 writer；provider、executor、model 或 agent profile 由 Owner 或宿主选择。

需要定位业务→执行协作→状态写入时读取 [Control Flow](references/control-flow.md)；恢复、返工、evidence 或 Gate mutation 时读取 [Runtime Protocol](references/runtime-protocol.md)。证据矛盾、部分写入、跨 stage 对账或异常排查时，主 session 直接核对 current state 与相关 artifact；复杂时可用 Dispatcher 委派只读调查。旧 Task Handoff 只作兼容恢复材料。

## Restore

首次确认 package anchor 后，Codex 从当前已加载 Skill 解析 plugin root，并调用 `python <plugin-root>/hooks/impl_package_hooks.py activate --package <package>` 绑定当前 session；其他宿主跳过。匹配 Capsule 只提供恢复事实，仍复核 package、HEAD 与 initial approval，不把 Capsule 当 acceptance、Gate evidence 或 dispatch credential。

已知 CLI 成功更新后按 delta 更新当前事实；Capsule 缺失或失配、Hook 未信任/禁用、读取 warning、未知外部状态变化或状态更新失败时，按 [Runtime Protocol](references/runtime-protocol.md) 执行完整恢复。真正 dispatch 前运行 `situation.py render` 生成 credential；偏离建议或表外行动使用 `escape` 记录理由。

显式离开 package 工作时，Codex 调用同一脚本的 `deactivate`。Restore 只恢复范围与事实，不推进 Gate。

## State、ER 与 Trail

- Ticket 状态使用 `ticket satisfy|block|needs-revalidation|pending|retire ... --expect ...`；`SATISFIED` 携带 current revision/environment，`BLOCKED`/`RETIRED` 携带直接 evidence。stale transition 先重读。
- 登记 `supporting` 或执行 `ticket satisfy` 前，逐 stable claim 核对 artifact 是否覆盖完整 acceptance atom。可独立失败或需要不同 oracle/evidence lane 的子句交回 `impl-planning` 修订；已 `SATISFIED` 的 Ticket 先 `needs-revalidation`。
- worker 只返回结构化事实；所有 state mutation 走语义 CLI。`recovery checkpoint` 保存恢复入口与 evidence；长期判断写 `recovery judgment`。
- `dispatch`、`worker-return`、`fact`、`escape` 使用 `trail append`；轨迹只追加，写错时追加更正。显式 handoff 先写 checkpoint，再轮换 trail。
- 新 package 不产生 `READY/RUNNING/DONE` Task 状态；旧 Task `DONE` 不等于 Ticket `SATISFIED`。

## Review、Findings 与人工验收

`/impl-package:do-review` 拥有 initial、finding-closure、terminal-final topology、comparison point、coverage 与 closure；本 Skill 判断 formal review requirement 并消费报告。

以下任一 material risk 命中时，当前 Ticket 需要独立 formal review：

- shared seam：改变多个执行方共同依赖的接口、协议、模块或集成边界；
- 安全：改变身份、信任边界或敏感数据暴露；
- 数据完整性：可能造成已写数据丢失、重复、错配、越界或不可恢复；
- 并发：改变多个执行路径读写同一可变状态的顺序；
- migration：改变既有数据的 schema 或语义；
- 权限：改变谁能执行动作、读取数据或触发外部副作用；
- 不可逆外部副作用：效果不能靠重跑或回滚撤销。

Plan/policy 明确要求时同样产生 formal review requirement。required review 完成前保持 `PENDING_REVIEW`；具体派发和 reviewer lifecycle 归 Dispatcher，formal topology 与 finding closure 归 do-review。

已确认 finding 可立即修、随相关下一步修或隔离并行修，由 Dispatcher 根据影响、资源和整合成本安排。延后不能放行依赖该缺陷的实现或验收。修复方向已失去可信边界、同一机制再次出现或影响跨多个 writer/入口/shared authority 时，先按 `/diagnosing-bugs` 定位；finding closure 仍归 do-review。

terminal pass 要求 terminal-final coverage 完整且阻断 findings 已闭合。Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 记录入口、oracle、环境、失败反馈与 teardown owner。

## Verify and Gate

Gate 只判断 current Attempt：`blocked` 保持 active 并记录 gap/next action；`pass` 要求 required Ticket、verification、review、manual acceptance 和 findings closure 均满足；`fail|defer` 如实终结，后续实现进入 patch Attempt。

terminal Gate 完成 Stage 7：记录 Durable Delta 与 truth pointer，或写明无增量理由；随后冻结 state、checkpoint 与 Execution Record。transport disconnect 后从幂等事实恢复。

先由本 Skill 根据 canonical facts 判断 Ticket 总数、剩余数、blocker、是否 closed 和需要 Owner 的决定；若 catalog 中存在 `talk-to-boss`，再由它组织叙述。
