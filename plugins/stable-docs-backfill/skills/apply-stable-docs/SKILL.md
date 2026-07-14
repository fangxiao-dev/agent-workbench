---
name: apply-stable-docs
description: Apply only explicitly owner-approved stable-docs audit item IDs to canonical documentation. Use when a user has approved exact items from a specific audit report and wants those durable deltas written, pending state reconciled, and the project watermark advanced safely.
---

# Apply Stable Docs

只应用 owner 对某一份 audit report 明确批准的 item ID。Audit 的候选、模糊的“全部处理”或旧对话中的赞同不构成写入授权。

## 授权与漂移门

1. 要求项目根、配置、canonical `audit.json` 或 report 路径，以及确切批准 item ID 清单。若 owner 说“报告全部”，先从 canonical audit 解析成确定 ID 清单并复述边界。
2. 验证配置与 audit schema，读取当前 Plugin `name + version`，重新核对 report 的 Source HEAD、watermark、dirty baseline 和每项 source evidence。任一 item 的 evidence 漂移时停止该 item，不影响其他独立批准项。
3. 未批准、冲突、destination 不唯一或 authority 不足的 item 保持 pending/carry-forward，不顺手修改。

## Apply 工作流

1. 把批准规则写入唯一 canonical owner home；跨 module 只放指针，不复制合同。
2. 保持 intent/behavior 边界。首次创建 module PRD 必须通过 [`../../references/constraint-extraction-and-routing.md`](../../references/constraint-extraction-and-routing.md) 的惰性创建门，否则留在 pending。
3. 只清除已完整应用或 owner 明确 supersede 的 pending 行；部分应用不清行。
4. 遵从 tombstone 最终目标；除非批准项明确要求，不改历史 source。
5. 对受影响顶层路径移除退役/current 混杂；future TODO 逐条确认 owner、non-current 标记、目标与前提。
6. 使用 [`../../templates/apply-template.md`](../../templates/apply-template.md) 记录批准 item 与实际 diff 的 1:1 映射、deferred/conflict、pending、carry-forward 和验证证据。
7. 所有批准项已 applied、deferred、rejected 或 conflict 后，watermark 最多推进到 audit 固定的 Source HEAD；audit 之后的新 commit 不得被吞入。未处置 package 继续保留 carry-forward。
8. 运行项目自有文档检查，并完整执行 [`verify-stable-docs`](../verify-stable-docs/SKILL.md)；verify 失败意味着 apply 尚未验证通过，不反向改变历史 implementation gate 的 closed 状态。

## State 方法锚点

新写入或迁移后的 compaction state 使用：

```json
{
  "method_activation": {
    "plugin": "stable-docs-backfill",
    "version": "0.1.0"
  }
}
```

实际值必须从当前 Plugin manifest 读取，不能复制示例常量。旧 Git-checkout Method Activation Ref 仅作为 migration provenance 保留，不继续充当当前方法锚点，也不得推进 Project Source Watermark。

## 完成标准与回复

批准 item 与 diff 1:1，未批准内容未改，pending/carry-forward/state 可追溯，独立 verify 已运行。最终回复区分 `apply completed` 与 `verify passed`，列出 applied/deferred/conflict 数量、记录路径、新旧 watermark、carry-forward 和仍需 owner 决策的 item ID。
