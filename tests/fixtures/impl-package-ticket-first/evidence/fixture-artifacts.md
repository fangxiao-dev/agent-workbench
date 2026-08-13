# Ticket-first fixture artifacts

这些是合同测试使用的最小真实产物锚点；它们不是当前 runtime 自动读取的 evidence index。

## TKT-01

- AC-1：source snapshot fixture output
- AC-2：source readback fixture output
- INV-tenant-isolation：tenant boundary fixture output
- INV-rbac-privacy：authorized subject fixture output
- INV-idempotency-integrity：duplicate submission fixture output

## TKT-02

- AC-1：projection fixture output
- AC-2：identity preservation fixture output
- INV-tenant-isolation：projection tenant fixture output
- INV-rbac-privacy：projection authorization fixture output
- INV-idempotency-integrity：repeat transform fixture output

## TKT-03

- AC-1：verification fixture output
- AC-2：revision/environment fixture output
- INV-tenant-isolation：report tenant fixture output
- INV-rbac-privacy：verification authorization fixture output
- INV-idempotency-integrity：repeat verification fixture output

## TKT-04

- AC-1：publication fixture output
- INV-tenant-isolation：publication tenant fixture output
- INV-rbac-privacy：publication authorization fixture output
- INV-idempotency-integrity：duplicate publication fixture output
