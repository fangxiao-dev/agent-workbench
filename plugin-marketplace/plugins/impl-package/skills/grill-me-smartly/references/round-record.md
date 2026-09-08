# 批记录格式

Answerer 将本批记录保存为 UTF-8 JSON，并在交回后保持原路径和原字节不变。`batch_id` 在本次 review 内唯一；每项 `id` 对应 Questioner 的稳定问题 ID。轮内分批使用不同 batch ID。正文保留足以理解选择的场景、选项、依据和影响；`discussion` 保存有实质内容的澄清往返，`questioner_review` 保存 Questioner 对答案的检查和未解决异议。

```json
{
  "batch_id": "R1-B1",
  "items": [
    {
      "id": "R1-Q1",
      "branch": "删除完成条件",
      "question": "现有 DELETE 返回时对象是否已删除？",
      "why_now": "判断当前响应是否能证明删除完成。",
      "recommended_default": "先以现有实现和测试确认事实。",
      "answer": "当前路由等待存储删除返回后才响应。",
      "evidence": "src/delete.py:42；tests/test_delete.py:18",
      "uncertainty": "未运行远端存储验证。",
      "needs_user": false,
      "discussion": "Questioner：异常是否也返回成功？Answerer：异常向上传播，见 src/delete.py:46。",
      "questioner_review": "证据支持当前同步行为，远端完成语义仍需另行查证。",
      "proposal": {
        "line": "现有 REST 实现等待存储调用完成。",
        "rationale": "路由直接 await 删除调用。",
        "impact": "后续异步化设计需显式改变响应合同。"
      }
    }
  ]
}
```

`proposal` 可省略；其他字段必填，`discussion` 和 `uncertainty` 可为空字符串。证据缺失时如实说明查证范围和缺口。`needs_user` 必须为 JSON boolean；涉及 Owner 新选择时设为 `true`，问题正文用于待用户裁决摘要，即使给出推荐也保持未决。这里的例子仅展示格式，实际记录必须引用当前目标证据。

主控读过批文件与检查反馈后调用 `import-round --file <path>`。`--accept <item-id> ...` 仅接纳列出的事实候选，其余项保持已回答；`needs_user=true` 项自动进入待用户裁决并拒绝通过 `--accept` 收敛。脚本在权威 JSON ledger 中记录原件路径、SHA-256、批次引用、稳定问题 ID 到 ledger Q ID 的映射及控制器裁决，不把完整问答复制进 JSON；后续 `get-question` 通过引用解析原件并校验哈希，再返回有效详情。

整批先校验，再写入 ledger。相同批内容和接纳列表重复导入不重复创建问题；同 batch ID 内容或接纳列表不同则拒绝覆盖。稳定问题 ID 在整个 review 内唯一，跨批重复导入会被拒绝。已导入问题的后续回答与裁决使用原 ledger Q ID；若澄清产生了新的独立问题，使用新批 ID 和新问题 ID，并引用原问题。批文件始终是不可变审计原件，主控只写自己的裁决，不重写 Answerer 原文；原件缺失或哈希变化时，`get-question` 返回显式来源错误，但 `status` 和 `list-questions` 仍返回 JSON 中可用的计数和索引。

## 查询与历史

恢复时按 `status` → `list-questions` → `get-question` 读取：`status` 默认只看紧凑计数、状态和路径，需审计停止依据时才加 `--proof`；`list-questions` 按 `--offset`/`--limit` 分页并可按中文状态或 branch 子串过滤，详情只按需选取，历史版本仅在 `get-question --history` 时展开。不要用 `Get-Content` 或等价方式读取整个 JSON/Markdown。

直接 `record-answer` 或 `converge` 改变有效答案/决策时，保留理解该变化所需的前一版本，供 `--history` 查询；不要用没有语义的通用事件列表替代答案和决策历史。旧的嵌入 JSON ledger 只读查询，详情通过 `legacy_archive` 指向原记录；首次 mutation 先备份原字节为 `grill-<slug>.legacy.md`，再原子提交新 JSON 并派生 `.ledger.md`；没有批量迁移。
