# Worked Example — KaiSpan System Layered Audit

A concrete run of [../references/system-audit.md](../references/system-audit.md) on a multi-tenant B2B SaaS monorepo (NestJS API, Next.js web apps, Prisma). Use it as a model for mapping layers and reading a heatmap — not as a checklist to copy. Numbers are from one sampled run and are illustrative.

## Trigger

An implementation package tightened the rule layer well but, while splitting permissions (scheduling, onboarding invitations, contract dispatch/confirm, attendance, payroll), built parallel `*-minimal` endpoints and components for single-permission users and copied the work-time-account and month-closing components into the payroll page. The owner asked: is this a one-off, or does the whole system lack outer-layer design?

## Layer map

| Layer | Directories |
| --- | --- |
| Page | `apps/web/components/**`, `apps/web/app/**`, `apps/tax-web/**` |
| Interface | `apps/api/src/**/*.controller.ts`, DTOs, `packages/contracts` (OpenAPI + generated client) |
| Orchestration | `apps/api/src/**/*.service.ts` and helpers |
| Rules | `apps/api/src/hr/rules/`, `apps/api/src/billing/daily-ledger/`, `apps/api/src/platform/business-hours/` |
| Data | `packages/db` (schema, tenant-scoped client) |
| Foundation | `apps/api/src/platform/**` (auth, tenant, RBAC, audit, files, jobs), `packages/{config,storage,observability}` |

Module rows were split where the owner reported different maturity: finance *daily ledger* (rule layer refactored) vs *Kontierung* (not refactored) vs *other finance*.

## Slicing

Eleven read-only agents: foundation (auth/RBAC/audit/clock), foundation (files/jobs/action center/config), data, rules-HR, rules-finance (per sub-module), orchestration-HR, orchestration-finance (per sub-module), interface (per module), page-HR, page-finance/workspace, page-tax-web + shared packages. Cheap models for most; a stronger one for interface and orchestration.

## Verification outcomes (examples)

- **Confirmed, O1:** leave approval ran in a serializable transaction with a row lock but never performed the same-value update that makes a waiting month-close retry — the fourth leak of a convention enforced by discipline, not by the helper.
- **Confirmed, F2:** the in-transaction session refresh dropped the request's business clock that the non-transaction variant passed.
- **Corrected cause, I3:** the generated contract lacked the new response shapes because it was not regenerated after merge; the controller declared them.
- **Narrowed:** a cash-upload authorization used the calendar day instead of the store business day only on one integration entry path.
- **Downgraded, D2:** "tenant client can delete audit rows" — an append-only DB trigger blocks it.
- **Downgraded, F4:** "test business-day switch fail-open if env unset" — config validation makes the variable mandatory.

## Heatmap (0–10, 10 = healthy)

| Module | Page | Interface | Orchestration | Rules | Main deductions |
| --- | --- | --- | --- | --- | --- |
| HR | 5 | 5 | 6 | 8 | P1, P3, P4, O1 |
| Finance · daily ledger | 5 | 6 | 8 | 8 | O4 (one 4.5k-line page), P1 |
| Finance · Kontierung | 2 | 7 | 4 | 3 | O4, P6 (mock default), R2 (×4), R3 |
| Finance · other | 4 | 5 | 3 | 4 | O4 (16k / 13k-line services), O3 |
| Tax web | 4 | 5 | 5 | — | cross-app relative imports, P1, I3 |
| Foundation · auth/RBAC | — | — | 8 | — | F2 |
| Foundation · services | — | — | 6 | — | O2, F3, F4 |
| Data | — | — | — | 7 | D1 |

Readings: the refactored daily ledger and the unrefactored Kontierung sit in the same domain at 8 vs 3 on rules — the refactor method works and can be repeated. Across modules, foundation and rules are healthy while interface, orchestration and page are weak — the outer layers had no systematic design.

## Remediation order

1. Stop the bleeding: outer-layer reuse checks in design review; guard tests against new `*-minimal` surfaces, new direct job-table writes, and unenforced write fences.
2. Fast-lane: the confirmed O1 and F2 defects fixed in small PRs; the contract regenerated; a file-upload bypass filed as an issue because the fix changes the client upload protocol.
3. Vertical slices: the module about to face external users first (Kontierung + bank reconciliation), bottom-up, scoped to what can land before the deadline; HR outer layers as a longer track.
