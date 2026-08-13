# 04 — Publication release

**Ticket ID：** TKT-04
**Publication Status：** Draft
**Attempt ID：** initial

## 验收标准

- **AC-1：** 发布只使用已验证的 projection。
  - Stable claim ID：`AC-1`
  - 证据时机：`remaining-completion`

## 安全不变量

- tenant：发布目标与 source 租户一致。
  - Stable claim ID：`INV-tenant-isolation`
- RBAC / privacy：发布操作需要明确授权。
  - Stable claim ID：`INV-rbac-privacy`
- 幂等 / 数据完整性：重复发布不会产生重复公开版本。
  - Stable claim ID：`INV-idempotency-integrity`

## 阻塞依赖

- release: TKT-01
