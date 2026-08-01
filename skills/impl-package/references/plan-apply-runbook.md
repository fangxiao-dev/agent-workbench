# Planning-only fast apply

This runbook is the short path for an already reviewed and owner-approved
Implementation Package whose change surface is limited to planning artifacts:
Ticket publication, D/S/P binding, projections, and local package state. It is
not an implementation, database, application-runtime, commit, push, or GitHub
mutation path.

## Entry gate

Use the fast path only when all of these facts are true at invocation time:

- the applicable `plan-review` ledger passes `verify-clearance` with a fresh
  baseline and no unresolved or stale blocker;
- the ledger contains one owner authorization for `action=apply` bound to the
  exact current manifest, and the supplied authorization matches it exactly;
- the current plan declares `Composition: tickets=true`; every current-attempt
  ticket is in the same package and has the requested D/S/P binding;
- the earned DAG is present and revision-bound when `dag=true`, or absent when
  `dag=false`;
- the package contains no implementation, database, application-runtime
  transition, or external-mutation request; machine-owned `.impl-package`
  state/projections are explicitly in scope.

If any entry fact is false, return `BLOCKER <reason>` and route back to the
owning stage. Do not turn a failed fast apply into a new review or a manual
staging ceremony.

## Command

From the workbench checkout:

```powershell
python skills/impl-package/scripts/impl_package_apply.py publish-plan `
  --package <package> `
  --decision D6 `
  --spec S7 `
  --plan P3 `
  --ledger <ledger> `
  --authorization <owner-authorization.json>
```

`--authorization -` accepts the same JSON object from stdin. The default
transaction deadline is 90 seconds; use `--timeout-seconds` only to make a
deliberate, bounded change to that local deadline.

The command performs one deterministic local transaction:

1. inspect and recover any uncleared transaction journal, refusing new
   unrelated worktree changes;
2. verify clearance and exact owner authorization, then preflight the complete
   ticket/AC/typed-edge/DAG set;
3. snapshot the complete package-local target set in one transient journal and
   replace Draft publication markers atomically;
4. register D/S/P revisions and refresh the existing runtime/projection state
   engine;
5. run one final state, AC, dependency, DAG, package-state, and Approved-status
   summary validation; and
6. remove the transaction journals only after the final validation succeeds.

Success writes exactly `APPLIED` to stdout. Any failure writes exactly one
`BLOCKER ...` result to stderr, restores the byte-for-byte snapshot, verifies
the restoration, and removes transient transaction data. If restoration cannot
be verified, the journal is retained and the blocker names the recovery
failure.

The journal is the recovery record; a separate hand-created backup or staging
directory is not part of this path. Before retrying after an interrupted
parent process, inspect `git status --short` and let the command reconcile its
journal. Do not assume that a process interruption near cleanup means the
transaction completed.

## Independent downstream work

The local apply ends before Git operations. After the result is `APPLIED`, the
working unit can be committed and pushed using the repository's normal Git
workflow. These operations are intentionally not hidden inside the package
transaction.

To generate the PR/Issue handoff from the registered package state:

```powershell
python skills/impl-package/scripts/impl_package_apply.py sync-working-unit `
  --package <package> `
  --repo <owner/repository> `
  --pr 180 `
  --issue 179 `
  --committed
```

This helper validates the selected working-tree or committed state and emits a
deterministic Markdown summary. It does not run `git commit`, `git push`, or
write GitHub; a separately authorized GitHub workflow may consume the summary
and update PR/Issue text.

## Time budget

The intended critical path is:

| Segment | Budget | Owner |
| --- | ---: | --- |
| apply + binding | ≤ 90 s | `publish-plan` |
| validation + commit | ≤ 2 min | normal Git workflow |
| push + PR/Issue handoff | ≤ 2 min | independent Git/GitHub workflow |

If the end-to-end operation exceeds five minutes, stop retrying and report the
specific blocker (clearance, authorization, worktree drift, validation,
rollback, Git, or remote update). A slow run is not evidence that more review
or more ceremony is required.
