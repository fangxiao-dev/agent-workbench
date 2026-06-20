# PR #64: Internal job runner foundation

This PR lands the internal job runner used by operations automation. It is not a
customer-facing or multi-tenant service.

Implemented:

- idempotent job submission;
- atomic worker leasing;
- durable audit rows for submit/lease/complete;
- durable outbox dispatch after the job record is committed.

Please review whether the foundation is sound without applying SaaS tenant rules
that do not belong to this service.
