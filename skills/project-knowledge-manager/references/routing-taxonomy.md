# Documentation Routing Taxonomy

Use this reference when the short routing rules in `SKILL.md` are not enough.

## Documentation Homes

| Destination | Purpose |
|---|---|
| `docs/hands-on-knowledge/entry-map.md` | Routing and search strategy. Keep it as a map, not a full index. |
| `docs/hands-on-knowledge/implementation/` | Reusable implementation patterns, migration notes, verification notes, integration practices, and maintained implementation references. |
| `docs/hands-on-knowledge/debug/` | Investigations, runbooks, known failure modes, recovery procedures, postmortems, platform traps, and diagnostic references. |
| `docs/top-level-knowledge/prd.md` | Product-level PRD. Keep it focused on product positioning, users, core workflows, current milestones, global scope/non-scope, and success criteria. Do not use it for field-level details or implementation rules. |
| `docs/top-level-knowledge/prd-*.md` | Module, domain, or capability PRDs. Use these for stable module behavior, durable business rules, capability scope, and accepted product decisions that are too detailed for the product-level PRD. |
| `docs/top-level-knowledge/` | Stable project, architecture, product, domain, or technology-stack facts that are not better represented by a PRD or module PRD. |
| `docs/exchange/req-*.md` | Requirement inbox, change request, or mini-PRD draft. Use these to capture new or changed requirements, discussion context, and owner decisions before they are merged into stable docs. |
| `docs/func-design/*.md` | Confirmed feature or module design. Use these for interfaces, data models, state transitions, boundaries, failure modes, and design-level acceptance criteria. |
| `docs/impl-plans/*.md` | Temporary execution plans. Use these for implementation sequencing, verification steps, and progress records; archive them after completion when the repository has that convention. |
| `AGENTS.md` or `CLAUDE.md` | Mandatory operating rules that must be seen in every session. Choose the repository's canonical agent entry file for the active host. |

Source material may come from conversation context, completed plans, handoffs, logs, code review notes, verification output, changed files, temporary notes, `docs/impl-plans/`, `docs/exchange/`, repo-root `exchange/`, or retrospectives. These are sources, not final homes.

## Requirement Lifecycle

Use this flow when the input is a new requirement, changed requirement, PRD cleanup, or product decision rather than implementation/debug experience:

1. Capture new or changed requirements in `docs/exchange/req-*.md` when they still need review, traceability, or owner decisions.
2. Merge accepted stable behavior into the product PRD or the relevant `docs/top-level-knowledge/prd-*.md` module/domain PRD.
3. Move confirmed requirements into `docs/func-design/*.md` when design details, interfaces, data models, or failure modes need to be specified.
4. Create or update `docs/impl-plans/*.md` only for execution planning and progress tracking.
5. Route only reusable implementation or debugging lessons with reverse-lookup value into `docs/hands-on-knowledge/`.

Treat `req` files as inbox and audit records, not final long-term PRDs. A large PRD should usually be split into a product-level PRD plus module/domain PRDs instead of growing into a single catch-all document.

## Examples

Input: `把这次 API schema refactor 的经验沉淀一下`

Route: `impl-knowledge-maintainer`

Reason: implementation/refactor lessons usually belong under `docs/hands-on-knowledge/implementation/`.

Input: `把刚才排查部署失败的过程整理成 runbook`

Route: `debug-knowledge-maintainer`

Reason: diagnostic and recovery procedures belong under `docs/hands-on-knowledge/debug/runbooks/`.

Input: `这次实现里发现了一个验证命令模式，也踩了一个预览链接 404 的坑，帮我沉淀`

Route: both

Reason: verification command pattern routes to implementation knowledge; preview-link 404 diagnosis routes to debug knowledge.

Input: `把项目背景写进 top-level docs`

Route: `docs/top-level-knowledge/`

Reason: stable project context should not be forced into implementation or debug hands-on knowledge.

Input: `新增一个 reporting workflow 需求，先帮我沉淀一下`

Route: `docs/exchange/req-*.md` first; later merge accepted stable behavior into the relevant product or module PRD.

Reason: a new requirement needs inbox traceability and owner decision history before becoming durable PRD content.

Input: `这个 PRD 太大了，帮我拆成顶层和模块 PRD`

Route: `docs/top-level-knowledge/prd.md` plus relevant `docs/top-level-knowledge/prd-*.md` module/domain PRDs.

Reason: PRD structure is a product documentation concern, not hands-on implementation or debug knowledge.

Input: `把“用户重复注册时必须走账号恢复流程”沉淀成 hands-on pattern`

Route: no hands-on write; keep in `docs/func-design/`, PRD, and executable test docs unless a real trap, recovery path, or missing reverse-lookup need emerges.

Reason: this is primarily a requirement/flow rule. Without extra trap or recovery value, it is not yet reusable hands-on knowledge.

Input: `把这次反复踩到的 API migration trap 沉淀一下`

Route: `impl-knowledge-maintainer` only if the note explains a reusable migration trap, safe pattern, or verification shortcut beyond ordinary design documentation.

Reason: recurring implementation traps can be hands-on knowledge, but ordinary API design decisions belong in design docs.
