# System Layered Audit

A rough, comparable health picture of a whole system across **modules × layers**, ending in a heatmap and a fix order. It trades depth for breadth: sampled evidence, verified where it matters. Use [layer-model.md](layer-model.md) for the layers and symptom IDs.

## Step 1 — Build the grid

1. Read the project's layer map and module list from its baseline. If missing, derive them: list top-level backend modules and frontend feature folders with non-test file counts, then map directories to the six layers.
2. Split modules where maturity differs inside them. Ask the owner which sub-modules were refactored and which were not; a refactored and an unrefactored sub-module averaged into one cell hides the most useful signal.
3. Write the grid (rows = modules/sub-modules, columns = layers). Mark non-existent cells `—`.

Completion criterion: every non-trivial module (by file count) is a row, and the owner's known maturity splits are separate rows.

## Step 2 — Slice and dispatch

Cut the grid into **scoped slices** small enough for one cheap agent each (typically one layer of one large module, or one layer across small modules). Prefer many small, cheap, read-only agents over one or two large ones; reserve a stronger model for a slice that is genuinely hard to split.

Every slice gets the same common brief (write it once to a scratch file and point each agent at it):

- system context in three lines and the six-layer definitions;
- the reference symptom (the pattern that prompted the audit) **and** "do not look only for this";
- read-only rules: no edits, branch switches, test runs, servers, or production config;
- sample, don't sweep: structure first, then 3–6 deep reads;
- every claim carries `path:line`; guesses are labelled;
- fixed return format, bounded length:

```
Scope: <dirs>
Health: green / yellow / red (one-line reason)    # per sub-module when asked
Top issues (≤5, by severity): <issue> | <path:line> | <impact: maintenance / user-visible / data safety>
Done well (≤2): ...
Rough size: ...
Not checked: ...
```

When the owner adds context mid-run (e.g. "rate sub-module X separately"), message the affected agents instead of restarting them.

Completion criterion: every grid cell is covered by exactly one slice, and every agent has returned or is explicitly recorded as missing.

## Step 3 — Verify before you score

Agent output is a **candidate**. The controller personally checks every claim that would land in the risk dimension (data safety, user-visible error, money, permission, concurrency), against the source.

Typical outcomes:

- **Confirmed** — e.g. a write path takes a row lock but never performs the write that makes a concurrent serializable reader retry; the claim holds, and it is the Nth leak of the same convention (symptom O1).
- **Confirmed, cause corrected** — e.g. "the contract is missing response branches" turns out to be "the controller declares them; the generated contract was never regenerated after merge" — a process gap, not a design bug.
- **Downgraded** — e.g. "the tenant client allows deleting audit rows" while a DB trigger blocks it; "a test switch is fail-open when the env var is unset" while config validation makes the variable mandatory at boot.
- **Narrowed** — the defect exists but only on one entry path.

Record the verdict next to each risk claim. Unverified risk claims are scored as `PLAUSIBLE` at half weight, never as confirmed.

Completion criterion: every risk-dimension claim carries confirmed / corrected / downgraded / narrowed / plausible.

## Step 4 — Score on one ruler

Agents' own colours are not comparable (each graded on its own scale, and a three-level scale collapses to "all yellow"). Re-score every cell yourself, 0–10 (10 = healthy), with fixed weights:

| Dimension | Weight | What lowers it |
| --- | --- | --- |
| **Risk** | 40% | Confirmed data-safety or user-visible defects; plausible ones at half weight |
| **Parallel implementations** | 25% | Same capability implemented more than once in this cell (I1, P1, O2, O3, D3) |
| **Rule leakage** | 20% | Rules outside the rule layer: services, prompts, client mirrors (R1–R3, P4) |
| **Size & guards** | 15% | Over-limit files, no architecture guard tests, no rule IDs (O4, O5) |

Risk carries the most weight because it decides *what to fix first*; the other three decide *how expensive future change is*. Charge the layer where a symptom surfaces; note the causing layer separately.

State plainly that scores are estimates from sampled evidence, fit for ranking cells against each other, not for absolute claims.

## Step 5 — Report

1. **Heatmap**: modules × layers, scores, one "main deductions" column citing symptom IDs.
2. **Top 5 cells** to act on, using the ordering below.
3. **Risk fast-lane list**: confirmed point defects, each with evidence and a proposed handling (fix now / issue).
4. **Downgraded claims** with the reason — they show the audit was not a rubber stamp.
5. **Not checked** and the raw-result location (scratch).

## Remediation ordering

Two intuitive axes — *risk > parallel implementation > rule leakage* and *lower layers first* — are right in direction but wrong if applied literally. Use this order:

1. **Stop the bleeding.** Prevent new divergence before paying old debt: add design-review checks for outer-layer reuse (single entry + capability projection + shared components) and architecture guard tests (e.g. forbid new `*-minimal` surfaces, freeze direct job-table writes to a baseline, make the write channel enforce its constraint). Cheapest, highest leverage.
2. **Risk fast-lane.** Confirmed data-safety and user-visible defects are point fixes; fix or file them immediately, independent of any layer plan. Rule leakage that causes user-visible drift belongs here, not in the "leakage" tier.
3. **Vertical slices by module.** Rank modules by *upcoming change × low score*: a module about to receive features absorbs the cleanup cost into that work; a dormant module with a bad score can wait without getting worse. Inside the chosen module go bottom-up — rules → orchestration → interface → page — and only build the lower-layer capabilities the upper layers actually lack. Don't sweep one layer across the whole system: the blast radius and regression risk are too large, and nothing is independently acceptable until the end.

Do not restructure a lower-layer component that works and is guarded merely because it is large; size alone is the weakest dimension.

Completion criterion: every top-5 cell names its tier (1/2/3) and its causing layer; every fast-lane item names fix-now or issue.
