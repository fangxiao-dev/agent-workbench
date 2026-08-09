# Parallel Work Admission

Read this reference only when two or more bounded work items are candidates for concurrent execution.

Parallelism is admitted only when every candidate has an independent objective and completion condition, no unresolved dependency on another candidate, no overlapping primary ownership, and no shared mutable runtime resource. Ports, test data, output directories, worktrees, external records, and other shared resources must be isolated before dispatch.

Return one decision:

- `PARALLEL`: list the admitted batches, each task's ownership and isolated resources, and the integration verification that runs after all results return.
- `SERIAL`: name the dependency, ownership overlap, shared resource, or unresolved seam that requires ordered execution.
- `BLOCKED`: name the missing decision or authorization that prevents either safe parallel or serial execution.

Partition by problem ownership, not file count. The main session remains responsible for checking conflicting conclusions or changes and for running shared integration verification. This reference does not choose models, create worker prompts, dispatch agents, or own result recovery.
