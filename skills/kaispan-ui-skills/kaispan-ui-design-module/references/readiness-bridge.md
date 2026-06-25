# Module Readiness Bridge 流程

## 目标

把 global UI evidence 和模块生产事实对齐，防止 prototype demo 语义直接进入生产实现。

## Step 1: Pointer 与 locator

读取 `.kaispan-ui-design.json`，确认：

- `projectKey`
- `moduleKey`，仅在 monorepo 模块子上下文中需要
- `contextPath`
- `activeSnapshotId`
- `surfaceIds`
- 必要 aliases

解析失败时输出 `blocked-by-skill-missing-locator`。

## Step 2: 读取高优先级事实源

按任务涉及范围读取：

- official docs/API/DB/RBAC/Action Center/file security/audit/contracts。
- 项目/模块 PRD、roadmap、实现和测试。
- global prototype capture 和 shared UI 决策。

不要只看 prototype 或旧 POC。

## Step 3: 建立映射

对每个 surface 记录：

- prototype label。
- 当前 route。
- 当前 API/DTO/typed client。
- 当前 DB model 或缺口。
- 当前 RBAC permission 和 scope。
- 文件、安全、审计、idempotency、Action Center 关联。
- loading、empty、error、permission denied、scope denied、future disabled、API/export failed、长文本溢出等状态。

## Step 4: 分类

使用 `real`、`partial`、`future`、`lab` 分类。分类理由必须引用高优先级事实源。

## Step 5: 决策阻塞

把会阻塞 Phase 0/0.5/1 的问题写入 readiness bridge：

- 缺 API contract。
- 缺 DB 模型或迁移策略。
- 缺 RBAC permission/scope。
- 缺 Action Center source registry。
- 缺金额事实链。
- 缺 publishability/security gate。

不要把 blocked decision 藏在聊天里。
