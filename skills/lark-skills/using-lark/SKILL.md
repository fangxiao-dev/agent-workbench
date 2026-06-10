---
name: using-lark
version: 1.0.0
description: "Lark International capability router. Use this before Lark work when deciding whether a task should use lark-cli skills, the @larksuiteoapi/node-sdk runtime skill, or official Lark docs fallback. Also serves as the index for all bundled lark-intl-* skills."
metadata:
  requires:
    bins: ["lark-cli"]
    packages: ["@larksuiteoapi/node-sdk"]
---

# Using Lark

Use this skill as the entry point for Lark International work. It routes the task to either CLI-oriented skills, runtime SDK integration, or official documentation fallback.

## First Decision: CLI Or SDK

### Use CLI Skills

Use `lark-cli` skills when the task is operator/admin/data work outside production runtime code:

- One-off Base setup, field creation, record inspection, imports, cleanup, or diagnostics.
- Working with Drive, Docs, Sheets, Wiki, IM, Calendar, Tasks, Minutes, Approval, Mail, or other Lark resources as an agent/operator.
- Searching for resources by name or URL, resolving wiki/base/doc links, or exporting/importing files.
- Running smoke setup, data repair, schema checks, or marked-record cleanup from the local workspace.
- Building a reusable CLI workflow skill around existing `lark-cli` commands.

When using CLI skills:

1. Read `../lark-intl-shared/SKILL.md` first for auth, identity, scopes, and International domain rules.
2. Read the specific `../lark-intl-*/SKILL.md` for the target capability.
3. Before executing a command, read that skill's referenced command guide when it tells you to.
4. Prefer `lark-cli ... +shortcut` commands where the child skill requires them.

### Use SDK Skill

Use `lark-intl-sdk` when the task changes, reviews, migrates, or debugs application runtime code that calls Lark through `@larksuiteoapi/node-sdk`:

- Code under `web/lib/lark/**`, `web/app/**`, or backend adapters that reads/writes Lark Base at runtime.
- SDK client setup, app token/table ID usage, Base record create/update/delete/list payloads, attachment upload code, retry/error boundaries, and sanitized logging.
- Tests that assert exact SDK payloads or runtime Lark response handling.
- Avoiding shell commands in production-facing modules.

When using SDK:

1. Read `../lark-intl-sdk/SKILL.md`.
2. Reuse project helpers before adding SDK calls:
   - `web/lib/lark/client.ts`
   - `web/lib/lark/base-write.ts`
   - domain sources under `web/lib/lark/*-source.ts`
3. Confirm API shapes from installed SDK types, existing tests, and local helper conventions.
4. Add focused tests for value conversion, response validation, and sanitized errors.

## Skill Index

### Shared Foundation

| Skill | Use for |
| --- | --- |
| `lark-intl-shared` | CLI config init, auth login, user/bot identity, scopes, permission errors, International domain rules. |
| `lark-intl-sdk` | Runtime application code using `@larksuiteoapi/node-sdk`. |
| `lark-intl-openapi-explorer` | Native OpenAPI discovery when no `lark-cli` shortcut or SDK helper covers the need. |
| `lark-intl-skill-maker` | Creating reusable custom skills around `lark-cli` operations. |

### Data, Docs, And Files

| Skill | Use for |
| --- | --- |
| `lark-intl-base` | Base/Bitable tables, fields, records, views, forms, dashboards, roles, formulas, lookups, data-query. |
| `lark-intl-sheets` | Spreadsheet create/read/write/append/search/export. |
| `lark-intl-doc` | Cloud Docs create/fetch/update, Markdown-to-doc, image/file insertion, document search. |
| `lark-intl-drive` | Drive files/folders, upload/download, import, copy/move/delete, comments, permissions. |
| `lark-intl-wiki` | Wiki spaces and document nodes. |
| `lark-intl-whiteboard` | Whiteboard diagrams and visual content in Lark docs. |

### Collaboration And People

| Skill | Use for |
| --- | --- |
| `lark-intl-im` | Messages, replies, chat history, group members, message files/images, reactions. |
| `lark-intl-mail` | Draft, compose, send, reply, forward, read/search mail, attachments, folders, labels. |
| `lark-intl-calendar` | Calendar events, agenda, create/update meetings, attendees, freebusy, RSVP, time suggestions. |
| `lark-intl-contact` | Organization/user lookup, employee search, open_id resolution, department info. |
| `lark-intl-task` | Tasks, task lists, assignment, status, subtasks. |
| `lark-intl-minutes` | Minutes metadata, summaries, todos, chapters, transcripts, media download. |
| `lark-intl-vc` | Ended video meeting records and meeting artifacts. Use calendar for future scheduled meetings. |

### Automation And Workflows

| Skill | Use for |
| --- | --- |
| `lark-intl-event` | Webhook event subscriptions and event-driven pipelines. |
| `lark-intl-approval` | Approval instances and approval task management. |
| `lark-intl-workflow-meeting-summary` | Meeting-summary report workflow. |
| `lark-intl-workflow-standup-report` | Calendar + task standup/agenda workflow. |

## URL And Intent Routing

- `/base/` or "Base/多维表格/bitable" → `lark-intl-base`.
- `/wiki/` → `lark-intl-wiki`; if the node resolves to a Base, continue with `lark-intl-base`.
- Docs, Sheets, or Drive links without a clear target type → start with `lark-intl-doc` search or `lark-intl-drive` metadata, then route to the specific child skill.
- Meeting minutes URLs → `lark-intl-minutes`.
- Future meetings and schedule planning → `lark-intl-calendar`.
- Ended meeting records/artifacts → `lark-intl-vc`.
- Runtime code mentioning `@larksuiteoapi/node-sdk`, `getLarkClient`, `base-write`, or `web/lib/lark` → `lark-intl-sdk`.

## Fallback Order

Use fallback only after checking the relevant child skill and local project helpers.

1. **Child skill references**: Read the relevant `../lark-intl-*/SKILL.md` and its local `references/` files.
2. **Installed CLI/SDK truth**:
   - CLI: run `lark-cli <domain> --help` or the exact child-skill shortcut help.
   - SDK: inspect installed `@larksuiteoapi/node-sdk` types and existing project tests/helpers.
3. **Official Lark International docs**:
   - Open platform docs: https://open.larksuite.com/document/
   - API explorer: https://open.larksuite.com/document/server-docs/api-call-guide/explorer
   - Node SDK package: https://www.npmjs.com/package/@larksuiteoapi/node-sdk
   - GitHub SDK repository: https://github.com/larksuite/oapi-sdk-nodejs
4. **Native OpenAPI fallback**: If no CLI shortcut or SDK helper exists, use `lark-intl-openapi-explorer` to find the endpoint and document the gap.

When using official docs fallback, record the exact endpoint/doc page consulted in the response or implementation notes so future agents can replace the fallback with a local reference or helper.

## Safety Boundaries

- Do not put `lark-cli` shell calls into runtime app modules under `web/app` or `web/lib/lark`.
- Do not use SDK runtime code for one-off operator tasks that are better handled by CLI skills.
- Confirm user vs bot identity before accessing personal resources.
- Treat Lark Base field names and table IDs as exact external contracts; do not guess them from natural language.
- For real Lark writes, use marked records/run IDs and cleanup evidence when running smoke or repair workflows.
