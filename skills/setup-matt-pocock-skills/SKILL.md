---
name: setup-matt-pocock-skills
description: Configure a repository for the engineering skills: issue tracker, shared issue-workflow contract, and domain-document layout.
disable-model-invocation: true
---

# Setup Engineering Skills

Set up repository-local documents for the engineering skills. For GitHub Issue work, use the shared `issue-workflow` contract instead of the retired Matt `needs-triage` flow.

## Process

1. Inspect `git remote -v`, root `AGENTS.md` / `CLAUDE.md`, `CONTEXT.md` / `CONTEXT-MAP.md`, `docs/agents/`, and existing Issue labels. Do not overwrite existing local conventions.
2. Confirm the Issue tracker, whether PRs are a requirement intake surface, the repository's people aliases, and its domain-doc layout. GitHub is the default only when its remote proves it.
3. For GitHub, draft `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and `.agents/issue-workflow.yaml`. The config holds only local aliases; shared shape/readiness/type rules remain in `skills/issue-workflow/references/issue-contract.yaml`.
4. Update the existing Agent-skills block in `AGENTS.md` or `CLAUDE.md` in place. State that `$issue-triage` proposes before writing and `$issue-reporter` is read-only.
5. Show the complete local draft and wait for confirmation before writing files or creating labels.

## Contract boundary

Do not add `needs-triage`, an agent-brief requirement, PR-as-request handling, a provenance label, or a priority label. Use `work:initiative`, `work:investigation`, the readiness labels, and type labels defined by the shared contract. A normal leaf has no `work:` label.

## Done

Report the local files changed, configured alias mappings, and whether GitHub label materialization still needs a separate confirmed `$issue-triage` proposal.
