# Workflow

Follow this sequence for a session-derived experience curation pass.

## 1. Establish Scope And Baseline

Resolve the exact time window, project path, and current baseline:

- Convert relative dates to concrete dates.
- Record timezone if the source sessions use timestamps.
- Record repository branch, HEAD commit, and `git status --short`.
- Read project instructions such as `AGENTS.md`.
- Read existing knowledge entrypoints: `docs/hands-on-knowledge/README.md`, `docs/hands-on-knowledge/entry-map.md`, and project ubiquitous language if present.

If the project has no maintained knowledge root, create `docs/hands-on-knowledge/` with an `entry-map.md` and minimal README, unless the user specified a different path. Treat typos like `hands-on-knowlegde` as referring to the canonical `hands-on-knowledge` path unless the user explicitly insists on the spelling.

## 2. Discover Sessions

Read actual session/thread content. Do not rely on handoff summaries unless they are only pointers to the underlying session.

Preferred sources, depending on tool availability:

- thread tools such as `list_threads` / `read_thread`.
- local Codex/agent session JSONL files.
- project-local exchange notes only as supporting evidence, not as a substitute for session reads.

Search first for terms that indicate prior knowledge work:

- `hands-on-knowledge`
- `project-knowledge-manager`
- `impl-knowledge-maintainer`
- `debug-knowledge-maintainer`
- `entry-map`
- `session-handoff`

Use those hits to classify sessions as already curated, already discussed but not covered, or needing full read.

## 3. Build The Shared Approval Report

Create a temporary report in the project, preferably under `docs/exchange/` if that directory exists. If it does not exist, create a temporary report under `docs/exchange/` or another user-approved ignored exchange directory.

Use `references/report-template.md`.

The report must be baseline-decoupled:

- Thread ids are evidence pointers only.
- Current workspace files and current branch are the baseline.
- Do not write "this was true in session X" as a durable fact unless it is still true now.

## 4. Dispatch Subagents

Use subagents for both exploration and audit when available. Follow `references/subagent-protocol.md`.

Default lanes:

- session scanner: reads assigned sessions and extracts candidate lessons.
- baseline reviewer: compares candidates to current code/docs/entry-map.
- curation auditor: checks duplicates, over-broad references, missing indexing, and inconsistent terminology.

Subagents are read-only during report creation. They should not edit maintained knowledge docs.

## 5. Consolidate And Ask For Approval

Merge subagent findings into the report:

- Keep actionable candidates.
- Keep already-covered items only when they need wording/indexing review.
- Remove rejected/one-off/ordinary planning items from the main report.
- Use ubiquitous language and scenario language; avoid leading with code variable names.

Ask the user to approve the report before curation. If the user changes principles or scope, update the report first.

## 6. Curate Approved Knowledge

After approval, use `project-knowledge-manager` as the parent router.

For each approved item:

- Search existing `docs/hands-on-knowledge/` and `entry-map.md`.
- Prefer the smallest existing document update.
- Create a new short pattern/runbook/investigation only when existing docs would become too broad.
- Split implementation and debug lessons when they have different future lookup paths.
- Update `entry-map.md` after durable docs change.

Keep durable docs concise. Avoid raw logs, session narration, temporary IDs, credentials, and obsolete session state.

## 7. Verify And Close

Run lightweight verification:

- `git diff --check`
- `git status --short`
- targeted file existence and `entry-map.md` search checks

Run code tests only if code or executable verification assets changed. For documentation-only curation, state that no runtime tests were needed.

Update the temporary report with what was curated and where.
