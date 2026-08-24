---
name: execution-boundaries
description: 覆盖执行前授权确认（preflight）、执行期异常 slow path（standing bookkeeper）与完成前 claim-evidence 审计（verification before completion）三个边界；三者合并为一个宿主无关入口。
---

# 执行边界与收口

本入口覆盖三个独立边界，各自独立生效，互不串读：执行前确认授权，异常时恢复与对账，完成前审计 claim 是否有足够 evidence。日常状态变更走现有语义 CLI；恢复先消费宿主提供的处境注入，或按需读取 `../../scripts/situation.py render` 的当前 digest、动作和 protocol，再展开本次动作所需材料。

## 执行前（preflight）

执行前确认初始 Decision/Spec/Plan bundle 的最终批准，以及会改变权限或安全边界的事实；同一 package 的后续 plan、state、progress、Execution Record、evidence、review 和 Gate 更新沿用该批准。push、merge、发布、生产/shared mutation、数据迁移、删除等外部副作用仍需独立授权。

### 渐进读取（步骤 1–3）

1. **Wave 1 — anchor**：确认 worktree、branch、HEAD、package、current Attempt 和 `progress.md`，先判断是否仍是同一任务与授权范围。
   - 常见误判：跳过锚点就开始读材料，会把 package 或 authority 已漂移的工作区误当成同一任务。
2. **Wave 2 — control map**：读取 current plan、Composition、授权/write-set、Ticket/DAG 状态、blocker、Gate 和外部 mutation 边界。
   - 常见误判：没有先建立 control map，下一动作可能越过 write-set，或漏掉已经存在的 blocker/Gate 边界。
3. **Wave 3 — active unit**：只展开下一动作需要的 Ticket、Task、Handoff、Execution Record checkpoint、evidence 与目标代码。
   - 常见误判：把全量材料读取当成恢复证明，会增加选择性漏读；只读 active unit 才能让当前动作的证据边界保持可辨。

Wave 1 已暴露 package/authority drift 时停止，不通过全量读取制造“看起来已恢复”的假象；恢复只读 `progress.md` 与当前 Ticket，不读 `state.json` 全文或 `situation.py --json` 全量。状态、处境和校验的机械读取分别由 `../../scripts/impl_package_state.py` 与 `../../scripts/situation.py` 承接，不在本 skill 复制 schema。

### Ticket 首次激活（步骤 4–7）

当 `/impl-package:dev-with-track` 首次派发一个新 Ticket，且 Planned Verification 声明了 `Evidence Lane Contract` 时，主 session 自己核四项并只输出 `READY | BLOCKED`：

1. target 唯一（实际 URL/库身份）；
   - 常见误判：只确认名称、不确认实际身份，会把别的环境的结果误记到当前 Ticket。
2. 端口 owner；
   - 常见误判：没有唯一 owner，多个 lane 可能抢占端口，失败后也没人负责释放。
3. 应用库与 integration 库不串；
   - 常见误判：把 integration 库当应用库检查，局部路径可能通过，但 lane 的真实边界已经被破坏。
4. cleanup owner。
   - 常见误判：没有 cleanup owner，测试留下的进程或资源会污染后续验证，失败原因也无法归属。

子代理只回收路径、符号和缺口，不得输出 READY/BLOCKED 或判 lane 生死；不要派环境探路 agent 当闸门。admission 失败时主 session 做有界 investigate，在现有授权内安全修复后重查；只有缺授权、下一步不安全/破坏性或安全路径耗尽才 `BLOCKED`。每个 Ticket 首次激活只执行一次，不放进每轮控制循环，也不产生 receipt、profile artifact、持久 readiness 状态或新的 Ticket/Attempt 状态；昂贵验证真正运行前再核 health/session/S3，结果不回溯否定已经开始的纯代码 dispatch。

### 必查与授权

- 必查当前仓库/worktree、branch、HEAD Git commit；package 与 current plan 的仓库相对路径；初始 bundle 的 owner final approval、scope/write-set、明确禁区与 HITL；dirty paths 是否与 write-set 冲突；push/merge/发布、生产/shared mutation、数据迁移、删除等是否另需授权；`.impl-package/state.json` 是否通过 validate、`progress.md` 是否可重建、是否有 blocker/next action；高风险动作是否有 rollback、可观察结果和必要 HITL。
- READY/BLOCKED 的四项 lane 核查只能由主 session 作出；授权列出的下一动作及同 package 的正常记录收口可继续，外部 mutation 必须另行授权。dirty paths 与 write-set 冲突，或高风险动作缺 rollback、可观察结果、必要 HITL 时 `BLOCKED`。

### 输出

```text
Preflight: READY | BLOCKED
worktree: <absolute local path，仅会话输出，不持久化>
branch: <name>
HEAD: <git commit>
package: <repo-relative path>
authorized write-set: <repo-relative paths>
dirty conflicts: <none | paths>
external mutation: <none | authorization>
next action: <one action>
blocker/owner decision: <none | item>
```

输出 `Preflight: READY | BLOCKED + authorized write-set + 单一 next action`，不产生 receipt、profile artifact 或持久 readiness 状态。授权细节按需读 `references/authorization-contract.md`；需要调度时使用 `/impl-package:subagent-driven-development`，本边界只提供任务特定的 scope、write-set、authorization、verification 和输出合同。

## 异常（standing bookkeeper slow path）

这是 package thread 的异常 slow path 入口，不是日常记账角色；日常结构化写入由主 thread 直接调用现有语义 CLI，Execution Record judgment 和 findings 分流也由主 thread 自己形成。bookkeeper 只在异常场景下恢复上下文、做对账并返回结构化修复建议或证据，不改变语义 owner、状态机或验收门。

### 触发判定

仅当证据互相矛盾需核对 claim/revision/environment/timing/artifact pair、跨 session 或 transport 中断后恢复、部分写入已落盘需补齐、跨 stage 的 artifact/state/Progress/checkpoint/Gate 需要对账，或其他异常使主 thread 无法仅凭现有 state/CLI 安全收口时才进入 slow path。evidence、checkpoint、fact、trail、state transition、Gate 等日常结构化写入，以及 Execution Record judgment 和 findings 分流，不触发 bookkeeper。

### 角色边界

- 一个 package 不要求常驻或预先初始化 bookkeeper；需要时按当前 package/Attempt 按需启动或恢复。
- 主 thread 保留 requirement、architecture、implementation direction、acceptance、finding disposition、Gate verdict、最终复核权，以及 `state.json` 的唯一写入权。
- bookkeeper 只负责异常上下文重建、证据/状态对账、缺口定位和结构化修复建议；不独占 package 物理写入，不直接修改 `state.json`，不替主 thread 形成 judgment 或 disposition。
- bookkeeper 不修改业务实现代码，不服务其他 package，不接管 commit、merge、push、release、数据迁移、删除或外部 mutation。

### 主 thread 流程

1. 无异常时主 thread 读取当前 state 并直接调用适用 CLI，不启动或等待 bookkeeper。
   - 常见误判：把 bookkeeper 变成日常等待环节，会制造第二个 state writer 和不必要的协调延迟。
2. 发现异常时按需启动/恢复 slow path，提供 package、Attempt、相关 artifact/state、已知事实、矛盾或缺口、期望收口条件；宿主无法维持可继续对话的 subagent 时报告 blocker，不扩展成新的协调系统。
   - 常见误判：只给“有问题”而不给 canonical 上下文，slow path 只能猜缺口；把宿主能力缺失扩展成新协调系统也会越过本入口边界。
3. slow path 返回结构化对账结果、修复建议和 focused validation；主 thread 复核后直接执行接受的 CLI/文档写入。最小输入可沿用：
   - 常见误判：把 bookkeeper 的建议直接当作语义决定，会让异常辅助角色取得 requirement、judgment 或物理写入 ownership。

   ```text
   更新：
   结论/事实：<要记录什么>
   依据：<必要时提供>
   依赖：是 | 否
   ```

4. `依赖：是` 只表示下一动作确实需要 slow-path 结果，主 thread 才等待回执；`依赖：否` 时可以继续推进，稍后消费回执，日常 CLI 写入不因依赖语义停顿。
   - 常见误判：把所有回执都当成依赖，会让正常 CLI 停摆；把真正的依赖当成非依赖，则会在缺少对账结果时继续收口。
5. 主 thread 检查回执中的理解、对账结果、修复建议和 focused validation；不正确时发送 correction event，仍由 slow path 修正，最终物理写入由主 thread 执行。
   - 常见误判：主 thread 直接修正错误回执而跳过 correction event，会丢掉异常处理的可恢复链路。
6. 每次 slow-path 回执只追加一行到 `<package>/execution/<attempt>/bookkeeper-receipts.jsonl`；正常 CLI 写入不追加该文件。回执格式、恢复读取顺序与失败边界按需读 `references/role.md`，不依赖聊天记录。
   - 常见误判：把正常 CLI trail 和异常回执混在一起，会无法区分日常状态变更与需要恢复的 slow-path 事实。

### 物理写入与完成条件

- Decision、Spec、`contract-design.md`、Plan、Ticket、Progress、Execution Record、active checkpoint、execution findings 和 Gate 的日常物理写入由对应 owning stage 的主 thread 执行；slow path 只提供异常对账和修复输入，不成为第二个 state writer。
- runtime state 优先通过现有 `../../scripts/impl_package_state.py` 语义命令更新；bookkeeper 不复制 state schema、另建 ledger 或引入并发协调设施。stable-doc backfill 由 `/impl-package:backfill-stable-docs` owning workflow 管理，不纳入日常 package 簿记。
- 只有 bookkeeper 已完成异常对账、返回结构化修复输入、运行适用 focused validation，且主 thread 已复核并执行接受的写入，slow-path 更新才可采信；回执失败或信息不足时保持未完成并报告具体 blocker。

## 收口（verification before completion）

Completion claim 不能宽于 evidence；这是 claim-to-evidence 契约，不要求在当前消息机械重跑所有可能检查。涉及 material seam、昂贵 E2E 或 failure learning 时按需读 `../../references/progressive-system-evidence.md`；本边界只审计当前 claim，不重新选择 Planned Verification。

### Impl-Package orchestration

- 本边界是 Impl-Package 的 completion-claim evidence gate，不是 DAG task，也不按 Ticket 或 implementation unit 重复运行。局部进度、单个文件已修改、某个定向检查通过或“完成了第 N 步”属于 scoped status，不是 terminal completion claim；只有准备写 terminal pass，或声称整个约定范围 complete/closed/fixed/merge-ready/release-ready 时，才进入完整 orchestration。
- terminal Gate 前，在适用的 implementation review、package 级 execution findings closure 和 Stage 7 artifact 准备完成后执行本审计；terminal metadata commit、目标分支合入或相关 environment 变化后，在声称 complete/closed/merge-ready/release-ready 前再次审计，只验证 delta 与 claim-specific gate。
- terminal Gate 后只有 runtime metadata 变化时，可以复用 provenance 完整的行为 evidence 并验证 metadata delta；行为代码、合同或影响 behavior 的配置变化会使旧 Gate 失效，必须进入 patch Attempt 并重新验证受影响范围。
- 已合入目标分支但无 terminal gate 的真实状态是 `Integrated, gate open`；只能报告 integration 阶段，不能把 merge 当作 closed evidence。默认 `gate-before-merge` 下，current Attempt 的 finalized `pass` 是 merge-ready 前提；`blocked`、`fail`、`defer` 或没有 `gate.md` 都不能支持 merge-ready claim。
- 若已发生 pre-gate integration，必须从 Plan 核对 integration 前已记录的 owner authorization；没有该证据时报告 process violation，不得事后倒灌授权或 terminal pass。
- 若当前 diff 只实现 Spec 的一部分 AC，claim 只能覆盖明确边界的子切片；除非 Decision/Spec/Plan 已同步收窄或拆分 Attempt，不得把局部 merge、测试或 schema rollout 说成完整 package/issue closure。
- proof 缺失或 stale 时阻止的是 completion claim，不一定否定 implementation；报告 `implemented, not verified` 或具体 pending gate，不写入或重复 pass claim。本边界不替代 `/impl-package:review-code`、`/impl-package:review-code-by-standards`、`/impl-package:review-code-by-spec`、`/impl-package:safety-review`、planned test、smoke 或项目特定 acceptance。

### Claim 范围

报告成功前先说明 claim 是：某个具体 behavior 可用、某项定向检查 passing、某个 implementation phase complete，还是某个 merge/release/production gate 已满足。定向 claim 可使用定向 evidence；宽泛 readiness claim 必须覆盖所有相关 gate。

### Evidence contract

可采信 evidence 必须直接执行或检查被 claim 的 behavior，来自同一 worktree、revision 与相关 environment，晚于最后一次可能影响结果的变化，包含 command/procedure、exit status、failure count 和决定性 artifact，并覆盖该 claim 要求的 gate。不能用相邻 evidence 替代：lint 不证 build，unit 不证 integration，passing regression test 不单独证明原始 symptom 已解决，mock 不冒充真实 browser/provider/native-tool/E2E。

同名 verification 的 command、pass/skip/failure count 与前次不一致时说明测试选择集、测试增量或环境差异；无法由当前 revision 的直接 artifact 解释的计数漂移使 claim 为 `UNCERTAIN`，不靠摘要猜测补齐，也不建立无关 evidence registry。除 revision/environment 外，检查与 claim 相关的 feature flag、schema、部署配置、共享数据前置和认证策略；只让相关 evidence 失效，不机械重跑无关检查。

### 复用、独立验证与真实状态

- provenance 清楚且相关 revision/environment 未变时可复用 subagent、Execution Record、CI run 或较早 turn 的完整 evidence，但必须对照实际 diff，不能只信 success label。
- evidence 不完整、stale、冲突、跨 revision，之后有影响结果的变化，claim 属于高风险 merge/release/migration/security/data-integrity/external-side-effect gate，或项目 policy 要求 fresh run 时，运行独立或更宽的 verification；关键因果输入变化时只补跑依赖它的 check。
- 不为制造 RED evidence 临时回退 fix；使用已有 failing run、受控 worktree、fixture mutation，或明确记录没有独立证明 RED。与当前 claim 相关的确定性内部 failure 应有稳定回归证据，偶发环境问题只能作为 readiness、runbook、observability 或真实验证风险，不能伪造绿色测试。
- evidence 覆盖 claim 才陈述该 claim 并引用 evidence；验证运行但失败时报告 failure 与剩余工作；部分 gate 通过、其余 pending 时明确阶段和 outstanding gate，不称整个任务 closed。不得把 confidence、agent report 或局部相邻检查转化为 completion claim。
