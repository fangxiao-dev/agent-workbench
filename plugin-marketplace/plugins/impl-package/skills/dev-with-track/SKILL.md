---
name: dev-with-track
description: 当批准 implementation plan 正式开始或恢复执行、确定业务重点与候选范围、记录 evidence、处理 findings 或写 Gate 时使用；拥有 Ticket readiness、语义裁决与 State/Evidence/Gate。
---

# Dev With Track

开工只需读 `$dispatcher` 的执行原则（四行）；其余材料按需读：登记 evidence 或核对 claim 时读 `../../references/impl-package-composition-contract.md`（3.6 package 读 §7），恢复或核对 state 时读 `../../references/impl-package-current-state.md`（3.6 格式与命令在其“3.6 格式”节），当前 Attempt 涉及 material seam、browser/provider/native-tool 或真实系统运行验证时读 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md)。

## 业务控制循环

1. **刷新业务事实。** 优先消费匹配当前 session/package 的 `Impl-Package Resume Capsule v1`；缺失或失配时执行 Restore，取得 current Attempt、canonical Ticket state、blocker、候选与 situation。
2. **确定重点和候选范围。** 根据 typed dependency、批准合同与 evidence 选定当前交付重点，同时把范围内相关剩余工作交给 Dispatcher 看见。`implementation` edge 阻止绑定未稳定语义的实现；`acceptance` edge 只阻止正式验收与状态宣称；`release` edge 在 Gate 前复核。Decision/Spec 能唯一裁决时按 implementation defect 处理；存在多个合理业务结果时请求 Owner。
3. **应用 `$dispatcher`。** 形成第一份 brief 前先读 `$dispatcher` 的执行原则（角色≠载体、载体可有 worktree、先 foundation 再 fan-out、ready≠执行 dependency），再提供业务目标、事实、授权、候选 subject、dependency、acceptance 和禁改范围，由 Dispatcher 完成候选选择、brief、资源隔离、dispatch/receipt、worker return、delta review 与 idle。工作无需预登记；资源与授权由主控按当前事实判断。主控直接实现时遵守相同 write ownership、自证和独立 delta review 要求。Progress/checkpoint 不授权 dispatch。
4. **消费并记录。** 核对可归因 diff、evidence、residue、cleanup 和 review 状态；局部 `DONE`、`PASSED` 或 checkpoint PASS 只释放对应候选。随后用 package CLI 写 State、Evidence、Execution Record、Checkpoint 与 Trail；finding 的等级、disposition、影响范围和解决期限由本 Skill 判断。
5. **判断继续或收口。** Dispatcher idle 后仍按 canonical State、Evidence、required review、manual acceptance、findings closure 与 Gate 判断继续、blocked 或 closure。每轮记录当前交付重点、可推进候选、局部 blocker 与恢复入口；局部等待不自动关闭 package。

完成标准：业务范围与候选没有被单一恢复 next 缩窄；每个状态变化有直接 evidence；Dispatcher 的局部结果没有被误报为 Ticket/package 完成；Gate 只由 current Attempt 的 canonical facts 决定。

## Owner 边界

本 Skill 拥有 Ticket readiness、语义裁决、State、Evidence、Execution Record、Checkpoint 与 Gate；`$dispatcher` 是通用执行协作入口，拥有候选选择、委派合同、资源隔离、receipt、return、delta review 和 idle。provider、executor、model 或 agent profile 由 Owner 或宿主选择。

需要定位业务→执行协作→状态写入时读取 [Control Flow](references/control-flow.md)；恢复、返工、evidence 或 Gate mutation 时读取 [Runtime Protocol](references/runtime-protocol.md)。证据矛盾、部分写入、跨 stage 对账或异常排查时，主 session 直接核对 current state 与相关 artifact；复杂时可用 Dispatcher 委派只读调查。旧 Task Handoff 只作兼容恢复材料。

外部副作用（push、merge、发布、生产/shared mutation、数据迁移、删除）需要独立授权；高风险动作先有 rollback 与可观察结果。

## Restore

首次确认 package anchor 后，宿主（Codex/ZCode）从当前已加载 Skill 解析 plugin root，并调用 `python <plugin-root>/hooks/impl_package_hooks.py activate --package <package>` 绑定当前 session；Codex 经 session 环境变量绑定，ZCode 拿不到 session id 时自动落为仓库级 default 绑定；其他宿主跳过。匹配 Capsule 只提供恢复事实，仍复核 package、HEAD 与 initial approval，不把 Capsule 当 acceptance、Gate evidence 或 dispatch credential。

已知 CLI 成功更新后按 delta 更新当前事实；Capsule 缺失或失配、Hook 未信任/禁用、读取 warning、未知外部状态变化或状态更新失败时，按 [Runtime Protocol](references/runtime-protocol.md) 执行完整恢复。真正 dispatch 前运行 `situation.py render` 刷新当前投影（`trail append` 会自行检查全局 blocking）；偏离建议或表外行动使用 `escape` 记录理由。

显式离开 package 工作时，同一宿主调用同一脚本的 `deactivate`。Restore 只恢复范围与事实，不推进 Gate。

## State、ER 与 Trail

- Ticket 状态、Evidence、Checkpoint 与 Trail 都通过 `impl_package_state.py` 语义 CLI 写入（唯一 writer 与 Task/Ticket 关系见 Composition Contract）；被拒就按错误信息处理，stale 先重读。worker 只返回结构化事实。
- （3.5）登记 `supporting` 或 `ticket satisfy` 前，逐 stable claim 核对 artifact 是否覆盖完整 acceptance atom；可独立失败或需要不同 oracle 的子句交回 `impl-planning` 修订，已 `SATISFIED` 的 Ticket 先 `needs-revalidation`。
- 显式 handoff 先写 checkpoint 再轮换 trail；trail 写错时追加更正。

## Journey 验收（3.6 package）

3.5 package 沿用上文的 claim 流程。3.6 的格式与命令见 current-state，这里只写怎么做：

- 每次合入后，从 Journey 第 1 步起按 Spec 的操作入口走到当前能到的最远一步，在观察表面取证，登记 `journey-step` evidence（同一 run、同一 environment，artifact 在 package 内）。reach 让 Owner 看到产品结果逐步前移；Gate 要的是最终版本上的一次走完。
- 页面承诺的步骤用浏览器取证（可用 Playwright），API 重放只证明它实际覆盖的部分。Spec 该步“承接”不是 `—` 时，登记上一步的 `outputRef`（业务对象 ID）并把它作为本步 `inputRef`，两者不一致 `evidence add` 会拒绝；失败后另起 run 从第 1 步重走，局部测试、mock 和套件结果用来定位原因，不拼进走通记录。
- 套件按 Required Suites 的入口与环境运行，结果以 `suite:<id>` 登记；revision 已合入、implementation/acceptance 入边已释放、负责的套件通过且 required review 完成后 `ticket satisfy`。
- 后续提交让旧记录待复验时重跑受影响的 Journey；只动 package 内文件的提交不使记录失效。
- 实现中确认的合同澄清若改变用户可见结果，先 `package amendment add` 登记并告知 Owner，再继续不依赖它的工作；写进 ER 而不登记，Gate 就看不到这条修订。Amendment 待确认或漏登只阻止最终 `gate pass`，`gate blocked` 记录缺口与 next action，不停工。
- Manual 取证的 Journey 记录用 `assets/templates/manual-acceptance-readiness.md`，结果同样登记为 package 内 evidence。

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

Plan/policy 或 Ticket Coverage 的 Required review 明确要求时同样产生 formal review requirement。required review 完成前保持 `PENDING_REVIEW`；具体派发和 reviewer lifecycle 归 Dispatcher，formal topology 与 finding closure 归 do-review。

消费 return 时按原因分流：已知未实现范围继续实施；验收证据缺口保持 `acceptance pending`，不阻塞无关实现；真正实现缺陷按影响安排 `fix`。`INCOMPLETE` 只表达局部未完成，formal review requirement 仍按实际 material risk 判断，不因单一 return 自动改成完整 topology。

已确认 finding 可立即修、随相关下一步修或隔离并行修，由 Dispatcher 根据影响、资源和整合成本安排。延后不能放行依赖该缺陷的实现或验收。修复方向已失去可信边界、同一机制再次出现或影响跨多个 writer/入口/shared authority 时，先按 `/diagnosing-bugs` 定位；finding closure 仍归 do-review。

terminal pass 要求 `review.terminal_summary` 支撑的 terminal-final coverage 明确完整（unknown 时拒绝），且阻断 findings 已闭合；启动条件与结果复用遵循 do-review。terminal-final 返回 FAIL/INCOMPLETE 后的下一步是 `fix` 加 `finding-closure`（一名 reviewer 只核对点名 findings），不是再起一轮 terminal-final；accepted findings 全部闭合、没有在途 fix、HEAD 不再变化时才在最终 HEAD 再起一次 terminal-final，C/Safety 按 admission 复用旧 PASS。Planned Verification 有 manual owner 时，使用 `assets/templates/manual-acceptance-readiness.md` 记录通过标准与 manual owner。

## Verify and Gate

Gate 只判断 current Attempt：`blocked` 保持 active 并记录 gap/next action；`pass` 按格式核对：3.5 要求 required Ticket、verification、review、manual acceptance 和 findings closure 均满足；3.6 按 Journey 与 Required Suites 两层核对，并检查 Ticket/依赖、terminal-final review、Amendment、发布顺序和既有终态条件，必需事实缺失或 unknown 时拒绝；`fail|defer` 如实终结，后续实现进入 patch Attempt。

Completion claim 不能宽于 evidence；准备写 terminal pass 或声称 complete/closed/fixed/merge-ready/release-ready 时，逐条核对 claim 与 evidence：

- 只实现 Spec 部分 AC 时，claim 只覆盖该子切片，除非 Decision/Spec/Plan 已收窄或拆分 Attempt。
- 已合入但无 terminal Gate 的真实状态是 `Integrated, gate open`；默认 `gate-before-merge` 下，current Attempt 的 finalized `pass` 是 merge-ready 前提，pre-gate integration 若无 integration 前记录的 Owner 授权，报告为 process violation。
- evidence 缺失或 stale 时报告 `implemented, not verified` 或具体 pending gate，实现本身不因此被否定。
- 相邻 evidence 不能替代：lint≠build，unit≠integration，mock 不是真实 browser/provider/E2E，套件通过不是 Journey 走通。
- terminal metadata commit、merge 或 environment 变化后，声称前重审 delta。
- 行为代码、合同或影响 behavior 的配置变化使旧 Gate 失效，进入 patch Attempt 重验受影响范围；仅 runtime metadata 变化时复用 provenance 完整的行为 evidence。
- 复用 subagent、Execution Record 或 CI evidence 前对照实际 diff，不只信 success label。

terminal Gate 完成 Stage 7：记录 Durable Delta 与 truth pointer，或写明无增量理由；随后冻结 state、checkpoint 与 Execution Record。transport disconnect 后从幂等事实恢复。

先由本 Skill 根据 canonical facts 判断 Ticket 总数、剩余数、blocker、是否 closed 和需要 Owner 的决定；3.6 的 Gate 第一屏由 runtime 生成 Owner Summary（Journey 走通进度、套件、待确认 Amendment、发布顺序、最终版本），汇报先说产品结果；若 catalog 中存在 `talk-to-boss`，再由它组织叙述。
