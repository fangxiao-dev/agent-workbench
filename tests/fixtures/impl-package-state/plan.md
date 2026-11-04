# Ticket-first Stage A Fixture

Attempt ID：initial
Composition：tickets=true, dag=false
Acceptance: journey
Release order: none
Harness setup: python harness.py setup
Harness precheck: python harness.py precheck
Harness cleanup: python harness.py cleanup
Harness isolation: per-run
First visible step: J1-S1 @ TKT-01

## 输入

- 前置包（Predecessors）：None

## Execution strategy

Ticket-only / strict barrier.
