# Dispatch situation digest audit

阶段 1 设计定稿：让“派活时没查处境表”成为轨迹上的可发现信号。

## 1. `situation_digest` 设计

### 1.1 事件范围

只给 `kind=dispatch` 增加 `situation_digest`。`decision` 是选择/路由事件，
`result` 与 `worker-return` 是结果事件；它们不是一次新的 worker 派发，增加同一个快照值
只会复制信息，不能提高本轮要发现的信号密度。

dispatch 的动作仍使用已有的 `chosen` 字段；`dispatch.id` 是派发实例标识，不把它误当成
situation action id。`chosen` 若用于机械动作对账，必须是该处境的 action `id`；明确逃逸时
使用 `escape`/`escape: <reason>` 并留下理由。

### 1.2 可选性

字段可选。缺失不是 renderer 或 trail reader 的硬失败，而是审计输出中的 `no-digest`：
它正是“这次派活没有可见处境快照”的机械信号。必填会让历史包、手工补写的轨迹和本轮
既有 fixture 因 schema 违规而失败，违反“只增加可发现性、不增加阻断”的范围。

### 1.3 值的形态

值直接使用 renderer 返回的 12 位 digest 字符串（当前为截短 SHA-256 的 12 个十六进制字符）。
不嵌入 `layer`、`selected` 或 actions：这些是 digest 的输入/回放结果，重复保存会制造第二
份可能漂移的事实；需要解释时由 `situation.py render --at <head> --json` 回放。

规范形态示例：

```json
{"kind":"dispatch","subject":"ticket:TKT-01","id":"dispatch-01","outcome":"RUNNING","worker":"worker-01","returned":false,"head":"5f299f3","chosen":"dispatch-investigate","situation_digest":"a1b2c3d4e5f6"}
```

## 2. 审计对账口径

脚本读取一个 package 当前 attempt 的 `execution/<attempt>/trail.jsonl`，只读，不修改
package、trail 或 situation table。

### 2.1 `no-digest`

分母是轨迹中所有 `kind=dispatch` 行；缺失、`null` 或空字符串都计为 no-digest，输出
`count/total` 和百分比。零 dispatch 输出 `0/0 (n/a)`。所以老轨迹全部没有该字段时，
`no-digest=100%` 是正确结果，不是脚本错误。

### 2.2 `stale-digest`

只在有非空 digest 的 dispatch 子序列中统计连续重复。连续 **3** 次相同 digest 形成
`stale-digest` 记录；不同 digest 或没有 digest 会打断连续段，非 dispatch 行不改变 dispatch
子序列。

阈值理由：同一快照下允许最多两次派发，覆盖并列 action 的小批量派发或一次有理由的重试；
第三次连续复用同一快照才是控制循环没有重新渲染的最小可见信号。阈值只产生审计提醒，
不改变 renderer、state 或任何 gate。

### 2.3 `deviation`

只有同时具备 `situation_digest`、`head` 和可识别 `chosen` action id 时才尝试判定：

1. 运行 `situation.py render --package <package> --at <head> --json`，不使用 `--since`。
2. 要求回放输出的 `head/at` 与该 commit 一致，并检查回放 digest 是否等于 dispatch 行的
   `situation_digest`。
3. 在回放的 `selected`、`parallel_matches`、`other_matches`、`suppressed_matches` 中，
   找同一 `subject` 的 candidates，收集其结构化 `action_ids`。
4. `chosen` 不在这些 action ids 中，且没有同 subject、同派发 id（通过 `of`、
   `dispatch_id`/`dispatchId`、`decision_id`/`decisionId` 关联）的带理由 escape/decision，
   才记为 deviation。

缺少 `head`、缺少 action id、回放失败、digest 与回放不一致、或动作候选无法唯一定位，
只记为 deviation 的 `uncheckable`，不把证据不足升级为违规。显式 `escape` 需有本行
`reason`、`escape: <reason>` 或关联 decision 的非空理由。

### 2.4 轨迹 schema 卫生

同一审计顺手检查可机械识别的 fact 形状：`kind=fact` 缺 `key`，以及 `subject` 直接填成
已知 when-key 名字而非 subject scope（例如 `trail.reviewer_unavailable`）。坏 JSON、非
object、fact 缺少 `ts`/`value` 和未知 fact key 也作为 schema violation 报告；这些报告不
调用 `situation.py`，不改变其现有兼容读取行为。

## 3. 已知回放边界

`--at` 只能看到目标 Git commit 中的 package 文件；commit 外的 untracked/staged trail
不会出现在回放快照里。当前基础 `situations.yaml` 与 renderer 代码也来自执行审计脚本时的
worktree，而不是自动回放历史版本。遇到这些边界，脚本报告 `uncheckable`，不伪造动作比对。

## 4. 本轮范围

- 不修改 `situations.yaml`、`situation.py`、`impl_package_state.py` 或任何 leaf agent。
- 不增加 gate、不会让 `render` 因缺 digest 失败。
- 阶段 2 只同步 `situation-inputs.md`、本目录 `trail-schema.md` 和 `dev-with-track/SKILL.md`
  的一句话；阶段 3 新增只读 `dispatch_audit.py` 及 focused tests，并用指定真实 package
  实跑。该报告在阶段 3 回填最终命令输出和实际 schema violation 数量。

## 5. 阶段 3 实跑回填

focused 审计测试：`7 passed`。既有 renderer 测试：`53 passed`。两组 pytest 都只有环境已有的
`.pytest_cache` 无访问权限 warning，不影响退出码。

`situation.py check` 原文：

```text
check: PASS
- stage: dev-with-track
- situations: 56
- implemented when keys: 66
- priority groups: 6
```

指定真实 package 的审计原文：

```text
dispatch-audit
package: D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning\docs\domains\finance-assistant\implementations\2026-08-15-datev-tax-advisor-import-workbench
attempt: initial
trail: D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning\docs\domains\finance-assistant\implementations\2026-08-15-datev-tax-advisor-import-workbench\execution\initial\trail.jsonl
dispatches: 16
no-digest: 16/16 (100.0%)
stale-digest: 0 (threshold: 3 consecutive dispatches)
deviation: 0 (replayed: 0, uncheckable: 0)
schema-violations: 0
```

当前指定文件实际读取到 51 条非空 JSON 行、16 条 dispatch、2 条 decision、5 条 fact。
用户描述的 3 条“subject 是 when-key 且缺 key”的 fact 在当前文件中没有复现：这 5 条 fact
都有顶层 `key`，且 `subject` 分别是 `attempt` 或 `finding:*`；审计输出因此诚实为
`schema-violations: 0`，没有修改外部轨迹。若外部 package 在本报告之后被恢复为用户描述的
版本，脚本会把每个同时命中该两种形状的 fact 行聚合为一条 schema violation，并列出
`missing-key, subject-is-fact-key`。

最终边界：fresh closure reviewer 因当前 subagent thread limit 无法再次启动；已有独立 review
曾报告的 3 个实现 finding 已修正，并由 focused tests、renderer tests、check 和真实审计命令
复核。未做 commit；未修改 `situations.yaml`、`situation.py`、`impl_package_state.py`、
leaf agents 或 `kaispan-dev` 仓库。
