# Handoff Status and Owner Output

Read this reference when reporting a Decision/Spec result or handing an aligned package forward. Derive the exact status below first. If `talk-to-boss` exists in the active skill catalog, use it only to organize that established status; it does not decide Decision/Spec state, closure, or planning readiness. Otherwise lead directly with scope, completed phase, remaining owner decisions, whether the package is closed, and whether implementation planning can start. Optional skill absence does not block the handoff. Do not open with paths or revisions.

Derive one exact status from recorded Markdown gate facts and downstream closure evidence:

- `Decision blocked: investigation pending`: Decision is `BLOCKED` and the blocker is an unfinished permitted or authorization-pending investigation.
- `Decision blocked: owner decision pending`: Decision is `BLOCKED` and the blocker is an owner choice rather than investigation.
- `Decision passed / ready for Spec`: Decision is `PASSED` and Spec has not yet been created or evaluated.
- `Spec blocked: contract or owner decision pending`: Spec is `BLOCKED`; name the exact missing contract, evidence, or owner decision and do not hand off to planning.
- `ready for implementation planning`: Decision and Spec are `PASSED`, with no recorded downstream package-closure evidence gap.
- `implementation may proceed, package closure evidence pending`: Decision and Spec are `PASSED`, and downstream records explicitly name implementation, verification, backfill, or merge evidence that remains open.

Do not infer downstream closure pending merely because it was not checked. Artifact Status and Gate Result must agree. After writes, include topic slug, package ID/path, current Decision/Spec paths, gate results and evidence location, changed `execution-findings.md` only if appended, and remaining owner decisions. When `contract-design.md` exists, report it as detailed evidence under the same Spec contract rather than as another approved artifact. Do not require owners to read JSON. When Grill ran, name its temporary discussion record and summarize its outcomes.
