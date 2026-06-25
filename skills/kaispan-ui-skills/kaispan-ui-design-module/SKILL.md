---
name: kaispan-ui-design-module
description: KaiSpan 模块 UI 迁移 Skill。用户要求把老板 prototype 或 KaiSpan global UI evidence 落到 Billing、Webshop 或其他独立项目/monorepo 模块，生成 readiness bridge、slice plan、verification gates、closure note，或按真实 API/DB/RBAC/Action Center/file/audit/contracts 推进实现时使用。
---

# KaiSpan UI Design Module

本 Skill 用于模块层 UI 迁移准备、计划和关闭记录。它不保存全局 prototype source，不把 demo 数据写入生产，不绕过模块事实源。

## 使用前读取

- `references/readiness-bridge.md`：从 locator 到模块事实源的对齐流程。
- `references/verification-gates.md`：按改动类型选择验证。
- 需要创建骨架时使用 `templates/module-readiness-bridge.md`、`templates/slice-plan.md`、`templates/closure-note.md`。

## Preflight

1. 读取当前仓库 `.kaispan-ui-design.json`；跨仓库 checkout 映射只读 `.kaispan-ui-design.local.json`。
2. 优先读取 `projectContexts`，旧指针可兼容 `moduleContexts`。
3. 定位目标 `projectKey`、可选 `moduleKey` 和 `contextPath`。
4. 解析 `activeSnapshotId` 和目标 `surfaceIds`。
5. 解析 `ksui://snapshot/...`、`ksui://surface/...`、`ksui://shared-ui/...` 或 `ksui://module/...`。
6. 缺少 locator 或无法解析时停止，并输出：

```text
blocked-by-skill-missing-locator
missing:
- <field or locator>
```

不要在缺失 global evidence 时生成看似确定的迁移计划。

## 模块事实源读取顺序

1. 目标项目/模块 official docs、API、DB、RBAC、Action Center、file security、audit 和 contracts。
2. 当前项目/模块 PRD、roadmap、实现和测试。
3. global prototype capture 和 shared UI 决策。
4. Boss prototype。
5. Webshop pilot reference。
6. Legacy proof-of-concept reference。

涉及 RBAC、Action Center、文件、审计、金额、tenant isolation 或 contracts 时，先读对应权威文档和实现，再写 readiness 或代码。

## 产物

独立项目默认使用 repo root 下的项目级上下文：

```text
docs/kaispan-ui-design/
  global-pointer.md
  readiness-bridge.md
  slice-plan.md
  closure-note.md
```

monorepo 内部模块可使用项目级目录下的模块子上下文：

```text
docs/kaispan-ui-design/modules/<moduleKey>/
  global-pointer.md
  readiness-bridge.md
  slice-plan.md
  closure-note.md
```

pointer 中只登记当前 repo 内的 repo-relative path；跨仓库 checkout 关系放在 `.kaispan-ui-design.local.json`，不要把独立项目伪装成父项目内部模块。

## 分类规则

每个 surface、metric、card、action 或 state 都必须分类：

- `real`：已有或本 slice 补齐生产事实、API、权限、审计和测试。
- `partial`：只上线可解释子集，未完成部分明确隐藏或降级。
- `future`：产品计划中的未来能力，UI 必须 disabled 或不展示假数据。
- `lab`：实验或概念验证，不进入生产默认路径。

Prototype、pilot reference 和 legacy POC 不能把能力直接提升为 `real`。

## 实现边界

- 前端通过 typed contracts 调 API，不直接访问业务数据库。
- 不新增 `role === "admin"` 临时判断。
- 不持久化 Action Center `actionHref`。
- 文件上传/下载保持后端权限校验和 organization-relative key。
- 金额指标标为 `real` 前，必须有 Decimal/currency/provenance/backfill/API serialization/audit 事实链。

## 完成输出

结束时说明：

- 哪些 locator 已解析。
- 哪些 readiness/slice/closure 文件创建或更新。
- 哪些 UI 能 `real`，哪些必须 `partial`、`future` 或 `lab`。
- 跑过哪些验证；未跑的验证说明原因。
