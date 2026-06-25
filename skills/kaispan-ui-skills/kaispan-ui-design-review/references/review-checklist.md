# Review Checklist

## Router 与模式

- 是否先判定 global/module/review/tooling。
- 是否加载正确 child Skill。
- v0 是否没有创建或依赖 `kaispan-ui-design-tooling`。
- tooling 请求是否被标记为 v1 候选或一次性计划。

## Pointer 与 Locator

- `.kaispan-ui-design.json` 是否只包含 logical locator、repo-relative path 和可公开 alias。
- 新指针是否以 `projectContexts` 为主，旧 `moduleContexts` 是否仅作为兼容读取。
- 跨仓库 repo root 是否没有写入 committed pointer，只由 `.kaispan-ui-design.local.json` 映射。
- `.kaispan-ui-design.local.json` 是否只用于本地路径，并被要求 gitignored。
- 是否覆盖 locator 格式：
  - `ksui://snapshot/<snapshotId>`
  - `ksui://surface/<snapshotId>/<surfaceId>`
  - `ksui://shared-ui/<componentOrPatternId>`
  - `ksui://module/<moduleKey>/<surfaceId>`
- Module mode 缺 locator 时是否停止并输出 `blocked-by-skill-missing-locator`。

## 事实源优先级

检查是否按以下顺序裁决：

1. 目标项目 official docs/API/DB/RBAC/Action Center/file security/audit/contracts。
2. 当前项目/模块 PRD、roadmap、实现和测试。
3. global prototype capture 和 shared UI 决策。
4. Boss prototype。
5. Webshop pilot reference。
6. Legacy proof-of-concept reference。

低优先级来源不得覆盖高优先级事实。

## 资产与发布安全

- Skill 目录是否只放流程、检查表和模板骨架。
- 是否没有真实 prototype source、surface inventory、业务映射、closure note、截图或生产事实。
- 正式内容是否没有本机绝对路径。
- publishability/security gate 是否覆盖 source、fonts、images、screenshots、demo data。
- gate 未通过时是否禁止复制素材，只允许重建等价 UI。

## Module Readiness

- 是否记录 current routes、API/DB/RBAC facts、file/audit/Action Center/contracts。
- 是否把每项能力分类为 `real`、`partial`、`future` 或 `lab`。
- 金额、税务师、每日现金账、银行流水、重复账单、Lieferschein 匹配等能力是否有生产事实链；没有时不得标为 `real`。
- Future card 是否 disabled，不展示假 connected 或假完成状态。

## Verification

- 纯 UI 是否包含 typecheck、browser screenshot、responsive。
- API/contract 是否包含 OpenAPI export 和 contracts generate。
- DB/RBAC/Action Center/file/audit 是否有对应测试或明确缺口。
- 是否记录未运行验证的原因。

## discuss-ledger

仅在用户要求或复杂多方争议时建议使用。普通 Skill 文件审查、单模块 readiness 审查和边界检查不默认重开 ledger。
