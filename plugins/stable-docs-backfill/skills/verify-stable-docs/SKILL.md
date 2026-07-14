---
name: verify-stable-docs
description: Independently verify a stable-docs audit or apply result. Use when checking canonical authority, local links and anchors, module coverage, pending and carry-forward reconciliation, project watermark safety, Plugin method identity, or configured dangerous-content residue.
---

# Verify Stable Docs

独立验证 audit/apply 产物与当前常青层。Verify 不补写候选、不替 owner 裁决 authority，也不把通过验证等同于原开发任务或整个维护周期 closed。

## 确定性检查

运行：

```text
python ../../scripts/verify_stable_docs.py \
  --project-root <root> \
  [--config <explicit-config>] \
  [--audit-json <audit.json>] \
  [--source-head <audited-source-head>]
```

脚本必须独立检查并以非零退出码报告：

- 配置 schema、canonical home 的存在性与唯一 authority destination；
- canonical Markdown 的相对链接与本地 anchor；
- `audit.json` 的 Plugin name/version、stable item ID、唯一 ID、module coverage 和 disposition；
- pending、carry-forward 与 compaction state 的基本对账；
- Project Source Watermark 可解析且不越过 audited Source HEAD；
- 当前方法锚点使用 Plugin identity/version，而非 checkout commit 或本机路径；
- 配置的危险内容 literals 在指定 canonical paths 中没有残留。

脚本负责确定性断言；“哪条业务规则仍是 current truth”“冲突 authority 选择哪一边”“未来能力是否应批准”仍由 owner 决定。项目另有 validator 时继续运行，Plugin validator 不能替代项目检查。

## 语义复核

1. 对每个 applied item 核对 source evidence、唯一 durable home 和实际 diff；指针不能伪装为重复 authority。
2. 确认未批准或漂移 item 仍在 pending/carry-forward，watermark 推进没有隐式吞掉来源。
3. 确认顶层知识只描述 current contract；退役 provenance 留在历史/ledger/report，future TODO 具备 owner、non-current 标记、目标与前提。
4. 对 audit 检查所有 configured modules 均有 disposition；对 apply 检查批准 ID 与 diff 1:1。

## 输出

使用 [`../../templates/verify-template.md`](../../templates/verify-template.md) 记录 checks、证据、失败项和 owner decisions。最终回复报告 `verify passed` 或 `verify failed`、检查总量/通过/失败数量、水位线与 carry-forward 状态；存在失败时列出独立 blocker，不能宣称整体 backfill closed。
