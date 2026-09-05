---
target: plugin-marketplace/plugins/impl-package/skills/impl-planning
updated: 2026-09-05
---
# Impl Planning Rubric

## Confirmed preferences

- Choose the smallest earned Composition; small linear work may use no Tickets and no DAG.
- D/S/P are optional readable aliases only; Git commit is the cross-session comparison point.
- One complete bundle receives one review and one owner approval.
- Plan holds only global scheduling — Composition, Ticket order/dependency, shared-resource serialization, integration/rollout boundary, and Final Gate criteria — while per-constraint coverage and verification live in each Ticket's Contract references and AC; current execution state stays in `state.json` and is exposed through `progress.md`.
- Only affected records require revalidation after a plan change.
- Plan only maps an already-frozen Spec contract ensemble to implementation and verification. If observable behavior, data identity, permission, concurrency, recovery, or public shape remains undecided, return to req-align without creating Plan/state or inventing a second DTO/schema contract.

## 本轮原则

- [待验证] 并行设计采用引导式判断，只记录会改变安排的结论；复用现有调度方法，执行时动态调整工作线。（证据: R1）
- [待验证] 并行机会以当前可用能力、真实依赖产物及资源为依据；允许在整票验收前交接已可用的实现增量。（证据: R1）
- [待验证] 保持现有 Ticket 粒度规则；高复用场景的合票经验仅保留观察，不推广为合票倾向。（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-05
- 采纳轻量并行引导 — 用户原话：“做一些并发的设计，但不做成机械的、重型的。”批准将判断融入现有规划步骤，沿用四列表和现有依赖语义。
- 采纳按实际产物安排交接 — 接手任务已提前产出基础、UI 和 Core，并在执行中调整工作线；这些是本次观察，不是固定人数或步骤队列的依据。
- 保留粒度观察 — 用户原话：“这次不应该拆太碎是因为已经有大量可以复用的，但其实很多时候问题仍然是ticekt 太肥，所以暂时保留观察，不贸然鼓励合ticket”。
