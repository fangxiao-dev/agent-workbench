---
name: execution-boundaries
description: 覆盖执行前授权确认（preflight）、执行期异常 slow path（standing bookkeeper）与完成前 claim-evidence 审计（verification before completion）三个边界；原 execution-preflight / standing-bookkeeper / verification-before-completion 合并。
---

# 执行边界与收口

三个独立边界，各自独立生效，互不串读。

## 执行前（preflight）

执行前确认初始 Decision/Spec/Plan bundle 的最终批准，以及会改变权限或安全边界的事实；同 package 后续更新沿用该批准。渐进读取顺序由恢复与处境注入承接，不在此重复。

- READY/BLOCKED 判定：target 唯一（实际 URL/库身份）、端口 owner、应用库与 integration 库不串、cleanup owner 四项 lane 核查由主 session 自己核，只输出 READY | BLOCKED；子代理只回收路径/符号/缺口，不得输出判定或判 lane 生死，也不派环境探路 agent 当闸门。admission 失败做有界 investigate，在现有授权内安全修复后重查；只有缺授权、下一步不安全/破坏性或安全路径耗尽才 BLOCKED。

- 授权 write-set 边界：初始 bundle 的 final approval 覆盖同 package 后续 plan/state/progress/ER/evidence/review/Gate 更新；push/merge/发布、生产/shared mutation、数据迁移、删除等外部副作用需独立授权。dirty paths 与 write-set 冲突、高风险动作缺 rollback/可观察结果/必要 HITL 时 BLOCKED。输出 Preflight: READY | BLOCKED + authorized write-set + 单一 next action；不产生 receipt/持久 readiness 状态。授权细节按需读 references/authorization-contract.md。

## 异常（standing bookkeeper slow path）

异常 slow path 入口，不是日常记账角色；日常结构化写入由主 thread 直接调用现有 CLI。

- 触发判定：仅当证据互相矛盾需核对 claim/revision/environment/timing、跨 session 或 transport 中断后恢复、部分写入已落盘需补齐、跨 stage artifact/state/Progress/checkpoint/Gate 对账，或其他异常使主 thread 无法仅凭现有 state/CLI 安全收口时才走 slow path；日常 CLI 写入、ER judgment 与 findings 分流不触发。

- 写入权边界：主 thread 保留 requirement/architecture/acceptance/finding disposition/Gate verdict/最终复核权与 state.json 唯一写入权；bookkeeper 只做异常上下文重建、对账、缺口定位与结构化修复建议，不成为第二个 writer，不直接修改 state.json，不接管 commit/merge/push/release 或外部 mutation。回执由主 thread 复核后执行接受的写入；回执失败或信息不足时保持未完成并报告 blocker。角色细则按需读 references/role.md。

## 收口（verification before completion）

Completion claim 不能宽于 evidence；claim-to-evidence 契约，不机械重跑所有检查。material seam、昂贵 E2E 或 failure learning 时按需读 ../../references/progressive-system-evidence.md；本边界只审计当前 claim，不重新选择 Planned Verification。

- claim-evidence 契约：evidence 必须直接执行/检查被 claim 的行为，来自同一 worktree/revision/environment，晚于最后一次可能影响结果的变化，含 command/procedure/exit status/failure count/决定性 artifact，并覆盖该 claim 要求的 gate；不得用相邻 evidence 替代（lint 不证 build、unit 不证 integration、mock 不冒充真实 E2E）。同名验证的计数漂移无法由当前 revision 的直接 artifact 解释时，claim 为 UNCERTAIN。

- 复用与独立验证：provenance 清楚且相关 revision/environment 未变时可复用完整 evidence，但必须对照实际 diff，不能只信 success label；evidence 不完整/stale/冲突/跨 revision，之后有影响结果的变化，高风险 gate（merge/release/migration/security/data-integrity/external side-effect）或 policy 要求 fresh run 时运行独立验证；关键因果输入变化只补跑依赖它的 check。不得为制造 RED evidence 临时回退 fix。

- 真实状态报告：evidence 覆盖 claim 则陈述 claim 并引用 evidence；实现存在但验证缺失报告 implemented, not verified；验证失败报告 failure 与剩余工作；部分 gate 通过不得称整个任务 closed。默认 gate-before-merge 下 pass 是 merge-ready 前提；已合入目标分支但无 terminal gate 报告 Integrated, gate open；terminal 后仅 runtime metadata 变化可复用行为 evidence 只验 delta，行为/合同/配置变化必须进入 patch attempt 重新验证。不得把 confidence、agent report 或局部相邻检查转化为 completion claim；本边界不替代 review-code / safety-review / planned test。
