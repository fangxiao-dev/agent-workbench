# Worked Example — KaiSpan SaaS Foundation Review

A concrete instantiation of the `architecture-review` methodology for a multi-tenant B2B SaaS platform (KaiSpan: German/EU B2B, Supabase Auth as identity provider, own DB as source of truth for orgs/membership/RBAC/billing). Use it as a model for adapting the generic domain catalog to a real system — not as a checklist to copy verbatim.

This example is intentionally SaaS-heavy. Do not import its tenant, billing, supplier, or file gates into unrelated systems unless the reviewed system actually has those concerns. For an internal single-tenant job runner, for example, tenant isolation may be `not-applicable` while idempotency, audit, and worker leasing become the real foundation gates.

## How the baseline was specialized

The generic domains in `../references/review-domains.md` were renamed into the system's own language and pinned to concrete evidence locations. KaiSpan's durable baseline ended up with ~16 domains:

1. Identity, organization & membership — external IdP proves identity only; local DB owns org/membership/subscription/grant/audit.
2. Tenant isolation & data ownership — every tenant table carries `organization_id`; tenant-scoped client forbids raw SQL and global-key ops.
3. Module grant, RBAC & temporary access — person→role→permission, role assignment binds data scope; `session.permissions` is for menus only, real scope via access grants.
4. Subscription, entitlement & usage — plan catalog as single source; stable error codes; usage metered per org/feature/period with idempotency.
5. File security & lifecycle — keys under `organizations/<id>/…`, pending→uploaded confirm, download authorized server-side, no long-lived public URLs.
6. Billing assistant — OCR raw / review row / confirmed fact / export modeled in layers; human confirmation before confirmed financial data.
7. Store inventory & supplier adapter — store-side ordering bound to org/store; minimum supplier adapter contract (id/channel, credential ref, order req/resp, canonical+raw status, idempotency, audit, failure handling, future push/polling).
8. Async jobs, queue transport & outbox — DB job is source of truth, transport is delivery; no double-claim; retry without duplicate side effects.
9. External API, credentials & rate limiting — API credential is its own actor type; browser-only routes closed by default.
10. Supplier connector, webhooks & recommendations — pull vs push as separate capabilities; signed, idempotent, retryable webhooks.
11. Audit, logging & observability — business audit separated from ops logs; IBAN/token/full-document/full-prompt redaction; request id end to end.
12. Transactions & external side effects — external calls outside the committing transaction; outbox/idempotency for side effects.
13. Environment, deploy & ops — local/dev/staging/prod isolation; fail fast on prod credentials in non-prod; real CI gates.
14. Compliance, retention, GDPR & GoBD — legally retained vs deletable vs anonymized; physical delete must not destroy accounting evidence.
15. Frontend surface — real vs demo vs placeholder pages; route protection matches API protection.
16. Extensibility / seam readiness — storage / OCR / supplier / job / entitlement / export / audit seams each have a stable contract + mock/real path.

## KaiSpan's P0 gate set (fail-closed)

A review may **not** call the foundation acceptable if any holds:

- Local user/org/membership/active-org resolver not closed.
- Core tenant data lacking a tenant key or isolation tests.
- Module grant / RBAC / entitlement / subscription mixed with no fail-closed tests.
- Temporary access missing or fused into permanent roles (no expiry/scope/audit).
- File download bypassable or using long-lived public URLs.
- Billing OCR/review/confirm/export crossing org or unit scope.
- Critical money/status/permission/file/export/lifecycle action with no audit.
- Jobs/workers/webhooks missing tenant context and idempotency.
- External side effects inside a business transaction with no outbox/recovery.
- Supplier adapter contract missing, or credentials exposed to the frontend.
- Staging/prod credentials & side effects not isolated.
- CI missing schema/migration/type/test/build/contract-drift gates.

## A real finding, graded with the taxonomy

From reviewing a large foundational PR ("~85% done"):

| Capability | Status | Why (evidence discipline applied) |
| --- | --- | --- |
| Tenant isolation on billing | `partial` | API tenant-safe, but CSV **export** path needed a negative cross-org probe before claiming `verified`. |
| Real OCR | `design-only` | Billing path used a mock OCR worker; provider boundary present, real extraction not wired. |
| External API surface | `not-found` | RBAC types mention `api_client`, but no credential-management routes located in the PR. |
| Temporary access | `partial` until probed | Schema + service present; needed an expiry/scope test to confirm it can't become a 2nd permanent permission system. |

The lesson the example carries: a contributor's "85% done" is a **claim**; the review's job was to convert each line of it into an evidence row and grade honestly — `verified` only where a negative test or runtime probe backed it, `design-only`/`not-found` where only a seam or a mention existed.

## Lifecycle in practice

The KaiSpan review kept a durable baseline checklist + a blank per-review template in the repo, and routed each one-off review instance to a gitignored scratch area — never committing instances into the long-term docs. Durable conclusions graduated into follow-up issues and architecture decisions. That separation (baseline vs instance) is the single most reused idea from the whole exercise.
