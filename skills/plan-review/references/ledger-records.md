# Ledger Record Inputs

只在调用 `record` 或 `authorize` 时读取。把以下对象写入临时 JSON 文件，或用 `--input -` 从 stdin 传入。

## Outside Voice 状态

```json
{"type":"review_state","outside_voice":"complete"}
```

不可用时使用 `{"type":"review_state","outside_voice":"unavailable","reason":"具体能力限制"}`。该状态进入 manifest；角色配置本身只在聊天报告，不写 ledger。

## Materiality

```json
{"type":"materiality","dimension":"tests","status":"finding","reason":"行为变化需要回归与 failure-mode coverage","finding_ids":["ENG-T1"]}
```

Dimension 使用 `scope / architecture / code_quality / tests / performance`。Status 使用 `reviewed / not_applicable / finding`，任何状态都要写与目标相关的 reason。

## Formal Finding

```json
{
  "type": "finding",
  "id": "ENG-T1",
  "section": "tests",
  "claim": "错误路径没有回归测试",
  "risk": "失败会在发布后重新出现",
  "severity": "P1",
  "confidence": "high — direct repository evidence",
  "evidence": [{"kind": "repository-fact", "summary": "现有 suite 只覆盖成功路径"}],
  "evidence_dependencies": [{"path": "tests/example_test.py", "kind": "file"}],
  "recommendation": "增加失败路径回归测试并断言用户可见结果",
  "owner_gate": "not_required",
  "resolution": {"state": "accepted", "authority": "agent"}
}
```

Absence-proof 对有界目录使用 `kind: tree`，使新增、删除或修改文件都能使 finding stale。`owner_gate: required` 的 accepted/rejected resolution 必须使用 `authority: owner` 并附 source。

## Owner Source

```json
{"actor":"owner","channel":"chat","reference":"稳定的消息或 turn 引用","action":"apply","manifest_hash":"<exact-manifest-hash>","statement":"apply <exact-manifest-hash>"}
```

把包含 `action` 与 `manifest_hash` 的对象保存为文件传给 `authorize --source`；脚本拒绝非 Apply action 或不匹配的 hash，并记录 statement hash。Owner resolution 可以使用不带 Apply 字段的基础 source。脚本验证授权记录的结构与绑定关系，不声称独立证明消息发送者身份。

## Abandonment Source

```json
{"actor":"owner","channel":"chat","reference":"稳定的消息或 turn 引用","action":"abandon","run_id":"<exact-run-id>","statement":"abandon <exact-run-id>"}
```

`abandon` 只关闭明确绑定的 active run、撤销其 authorization 并保留 ledger；不会删除记录，也不能用于角色或推理状态恢复。`applying` 表示 Apply receipt 已落盘但最终结果尚未收敛，必须先 `resume`：目标仍是 preimage 时回到 `active`，目标等于 proposed output 时收敛为 `applied`，两者都不匹配时停止并要求 owner 检查。
