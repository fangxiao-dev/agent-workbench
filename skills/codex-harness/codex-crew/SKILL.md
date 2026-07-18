---
name: codex-crew
description: Use as the Full execution profile of codex-harness when a persistent parent needs the complete Harness policy, approved Impl-Package binding, isolated Codex workers, independent verification, structured continuation, and a post-implementation do-review loop. Also use when explicitly asked for codex-crew.
---

# Codex Crew

Codex Crew is the Full execution profile of the same persistent parent used by Crew Lite. The interactive main session remains accountable for the issue and owner communication; it confirms the parent’s Full proposal and forwards decisions. The parent performs all task decomposition, worker dispatch, package coordination, verification and review orchestration. It combines the shared worker/worktree dispatcher with the existing Harness lifecycle and Impl-Package gates rather than replacing either.

Read the shared [continuation contract](../references/codex-crew-continuation-contract.md), the canonical [full manifest example](../assets/codex-crew.v0.json), the [dispatch schema](../assets/codex-crew-dispatch.schema.json), and `skills/codex-harness/assets/codex-harness-poc-design.md` before running it. Treat the structured profile as canonical; do not encode policy values in this Skill.

## When to select it

Use Crew for an approved work package, a task that earns independent review, or an implementation requiring persistent parent continuation, revision binding, structured acceptance, or a review gate. It is not a replacement for `impl-package` planning: S/M/L/D remains the composition route, where S means `tickets=false` and `dag=false`, not a promise that the change is small.

## Operating flow

1. Let the persistent parent analyze the issue and propose Full. The main session confirms the proposal; the controller then loads the canonical runtime policy and resumes the same parent thread with the Full boundary.
2. Use `impl-package` and `impl-planning` to verify the package has earned execution. For S Composition, create the approved S package; for larger or dependency-bearing work, use the required tickets/DAG route. Keep the source revision and D/S/P binding fixed. An unapproved package may be planned but not executed.
3. Let the parent create only disjoint worker worktrees through the shared dispatcher. The dispatcher is an explicit external-worker route for this Crew workflow, not a new default acceptance requirement for native Codex child topology.
4. Workers return structured results. The parent makes ordinary in-scope judgments in the same logical thread. Only scope, authority, irreversible external effects, or acceptance ambiguity goes to the main session/user; after the answer, the main session forwards it and the controller resumes the same parent thread.
5. Validate the full bounded change unit: compare it with the captured base, inspect all worktree changes, and run the package/manifest verifiers and independent acceptance checks. The controller records policy identity and keeps the parent continuation lease and Full-mode ledger; the parent must still produce the package, verifier, Parent Result, and terminal-disposition evidence rather than treating controller startup as an automatic gate pass.
6. After implementation commits exist, invoke `do-review` over the explicit base..head range. Fix confirmed P0/P1 findings within the granted scope, re-run affected checks, and repeat with a bounded loop. P2 findings are reported as follow-up unless the owner changes scope.
7. Return the parent result, verification evidence, review disposition, unresolved decisions, and worktree/commit ranges to the main session. Do not auto-merge, delete worktrees, or claim the package gate passed without its independent gate.

## Boundaries

Crew adds controls; it does not make the main session passive. A `needs_owner` result pauses only the affected continuation, not the whole conversation. The main session should resolve what is already authorized, ask the owner for the four defined boundary categories, and resume rather than spawning an unrelated replacement thread.

Use `do-review` only after code is present and the change range is explicit. Its review agents provide independent evidence; they do not automatically authorize mutations or substitute for Impl-Package completion gates.

The current runtime policy vocabulary remains `design_baseline`: this Full profile structures and records the policy boundary, but it does not claim that the policy is a separately deployed `runtime_enforced` standard.
