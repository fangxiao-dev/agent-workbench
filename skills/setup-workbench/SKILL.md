---
name: setup-workbench
description: >
  Use after pulling agent-workbench changes, when the user asks what changed in
  the pull, or when they want to inspect, update, sync, repair, or apply the
  repository-managed Codex plugin, skills, and agents setup, or audit the
  Claude host's plugin and skills. Always report setup drift before applying it.
---

# Setup Workbench

Use the repository's existing setup scripts from the agent-workbench
repository root: `scripts/codex_setup.py` for the Codex audit/apply flow and
`scripts/claude_setup.py` for the read-only Claude audit.

## Route the request

- After a pull, or when asked what the pull changed, run:
  `python scripts/codex_setup.py pull-diff`.
- When asked to inspect the current Codex/workbench setup, run:
  `python scripts/codex_setup.py audit`.
- When asked to inspect or audit the Claude host's plugin and skills, run:
  `python scripts/claude_setup.py audit` (optionally with `--claude-home <dir>`).
- When asked to update, sync, repair, bootstrap, or apply the setup without an
  approved current report, run `audit`, present its differences and audit SHA,
  then stop for Owner approval.
- When the Owner explicitly approves the current report or asks to apply it,
  run `python scripts/codex_setup.py apply --expect-report <audit-sha>` using
  that report's exact SHA.
- When the approved report contains stale workbench skill or agent links and the
  Owner explicitly asks to delete them, append `--prune-stale` to that apply.
- The Claude audit has no apply. To repair Claude drift, propose the native
  `claude plugin` commands for plugin drift and
  `python scripts/link_skill.py <skill> --host claude` for skill-link drift,
  then act only on explicit Owner approval.

## Boundaries

- Never apply before reporting. A direct update request authorizes the audit,
  not the mutation.
- `claude_setup.py` never mutates `~/.claude`; its audit SHA is for
  drift comparison between runs, not an apply gate.
- If no current audit SHA is available, or repository/setup state may have
  changed since it was produced, run a fresh audit and stop for approval.
- Let the scripts enforce SHA validity, managed-file ownership, cross-platform
  paths, conflict protection, and post-apply verification. Do not reproduce or
  bypass that logic.
- Unless the user requests a report file, use stdout rather than `--output`.
- Summarize only differences. For each item, show its category, name,
  installation location, status, and relevant SHA; omit `MATCH` items and file
  contents.
- When the audit reports an existing unmanaged top-level TOML under the
  repository's `agents/` inventory and the Owner explicitly wants to adopt it,
  pass `--adopt-agents` to the approved `apply` command; do not use it for
  unrelated files.
- `--prune-stale` removes only stale skill or agent links named by the approved
  audit and still pointing into this workbench. It refuses real directories,
  user-owned targets, changed links, and unaudited paths.
- Do not treat `pull-diff` as setup approval. It only explains repository
  changes after a pull.

For native plugin lifecycle operations outside this one-shot Codex bootstrap,
follow `docs/workbench-design/04-install-spec.md`.
