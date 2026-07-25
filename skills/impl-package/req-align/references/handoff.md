# Handoff Status and Owner Output

Read this reference when reporting a Decision/Spec result or handing an aligned package forward. Use `talk-to-boss`: lead with scope, completed phase, remaining owner decisions, whether the package is closed, and whether implementation planning can start. Do not open with paths, revisions, or sidecars.

Derive one exact status from recorded Markdown gate facts and downstream closure evidence:

- `Decision blocked: investigation pending`: Decision is `BLOCKED` and the blocker is an unfinished permitted or authorization-pending investigation.
- `Decision blocked: owner decision pending`: Decision is `BLOCKED` and the blocker is an owner choice rather than investigation.
- `Decision passed / ready for Spec`: Decision is `PASSED` and Spec has not yet been created or evaluated.
- `Spec blocked: contract or owner decision pending`: Spec is `BLOCKED`; name the exact missing contract, evidence, or owner decision and do not hand off to planning.
- `ready for implementation planning`: Decision and Spec are `PASSED`, with no recorded downstream package-closure evidence gap.
- `implementation may proceed, package closure evidence pending`: Decision and Spec are `PASSED`, and downstream records explicitly name implementation, verification, backfill, or merge evidence that remains open.

Do not infer downstream closure pending merely because it was not checked. Artifact Status and Gate Result must agree. After writes, include topic slug, package ID/path, current D/S revision set, binding validation, gate results and evidence location, changed `execution-findings.md` only if appended, and remaining owner decisions. Do not require owners to read JSON. When Grill ran, name its temp ledger and summarize its outcomes.
