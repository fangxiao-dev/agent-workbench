---
name: codex-crew-lite
description: Use as the Lite execution profile of codex-harness when a persistent parent can handle a clear, bounded issue through isolated Codex App Server workers in separate Git worktrees without loading the full Harness or Impl-Package lifecycle. Also use when explicitly asked for codex-crew-lite.
---

# Codex Crew Lite

Use this as a mode selected and confirmed for the persistent parent, not as a second main-session scheduler. The parent owns issue analysis, creates the dispatch manifest, starts isolated workers, judges their questions, and gathers results. The main session only confirms the mode, forwards user decisions, and presents delivery. Each worker gets a fresh thread and worktree.

Read the shared [continuation contract](../references/codex-crew-continuation-contract.md) and use the canonical [Lite manifest example](../assets/codex-crew-lite.v0.json) with [its schema](../assets/codex-crew-dispatch.schema.json). Do not copy configuration values into Markdown prompts.

## Route selection

The parent may propose Lite only when the issue is understood and the intended repair does not need a new Decision/Spec, interface redesign, data migration, permission change, irreversible external action, or changed acceptance criteria. The main session confirms the proposal before mutation. A worker discovering one of those conditions reports `needs_parent` or `needs_owner`; this upgrades the parent conversation, not the worker’s authority.

## Dispatch procedure

1. Define disjoint task ownership and one worktree/branch per task in the structured manifest. Do not split the same file or shared external resource merely to increase parallelism.
2. Create a durable dispatch state and safe worktrees with `scripts/codex_harness_dispatch.py init-state` then `ensure-worktrees`.
3. Start one or more fresh worker threads with `start-workers --parallelism N`; the dispatcher returns structured worker outcomes to the parent and does not claim acceptance from natural-language completion.
4. For `needs_parent` or `failed`, the parent reasons and sends a narrowed correction through the same parent thread. For `needs_owner`, the parent returns the structured request to the main session; after the owner decision is forwarded, the parent continues the same thread.
5. Inspect each worktree diff and run the declared focused checks. The parent aggregates results for the main session; it does not automatically delete, merge, or promote worktrees.

## Minimal commands

```powershell
python scripts/codex_harness_crew.py start --repository-root . --issue-file issue.md --state .codex/crew/parent.state.json
python scripts/codex_harness_crew.py confirm-mode --state .codex/crew/parent.state.json --mode lite
$artifactRoot = (Get-Content .codex/crew/parent.state.json | ConvertFrom-Json).artifact_root
python scripts/codex_harness_dispatch.py init-state --manifest .codex/crew/lite.json --parent-state .codex/crew/parent.state.json --state (Join-Path $artifactRoot 'lite.dispatch.state.json')
python scripts/codex_harness_dispatch.py ensure-worktrees --state (Join-Path $artifactRoot 'lite.dispatch.state.json')
python scripts/codex_harness_dispatch.py start-workers --state (Join-Path $artifactRoot 'lite.dispatch.state.json') --parallelism 2
python scripts/codex_harness_crew.py register-dispatch --state .codex/crew/parent.state.json --dispatch-state (Join-Path $artifactRoot 'lite.dispatch.state.json')
```

Lite deliberately omits Full-mode policy-bound ledger controls, Impl-Package binding, review gates, and worktree cleanup. The parent controller still keeps a single-writer lease for continuations, captures the controller worktree boundary, and requires structured dispatch state. If Full-mode controls become necessary, the parent requests a mode change through the main session and continues as `codex-crew`; it does not create a second parent.
