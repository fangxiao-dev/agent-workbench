---
name: backfill-stable-docs
description: Route stable-docs backfill requests to a read-only audit, an owner-approved apply, or an independent verify phase. Use this as the public entry whenever a user asks to backfill, compact, reconcile, or refresh canonical project knowledge from completed work, pending registers, or unowned commits.
---

# Backfill Stable Docs

作为 Stable Docs Backfill Plugin 的薄入口，只解析意图、输入和授权，然后把工作交给唯一阶段 Skill；本入口不扫描 sources、不生成报告、不修改 canonical docs，也不把任一阶段混称为整体 backfill 完成。

## 路由合同

1. 解析项目根目录。配置按以下顺序选择：用户显式给出的 `--config` 路径；否则项目根目录的 `.stable-docs-backfill.json`。两者都不存在时 fail closed，不猜测仓库结构。
2. 解析阶段：`report`、`audit`、`盘点`、`扫描` 路由到 [`audit-stable-docs`](../audit-stable-docs/SKILL.md)；`apply`、`应用`、`写入` 路由到 [`apply-stable-docs`](../apply-stable-docs/SKILL.md)；`verify`、`验证`、`复核` 路由到 [`verify-stable-docs`](../verify-stable-docs/SKILL.md)。
3. 用户未明确阶段时，默认路由到只读 `audit`。不得从“处理一下”“完成 backfill”推导 apply 授权。
4. Apply 必须同时得到 owner 批准的 report 路径和确切 item ID；缺少任一输入时停在授权门，不降级为全量 apply。
5. 报告阶段状态时明确使用 `audit completed`、`apply completed` 或 `verify passed`。只有用户定义的全部阶段与交付门均通过时，才能称整个 backfill `closed`。

## Plugin 方法锚点

方法版本只从 Plugin 根目录的 `.codex-plugin/plugin.json` 读取，持久化为 `plugin name + version`。本机 Plugin/cache 路径只用于本次调用，不写入目标项目报告或 state，也不参与目标项目 Git range。

## 输出

在路由后复述所选阶段、项目根目录、配置来源、写入边界和仍缺少的 owner 授权，然后完整遵循目标阶段 Skill。

只有用户或 Automation 明确要求以 PR 作为交付界面时，才读取 [`../../templates/pr-summary-template.md`](../../templates/pr-summary-template.md)。默认 audit/apply/verify 不创建分支、提交、推送或 PR；PR summary 面向 owner 阅读，item ID、watermark 和 hash 留在 canonical audit/apply record。
