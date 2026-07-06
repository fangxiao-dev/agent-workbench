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
- [ ] 不触发外部 mutation：billing、payment、email、ERP、Lark、Lexware、Redis 等。
- [ ] dev-only route 有 production guard。

Notes：

- [记录例外或确认方式。]

## UI Evidence

- [ ] Desktop evidence 已保存。
- [ ] Constrained viewport evidence 已保存。
- [ ] Console / hydration 状态已记录。
- [ ] 可见 overflow / clipping / density 问题已记录到 findings。

Evidence files：

- `[file-or-link]`
- `[file-or-link]`

## Real Route Safety

适用于 Phase B；Phase A 可标记为 N/A。

- [ ] auth / permission boundary 保持。
- [ ] i18n / dictionary wiring 保持。
- [ ] data loading / service contract 保持。
- [ ] Server Action / Route Handler 边界保持。
- [ ] mutation availability 未被布局重构扩大。

Notes：

- [记录 N/A 或风险。]

## Spec Backfill

- [ ] `spec.md` 中仍有效的长期结论已回写到稳定 PRD / Func Design / ARD，或明确延期。
- [ ] 本任务临时决策没有被误留在长期稳定文档之外却宣称已沉淀。
- [ ] 不需要回写的内容已标记为 task-local / historical-only。

Backfill notes：

- [记录已回写路径、延期原因或 N/A。]

## Shared UI

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
