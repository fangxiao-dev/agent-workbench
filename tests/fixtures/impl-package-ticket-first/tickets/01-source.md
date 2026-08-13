# 01 — Source admission

**Ticket ID：** TKT-01
**Publication Status：** Draft
**Attempt ID：** initial

## 验收标准

- **AC-1：** 受支持输入可确定性生成 source snapshot。
  - Stable claim ID：`AC-1`
  - 证据时机：`early-falsification`
- **AC-2：** snapshot 可由同一授权主体读回。
  - Stable claim ID：`AC-2`
  - 证据时机：`remaining-completion`

## 安全不变量

- tenant：只读当前租户数据。
  - Stable claim ID：`INV-tenant-isolation`
- RBAC / privacy：仅允许已授权主体访问。
  - Stable claim ID：`INV-rbac-privacy`
- 幂等 / 数据完整性：重复提交不产生第二份 source snapshot。
  - Stable claim ID：`INV-idempotency-integrity`

## 阻塞依赖

- None
