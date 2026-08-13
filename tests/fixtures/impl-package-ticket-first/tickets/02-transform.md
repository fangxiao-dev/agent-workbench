# 02 — Transform projection

**Ticket ID：** TKT-02
**Publication Status：** Draft
**Attempt ID：** initial

## 验收标准

- **AC-1：** source snapshot 转为可验证 projection。
  - Stable claim ID：`AC-1`
  - 证据时机：`early-falsification`
- **AC-2：** projection 保留 source identity 和数据完整性。
  - Stable claim ID：`AC-2`
  - 证据时机：`remaining-completion`

## 安全不变量

- tenant：projection 不跨租户读取 source。
  - Stable claim ID：`INV-tenant-isolation`
- RBAC / privacy：projection 读取遵循 source 授权。
  - Stable claim ID：`INV-rbac-privacy`
- 幂等 / 数据完整性：重复转换保持相同 projection。
  - Stable claim ID：`INV-idempotency-integrity`

## 阻塞依赖

- implementation: TKT-01
