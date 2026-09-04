---
name: setup-workbench
description: >
  Use after pulling agent-workbench changes, when the user asks what changed in
  the pull, or when they want to inspect, update, sync, repair, or apply the
  repository-managed Codex plugin, skills, and agents setup. Always report
  setup drift before applying it.
---

# Setup Workbench

Use the repository's existing `scripts/codex_setup.py` as the only setup
implementation. Run commands from the agent-workbench repository root.

## Route the request

- After a pull, or when asked what the pull changed, run:
  `python scripts/codex_setup.py pull-diff`.
- When asked to inspect the current Codex/workbench setup, run:
  `python scripts/codex_setup.py audit`.
- When asked to update, sync, repair, bootstrap, or apply the setup without an
  approved current report, run `audit`, present its differences and audit SHA,
  then stop for Owner approval.
- When the Owner explicitly approves the current report or asks to apply it,
  run `python scripts/codex_setup.py apply --expect-report <audit-sha>` using
  that report's exact SHA.

## Boundaries

- Never apply before reporting. A direct update request authorizes the audit,
  not the mutation.
- If no current audit SHA is available, or repository/setup state may have
  changed since it was produced, run a fresh audit and stop for approval.
- Let the script enforce SHA validity, managed-file ownership, cross-platform
  paths, conflict protection, and post-apply verification. Do not reproduce or
  bypass that logic.
- Unless the user requests a report file, use stdout rather than `--output`.
- Summarize only differences. For each item, show its category, name,
  installation location, status, and relevant SHA; omit `MATCH` items and file
  contents.
- Do not treat `pull-diff` as setup approval. It only explains repository
  changes after a pull.

For native plugin lifecycle operations outside this one-shot Codex bootstrap,
follow `docs/workbench-design/04-install-spec.md`.
