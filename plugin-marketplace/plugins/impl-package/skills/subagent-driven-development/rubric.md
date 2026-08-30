---
target: plugin-marketplace/plugins/impl-package/skills/subagent-driven-development
updated: 2026-08-25
---

## 原则

- [已确认] SDD 是下游 bounded worker 的完整方法定义；与上游 `$dispatcher` 平级，分别直接指导下游工作方法与上游调度。（证据: R12）
- [已确认] bounded Topic 可使用当前或新隔离 worktree；caller 根据文件 ownership 与资源交叉决定，DB、端口和其他运行资源分别验证隔离。（证据: R13）
- [已确认] 方法主轴是 `Topic → dependency class → execution lane → lifecycle`；worker 复用来自同一 Topic/lane 连续性，新 Topic fresh，Topic closure 后退役。（证据: R12）
- [已确认] Acceptance Gate/Checkpoint 是结论点，不自动阻止隔离、可回收且不绑定未稳定语义的一步前瞻准备。（证据: R12）
- [已确认] worker mode 统一为 `investigate | implement | fix | verify`；独立 review topology 与 finding closure 由 `do-review` 拥有。（证据: R12）
- [已确认] work lane 可复用同 Topic implementer/fixer；review lane 必须独立于 work lane但可复用同 Topic reviewer；test lane 只在有界 campaign 内复用。（证据: R12）
- [已确认] 真实消费者使用 `DONE|BLOCKED|INCOMPLETE`、`EVIDENCE_SUFFICIENT|EVIDENCE_GAP` 和 `PENDING_REVIEW|PASSED`，主 session 将其作为 Topic-local facts 消费。（证据: R12）
- [已确认] foundation、acceptance、resource、authorization dependency 分开判断；共享可变资源能隔离才并行，否则串行并指定 cleanup owner。（证据: R12）
- [已确认] `investigate`、`implement`、`fix` 的派发 prompt 由 caller 按单一目标和强相关上下文裁剪；executor、model、provider 选择不属于本 Skill。（证据: R14）

## 决策记录

### R12 · 2026-08-25（method-first 与 Topic lane 生命周期）

- Owner 以 method-first redesign 取代旧 worker-centric strategy、resolver、provider fallback、固定 envelope、Progress File 和强制换人规则。
- Dispatcher 面向上游主控调度；SDD 面向下游 bounded worker 方法，两者共享 dependency/lifecycle 原则并保持平级。
- finding 默认回到同 Topic work lane；reviewer 与 work lane 独立，同 Topic recheck 可以复用 reviewer；test wrapper 在 campaign 结束后退役。
- 历史 R4–R11 由 Git 保留，不再作为 active rubric。

### R13 · 2026-08-25（worktree isolation）

- caller 可为 bounded Topic 选择当前或新隔离 worktree；可隔离的文件 ownership 交叉继续派发，运行资源逐项判断。

### R14 · 2026-08-29（worker brief、dependency 去重与 material-risk 校准）

- 新增 `references/worker-briefs.md`，填补 mode 到 prompt 内容的空白；只规定 caller 提供单一目标和强相关上下文，不包含 executor 选择内容。
- `references/parallel-work-admission.md` 去重 foundation、acceptance、authorization 的重复定义，回指 Step 2 表作为唯一权威，同时保留 resource 的增量细节。
- `SKILL.md` 增加 worker-briefs pointer，并补充直接对应 eval id=3 的 worked example。
- `references/review-gate.md` 为七类 material-risk 补充可对照的判断启发式。
