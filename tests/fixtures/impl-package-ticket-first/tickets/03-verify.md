# 03 — Verification evidence

**Ticket ID：** TKT-03
**Publication Status：** Draft
**Attempt ID：** initial

## 验收标准

- **AC-1：** 验证报告覆盖 source 与 projection 的可读回结果。
  - Stable claim ID：`AC-1`
  - 证据时机：`early-falsification`
- **AC-2：** 完成证据覆盖当前 revision/environment。
  - Stable claim ID：`AC-2`
  - 证据时机：`remaining-completion`

## 安全不变量

- tenant：报告不泄露其他租户数据。
  - Stable claim ID：`INV-tenant-isolation`
- RBAC / privacy：验证入口复用授权边界。
  - Stable claim ID：`INV-rbac-privacy`
- 幂等 / 数据完整性：重复验证不改写业务数据。
  - Stable claim ID：`INV-idempotency-integrity`

## 阻塞依赖

- acceptance: TKT-01
