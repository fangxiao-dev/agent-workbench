---
name: lark-intl-sdk
version: 1.0.0
description: "Use whenever implementing, reviewing, migrating, or debugging application runtime code that calls Lark International through @larksuiteoapi/node-sdk. Covers client setup, Base record reads/writes, attachment uploads, API value formats, error handling, retries, and production runtime boundaries."
metadata:
  requires:
    packages: ["@larksuiteoapi/node-sdk"]
---

# Lark SDK Runtime Integration

This skill is for application runtime code that talks to Lark International through the official Node SDK. It is not for one-off operator administration.

## Quick Workflow

1. Read this index and choose the relevant reference.
2. Reuse existing project helpers before adding new SDK calls:
   - `web/lib/lark/client.ts`
   - `web/lib/lark/base-write.ts`
   - domain sources under `web/lib/lark/*-source.ts`
3. Confirm the target API shape from installed SDK types or existing helper tests.
4. Add or update focused tests around value conversion, response validation, and sanitized errors.
5. For runtime code, do not depend on local executable paths or shelling out.

## Reference Index

| Task | Read |
|---|---|
| Create the SDK client | [`references/client.md`](references/client.md) |
| Lark Base record writes | [`references/base-record-writes.md`](references/base-record-writes.md) |
| Lark Base value formats | [`references/base-field-values.md`](references/base-field-values.md) |
| Bitable attachment uploads | [`references/attachments.md`](references/attachments.md) |
| Error handling and retries | [`references/errors-and-retries.md`](references/errors-and-retries.md) |
| Verification for runtime migrations | [`references/verification.md`](references/verification.md) |

## Runtime Boundary

- Runtime application code uses SDK/API helpers.
- Local project management, Base setup, operator imports, cleanup, and diagnostics may use CLI-oriented tools.
- Do not introduce `node:child_process`, executable path env dependencies, or shell commands into production-facing app modules under `web/app` or `web/lib/lark`.

## Project Conventions

- Use `getLarkClient()` from `web/lib/lark/client.ts` so the app consistently uses `AppType.SelfBuild` and `Domain.Lark`.
- Use `LARK_BASE_APP_TOKEN` as `path.app_token` for Base APIs.
- Use table IDs from `LARK_TABLE_*` env vars.
- Keep SDK write operations behind small helpers so field conversion, ID validation, sanitized error messages, and retry behavior stay consistent.
- Treat formula, lookup, and system fields as read-only outputs unless the task is field-definition management.

## When Adding A New Runtime Write

1. Add a domain-level function in `web/lib/lark/*-source.ts`.
2. Route create/update/delete through `web/lib/lark/base-write.ts` when it is a Base record operation.
3. Normalize and validate returned record IDs before exposing them to callers.
4. Add tests that assert the exact SDK call payload.
5. Add a failing-path test for Lark response errors when the new operation changes error handling.
