# [Implementation Name] Gate

状态：[开放 / 等待人工确认 / 已通过 / 未通过]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
Plan：[plan.md](plan.md)
DAG：[dag.md](dag.md)
对应 findings：[findings.md](findings.md)
Evidence：[path-or-link]

本文记录当前 implementation 是否可以关闭、阻塞、延期，或转入人工判断。不要用单个 task 通过代替 implementation gate 通过。

## Scope

- Implementation phase：[planning / running / integrated / verified local / verified external / closing]
- Spec coverage：[complete / partial / deferred / N/A]
- Target surfaces：
  - [surface / route / component]
  - [surface / route / component]
- Boundary：[fixture-only / real route / shared primitive / mixed]

## Data Safety

- [ ] 不使用生产数据。
- [ ] fixture 数据可识别为 fake/test data。
- [ ] 不读取真实 backend service，或读取边界已记录。
- [ ] 不触发外部 mutation：billing、payment、邮件、ERP、IM、外部存储等。
- [ ] dev-only route 有 production guard。

Notes：

- [记录例外或确认方式。]

## UI Evidence

适用于有 UI 面的实现；无 UI 面时标记 N/A。

- [ ] Desktop evidence 已保存。
- [ ] Constrained viewport evidence 已保存。
- [ ] Console / hydration 状态已记录。
- [ ] 可见 overflow / clipping / density 问题已记录到 findings。

Evidence files：

- `[file-or-link]`
- `[file-or-link]`

## Real Route Safety

仅当本次实现改动或吸收真实 route / 生产入口时适用；否则标记 N/A。

- [ ] auth / permission boundary 保持。
- [ ] i18n / dictionary wiring 保持。
- [ ] data loading / service contract 保持。
- [ ] Server Action / Route Handler 边界保持。
- [ ] mutation availability 未被布局重构扩大。

Notes：

- [记录 N/A 或风险。]

## Durable Knowledge Registration

登记不要求本次 gate 当场完成长期文档回写；后续由 compaction/backfill 压实。
若无 durable delta，填写 `none` 并给出原因。
Durable deltas 表与 No durable delta 字段互斥：保留并填写其中一种，删除另一种。
约束型 delta（禁止事项、信任边界、精度、provider 义务、负依赖）也是 durable delta。

- [ ] 若完全替换实现但用户价值不变，该陈述仍必须成立，则登记为意图候选。
- [ ] 若可由测试、接口、状态查询或故障演练直接验证，则登记为行为合同候选。
- [ ] 具体分流、约束类别与压实交给 `backfill-stable-docs`。
- [ ] 同时包含 why 与 how 的陈述已拆分，没有在 PRD 与 spec 原样复制。
- [ ] 每条 delta 已填写 destination、source、statement、受影响模块、authority 与 evidence。
- [ ] `module-prd` 文件不存在时只登记到 `docs/module-knowledge/_pending.md`；未在普通 gate 首建文件。只有 owner 审阅后的 backfill apply 可首次创建，已有文件才由正常维护流程更新。
- [ ] `top-level-prd` 在 journey 重构完成前已持久化到项目 `docs/module-knowledge/_pending.md`，记录 destination=`top-level-prd`、source、statement 与 authority；未继续扩写现有巨型 PRD。

Durable deltas：

| Destination | Source | Statement | Affected modules | Authority | Evidence |
| --- | --- | --- | --- | --- | --- |
| `[module-spec / module-prd / top-level-prd / context-language / hands-on / other]` | `[implementation slug / source path]` | [一句话 delta] | `[module-slug / N/A]` | `[approved design / owner decision / confirmed gate / other]` | `[path-or-link]` |

No durable delta：`none`

Reason：

- [必填：为什么本次只有 task-local / historical-only 结论。]

## Shared UI

适用于改动共享 UI 组件的实现；否则标记 N/A。

- [ ] 新增或变更 shared primitive 已登记到 component inventory。
- [ ] preview-only 组件没有伪装成通用组件。
- [ ] 可复用布局语法已沉到真实组件或 shared primitive。

## Verification

- [ ] Typecheck：[command + result]
- [ ] Focused tests：[command + result]
- [ ] Build：[command + result / N/A]
- [ ] i18n audit：[command + result / N/A]
- [ ] Browser verification：[route + viewport + result]

Skipped checks：

- [check] skipped because [reason]

## Whole-Slice Review

- [ ] Task-level approvals are not the only closure evidence.
- [ ] Whole-slice review status：[APPROVED / NEEDS_CHANGES / N/A]
- [ ] Review findings are resolved, deferred, or promoted to `findings.md`.

Review evidence：

- [reviewer / command / notes]

## Manual Review

- [ ] 业务方 / 用户确认“第一眼看得懂”。
- [ ] 允许进入下一阶段。

Review notes：

- [记录人工判断。]

## Follow-up

- [ ] [finding/checklist/issue/backlog item]
- [ ] [finding/checklist/issue/backlog item]

## Gate Decision

Decision：[pass / fail / blocked / defer]

Reason：

- [一句话说明。]

Next step：

1. [下一步]
2. [下一步]
