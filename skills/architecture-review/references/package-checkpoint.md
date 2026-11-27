# Package Checkpoint

A small, independent architecture gate for one implementation package. It is called by the package workflow at two points but is not part of requirement alignment or planning; it asks only the few questions that the rule-correctness reviews miss — whether the **outer layers** (page, interface, orchestration) reuse instead of diverge.

## Inputs

- **Design checkpoint** (after the contract/design documents and the ticket plan exist, before implementation): the decision, spec, contract design, plan and tickets.
- **Terminal checkpoint** (at final review, fixed head): the full diff from the package base, plus the same documents.
- The project's layer map, if it has one.

## The four questions

Answer each with `pass` / `fail` / `n/a` and evidence (`path:line` or document section). Symptom IDs refer to [layer-model.md](layer-model.md).

1. **Single entry per business surface.** Does any capability get a second endpoint, DTO shape, or component because a different permission set uses it (I1, P1)? Expected: one resource and one component; the server projects fields and per-row action flags by capability; the client renders actions from those flags.
2. **Gates at the right granularity.** Is any access decision made per page or per route where the need is per section or per action (P2)? Does any caller stitch an aggregate the interface should provide (P3, I2)? Expected: section/action-level gates; an organization-level read where callers need one.
3. **Shared constraints in one channel.** Does any new write path have to *remember* a correctness constraint (concurrency fence, idempotency order, audit, job enqueue, file confirm) instead of getting it from a channel or helper that enforces it (O1, O2)? Expected: new writers use the enforcing channel; if the channel does not enforce, the package either fixes the channel or adds a guard test.
4. **Ticket cut follows surfaces, not permissions.** *(Design checkpoint only.)* Is one business surface split across tickets by permission set, so two workers build two versions of it? Expected: one ticket owns a surface end to end; permissions are a dimension inside it.

## Output

```
Package checkpoint (<design | terminal>): PASS | FAIL
Q1 single entry:        pass|fail|n/a — <evidence>
Q2 gate granularity:    pass|fail|n/a — <evidence>
Q3 enforcing channel:   pass|fail|n/a — <evidence>
Q4 ticket cut:          pass|fail|n/a — <evidence>
Required changes: <only for fail; the smallest change that restores reuse>
```

Any `fail` makes the checkpoint FAIL. A `fail` at the design checkpoint is cheap to fix — change the contract or the ticket cut; at the terminal checkpoint, prefer the root fix (projection, channel) over patching the copy, and record the decision if the owner accepts the divergence.

Completion criterion: all applicable questions answered with evidence; every `fail` names a required change.

## Boundaries

- Do not re-review rule correctness, tests, or spec fidelity — other reviews own those.
- Do not expand into a system audit; findings outside the package go to a follow-up list.
