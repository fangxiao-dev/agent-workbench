# Verification Gates

根据改动类型选择验证。不要把 `pnpm lint` 当成完整 ESLint 门禁；它可能只是占位。

| 改动类型 | 必要验证 |
| --- | --- |
| 纯 UI shell | web typecheck、browser screenshot、responsive 检查 |
| API/contract | OpenAPI export、contracts generate、web typecheck |
| 新增账单字段/模型 | Prisma migration、Database Design、tenant isolation test |
| 新增权限/菜单 | RBAC catalog、allow/deny test、scope test |
| 文件/导出 | 文件访问权限、R2 key scope、download permission、audit |
| Action Center task | source adapter idempotency、visibilityPermissionKeys、scope、dedupeKey、URL 不落库 |
| 金额/状态/付款/Kontierung | audit log、稳定错误 code、幂等 mutation |

## UI 状态覆盖

每个 surface 至少考虑：

- loading
- empty
- error
- permission denied
- scope denied
- future disabled
- API/export failed
- 长文本溢出
- keyboard/focus path
- non-color-only status indication

## 关闭条件

closure note 中记录：

- tests run。
- docs/contracts updated。
- 未运行 gate 的原因。
- remaining gaps。
- decision links。
