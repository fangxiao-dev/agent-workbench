# Audit JSON Contract

`audit.json` 是可选的机器辅助记录，帮 agent 和脚本对账候选清单；`human-report.md` 才是给 owner 看的主产物。两者的候选计数必须一致，但 `audit.json` 本身不是 apply 的唯一合法输入——owner 批准的是 `human-report.md` 里的 item ID，不是这份 JSON 的哈希。

`collect_sources.py` 的 source inventory 与本文件的 audit record 是不同合同：inventory 使用 `schemaVersion: 5`，每个 package row 以 `gateRecognition`（`indexed | legacy-heading | mismatch | manual | null`）、可信 `gateResolution`、派生的 `gateAppliesToCurrentRevision`、`needsManualGateReview` 和 `reason` 报告 gate；`gateRecognition=null` 用于没有 `gate.md`，或只有空 ledger 模板且 runtime gate 尚无 allocation/entry 的 open/no-verdict package。合法历史 indexed entry 的 `gateAppliesToCurrentRevision=false`、`gateResolution=null`，但不变成第五类或 manual；`mismatch`/`manual` 的 `gateResolution` 必须为 `null`，且即使 package 已被 `_pending.md` 引用也不得从 manual review 清单隐藏。inventory 的 `gapCatchingStructuralCandidate(s)` 只表示 Gate/pending 结构条件满足且 Git reachability 尚未核验；audit record 的 `gapCatchingCandidates` 是 agent 完成 target-branch Git 复验后的真实候选，两者不能混用。

## Minimum Shape

```json
{
  "schemaVersion": 3,
  "mode": "audit",
  "project": {
    "repository": "owner/repository",
    "sourceHead": "full commit"
  },
  "items": [
    {
      "id": "SDB-0123456789ab",
      "origin": "pending-registry",
      "pendingRef": "docs/module-knowledge/_pending.md#erp-order-documents|DELTA-014",
      "source": "docs/implementations/example/spec.md",
      "destination": "docs/module-knowledge/example/spec.md",
      "statement": "Atomic current contract.",
      "disposition": "candidate",
      "evidence": [{"path": "docs/implementations/example/spec.md"}],
      "canonicalOwner": "module-knowledge-owner",
      "risk": "Why an incorrect promotion matters.",
      "confidence": "high"
    }
  ],
  "pendingClosures": [],
  "gapCatchingCandidates": [],
  "retirementCandidates": [],
  "blockers": []
}
```

## Invariants

- `schemaVersion: 1` 与 `schemaVersion: 2` 是旧版 provenance（canonicalDocs/dangerRules 固定 schema、item-scoped fingerprint、`methodActivation`/`configSha256` 双锚点 fail-closed）；这些字段不再是新 audit 的强制要求，脚本仍可以选择性计算 fingerprint 辅助判断证据是否变化，但 apply 决策不能只靠字段匹配自动放行。
- `items[].origin` 只用 `pending-registry`（来自 `_pending.md` 主渠道）或 `gap-catching`（gate 已 terminal 但没有对应登记，agent 重新发现）。`pending-registry` 的 item 必须带 `pendingRef`，指向来源 `_pending.md` 文件和其中的登记行标识。
- `disposition` 只使用 `candidate`、`already-covered`、`conflict`、`no-delta`。
- `items[].id` 由 `make_item_id.py` 从 source、destination 和规范化 statement 生成，用于报告内部引用，不作为 fail-closed 校验的密钥。
- `pendingClosures`：本轮 apply 后需要关闭的 `_pending.md` 登记引用列表（即使为空也必须存在）。
- `gapCatchingCandidates`：agent 已完成 target-branch Git reachability 复验的 gap-catching 真实候选摘要，供 owner 单独识别哪些是"重新发现"而不是"消费既有登记"的；不得直接复制 inventory 的 `gapCatchingStructuralCandidates`。
- `retirementCandidates`：Package Retirement 的 GC 候选（见 [package retirement runbook](package-retirement-runbook.md)），只报告不清理。
- `blockers` 即使为空也必须存在，避免"未扫描"和"扫描后为空"无法区分。
- Human report 可以省略内部 ID，但不得省略 owner decision、blocker 或改变计数。
