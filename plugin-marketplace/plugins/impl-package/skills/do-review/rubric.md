---
target: plugin-marketplace/plugins/impl-package/skills/do-review
updated: 2026-08-19
---

## 原则

- [已确认] `do-review` 是唯一 orchestrator；默认三个并列 leaf track 为 `review-code`、`review-code-by-standards` 与 `review-code-by-spec`，命中高风险边界时条件追加 `safety-review`。
- [已确认] 同一完整 diff 与 fixed comparison point 只由主会话确定一次；三轨同轮独立，第二轮起只接收 canonical ledger。
- [已确认] 涉及计划包时，审查范围覆盖整个计划包的 commits，不只审查最后一个实现 commit。
- [待验证] 审阅编排使用最小必要的自然语言状态来保证轮次、证据和收敛可信，不以刚性 schema 或过度 canonical 字段限制 leaf reviewer 的主动探索。（证据: R2）
- [待验证] reviewer role 用首要审查意图与交接方向引导，不用排他的能力禁令；跨域风险仍可作为 candidate 交给父会话的 canonical ledger 归属与去重。（证据: R3）
- [待验证] 严格可维护性审查使用非穷尽启发式；建议应说明 diff 证据、维护后果和可行方向，但不设固定触发链或替代方案证明门槛。（证据: R3）
- [待验证] leaf reviewer 的 `SKILL.md` 与其参考材料只说明自身审查方法和证据表达；role、track、交接、归属和跨域协作统一由 `do-review` 说明。（证据: R4）
- [已确认] 高风险条件自动追加 Safety；显式 reviewer list 保持精确，但必须记录遗漏的适用 Safety 风险。（证据: R5）
- [已确认] 中间 finding closure 采用保守增量复核；terminal final 必须在最终实现 `HEAD` 运行完整适用 topology。（证据: R5）
- [已确认] ReviewRun 原子创建固定 base/head、拒绝空 three-dot diff，并从 resolved head 解析 UTF-8 Git blob 合同来源；失败不产生 ledger。（证据: R6）
- [已确认] 创建 ReviewRun 前必须先把审查单元本地 commit，使 `HEAD` 成为 comparison head；这是 `do-review` 的前置步骤，不把该规则写进通用 `git-commit` skill。（证据: R8）
- [已确认] 每个 selected track 必须使用 matching leaf subagent；主会话审查或 generic subagent 不是替代。（证据: R8）
- [已确认] reviewer 只通过 `git show <resolved-head>:<path>` 读取合同，ReviewRun 的 object ID 与 SHA-256 是唯一 provenance，不再读取工作树或二次 hash。（证据: R6）
- [已确认] accepted Track C / Spec fidelity finding 在交给 fix 前做一次 finding-scoped 独立 source recheck；按 parent 语义归类触发，不依赖最先报告它的 leaf，也不新增 review phase 或 runtime state。（证据: R7）

## 决策记录（滚动，最近 ≤5 轮）

### R2 · 2026-07-21
- 采纳「完整审阅上下文保留自由文本与证据语义」：用户明确要求字段用于兜底流程，而非限制 agent 主观能动性；真实的新风险经验证后应继续 loop。

### R3 · 2026-07-22
- 采纳「role 以审查偏重和交接引导，不以能力禁令限制 reviewer」— 用户确认：同意。
- 采纳「严格可维护性深挖使用启发式，不固定触发链或证据门槛」— 用户确认：同意。

### R4 · 2026-07-22
- 采纳「leaf skill 不描述其他 skill/track 的互动」— 用户原话：每个 skill 专注自己的事，调度层互动属于 `do-review`。

### R5 · 2026-08-12
- 采纳「高风险条件自动追加 Safety」：默认三轨保持不变；显式 reviewer list 不自动扩展，但记录遗漏的适用 Safety 风险。
- 采纳「中间 closure 保守增量、terminal final 完整复核」：finding closure 只跑来源、受影响与适用 Safety track；最终实现 `HEAD` 重新运行完整适用 topology。

### R6 · 2026-08-12
- 采纳「一个命令创建原子 ReviewRun」：commit 解析、空 diff 拒绝、resolved-head Git blob/UTF-8 校验、object ID/hash 记录先于 ledger 写入。
- 采纳「合同只从固定 revision 读取」：reviewer 使用 `git show <resolved-head>:<path>`，不依赖可变工作树，也不建立第二套 hash/capture 协议。

### R7 · 2026-08-14
- 采纳「accepted Track C 后的一次性源头复审」：用户确认只在 Spec review finding 被 parent 接受并归类后触发；不把普通 finding、candidate 或初始 Spec Gate 扩成额外 review。
- 采纳「少状态」：source recheck 留在当前 ReviewRun 的 finding 记录，不新增 phase、Ticket/Attempt 状态或 closure 替代物。

### R8 · 2026-08-19
- 采纳「commit 是 do-review 前置步骤」：用户确认把 pin `HEAD` 的本地 commit 收进 `do-review` Gate，不写进通用 `git-commit` skill，也不把该 skill 收进 `do-review`。
- 采纳「必须使用 leaf subagent」：每个 selected track 派 matching leaf agent；不可用时停在 ReviewRun 创建前询问，不得自行降级。
