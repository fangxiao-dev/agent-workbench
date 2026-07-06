# DAG And Ownership

Use this reference when drawing the task graph and assigning file ownership.

## Task Record

Every task should be concrete enough to dispatch without further decisions:

```markdown
### Task <ID>: <name>
- Depends on:
- Can run with:
- Primary owned files/modules:
- Conditional seam files/modules:
- Forbidden files/modules:
- Input contract:
- Output contract:
- Focused tests:
- Done when:
```

When a `dev-with-track` workspace exists, mirror these fields in `dag.md` under `Task Contracts`. Create `tasks/Tn-progress.md` only for tasks with durable local state, such as independent owner/subagent work, external gate evidence, blocker, review finding, or cross-session continuation.

## Ownership Rules

- Treat the DAG ownership map as the single source of truth for worker prompts. Do not manually narrow or broaden ownership while dispatching unless you also update the DAG.
- **Primary owned files/modules** are the worker's normal write scope.
- **Conditional seam files/modules** may be edited only when the named seam condition occurs. The worker must report the condition and the exact file changed.
- **Forbidden files/modules** must not be edited. If they are needed, the worker returns `NEEDS_SEAM` with the exact required change.
- Shared seam files belong to the main session unless one seam worker is explicitly assigned.
- Two workers should not write the same component, dictionary block, generated output, local data store, dev server port, or external smoke records.
- If a task is horizontal prerequisite work, record which vertical slice gates consume it. Do not mark a slice accepted from a horizontal worker alone.

## Seam Status

Use status labels to separate expected integration work from real blockers:

- `DONE`: primary work and focused tests are complete.
- `DONE_WITH_CONCERNS`: work is complete, but the worker reports a risk the main session must read before review.
- `NEEDS_SEAM`: the worker needs another task-owned or main-session-owned change; no human decision is required.
- `BLOCKED`: the worker cannot proceed because context, permission, data, a plan correction, or a human decision is required.

Record expected seams in the DAG before dispatch when they are foreseeable. During execution, mark a task `Needs seam` rather than `Blocked` when a broader test fails only because another planned task has not landed yet.

## Common Task Shapes

- **Data/source/readiness worker:** owns service/types/source/readiness tests for one contract; avoids UI.
- **Read-model worker:** owns source/service/types/tests for derived display data; avoids panel implementation except agreed prop seams.
- **UI worker:** owns component/panel and component tests; consumes frozen DTOs; avoids source internals.
- **i18n worker or reviewer:** owns dictionary namespaces or semantic review for agreed keys; coordinates new keys through the main session.
- **Seam owner:** usually the main session; owns route/page prop wiring, shared exports, central dictionary merge, and final conflict resolution.
- **External smoke worker:** runs after local/browser gates and target identity confirmation.

## Cohort Pattern

Use cohorts to maximize parallelism without hiding dependencies:

1. **Contract cohort:** data/source/readiness, read models, and independent cleanup tasks that share only frozen contracts.
2. **UI/i18n cohort:** UI shell and copy work after enough DTO/copy shape is stable.
3. **Integration cohort:** main session resolves seam files and runs slice-level tests.
4. **External cohort:** browser verification and external smoke after local evidence.
5. **Final review cohort:** whole-slice review over the integrated result.

## Example: Inventory Item UI Slice

```markdown
Task A: Inventory threshold data/source/readiness
- Primary owned files/modules: inventory item types/service/source/readiness tests.
- Conditional seam files/modules: none.
- Forbidden files/modules: Inventory UI, Product/SKU UI.

Task B: Product/SKU explicit-only read model + UI cleanup
- Primary owned files/modules: Product/SKU workbench service/types/panel/tests.
- Conditional seam files/modules: shared read-model types only if the DAG assigns this seam.
- Forbidden files/modules: Inventory compact UI.

Task C: Derived Products 0-N source/read model
- Primary owned files/modules: customer-product-config source/service/types/tests.
- Conditional seam files/modules: none.
- Forbidden files/modules: UI implementation.
- Outputs InventoryItemProductDisplay[] contract.

Task D: Inventory compact UI shell
- Primary owned files/modules: inventory-items panel and tests.
- Conditional seam files/modules: dictionary namespace only if UI copy keys were assigned here.
- Forbidden files/modules: source internals.
- Consumes frozen DTOs from A/C.

Task E: i18n copy pass/review
- Primary owned files/modules: assigned admin dictionary namespaces.
- Conditional seam files/modules: UI tests only if copy changes require assertion updates.
- Forbidden files/modules: service/source internals.
- Coordinates keys with UI worker through main session.

Task F: Lark readiness/smoke
- Depends on local tests and browser evidence.
- Mutates only confirmed Test Environment target.

Final: whole-slice review
- Checks cross-module consistency, missing acceptance items, test gaps, and external smoke risks.
```
