---
name: using-feishu
version: 1.0.0
description: "Feishu domestic capability router. Use this before Feishu work when deciding which feishu-* skill should handle lark-cli operations for the China Feishu product suite. Also serves as the index for bundled feishu-* skills."
---

# Using Feishu

Use this skill as the entry point for domestic Feishu work. It routes operator tasks to the bundled `feishu-*` skills under this directory.

## Routing

1. Read `../feishu-shared/SKILL.md` first for auth, identity, scopes, permission errors, and safety rules.
2. Read the specific `../feishu-*/SKILL.md` for the target capability.
3. Keep command examples as `lark-cli ...`; `feishu-*` is the skill naming convention, not the executable name.

## Core Skills

| Skill | Use |
|---|---|
| `feishu-shared` | CLI config, auth login, user/bot identity, scope and permission handling. |
| `feishu-openapi-explorer` | Native OpenAPI discovery when no registered CLI command covers the need. |
| `feishu-skill-maker` | Creating reusable custom skills around `lark-cli` operations. |
| `feishu-base` | Base/Bitable tables, fields, records, views, forms, dashboards, roles, workflows. |
| `feishu-sheets` | Spreadsheet create/read/write/search/export and workbook operations. |
| `feishu-doc` | Cloud Docs create/fetch/update, media handling, document content. |
| `feishu-drive` | Drive files/folders, upload/download/import, comments, permissions, sync. |
| `feishu-wiki` | Wiki spaces, document nodes, members, node movement/copying. |
| `feishu-whiteboard` | Whiteboard diagrams and visual content in Feishu docs. |
| `feishu-slides` | Feishu Slides create/read/update and slide media. |
| `feishu-im` | Messages, replies, chat history, groups, message files/images, reactions. |
| `feishu-mail` | Draft, compose, send, reply, forward, read/search mail, attachments, folders, labels. |
| `feishu-calendar` | Calendar events, agenda, meetings, attendees, freebusy, rooms, RSVP. |
| `feishu-contact` | User lookup, employee search, open_id resolution, departments and profile data. |
| `feishu-task` | Tasks, task lists, assignment, status, subtasks, task attachments. |
| `feishu-minutes` | Minutes metadata and media handling. |
| `feishu-vc` | Ended video meeting records, notes, transcripts, participants, recordings. |
| `feishu-vc-agent` | In-meeting bot join/leave and live meeting events. |
| `feishu-note` | Meeting note detail and transcript lookup when note_id is known. |
| `feishu-approval` | Approval instances and approval task management. |
| `feishu-attendance` | Current user's attendance clock records. |
| `feishu-okr` | OKR periods, objectives, and key results. |
| `feishu-apps` | Miaoda/Spark app development, static HTML publishing, cloud sessions, releases. |
| `feishu-markdown` | Feishu Markdown file operations. |
| `feishu-workflow-meeting-summary` | Meeting-summary report workflow. |
| `feishu-workflow-standup-report` | Calendar + task standup/agenda workflow. |

## Boundaries

- International Lark work uses `skills/lark-skills/using-lark` and `lark-intl-*`.
- Domestic Feishu work uses this router and `feishu-*`.
- Do not rename or wrap the `lark-cli` binary in examples; it is shared by both product surfaces.
