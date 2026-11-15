# Patch 与 Follow-Up 规则

Patch 归属于 package 已有 terminal gate 之后的生命周期，并继续复用 owning package-id；terminal 前的工作沿用当前 attempt。initial Decision/Spec/Plan bundle approval 是同一 package 唯一的 owner approval gate。

## 进入 patch 前

1. 读取 gate.md，确认它属于前一 attempt 且为 pass、fail 或 defer。
2. 将 package decision/spec 与当前 module knowledge 和代码对账。
3. 分类 drift 并直接更新 current artifact：
   - implementation-only：沿用当前 Decision/Spec；
   - behavior contract：更新当前 Spec，记录受影响范围并沿用 initial bundle approval；
   - decision direction：更新当前 Decision 与 Spec，记录受影响范围并沿用 initial bundle approval。
4. 后续 update 直接沿用 initial bundle approval。
5. Spec 章节发生变化时，找出引用该章节的全部 Ticket 并标为受影响，按完整集合更新 follow-up 范围。

## Patch plan

- 文件名为 YYYYMMDD-HHMM-<patch-topic>.patch-plan.md，Attempt ID 与文件名前缀一致。
- 不覆盖 plan.md，不向历史 DAG/ticket/task 追加本 attempt 状态。
- 需要恢复时只使用文档化 `state.json.activeCheckpoints`，compact 仅作意外耗尽兜底。
- Planned Verification 引用权威 policy；实际证据写入 `execution/<attempt>/execution-record.md`。

## Patch plan 最小模板

`package init --attempt <id> --plan <相对仓库根的路径>` 会一次性列出缺项。patch plan 至少含：

```
Attempt ID: <id>
Acceptance: journey
Release order: none
前置包（Predecessors）: None
Harness setup: <命令>
Harness precheck: <命令>
Harness cleanup: <命令>
Harness isolation: per-run
First visible step: <真实 StepId> @ <本 patch 的 TicketId>
```

每张 patch Ticket 含 `Ticket ID`、`Publication Status`、`Attempt ID: <id>` 与 `## Coverage` 三行：`- Journey steps: <J1-S1, ... | none>`、`- Suites: <S-id | none>`（两者不能都为 none）、`- Required review: <none | 说明>`。

patch 的 Ticket 须认领 Spec 的全部 Journey step，即使改动不影响页面可观察行为：Gate 只认当前 Attempt 的走查证据，没有“沿用上一 Attempt 的 Journey”的豁免。改动不影响页面时，用一张 Ticket 认领全部 step 并在修复后版本重走，每步只提交 Gate 依赖的最少凭据（页面步 1 张截图，文件/接口步 1 个返回），其余原始产物写被 git 忽略的 `output/qa/<runId>/`。

## Patch artifacts

- 创建属于本 Attempt ID 的新 ticket files；ticket id 在 package 内保持唯一。
- package 永远只有一个 current `gate.md`，不创建 patch-gate 文件；旧判决由 Git 和旧 Attempt Execution Record 的 Gate 摘要保留。

## Freeze

pass、fail、defer Gate 使对应 patch plan terminal/frozen。后续变化可创建新的 patch attempt，并沿用 initial bundle approval；blocked 保持 Attempt active，补证通过当前 Plan、Execution Record 与后续 Gate 表达。
