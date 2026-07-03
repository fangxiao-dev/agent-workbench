# DAG And Ownership

Use this reference when drawing the task graph and assigning file ownership.

## Task Record

Every task should be concrete enough to dispatch without further decisions:

```markdown
### Task <ID>: <name>
- Depends on:
- Can run with:
- Owns:
- Must not touch:
- Input contract:
- Output contract:
- Focused tests:
- Done when:
```

When a `dev-with-track` workspace exists, mirror these fields in `dag.md` under `Task Contracts`. Create `tasks/Tn-progress.md` only for tasks with durable local state, such as independent owner/subagent work, external gate evidence, blocker, review finding, or cross-session continuation.

## Ownership Rules

- A worker may edit only its owned files/modules.
- A worker must not edit unowned files to "just wire it up".
- If unowned edits are needed, the worker returns `NEEDS_SEAM` with the exact required change.
- Shared seam files belong to the main session unless one seam worker is explicitly assigned.
- Two workers should not write the same component, dictionary block, generated output, local data store, dev server port, or external smoke records.
- If a task is horizontal prerequisite work, record which vertical slice gates consume it. Do not mark a slice accepted from a horizontal worker alone.

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
- Owns inventory item types/service/source/readiness tests.
- Does not touch Inventory UI or Product/SKU UI.

Task B: Product/SKU explicit-only read model + UI cleanup
- Owns Product/SKU workbench service/types/panel/tests.
- Does not touch Inventory compact UI.

Task C: Derived Products 0-N source/read model
- Owns customer-product-config source/service/types/tests.
- Outputs InventoryItemProductDisplay[] contract.

Task D: Inventory compact UI shell
- Owns inventory-items panel and tests.
- Consumes frozen DTOs from A/C.

Task E: i18n copy pass/review
- Owns or reviews admin dictionary namespaces.
- Coordinates keys with UI worker through main session.

Task F: Lark readiness/smoke
- Depends on local tests and browser evidence.
- Mutates only confirmed Test Environment target.

Final: whole-slice review
- Checks cross-module consistency, missing acceptance items, test gaps, and external smoke risks.
```
