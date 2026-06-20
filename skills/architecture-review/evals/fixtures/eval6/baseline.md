# Foundation Baseline: Internal Job Runner

This is a single-tenant internal operations service. Tenant isolation and RBAC are
not applicable to this review.

## Required P0 gates

- Job submission must be idempotent by `idempotencyKey`.
- Worker leasing must prevent two workers from claiming the same pending job.
- Job state changes must write durable audit rows.
- Queue dispatch is represented by a durable outbox row in the same commit as
  the job record; the transport may deliver it after commit.
