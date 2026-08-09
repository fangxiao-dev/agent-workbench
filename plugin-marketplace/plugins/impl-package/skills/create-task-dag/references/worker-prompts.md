# Worker Prompts

普通 Task 的派发只需给出足够执行与安全返回的信息；不要因为 Task 存在就附加完整 Task Contract、独立正式 review 或默认 progress 文件。

```markdown
你在为 <implementation package> 执行 Task <ID>。

目标：
- <简明目标>

Primary ownership：
- <模块/目录/共享 seam 范围>

禁止越界范围：
- <不应编辑的范围；未列出的范围也不得自行扩展>

Known depends on：
- <Tn 或 none>

Contributes to tickets：
- <Ticket ID 列表，或 spec:AC-n>

局部验证：
- <相关测试、检查或 evidence 要求>

规则：
- 不要回滚或覆盖其他人的改动。
- 不要扩大 primary ownership；共享 seam、缺上下文、权限或依赖问题一律返回 BLOCKED。
- 高风险改动按 prompt 指定的额外验证执行；局部验证不等于 Ticket acceptance。

BLOCKED 返回格式：
- status: BLOCKED
- reason: <一句最小原因>
- suggested next action: <最小建议动作>
- affected tickets: <Ticket ID 列表或 none>
- evidence so far: <已完成局部证据或 none>
```

正常返回可使用 `READY`、`RUNNING`、`DONE`、`FAILED` 或 `BLOCKED`。`DONE` 应附局部改动与验证 evidence，但仅表示可以交回 Working Branch owner 集成。发现共享 seam 不能擅自编辑非属地范围，也不能返回 `NEEDS_SEAM`；以 BLOCKED 报告最小原因、建议动作和影响 Ticket。仅满足条件时才更新 `execution/<attempt>/task-handoffs/<task-id>-handoff.md`；不创建独立 Ticket progress artifact、不维护第二套 acceptance 状态，也不直接编辑 Ticket 或公共 Execution Record，除非主 session 明确委托。

高风险 Task（tenant isolation、auth/permission、migration、真实外部写入、金额或不可逆数据风险）可要求额外测试、独立 review 或人工确认。这是按实际 diff 增加的质量要求，不形成 Strict Task 模式，也不能替代 `dev-with-track` 的 Ticket 层正式 review/acceptance。
